import {
  computeTransitSnapshot,
  computeTransitTimeline,
} from "@astro/astrology-core";
import { askAssistant, createOllamaClient, probeAssistantHealth } from "@astro/ai-orchestrator";
import {
  lalKitabReport,
  VARSHPHAL_MAX_AGE,
  type LkOrigin,
} from "@astro/lal-kitab";
import {
  evaluatePredictionsEnriched,
  evaluateRemedies,
  type Domain,
} from "@astro/rule-engine";
import type { FastifyInstance } from "fastify";
import { createChartRequestInputSchema } from "../../../../../packages/shared-types/src/chart-request";

import { recordAudit } from "../audit/audit";
import { AssistantThreadRepository } from "./assistant-thread";
import { buildChartReading } from "./reading";
import { ChartRequestsRepository } from "./repository";

/** Sliding-window limiter: at most LIMIT assistant calls per IP+minute. */
const ASSISTANT_LIMIT_PER_MINUTE = 10;
const assistantCalls = new Map<string, number[]>();

function assistantRateLimited(ip: string): boolean {
  const now = Date.now();
  const calls = (assistantCalls.get(ip) ?? []).filter((t) => now - t < 60_000);
  if (calls.length >= ASSISTANT_LIMIT_PER_MINUTE) {
    assistantCalls.set(ip, calls);
    return true;
  }
  calls.push(now);
  assistantCalls.set(ip, calls);
  return false;
}

export async function registerChartRequestRoutes(
  app: FastifyInstance,
): Promise<void> {
  const repository = new ChartRequestsRepository();
  const assistantThreads = new AssistantThreadRepository();

  app.post("/api/v1/charts/generate", async (request, reply) => {
    const parsed = createChartRequestInputSchema.safeParse(request.body);

    if (!parsed.success) {
      return reply.code(400).send({
        error: {
          code: "chart_request_invalid",
          message: parsed.error.issues[0]?.message ?? "Invalid chart request",
        },
      });
    }

    const job = await repository.createChartRequest(parsed.data);
    const processed = await repository.processChartRequest(job.id);
    recordAudit({
      workspaceId: parsed.data.workspaceId,
      action: "chart.generated",
      subjectType: "chartRequest",
      subjectId: job.id,
      meta: { status: processed?.status ?? "queued" },
    });

    return reply.code(202).send({
      jobId: job.id,
      status: processed?.status ?? job.status,
      statusUrl: `/api/v1/charts/jobs/${job.id}`,
      artifactUrl: `/api/v1/charts/jobs/${job.id}/artifact`,
    });
  });

  app.get("/api/v1/charts/jobs/:jobId/artifact", async (request, reply) => {
    const { jobId } = request.params as { jobId: string };
    const job = await repository.findChartRequest(jobId);

    if (!job) {
      return reply.code(404).send({
        error: {
          code: "chart_job_not_found",
          message: "Chart job was not found.",
        },
      });
    }

    if (job.status === "failed") {
      return reply.code(409).send({
        error: {
          code: "chart_job_failed",
          message: job.error ?? "Chart computation failed.",
        },
      });
    }

    const artifact = await repository.findChartArtifact(jobId);

    if (!artifact) {
      return reply.code(409).send({
        error: {
          code: "chart_artifact_pending",
          message: "Chart artifact is not ready yet.",
        },
      });
    }

    return reply.send({ jobId, artifact });
  });

  app.get("/api/v1/charts/jobs/:jobId/reading", async (request, reply) => {
    const { jobId } = request.params as { jobId: string };
    const job = await repository.findChartRequest(jobId);

    if (!job) {
      return reply.code(404).send({
        error: {
          code: "chart_job_not_found",
          message: "Chart job was not found.",
        },
      });
    }

    const artifact = await repository.findChartArtifact(jobId);
    if (!artifact) {
      return reply.code(409).send({
        error: {
          code: "chart_artifact_pending",
          message: "Chart artifact is not ready yet.",
        },
      });
    }

    try {
      const reading = await buildChartReading(artifact);
      return reply.send({ jobId, reading });
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Reading engine is unavailable.";
      const code = message.includes("services/api-py/.venv")
        ? "reading_venv_missing"
        : "reading_engine_unavailable";
      return reply.code(503).send({
        error: {
          code,
          message,
        },
      });
    }
  });

  app.get("/api/v1/charts/jobs/:jobId/predictions", async (request, reply) => {
    const { jobId } = request.params as { jobId: string };
    const { horizonYears, domains, from } = request.query as {
      horizonYears?: string;
      domains?: string;
      from?: string;
    };

    const artifact = await repository.findChartArtifact(jobId);
    if (!artifact) {
      return reply.code(404).send({
        error: {
          code: "chart_artifact_not_found",
          message: "Chart artifact was not found for this job.",
        },
      });
    }

    const predictions = evaluatePredictionsEnriched(artifact, {
      from: from ? new Date(`${from}T00:00:00Z`) : undefined,
      horizonYears: horizonYears ? Number(horizonYears) : 5,
      domains: domains
        ? (domains.split(",") as Domain[])
        : undefined,
    });

    return reply.send({ jobId, predictions });
  });

  app.get("/api/v1/charts/jobs/:jobId/remedies", async (request, reply) => {
    const { jobId } = request.params as { jobId: string };
    const artifact = await repository.findChartArtifact(jobId);
    if (!artifact) {
      return reply.code(404).send({
        error: {
          code: "chart_artifact_not_found",
          message: "Chart artifact was not found for this job.",
        },
      });
    }
    return reply.send({ jobId, remedies: evaluateRemedies(artifact) });
  });

  app.get("/api/v1/charts/jobs/:jobId/lal-kitab", async (request, reply) => {
    const { jobId } = request.params as { jobId: string };
    const { origin, age } = request.query as { origin?: string; age?: string };
    const artifact = await repository.findChartArtifact(jobId);
    if (!artifact) {
      return reply.code(404).send({
        error: {
          code: "chart_artifact_not_found",
          message: "Chart artifact was not found for this job.",
        },
      });
    }
    if (origin !== undefined && origin !== "lagna_h1" && origin !== "aries_h1") {
      return reply.code(400).send({
        error: {
          code: "invalid_origin",
          message: "origin must be lagna_h1 or aries_h1.",
        },
      });
    }
    const ageNumber = age === undefined ? undefined : Number(age);
    if (
      ageNumber !== undefined &&
      (!Number.isInteger(ageNumber) ||
        ageNumber < 1 ||
        ageNumber > VARSHPHAL_MAX_AGE)
    ) {
      return reply.code(400).send({
        error: {
          code: "invalid_age",
          message: `age must be an integer from 1 to ${VARSHPHAL_MAX_AGE}.`,
        },
      });
    }
    return reply.send({
      jobId,
      lalKitab: lalKitabReport(artifact, {
        origin: origin as LkOrigin | undefined,
        age: ageNumber,
      }),
    });
  });

  app.post("/api/v1/charts/jobs/:jobId/assistant", async (request, reply) => {
    const { jobId } = request.params as { jobId: string };
    const query = request.query as { stream?: string };
    const wantsStream =
      query.stream === "1" ||
      String(request.headers.accept ?? "").includes("text/event-stream");
    const { question, history } = (request.body ?? {}) as {
      question?: string;
      history?: Array<{ role?: string; content?: string }>;
    };

    if (assistantRateLimited(request.ip)) {
      return reply.code(429).send({
        error: {
          code: "assistant_rate_limited",
          message: "Too many assistant requests - wait a minute and retry.",
        },
      });
    }

    if (!question || question.trim().length < 3) {
      return reply.code(400).send({
        error: {
          code: "assistant_question_missing",
          message: "A question of at least 3 characters is required.",
        },
      });
    }

    const artifact = await repository.findChartArtifact(jobId);
    if (!artifact) {
      return reply.code(404).send({
        error: {
          code: "chart_artifact_not_found",
          message: "Chart artifact was not found for this job.",
        },
      });
    }

    const priorTurns = Array.isArray(history)
      ? history
          .filter(
            (turn): turn is { role: "user" | "assistant"; content: string } =>
              (turn.role === "user" || turn.role === "assistant") &&
              typeof turn.content === "string" &&
              turn.content.trim().length > 0,
          )
          .map((turn) => ({
            role: turn.role,
            content: turn.content.trim(),
          }))
      : await assistantThreads.listHistoryTurns(jobId);

    const writeSse = (event: string, data: unknown) => {
      reply.raw.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
    };

    if (wantsStream) {
      reply.hijack();
      reply.raw.writeHead(200, {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
      });
      writeSse("status", { message: "Consulting the chart…" });
    }

    let reading = null;
    try {
      reading = await buildChartReading(artifact);
    } catch {
      // Reading tools fail soft; chart tools still work.
    }

    try {
      const client = createOllamaClient();
      const abort = new AbortController();
      const onClose = () => abort.abort();
      request.raw.once("close", onClose);
      const answer = await askAssistant(client, artifact, question.trim(), new Date(), {
        history: priorTurns,
        reading,
        onStatus: wantsStream
          ? (message) => writeSse("status", { message })
          : undefined,
        signal: abort.signal,
      });
      request.raw.off("close", onClose);
      await assistantThreads.appendExchange(
        jobId,
        question.trim(),
        answer.answer,
        answer.citations,
        answer.toolsUsed,
      );
      recordAudit({
        workspaceId: "ws_1",
        action: "assistant.asked",
        subjectType: "chartRequest",
        subjectId: jobId,
        meta: {
          question: question.trim().slice(0, 200),
          tools: answer.toolsUsed,
          historyTurns: priorTurns.length,
          stream: wantsStream,
        },
      });

      if (wantsStream) {
        writeSse("done", { jobId, ...answer });
        reply.raw.end();
        return;
      }
      return reply.send({ jobId, ...answer });
    } catch (error) {
      const aborted =
        error instanceof Error && error.name === "AbortError";
      if (wantsStream) {
        writeSse("error", {
          code: aborted ? "assistant_aborted" : "assistant_unavailable",
          message: aborted
            ? "Stopped."
            : "The assistant is offline - chart data is unaffected. " +
              (error instanceof Error ? error.message : ""),
        });
        reply.raw.end();
        return;
      }
      if (aborted) {
        return reply.code(499).send({
          error: { code: "assistant_aborted", message: "Stopped." },
        });
      }
      return reply.code(503).send({
        error: {
          code: "assistant_unavailable",
          message:
            "The assistant is offline - chart data is unaffected. " +
            (error instanceof Error ? error.message : ""),
        },
      });
    }
  });

  app.get("/api/v1/charts/jobs/:jobId/assistant/thread", async (request, reply) => {
    const { jobId } = request.params as { jobId: string };
    const job = await repository.findChartRequest(jobId);
    if (!job) {
      return reply.code(404).send({
        error: {
          code: "chart_job_not_found",
          message: "Chart job was not found.",
        },
      });
    }
    const exchanges = await assistantThreads.listExchanges(jobId);
    return reply.send({ jobId, exchanges });
  });

  app.delete(
    "/api/v1/charts/jobs/:jobId/assistant/thread",
    async (request, reply) => {
      const { jobId } = request.params as { jobId: string };
      const job = await repository.findChartRequest(jobId);
      if (!job) {
        return reply.code(404).send({
          error: {
            code: "chart_job_not_found",
            message: "Chart job was not found.",
          },
        });
      }
      await assistantThreads.clearThread(jobId);
      recordAudit({
        workspaceId: job.workspaceId,
        action: "assistant.thread_cleared",
        subjectType: "chartRequest",
        subjectId: jobId,
      });
      return reply.send({ jobId, exchanges: [] });
    },
  );

  app.get("/api/v1/assistant/health", async () => {
    return probeAssistantHealth();
  });

  app.get("/api/v1/charts/jobs/:jobId/transits", async (request, reply) => {
    const { jobId } = request.params as { jobId: string };
    const { date, years } = request.query as { date?: string; years?: string };

    const artifact = await repository.findChartArtifact(jobId);

    if (!artifact) {
      return reply.code(404).send({
        error: {
          code: "chart_artifact_not_found",
          message: "Chart artifact was not found for this job.",
        },
      });
    }

    const atDate = date ? new Date(`${date}T00:00:00Z`) : new Date();
    if (Number.isNaN(atDate.getTime())) {
      return reply.code(400).send({
        error: {
          code: "transit_date_invalid",
          message: "date must be an ISO date such as 2026-07-09.",
        },
      });
    }

    const horizonYears = years ? Number(years) : 2;

    return reply.send({
      jobId,
      snapshot: computeTransitSnapshot(artifact, atDate),
      timeline: computeTransitTimeline(atDate, horizonYears),
    });
  });

  app.get("/api/v1/charts/jobs/:jobId", async (request, reply) => {
    const { jobId } = request.params as { jobId: string };
    const job = await repository.findChartRequest(jobId);

    if (!job) {
      return reply.code(404).send({
        error: {
          code: "chart_job_not_found",
          message: "Chart job was not found.",
        },
      });
    }

    return reply.send({
      ...job,
      requestedOutputs: JSON.parse(job.requestedOutputs) as string[],
    });
  });
}
