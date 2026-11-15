import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { createReadStream } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import type { FastifyInstance } from "fastify";

import { recordAudit } from "../audit/audit";
import { ChartRequestsRepository } from "../chart-requests/repository";

const STORAGE_DIR = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../storage/reports",
);

function reportPath(jobId: string): string {
  return path.join(STORAGE_DIR, `${jobId}.pdf`);
}

/**
 * Renders the print route to PDF with Playwright chromium.
 * REPORT_RENDERER=stub writes a marker file instead (tests, CI).
 */
async function renderReportPdf(jobId: string): Promise<string> {
  mkdirSync(STORAGE_DIR, { recursive: true });
  const target = reportPath(jobId);

  if (process.env.REPORT_RENDERER === "stub") {
    writeFileSync(target, "%PDF-1.4 nakshatra-stub-report");
    return target;
  }

  const { chromium } = await import("@playwright/test");
  const webBaseUrl = process.env.WEB_BASE_URL ?? "http://localhost:3000";
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    await page.goto(`${webBaseUrl}/charts/${jobId}/print`, {
      waitUntil: "networkidle",
    });
    await page.waitForSelector('[data-testid="report-ready"]', {
      timeout: 30_000,
    });
    // Ensure logo and kundali assets have painted before capture.
    await page.evaluate(async () => {
      const images = Array.from(document.images);
      await Promise.all(
        images.map((img) =>
          img.complete
            ? Promise.resolve()
            : new Promise<void>((resolve) => {
                img.addEventListener("load", () => resolve(), { once: true });
                img.addEventListener("error", () => resolve(), { once: true });
              }),
        ),
      );
    });
    await page.pdf({
      path: target,
      format: "A4",
      printBackground: true,
      preferCSSPageSize: true,
      displayHeaderFooter: true,
      headerTemplate: `<div style="width:100%;padding:0 12mm;font-size:8px;color:#221E1D;font-family:system-ui,sans-serif;display:flex;justify-content:space-between;"><span>Nakshatra · Birth Chart Report</span><span></span></div>`,
      footerTemplate: `<div style="width:100%;padding:0 12mm;font-size:8px;color:#6C6866;font-family:system-ui,sans-serif;display:flex;justify-content:space-between;align-items:center;"><span>github.com/mrigankad</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>`,
      margin: { top: "16mm", bottom: "18mm", left: "12mm", right: "12mm" },
    });
  } finally {
    await browser.close();
  }
  return target;
}

export async function registerReportRoutes(app: FastifyInstance): Promise<void> {
  const repository = new ChartRequestsRepository();

  app.post("/api/v1/reports/:jobId", async (request, reply) => {
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

    try {
      await renderReportPdf(jobId);
      recordAudit({
        workspaceId: "ws_1",
        action: "report.rendered",
        subjectType: "chartRequest",
        subjectId: jobId,
      });
      return reply
        .code(201)
        .send({ jobId, reportUrl: `/api/v1/reports/${jobId}` });
    } catch (error) {
      return reply.code(503).send({
        error: {
          code: "report_render_failed",
          message:
            error instanceof Error ? error.message : "Report rendering failed.",
        },
      });
    }
  });

  app.get("/api/v1/reports/:jobId", async (request, reply) => {
    const { jobId } = request.params as { jobId: string };
    const file = reportPath(jobId);

    if (!existsSync(file)) {
      return reply.code(404).send({
        error: {
          code: "report_not_found",
          message: "Report has not been generated yet.",
        },
      });
    }

    return reply
      .header("Content-Type", "application/pdf")
      .header(
        "Content-Disposition",
        `attachment; filename="nakshatra-report-${jobId}.pdf"`,
      )
      .send(createReadStream(file));
  });
}
