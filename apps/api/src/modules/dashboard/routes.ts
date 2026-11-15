import {
  computePanchang,
  computeTransitSnapshot,
  computeTransitTimeline,
  meanLunarNode,
  normalizeDegrees,
  toSidereal,
  tropicalLongitude,
  type VedicChartArtifact,
} from "@astro/astrology-core";
import type { FastifyInstance } from "fastify";

import { getPrisma } from "../../db/prisma";

/** Latest completed artifact per client, capped for dashboard use. */
async function latestArtifactsByClient(
  workspaceId: string,
  cap = 50,
): Promise<VedicChartArtifact[]> {
  const prisma = getPrisma();
  const requests = await prisma.chartRequest.findMany({
    where: { workspaceId, status: "completed" },
    orderBy: { createdAt: "desc" },
    include: { artifact: true },
    take: 200,
  });

  const seen = new Set<string>();
  const artifacts: VedicChartArtifact[] = [];
  for (const request of requests) {
    if (seen.has(request.clientId) || !request.artifact) {
      continue;
    }
    seen.add(request.clientId);
    artifacts.push(
      JSON.parse(request.artifact.artifactJson) as VedicChartArtifact,
    );
    if (artifacts.length >= cap) {
      break;
    }
  }
  return artifacts;
}

export async function registerDashboardRoutes(
  app: FastifyInstance,
): Promise<void> {
  app.get("/api/v1/dashboard/summary", async (request) => {
    const { workspaceId } = request.query as { workspaceId?: string };
    const ws = workspaceId ?? "ws_1";
    const prisma = getPrisma();
    const now = new Date();

    const [clients, chartsCompleted, reportsRendered] = await Promise.all([
      prisma.client.count({ where: { workspaceId: ws } }),
      prisma.chartRequest.count({ where: { workspaceId: ws, status: "completed" } }),
      prisma.auditEvent.count({ where: { workspaceId: ws, action: "report.rendered" } }),
    ]);

    const artifacts = await latestArtifactsByClient(ws);
    const sadeSatiClients = artifacts.filter(
      (artifact) => computeTransitSnapshot(artifact, now).sadeSati.active,
    ).length;

    return { clients, chartsCompleted, sadeSatiClients, reportsRendered };
  });

  app.get("/api/v1/panchang/today", async (request) => {
    const { tz } = request.query as { tz?: string };
    const timezone = tz ?? "Asia/Kolkata";
    const now = new Date();

    const sunSidereal = toSidereal(tropicalLongitude("sun", now), now);
    const moonSidereal = toSidereal(tropicalLongitude("moon", now), now);
    const rahuSidereal = toSidereal(meanLunarNode(now), now);

    const localWeekday = new Date(
      now.toLocaleString("en-US", { timeZone: timezone }),
    ).getDay();

    const panchang = computePanchang(sunSidereal, moonSidereal, localWeekday);
    const upcomingEvents = computeTransitTimeline(now, 0.35).slice(0, 6);

    return {
      date: now.toISOString(),
      timezone,
      panchang,
      siderealLongitudes: {
        sun: sunSidereal,
        moon: moonSidereal,
        rahu: rahuSidereal,
        ketu: normalizeDegrees(rahuSidereal + 180),
      },
      upcomingEvents,
    };
  });
}
