import type { FastifyInstance } from "fastify";
import {
  createBirthRecordInputSchema,
  createClientInputSchema,
} from "../../../../../packages/shared-types/src/client";

import { recordAudit } from "../audit/audit";
import { ClientsRepository } from "./repository";

export async function registerClientRoutes(app: FastifyInstance): Promise<void> {
  const repository = new ClientsRepository();

  app.get("/api/v1/clients", async (request, reply) => {
    const { workspaceId } = request.query as { workspaceId?: string };
    const clients = await repository.listClients(workspaceId ?? "ws_1");
    return reply.send({ clients });
  });

  app.get("/api/v1/clients/:clientId", async (request, reply) => {
    const { clientId } = request.params as { clientId: string };
    const client = await repository.findClientDetail(clientId);
    if (!client) {
      return reply.code(404).send({
        error: { code: "client_not_found", message: "Client was not found." },
      });
    }
    return reply.send(client);
  });

  app.post("/api/v1/clients", async (request, reply) => {
    const parsed = createClientInputSchema.safeParse(request.body);

    if (!parsed.success) {
      return reply.code(400).send({
        error: {
          code: "client_input_invalid",
          message: parsed.error.issues[0]?.message ?? "Invalid client input",
        },
      });
    }

    const client = await repository.createClient(parsed.data);
    recordAudit({
      workspaceId: parsed.data.workspaceId,
      action: "client.created",
      subjectType: "client",
      subjectId: client.id,
    });
    return reply.code(201).send(client);
  });

  app.post("/api/v1/clients/:clientId/birth-records", async (request, reply) => {
    const clientId = (request.params as { clientId: string }).clientId;
    const parsed = createBirthRecordInputSchema.safeParse(request.body);

    if (!parsed.success) {
      return reply.code(400).send({
        error: {
          code: "birth_record_input_invalid",
          message: parsed.error.issues[0]?.message ?? "Invalid birth record input",
        },
      });
    }

    const birthRecord = await repository.createBirthRecord({
      ...parsed.data,
      clientId,
    });

    recordAudit({
      workspaceId: "ws_1",
      action: "birth_record.created",
      subjectType: "birthRecord",
      subjectId: birthRecord.id,
      meta: { clientId },
    });
    return reply.code(201).send(birthRecord);
  });
}
