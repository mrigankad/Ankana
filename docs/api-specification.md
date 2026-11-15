# API Specification

## API Style
- Primary interface: JSON over HTTPS.
- Auth: session auth for web, token auth for service integrations.
- Versioning: `/api/v1`.
- Async work: long-running operations return job handles and status endpoints.

## Auth And Access
### Core Scopes
- `workspace:read`
- `workspace:write`
- `client:read`
- `client:write`
- `chart:read`
- `chart:write`
- `report:read`
- `report:write`
- `assistant:use`
- `admin:audit`

## Resource Domains
### Workspaces
- `GET /api/v1/workspaces`
- `POST /api/v1/workspaces`
- `GET /api/v1/workspaces/{workspaceId}`
- `POST /api/v1/workspaces/{workspaceId}/members`

### Clients
- `GET /api/v1/clients`
- `POST /api/v1/clients`
- `GET /api/v1/clients/{clientId}`
- `PATCH /api/v1/clients/{clientId}`
- `POST /api/v1/clients/{clientId}/birth-records`
- `GET /api/v1/locations/search?q={query}`
- `POST /api/v1/locations/resolve`

### Charts
- `POST /api/v1/charts/generate`
  - input: client id, birth record id, astrology system, requested outputs
  - output: chart job id
- `GET /api/v1/charts/jobs/{jobId}`
- `GET /api/v1/charts/{chartArtifactId}`
- `GET /api/v1/charts/{chartArtifactId}/divisional`
- `GET /api/v1/charts/{chartArtifactId}/dashas`
- `GET /api/v1/charts/{chartArtifactId}/transits`
- `GET /api/v1/charts/{chartArtifactId}/findings`
- `GET /api/v1/charts/{chartArtifactId}/remedies`

### Forecasts
- `POST /api/v1/forecasts/generate`
- `GET /api/v1/forecasts/{forecastId}`
- `GET /api/v1/forecasts/{forecastId}/timeline`

### Reports
- `GET /api/v1/report-templates`
- `POST /api/v1/reports/generate`
- `GET /api/v1/reports/jobs/{jobId}`
- `GET /api/v1/reports/{reportId}`
- `POST /api/v1/reports/{reportId}/share`

### Assistant
- `POST /api/v1/assistant/threads`
- `POST /api/v1/assistant/threads/{threadId}/messages`
- `GET /api/v1/assistant/threads/{threadId}`
- `GET /api/v1/assistant/threads/{threadId}/messages`

### Governance
- `GET /api/v1/audit-events`
- `GET /api/v1/retention-policies`
- `POST /api/v1/deletion-requests`

## Example Contracts
### `GET /api/v1/locations/search?q=Varanasi`
```json
{
  "results": [
    {
      "providerPlaceId": "geo_123",
      "displayName": "Varanasi, Uttar Pradesh, India",
      "latitude": 25.3176,
      "longitude": 82.9739,
      "timezoneName": "Asia/Kolkata",
      "confidence": "high"
    }
  ]
}
```

### `POST /api/v1/locations/resolve`
```json
{
  "query": "Banaras, UP, India",
  "preferredCountryCode": "IN"
}
```

### `POST /api/v1/charts/generate`
```json
{
  "workspaceId": "ws_123",
  "clientId": "cli_123",
  "birthRecordId": "br_123",
  "astrologySystem": "vedic",
  "requestedOutputs": [
    "birthChart",
    "divisionalCharts",
    "shadbala",
    "vimshottariDasha",
    "transits",
    "yogaFindings",
    "remedies"
  ]
}
```

### Job Response
```json
{
  "jobId": "job_123",
  "status": "queued",
  "statusUrl": "/api/v1/charts/jobs/job_123"
}
```

### Assistant Message Request
```json
{
  "message": "Why is the current Saturn period difficult for this client?",
  "chartArtifactId": "chart_123",
  "consultationId": "con_123",
  "responseMode": "grounded_explanation"
}
```

### Assistant Message Response
```json
{
  "messageId": "msg_123",
  "content": "Current strain is linked to Saturn's role in the chart and its active period...",
  "citations": [
    { "type": "dasha_sequence", "id": "dash_1" },
    { "type": "yoga_finding", "id": "yoga_3" }
  ],
  "safetyFlags": []
}
```

## Error Contract
```json
{
  "error": {
    "code": "birth_data_invalid",
    "message": "Birth time is outside accepted range.",
    "details": {
      "field": "birthTime"
    },
    "requestId": "req_123"
  }
}
```

Location resolution failures should use specific codes such as:
- `location_not_found`
- `location_ambiguous`
- `timezone_resolution_failed`

## Async Status Model
All background jobs expose:
- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`

Include progress messages and timestamps where meaningful.

## Eventing
Emit internal domain events for:
- chart generated
- rule evaluation complete
- report ready
- assistant response created
- deletion request accepted

Optional outbound webhooks later for enterprise integrations.

## API Governance
- OpenAPI spec generated from source contracts.
- Backward compatibility guaranteed within a major version.
- Breaking changes require a new version path and migration notes.
