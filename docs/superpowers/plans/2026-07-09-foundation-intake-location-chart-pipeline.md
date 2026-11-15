# Foundation + Intake + Location Resolution + Chart Request Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first working product slice: a monorepo foundation with practitioner-facing client intake, location-to-latitude/longitude resolution, and a chart request pipeline that stores validated birth inputs and queues chart generation requests.

**Architecture:** Start with a modular TypeScript monorepo that establishes the long-term package boundaries from the docs, but only implements the smallest usable vertical slice. The slice includes shared contracts, API scaffolding, a practitioner web app with client intake, a location resolution service abstraction, persistence for clients and birth records, and queue-backed chart request creation without yet implementing the full Vedic calculation engine.

**Tech Stack:** TypeScript, Node.js, pnpm workspaces, Next.js for `apps/web-practitioner`, NestJS or Fastify-based TypeScript API for `apps/api`, PostgreSQL with Prisma, Zod, Vitest, Playwright, and a simple queue abstraction backed by database jobs initially.

## Global Constraints

- Deterministic before generative: astronomical and astrological outputs must come from validated algorithms, ephemeris data, and versioned rule packs.
- Explainability by default: every prediction, remedy, and recommendation must reference chart facts, timing systems, and rule outcomes.
- Modular astrology systems: each tradition is implemented as an isolated module behind shared contracts.
- Practitioner-first workflows: case management, client history, report delivery, and repeat consultations are first-class features.
- Enterprise governance: auditability, tenant isolation, consent, retention controls, and access control are mandatory architecture concerns.
- Safe advisory posture: the system may discuss wellness, timing, and spiritual guidance, but it must avoid impersonating regulated medical, legal, or financial advice.
- V1 implements Vedic/Jyotish deeply; other systems are future modules behind common interfaces.
- The platform is practitioner-first, so collaboration, client records, report delivery, and repeat consultations are first-class.
- The system must support daily-to-lifetime forecasting with chart-backed reasoning and confidence semantics.
- Remedy suggestions must include contraindications and must not overstate certainty, especially around gemstones and sensitive life advice.
- Security and governance should be designed at enterprise level from the start: tenant isolation, auditability, retention controls, explainability, and role-based permissions.

---

### Task 1: Monorepo Foundation

**Files:**
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\package.json`
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\pnpm-workspace.yaml`
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\tsconfig.base.json`
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\.gitignore`
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\apps\api\package.json`
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\apps\web-practitioner\package.json`
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\packages\shared-types\package.json`
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\packages\shared-config\package.json`
- Test: `C:\Users\mriga_ijtdono\Desktop\Astro\package.json`

**Interfaces:**
- Consumes: none
- Produces:
  - workspace scripts: `pnpm lint`, `pnpm test`, `pnpm dev`
  - TS path aliases for `@astro/shared-types` and `@astro/shared-config`

- [ ] **Step 1: Write the failing test**

```json
{
  "scripts": {
    "test:workspace": "pnpm -r test"
  }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm test:workspace`
Expected: FAIL because workspace packages and scripts do not exist yet

- [ ] **Step 3: Write minimal implementation**

```json
{
  "name": "astro-platform",
  "private": true,
  "packageManager": "pnpm@10",
  "scripts": {
    "dev": "pnpm --parallel --filter ./apps/* dev",
    "lint": "pnpm -r lint",
    "test": "pnpm -r test"
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm test`
Expected: PASS with placeholder package tests succeeding

- [ ] **Step 5: Commit**

```bash
git add package.json pnpm-workspace.yaml tsconfig.base.json .gitignore apps packages
git commit -m "chore: scaffold monorepo foundation"
```

### Task 2: Shared Contracts For Intake And Chart Requests

**Files:**
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\packages\shared-types\src\client.ts`
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\packages\shared-types\src\location.ts`
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\packages\shared-types\src\chart-request.ts`
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\packages\shared-types\src\index.ts`
- Test: `C:\Users\mriga_ijtdono\Desktop\Astro\packages\shared-types\src\client.test.ts`

**Interfaces:**
- Consumes: TS workspace foundation from Task 1
- Produces:
  - `CreateClientInput`
  - `CreateBirthRecordInput`
  - `LocationSearchResult`
  - `CreateChartRequestInput`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest";
import { createBirthRecordInputSchema } from "./client";

describe("createBirthRecordInputSchema", () => {
  it("requires either coordinates or a resolved provider place id", () => {
    const result = createBirthRecordInputSchema.safeParse({
      birthDate: "1990-01-01",
      birthTime: "10:30",
      timezoneName: "Asia/Kolkata",
      placeLabel: "Varanasi, India",
    });

    expect(result.success).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @astro/shared-types test`
Expected: FAIL because schemas and exports do not exist

- [ ] **Step 3: Write minimal implementation**

```ts
import { z } from "zod";

export const createBirthRecordInputSchema = z
  .object({
    birthDate: z.string(),
    birthTime: z.string(),
    timezoneName: z.string(),
    placeLabel: z.string(),
    latitude: z.number().optional(),
    longitude: z.number().optional(),
    providerPlaceId: z.string().optional(),
  })
  .refine(
    (value) =>
      (typeof value.latitude === "number" &&
        typeof value.longitude === "number") ||
      typeof value.providerPlaceId === "string",
    { message: "Coordinates or providerPlaceId is required" },
  );
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm --filter @astro/shared-types test`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/shared-types
git commit -m "feat: add intake and chart request contracts"
```

### Task 3: Persistence Layer For Clients, Birth Records, And Chart Requests

**Files:**
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\packages\shared-config\src\env.ts`
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\apps\api\prisma\schema.prisma`
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\apps\api\src\db\client.ts`
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\apps\api\src\modules\clients\repository.ts`
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\apps\api\src\modules\chart-requests\repository.ts`
- Test: `C:\Users\mriga_ijtdono\Desktop\Astro\apps\api\src\modules\clients\repository.test.ts`

**Interfaces:**
- Consumes:
  - `CreateClientInput`
  - `CreateBirthRecordInput`
  - `CreateChartRequestInput`
- Produces:
  - `createClient(input: CreateClientInput): Promise<ClientRecord>`
  - `createBirthRecord(input: CreateBirthRecordInput): Promise<BirthRecord>`
  - `createChartRequest(input: CreateChartRequestInput): Promise<ChartRequestRecord>`

- [ ] **Step 1: Write the failing test**

```ts
it("persists original location query and resolved coordinates", async () => {
  const birthRecord = await repository.createBirthRecord({
    clientId: "cli_1",
    birthDate: "1990-01-01",
    birthTime: "10:30",
    timezoneName: "Asia/Kolkata",
    placeLabel: "Varanasi, Uttar Pradesh, India",
    locationQueryText: "Banaras, India",
    canonicalLocationName: "Varanasi, Uttar Pradesh, India",
    latitude: 25.3176,
    longitude: 82.9739,
    providerPlaceId: "geo_123",
  });

  expect(birthRecord.locationQueryText).toBe("Banaras, India");
  expect(birthRecord.latitude).toBe(25.3176);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @astro/api test -- repository`
Expected: FAIL because schema and repositories do not exist

- [ ] **Step 3: Write minimal implementation**

```prisma
model BirthRecord {
  id                    String   @id @default(cuid())
  clientId              String
  birthDate             String
  birthTime             String
  timezoneName          String
  placeLabel            String
  locationQueryText     String?
  canonicalLocationName String?
  latitude              Float
  longitude             Float
  providerPlaceId       String?
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm --filter @astro/api test -- repository`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api packages/shared-config
git commit -m "feat: persist client intake and chart request data"
```

### Task 4: Location Resolution Service

**Files:**
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\apps\api\src\modules\locations\types.ts`
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\apps\api\src\modules\locations\provider.ts`
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\apps\api\src\modules\locations\service.ts`
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\apps\api\src\modules\locations\service.test.ts`
- Test: `C:\Users\mriga_ijtdono\Desktop\Astro\apps\api\src\modules\locations\service.test.ts`

**Interfaces:**
- Consumes:
  - `LocationSearchResult`
- Produces:
  - `searchLocations(query: string, preferredCountryCode?: string): Promise<LocationSearchResult[]>`
  - `resolveLocation(input: { query: string; preferredCountryCode?: string }): Promise<LocationSearchResult[]>`

- [ ] **Step 1: Write the failing test**

```ts
it("returns ranked normalized location matches", async () => {
  const results = await service.resolveLocation({
    query: "Banaras, UP, India",
    preferredCountryCode: "IN",
  });

  expect(results[0]?.displayName).toBe("Varanasi, Uttar Pradesh, India");
  expect(results[0]?.timezoneName).toBe("Asia/Kolkata");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @astro/api test -- locations`
Expected: FAIL because the service does not exist

- [ ] **Step 3: Write minimal implementation**

```ts
export interface LocationProvider {
  search(query: string, preferredCountryCode?: string): Promise<LocationSearchResult[]>;
}

export class LocationResolutionService {
  constructor(private readonly provider: LocationProvider) {}

  async resolveLocation(input: { query: string; preferredCountryCode?: string }) {
    return this.provider.search(input.query, input.preferredCountryCode);
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm --filter @astro/api test -- locations`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/modules/locations
git commit -m "feat: add location resolution service abstraction"
```

### Task 5: API Endpoints For Clients, Locations, And Chart Requests

**Files:**
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\apps\api\src\app.ts`
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\apps\api\src\modules\clients\routes.ts`
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\apps\api\src\modules\locations\routes.ts`
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\apps\api\src\modules\chart-requests\routes.ts`
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\apps\api\src\app.test.ts`
- Test: `C:\Users\mriga_ijtdono\Desktop\Astro\apps\api\src\app.test.ts`

**Interfaces:**
- Consumes:
  - `createClient`
  - `createBirthRecord`
  - `createChartRequest`
  - `resolveLocation`
- Produces:
  - `POST /api/v1/clients`
  - `POST /api/v1/clients/:clientId/birth-records`
  - `GET /api/v1/locations/search`
  - `POST /api/v1/charts/generate`

- [ ] **Step 1: Write the failing test**

```ts
it("creates a chart request after a birth record exists", async () => {
  const response = await app.inject({
    method: "POST",
    url: "/api/v1/charts/generate",
    payload: {
      workspaceId: "ws_1",
      clientId: "cli_1",
      birthRecordId: "br_1",
      astrologySystem: "vedic",
      requestedOutputs: ["birthChart"],
    },
  });

  expect(response.statusCode).toBe(202);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @astro/api test -- app`
Expected: FAIL because routes and app bootstrap do not exist

- [ ] **Step 3: Write minimal implementation**

```ts
app.post("/api/v1/charts/generate", async (request, reply) => {
  const job = await chartRequestRepository.createChartRequest(request.body as CreateChartRequestInput);
  return reply.code(202).send({
    jobId: job.id,
    status: "queued",
    statusUrl: `/api/v1/charts/jobs/${job.id}`,
  });
});
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm --filter @astro/api test -- app`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api
git commit -m "feat: expose intake, location, and chart request APIs"
```

### Task 6: Practitioner Intake UI

**Files:**
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\apps\web-practitioner\app\page.tsx`
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\apps\web-practitioner\app\clients\new\page.tsx`
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\apps\web-practitioner\components\client-intake-form.tsx`
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\apps\web-practitioner\components\location-search.tsx`
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\apps\web-practitioner\components\chart-request-form.tsx`
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\apps\web-practitioner\components\client-intake-form.test.tsx`
- Test: `C:\Users\mriga_ijtdono\Desktop\Astro\apps\web-practitioner\components\client-intake-form.test.tsx`

**Interfaces:**
- Consumes:
  - `GET /api/v1/locations/search`
  - `POST /api/v1/clients`
  - `POST /api/v1/clients/:clientId/birth-records`
  - `POST /api/v1/charts/generate`
- Produces:
  - `ClientIntakeForm`
  - `LocationSearch`
  - `ChartRequestForm`

- [ ] **Step 1: Write the failing test**

```tsx
it("requires a confirmed location before enabling chart generation", async () => {
  render(<ClientIntakeForm />);

  expect(
    screen.getByRole("button", { name: /generate chart/i }),
  ).toBeDisabled();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @astro/web-practitioner test -- client-intake-form`
Expected: FAIL because form components do not exist

- [ ] **Step 3: Write minimal implementation**

```tsx
export function ClientIntakeForm() {
  const [hasConfirmedLocation, setHasConfirmedLocation] = useState(false);

  return (
    <form>
      <button disabled={!hasConfirmedLocation} type="submit">
        Generate Chart
      </button>
    </form>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm --filter @astro/web-practitioner test -- client-intake-form`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/web-practitioner
git commit -m "feat: add practitioner intake and chart request flow"
```

### Task 7: End-To-End Slice Verification

**Files:**
- Create: `C:\Users\mriga_ijtdono\Desktop\Astro\tests\e2e\client-intake-chart-request.spec.ts`
- Modify: `C:\Users\mriga_ijtdono\Desktop\Astro\package.json`
- Test: `C:\Users\mriga_ijtdono\Desktop\Astro\tests\e2e\client-intake-chart-request.spec.ts`

**Interfaces:**
- Consumes:
  - practitioner intake UI
  - intake and location APIs
  - chart request queueing
- Produces:
  - verified slice: create client -> resolve place -> save birth record -> queue chart request

- [ ] **Step 1: Write the failing test**

```ts
test("practitioner can create a client and queue a chart request", async ({ page }) => {
  await page.goto("/clients/new");
  await page.getByLabel("Full name").fill("Test Client");
  await page.getByLabel("Birth place").fill("Varanasi, India");
  await page.getByRole("button", { name: "Search location" }).click();
  await page.getByRole("button", { name: /confirm varanasi/i }).click();
  await page.getByRole("button", { name: /generate chart/i }).click();
  await expect(page.getByText(/chart request queued/i)).toBeVisible();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm exec playwright test tests/e2e/client-intake-chart-request.spec.ts`
Expected: FAIL because the full flow is not implemented yet

- [ ] **Step 3: Write minimal implementation**

```ts
// Add success toast or confirmation panel after chart request creation:
setStatusMessage("Chart request queued");
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm exec playwright test tests/e2e/client-intake-chart-request.spec.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/e2e package.json apps/web-practitioner apps/api
git commit -m "test: verify end-to-end client intake chart request flow"
```

## Self-Review

### Spec coverage
- Covered the first usable slice from the roadmap: monorepo foundation, client intake, location resolution, and chart request pipeline.
- Intentionally deferred full deterministic Vedic calculation, rule engine, remedies, PDF reports, and assistant features to later plans because they are separate subsystems.

### Placeholder scan
- No `TODO`, `TBD`, or implicit “implement later” steps are used inside tasks.
- All task steps include concrete files, interfaces, commands, and expected outcomes.

### Type consistency
- Shared contracts are introduced before repositories, services, routes, and UI consume them.
- Location resolution interfaces remain consistent across shared types, API services, and UI usage.
