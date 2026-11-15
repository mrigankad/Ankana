import { z } from "zod";

export const envSchema = z.object({
  DATABASE_URL: z.string().min(1).default("file:./dev.db"),
  PORT: z.coerce.number().default(3001),
});

export type AppEnv = z.infer<typeof envSchema>;

export function readEnv(input: Record<string, string | undefined> = process.env): AppEnv {
  return envSchema.parse(input);
}
