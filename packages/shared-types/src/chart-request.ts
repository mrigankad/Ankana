import { z } from "zod";

export const createChartRequestInputSchema = z.object({
  workspaceId: z.string().min(1),
  clientId: z.string().min(1),
  birthRecordId: z.string().min(1),
  astrologySystem: z.enum(["vedic"]),
  requestedOutputs: z.array(z.string().min(1)).min(1),
});

export type CreateChartRequestInput = z.infer<typeof createChartRequestInputSchema>;
