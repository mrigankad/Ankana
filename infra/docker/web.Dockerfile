# Ankana web (Next.js, standalone output). Build context: repo root.
# NEXT_PUBLIC_* values are inlined at build time, so pass them as build args.
FROM node:22-slim AS build
RUN corepack enable
WORKDIR /repo
COPY . .
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_AUTH_MODE=builtin
ARG NEXT_PUBLIC_GIT_SHA=unknown
ARG NEXT_PUBLIC_SOURCE_URL=https://github.com/mrigankad/Ankana
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL} \
    NEXT_PUBLIC_AUTH_MODE=${NEXT_PUBLIC_AUTH_MODE} \
    NEXT_PUBLIC_GIT_SHA=${NEXT_PUBLIC_GIT_SHA} \
    NEXT_PUBLIC_SOURCE_URL=${NEXT_PUBLIC_SOURCE_URL} \
    NEXT_OUTPUT=standalone \
    NEXT_TELEMETRY_DISABLED=1
RUN pnpm install --frozen-lockfile --filter @astro/web-practitioner...
RUN pnpm --filter @astro/web-practitioner exec next build

FROM node:22-slim
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0 NEXT_TELEMETRY_DISABLED=1
RUN useradd --create-home --uid 10001 ankana
WORKDIR /app
COPY --from=build /repo/apps/web-practitioner/.next/standalone ./
COPY --from=build /repo/apps/web-practitioner/.next/static ./apps/web-practitioner/.next/static
COPY --from=build /repo/apps/web-practitioner/public ./apps/web-practitioner/public
COPY --from=build /repo/LICENSE ./LICENSE
USER ankana
EXPOSE 3000
CMD ["node", "apps/web-practitioner/server.js"]
