import { getPrisma } from "./prisma";

export interface ClientRecord {
  id: string;
  workspaceId: string;
  fullName: string;
  preferredName?: string | null;
  email?: string | null;
  phone?: string | null;
  timezone?: string | null;
}

export interface BirthRecordRecord {
  id: string;
  clientId: string;
  birthDate: string;
  birthTime: string;
  timezoneName: string;
  placeLabel: string;
  locationQueryText?: string | null;
  canonicalLocationName?: string | null;
  latitude: number;
  longitude: number;
  providerPlaceId?: string | null;
  geocodeProvider?: string | null;
  geocodeConfidence?: string | null;
}

export interface ChartRequestRecord {
  id: string;
  workspaceId: string;
  clientId: string;
  birthRecordId: string;
  astrologySystem: string;
  requestedOutputs: string;
  status: string;
  error?: string | null;
}

export async function resetDatabaseClient(): Promise<void> {
  const prisma = getPrisma();
  await prisma.auditEvent.deleteMany();
  await prisma.assistantMessage.deleteMany();
  await prisma.assistantConversation.deleteMany();
  await prisma.chartArtifact.deleteMany();
  await prisma.chartRequest.deleteMany();
  await prisma.birthRecord.deleteMany();
  await prisma.client.deleteMany();
}
