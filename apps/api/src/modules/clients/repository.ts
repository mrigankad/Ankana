import type { CreateBirthRecordInput, CreateClientInput } from "@astro/shared-types";

import type { BirthRecordRecord, ClientRecord } from "../../db/client";
import { getPrisma } from "../../db/prisma";

export interface ClientSummary extends ClientRecord {
  birthRecordCount: number;
  latestChartRequest: { id: string; status: string; createdAt: string } | null;
  createdAt: string;
  /** From the latest completed artifact, when one exists. */
  lagnaSign: string | null;
  currentMahadasha: string | null;
}

export class ClientsRepository {
  async listClients(workspaceId: string): Promise<ClientSummary[]> {
    const prisma = getPrisma();
    const clients = await prisma.client.findMany({
      where: { workspaceId },
      orderBy: { createdAt: "desc" },
      include: { birthRecords: { select: { id: true } } },
    });

    const now = Date.now();
    const summaries: ClientSummary[] = [];
    for (const client of clients) {
      const latest = await prisma.chartRequest.findFirst({
        where: { clientId: client.id },
        orderBy: { createdAt: "desc" },
        include: { artifact: true },
      });

      let lagnaSign: string | null = null;
      let currentMahadasha: string | null = null;
      if (latest?.artifact) {
        try {
          const artifact = JSON.parse(latest.artifact.artifactJson) as {
            ascendant: { signName: string };
            vimshottari: {
              mahadashas: Array<{ planet: string; start: string; end: string }>;
            };
          };
          lagnaSign = artifact.ascendant.signName;
          currentMahadasha =
            artifact.vimshottari.mahadashas.find(
              (m) =>
                new Date(m.start).getTime() <= now &&
                now < new Date(m.end).getTime(),
            )?.planet ?? null;
        } catch {
          // Corrupt artifact JSON: leave enrichment fields null.
        }
      }

      const { birthRecords, ...rest } = client;
      summaries.push({
        ...rest,
        birthRecordCount: birthRecords.length,
        createdAt: client.createdAt.toISOString(),
        lagnaSign,
        currentMahadasha,
        latestChartRequest: latest
          ? {
              id: latest.id,
              status: latest.status,
              createdAt: latest.createdAt.toISOString(),
            }
          : null,
      });
    }
    return summaries;
  }

  async findClientDetail(clientId: string) {
    const prisma = getPrisma();
    const client = await prisma.client.findUnique({
      where: { id: clientId },
      include: { birthRecords: true },
    });
    if (!client) {
      return null;
    }
    const chartRequests = await prisma.chartRequest.findMany({
      where: { clientId },
      orderBy: { createdAt: "desc" },
    });
    return { ...client, chartRequests };
  }

  async createClient(input: CreateClientInput): Promise<ClientRecord> {
    return getPrisma().client.create({ data: input });
  }

  async createBirthRecord(
    input: CreateBirthRecordInput & { clientId: string },
  ): Promise<BirthRecordRecord> {
    if (typeof input.latitude !== "number" || typeof input.longitude !== "number") {
      throw new Error("Resolved latitude and longitude are required before persistence.");
    }

    const { clientId, latitude, longitude, ...rest } = input;

    return getPrisma().birthRecord.create({
      data: {
        ...rest,
        latitude,
        longitude,
        client: { connect: { id: clientId } },
      },
    });
  }
}
