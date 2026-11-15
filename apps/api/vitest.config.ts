import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // Tests share one SQLite database; run files sequentially.
    fileParallelism: false,
    globalSetup: "./vitest.global-setup.ts",
    env: {
      DATABASE_URL: "file:./test.db",
    },
  },
});
