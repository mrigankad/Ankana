import path from "node:path";

import { PrismaBetterSqlite3 } from "@prisma/adapter-better-sqlite3";
import { PrismaClient } from "@prisma/client";

let prisma: PrismaClient | null = null;

function databaseUrl(): string {
  const url = process.env.DATABASE_URL ?? "file:./dev.db";
  if (!url.startsWith("file:")) {
    return url;
  }

  // Resolve relative sqlite paths against the api app root so the same
  // database is used regardless of the process working directory.
  const filePath = url.slice("file:".length);
  if (path.isAbsolute(filePath)) {
    return url;
  }
  const appRoot = path.resolve(new URL("../..", import.meta.url).pathname.replace(/^\/(\w:)/, "$1"));
  return `file:${path.join(appRoot, filePath)}`;
}

export function getPrisma(): PrismaClient {
  if (!prisma) {
    const adapter = new PrismaBetterSqlite3({ url: databaseUrl() });
    prisma = new PrismaClient({ adapter });
  }
  return prisma;
}
