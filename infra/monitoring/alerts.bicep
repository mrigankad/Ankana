// Alert rules for Ankana on Azure Monitor (log search alerts on the Log Analytics workspace
// behind Application Insights). Deploy on its own or from stack.bicep:
//   az deployment group create -g rg-ankana-prod-cin -f infra/monitoring/alerts.bicep \
//      -p workspaceId=<law resource id> alertEmail=ops@example.org
// Tables used: AppRequests (traces export), AppMetrics (OpenTelemetry metrics export, see
// docs/operations.md), AppTraces. Metric names are the ones in services/api-py/src/app/metrics.py.
// Counters arrive as per-interval deltas (the Azure exporter prefers delta temporality), so
// summing them over a window gives the count in that window.

param name string
param location string = resourceGroup().location
param tags object = {}
@description('Resource id of the Log Analytics workspace that backs Application Insights.')
param workspaceId string
@description('Email for the action group. Leave empty to create the rules without notifications (wire your own action group).')
param alertEmail string = ''
@description('Existing action group id; used instead of creating one when set.')
param actionGroupId string = ''

@description('Error-rate alert threshold, percent of requests answered 5xx (SLO is 0.5).')
param errorRatePercent int = 1
@description('Oldest ready job older than this many seconds raises the queue-age alert.')
param queueAgeSeconds int = 300
@description('Failed jobs (terminal, last 24 h) at or above this raises the failed-jobs alert.')
param failedJobs int = 3
@description('Failed + blocked sign-ins in 5 minutes at or above this raises the brute-force alert.')
param authFailures5m int = 50
@description('Notification send failures in 15 minutes at or above this raises the alert.')
param notificationFailures15m int = 10
@description('p95 latency (ms) of non-AI API requests over 10 minutes (SLO: chart generate 800, reads 200).')
param p95LatencyMs int = 800

resource ag 'Microsoft.Insights/actionGroups@2023-01-01' = if (empty(actionGroupId) && !empty(alertEmail)) {
  name: 'ag-${name}-ops'
  location: 'global'
  tags: tags
  properties: {
    groupShortName: 'ankana-ops'
    enabled: true
    emailReceivers: [
      { name: 'ops', emailAddress: alertEmail, useCommonAlertSchema: true }
    ]
  }
}

var actions = !empty(actionGroupId) ? [actionGroupId] : (!empty(alertEmail) ? [ag.id] : [])

var rules = [
  {
    key: 'error-rate'
    title: 'API 5xx error rate above ${errorRatePercent}%'
    description: 'More than ${errorRatePercent}% of API requests returned 5xx over 10 minutes (needs 50+ requests). SLO is 0.5%.'
    severity: 1
    window: 'PT10M'
    frequency: 'PT5M'
    query: replace('''
      AppRequests
      | where TimeGenerated > ago(10m) and Name !has "/health" and Name !has "/ready"
      | summarize total = count(), failed = countif(toint(ResultCode) >= 500)
      | where total >= 50
      | extend rate = 100.0 * failed / total
      | where rate > __ERR__
    ''', '__ERR__', string(errorRatePercent))
  }
  {
    key: 'p95-latency'
    title: 'API p95 latency above ${p95LatencyMs} ms'
    description: 'p95 of API request duration over 10 minutes, ignoring AI answers and report downloads (they are slow by design).'
    severity: 2
    window: 'PT10M'
    frequency: 'PT5M'
    query: replace('''
      AppRequests
      | where TimeGenerated > ago(10m) and (Name startswith "GET /v1" or Name startswith "POST /v1")
      | where Name !has "/ask" and Name !has "/storage/" and Name !has "/export"
      | summarize n = count(), p95 = percentile(DurationMs, 95)
      | where n >= 50 and p95 > __P95__
    ''', '__P95__', string(p95LatencyMs))
  }
  {
    key: 'queue-age'
    title: 'Job queue is backing up'
    description: 'The oldest ready job has waited more than ${queueAgeSeconds} s: workers are down, saturated, or stuck on a bad job.'
    severity: 2
    window: 'PT10M'
    frequency: 'PT5M'
    query: replace('''
      AppMetrics
      | where TimeGenerated > ago(10m) and Name == "ankana.jobs.oldest_queued_age"
      | summarize oldest = max(Max) by tostring(Properties.kind)
      | where oldest > __AGE__
    ''', '__AGE__', string(queueAgeSeconds))
  }
  {
    key: 'failed-jobs'
    title: 'Jobs are failing terminally'
    description: '${failedJobs} or more jobs ended in failed status within 24 hours. Check job.last_error (no payloads are logged).'
    severity: 2
    window: 'PT15M'
    frequency: 'PT15M'
    query: replace('''
      AppMetrics
      | where TimeGenerated > ago(15m) and Name == "ankana.jobs.failed_recent"
      | summarize failed = max(Max) by tostring(Properties.kind)
      | where failed >= __FAILED__
    ''', '__FAILED__', string(failedJobs))
  }
  {
    key: 'auth-brute-force'
    title: 'Sign-in failures spiking (possible brute force)'
    description: '${authFailures5m}+ failed or blocked sign-ins in 5 minutes, or any refresh-token reuse.'
    severity: 1
    window: 'PT5M'
    frequency: 'PT5M'
    query: replace('''
      AppMetrics
      | where TimeGenerated > ago(5m) and Name == "ankana.auth.events"
      | extend action = tostring(Properties.action)
      | summarize failures = sumif(Sum, action in ("signin.failed", "signin.blocked")),
                  reuse = sumif(Sum, action == "refresh.reuse_detected")
      | where failures >= __AUTH__ or reuse > 0
    ''', '__AUTH__', string(authFailures5m))
  }
  {
    key: 'notification-failures'
    title: 'Notification sends are failing'
    description: '${notificationFailures15m}+ reminder send failures in 15 minutes: provider outage or bad credentials.'
    severity: 3
    window: 'PT15M'
    frequency: 'PT5M'
    query: replace('''
      AppMetrics
      | where TimeGenerated > ago(15m) and Name == "ankana.notifications.failures"
      | summarize failures = sum(Sum)
      | where failures >= __NOTIF__
    ''', '__NOTIF__', string(notificationFailures15m))
  }
  {
    key: 'rate-limit-store'
    title: 'Rate limiter lost its shared store'
    description: 'The Postgres limiter fell back to per-process counters, so limits are per replica until the database recovers.'
    severity: 3
    window: 'PT10M'
    frequency: 'PT5M'
    query: '''
      AppMetrics
      | where TimeGenerated > ago(10m) and Name == "ankana.ratelimit.fallbacks"
      | summarize fallbacks = sum(Sum)
      | where fallbacks > 0
    '''
  }
]

resource alerts 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = [for r in rules: {
  name: 'alert-${name}-${r.key}'
  location: location
  tags: tags
  properties: {
    displayName: r.title
    description: r.description
    severity: r.severity
    enabled: true
    scopes: [workspaceId]
    evaluationFrequency: r.frequency
    windowSize: r.window
    criteria: {
      allOf: [
        {
          query: r.query
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          failingPeriods: { numberOfEvaluationPeriods: 1, minFailingPeriodsToAlert: 1 }
        }
      ]
    }
    autoMitigate: true
    actions: { actionGroups: actions }
  }
}]

output alertNames array = [for (r, i) in rules: alerts[i].name]
