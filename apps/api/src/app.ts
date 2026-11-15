import "dotenv/config";
import cors from "@fastify/cors";
import Fastify, { type FastifyInstance } from "fastify";
import { readEnv } from "../../../packages/shared-config/src/env";

import { registerChartRequestRoutes } from "./modules/chart-requests/routes";
import { registerClientRoutes } from "./modules/clients/routes";
import { registerLocationRoutes } from "./modules/locations/routes";
import { listAuditEvents } from "./modules/audit/audit";
import { registerDashboardRoutes } from "./modules/dashboard/routes";
import { registerReportRoutes } from "./modules/reports/routes";

export function buildApp(): FastifyInstance {
  const app = Fastify();

  void app.register(cors, {
    origin: true,
  });

  app.get("/health", async () => ({ status: "ok" }));

  app.get("/api/v1/audit-events", async (request) => {
    const { workspaceId, limit } = request.query as {
      workspaceId?: string;
      limit?: string;
    };
    const events = await listAuditEvents(
      workspaceId ?? "ws_1",
      limit ? Number(limit) : 50,
    );
    return { events };
  });

  void registerClientRoutes(app);
  void registerLocationRoutes(app);
  void registerChartRequestRoutes(app);
  void registerReportRoutes(app);
  void registerDashboardRoutes(app);

  return app;
}

if (!process.env.VITEST) {
  const app = buildApp();
  const env = readEnv();

  app
    .listen({ port: env.PORT, host: "0.0.0.0" })
    .then(() => {
      app.log.info(`API listening on port ${env.PORT}`);
    })
    .catch((error) => {
      app.log.error(error);
      process.exit(1);
    });
}
