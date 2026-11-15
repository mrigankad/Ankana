import {
  computeVedicChartArtifact,
  type VedicChartArtifact,
} from "@astro/astrology-core";
import type { CreateChartRequestInput } from "@astro/shared-types";

import type { ChartRequestRecord } from "../../db/client";
import { getPrisma } from "../../db/prisma";

export class ChartRequestsRepository {
  async createChartRequest(
    input: CreateChartRequestInput,
  ): Promise<ChartRequestRecord> {
    return getPrisma().chartRequest.create({
      data: {
        ...input,
        requestedOutputs: JSON.stringify(input.requestedOutputs),
        status: "queued",
      },
    });
  }

  /**
   * Computes the deterministic chart artifact for a queued request.
   * Runs in-process for the current slice; the same contract moves to
   * a worker when async job infrastructure lands.
   */
  async processChartRequest(jobId: string): Promise<ChartRequestRecord | null> {
    const prisma = getPrisma();
    const request = await prisma.chartRequest.findUnique({ where: { id: jobId } });

    if (!request) {
      return null;
    }

    const birthRecord = await prisma.birthRecord.findUnique({
      where: { id: request.birthRecordId },
    });

    if (!birthRecord) {
      return prisma.chartRequest.update({
        where: { id: jobId },
        data: { status: "failed", error: "Birth record not found for chart request." },
      });
    }

    try {
      const artifact = computeVedicChartArtifact({
        birthDate: birthRecord.birthDate,
        birthTime: birthRecord.birthTime,
        timezoneName: birthRecord.timezoneName,
        latitude: birthRecord.latitude,
        longitude: birthRecord.longitude,
        placeLabel: birthRecord.placeLabel,
      });

      await prisma.chartArtifact.create({
        data: {
          chartRequestId: request.id,
          artifactJson: JSON.stringify(artifact),
          engineVersion: artifact.calculationMetadata.engineVersion,
        },
      });

      return prisma.chartRequest.update({
        where: { id: jobId },
        data: { status: "completed" },
      });
    } catch (error) {
      return prisma.chartRequest.update({
        where: { id: jobId },
        data: {
          status: "failed",
          error:
            error instanceof Error ? error.message : "Chart computation failed.",
        },
      });
    }
  }

  async findChartRequest(id: string): Promise<ChartRequestRecord | null> {
    return getPrisma().chartRequest.findUnique({ where: { id } });
  }

  async findChartArtifact(
    chartRequestId: string,
  ): Promise<VedicChartArtifact | null> {
    const record = await getPrisma().chartArtifact.findUnique({
      where: { chartRequestId },
    });
    if (!record) {
      return null;
    }

    const artifact = JSON.parse(record.artifactJson) as VedicChartArtifact;

    // Self-healing upgrade: artifacts computed by older engine versions
    // may lack newer sections; recompute once and persist.
    if (!artifact.strengthMetrics || !artifact.yoginiDasha) {
      const fresh = computeVedicChartArtifact(
        artifact.calculationMetadata.input,
      );
      await getPrisma().chartArtifact.update({
        where: { chartRequestId },
        data: {
          artifactJson: JSON.stringify(fresh),
          engineVersion: fresh.calculationMetadata.engineVersion,
        },
      });
      return fresh;
    }

    return artifact;
  }
}
