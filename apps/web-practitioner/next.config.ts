import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Container image (infra/docker/web.Dockerfile) sets NEXT_OUTPUT=standalone.
  ...(process.env.NEXT_OUTPUT === "standalone"
    ? {
        output: "standalone" as const,
        outputFileTracingRoot: path.join(__dirname, "../.."),
      }
    : {}),
  // Playwright and local tooling reach the dev server via 127.0.0.1.
  allowedDevOrigins: ["127.0.0.1"],
  // Turbopack root is the monorepo; next must also be resolvable there
  // (see root package.json) or HMR panics with "Next.js package not found".
  turbopack: {
    root: path.join(__dirname, "../.."),
  },
};

export default nextConfig;
