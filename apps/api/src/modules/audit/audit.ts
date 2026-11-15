import { getPrisma } from "../../db/prisma";

export type AuditAction =
  | "client.created"
  | "birth_record.created"
  | "chart.generated"
  | "assistant.asked"
  | "assistant.thread_cleared"
  | "report.rendered";

/**
 * Records an audit event. Fire-and-forget by design: an audit failure
 * must never fail the user-facing operation, but it is logged.
 */
export function recordAudit(event: {
  workspaceId: string;
  action: AuditAction;
  subjectType: string;
  subjectId: string;
  meta?: Record<string, unknown>;
}): void {
  void getPrisma()
    .auditEvent.create({
      data: {
        workspaceId: event.workspaceId,
        action: event.action,
        subjectType: event.subjectType,
        subjectId: event.subjectId,
        metaJson: event.meta ? JSON.stringify(event.meta) : null,
      },
    })
    .catch((error: unknown) => {
      console.error("audit event failed", event.action, error);
    });
}

export async function listAuditEvents(workspaceId: string, limit = 50) {
  return getPrisma().auditEvent.findMany({
    where: { workspaceId },
    orderBy: { createdAt: "desc" },
    take: Math.min(limit, 200),
  });
}
