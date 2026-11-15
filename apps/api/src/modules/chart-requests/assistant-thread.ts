import { getPrisma } from "../../db/prisma";

export interface StoredCitation {
  index: number;
  tool: string;
  fact: string;
}

export interface ThreadExchange {
  question: string;
  answer: string;
  citations: StoredCitation[];
}

export interface HistoryTurn {
  role: "user" | "assistant";
  content: string;
}

const MAX_HISTORY_MESSAGES = 10;

export class AssistantThreadRepository {
  async getOrCreateConversation(chartRequestId: string) {
    const prisma = getPrisma();
    const existing = await prisma.assistantConversation.findUnique({
      where: { chartRequestId },
    });
    if (existing) return existing;
    return prisma.assistantConversation.create({
      data: { chartRequestId },
    });
  }

  async listHistoryTurns(chartRequestId: string): Promise<HistoryTurn[]> {
    const prisma = getPrisma();
    const conversation = await prisma.assistantConversation.findUnique({
      where: { chartRequestId },
      include: {
        messages: { orderBy: { createdAt: "asc" } },
      },
    });
    if (!conversation) return [];
    return conversation.messages
      .filter((m) => m.role === "user" || m.role === "assistant")
      .map((m) => ({
        role: m.role as "user" | "assistant",
        content: m.content,
      }))
      .slice(-MAX_HISTORY_MESSAGES);
  }

  async listExchanges(chartRequestId: string): Promise<ThreadExchange[]> {
    const prisma = getPrisma();
    const conversation = await prisma.assistantConversation.findUnique({
      where: { chartRequestId },
      include: {
        messages: { orderBy: { createdAt: "asc" } },
      },
    });
    if (!conversation) return [];

    const exchanges: ThreadExchange[] = [];
    let pendingQuestion: string | null = null;
    for (const message of conversation.messages) {
      if (message.role === "user") {
        pendingQuestion = message.content;
        continue;
      }
      if (message.role === "assistant" && pendingQuestion) {
        let citations: StoredCitation[] = [];
        if (message.citationsJson) {
          try {
            citations = JSON.parse(message.citationsJson) as StoredCitation[];
          } catch {
            citations = [];
          }
        }
        exchanges.push({
          question: pendingQuestion,
          answer: message.content,
          citations,
        });
        pendingQuestion = null;
      }
    }
    return exchanges;
  }

  async appendExchange(
    chartRequestId: string,
    question: string,
    answer: string,
    citations: StoredCitation[],
    toolsUsed: string[],
  ): Promise<void> {
    const prisma = getPrisma();
    const conversation = await this.getOrCreateConversation(chartRequestId);
    await prisma.assistantMessage.createMany({
      data: [
        {
          conversationId: conversation.id,
          role: "user",
          content: question,
        },
        {
          conversationId: conversation.id,
          role: "assistant",
          content: answer,
          citationsJson: JSON.stringify(citations),
          toolsUsedJson: JSON.stringify(toolsUsed),
        },
      ],
    });
    await prisma.assistantConversation.update({
      where: { id: conversation.id },
      data: { updatedAt: new Date() },
    });
  }

  async clearThread(chartRequestId: string): Promise<void> {
    const prisma = getPrisma();
    const conversation = await prisma.assistantConversation.findUnique({
      where: { chartRequestId },
    });
    if (!conversation) return;
    await prisma.assistantMessage.deleteMany({
      where: { conversationId: conversation.id },
    });
  }
}
