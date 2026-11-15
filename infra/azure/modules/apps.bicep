// Container Apps environment (VNet integrated) with api, worker, web, the migration
// job and the preflight job.
param name string
param location string
param tags object
param sizing object
param acaSubnetId string
param workspaceCustomerId string
@secure()
param workspaceKey string
param acrLoginServer string
param kvUri string
param idApiId string
param idWorkerId string
param idWebId string
param idMigrateId string
param idApiClientId string
param idWorkerClientId string
param storageAccountName string
@description('true creates the migrate and preflight jobs (stage 2a).')
param deployApps bool
@description('true also rolls out api, worker and web (stage 2b, after preflight and migrations passed).')
param deployServices bool
param imageTag string
param gitSha string
param sourceUrl string
param webCustomDomain string
@description('Public https origin of the api when it has a custom domain; else the default Container Apps host is used.')
param apiCustomDomain string
@description('Non-secret production config, see parameters/*.bicepparam and docs/deploy.md.')
param appConfig object

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${name}'
  location: location
  tags: tags
  properties: {
    vnetConfiguration: {
      infrastructureSubnetId: acaSubnetId
      internal: false
    }
    zoneRedundant: false
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: workspaceCustomerId
        sharedKey: workspaceKey
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

var apiImage = '${acrLoginServer}/ankana-api:${imageTag}'
var webImage = '${acrLoginServer}/ankana-web:${imageTag}'
// Container Apps `command` REPLACES the image ENTRYPOINT, so every command below starts
// with the entrypoint script (blank Key Vault placeholders become unset, then preflight).
var entrypoint = '/usr/local/bin/api-entrypoint.sh'

// Public origins. The default Container Apps host name is deterministic, so the api
// knows its own issuer URL before the first revision exists. Default hosts are
// cross-site (azurecontainerapps.io is a public suffix): use custom domains under one
// registrable domain in production, or the refresh cookie is not sent (preflight warns).
var envDomain = env.properties.defaultDomain
var apiBase = !empty(apiCustomDomain) ? trim(apiCustomDomain) : 'https://ca-${name}-api.${envDomain}'
var webBase = !empty(webCustomDomain) ? trim(webCustomDomain) : 'https://ca-${name}-web.${envDomain}'
var blobUrl = 'https://${storageAccountName}.blob.${environment().suffixes.storage}'

var mailFromAddress = appConfig.?mailFromAddress ?? ''
var billingOn = (appConfig.?billing ?? 'off') == 'on'

// Secrets come from Key Vault, read with the app's own managed identity. The Key Vault
// name doubles as the Container Apps secret name. Which identity may read which secret
// is set in data.bicep (least privilege).
func kvSecrets(kvUri string, identityId string, names array) array =>
  map(names, n => { name: n, keyVaultUrl: '${kvUri}secrets/${n}', identity: identityId })

var workerSecretNames = [
  'db-app-url'
  'redis-url'
  'appinsights-connection-string'
  'sentry-dsn'
  'anthropic-api-key'
  'ankana-secret-key'
  'ankana-master-key'
  'notify-link-secret'
  'acs-connection-string'
]
var apiSecretNames = concat(workerSecretNames, [
  'auth-signing-key-pem'
  'razorpay-key-id'
  'razorpay-key-secret'
  'razorpay-webhook-secret'
])

// Env shared by api, worker and the preflight job.
var commonEnv = [
  { name: 'API_ENV', value: 'production' }
  { name: 'ANKANA_EPHEMERIS', value: 'swiss' }
  { name: 'ANKANA_SE_EPHE_PATH', value: '/opt/ephe' }
  { name: 'ANKANA_GIT_SHA', value: gitSha }
  { name: 'RELEASE_SHA', value: gitSha }
  { name: 'ANKANA_SOURCE_URL', value: sourceUrl }
  { name: 'ANKANA_LEGACY_API', value: '0' }
  { name: 'API_DATABASE_URL', secretRef: 'db-app-url' }
  { name: 'REDIS_URL', secretRef: 'redis-url' }
  { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'appinsights-connection-string' }
  { name: 'SENTRY_DSN', secretRef: 'sentry-dsn' }
  // AI: hosted Claude only. Local CLI providers would let tenants run binaries in the container.
  { name: 'ANKANA_AI_PROVIDER', value: appConfig.?aiProvider ?? 'anthropic' }
  { name: 'ANKANA_ALLOW_LOCAL_PROVIDERS', value: '0' }
  { name: 'ANTHROPIC_API_KEY', secretRef: 'anthropic-api-key' }
  // Encryption: stored AI provider keys, and the privacy envelope (per-practice data keys).
  { name: 'ANKANA_SECRET_KEY', secretRef: 'ankana-secret-key' }
  { name: 'ANKANA_MASTER_KEY', secretRef: 'ankana-master-key' }
  { name: 'ANKANA_MASTER_KEY_ID', value: 'env-1' }
  // Reminders: the worker sends them, the api builds the one-tap links.
  { name: 'NOTIFY_LINK_SECRET', secretRef: 'notify-link-secret' }
  { name: 'NOTIFY_PUBLIC_BASE_URL', value: apiBase }
  { name: 'NOTIFY_EMAIL_BACKEND', value: 'acs' }
  { name: 'ACS_CONNECTION_STRING', secretRef: 'acs-connection-string' }
  { name: 'ACS_EMAIL_FROM', value: mailFromAddress }
  // 'off' until Meta WhatsApp or MSG91/Twilio are registered (docs/deploy.md step 11); console is refused in production.
  { name: 'NOTIFY_WHATSAPP_BACKEND', value: 'off' }
  { name: 'NOTIFY_SMS_BACKEND', value: 'off' }
  // Reports: private blob container, user-delegation SAS (the account has no key).
  { name: 'STORAGE_BACKEND', value: 'azure' }
  { name: 'AZURE_STORAGE_ACCOUNT_URL', value: blobUrl }
  { name: 'AZURE_STORAGE_CONTAINER', value: 'reports' }
  // Billing: off means unlimited usage and /v1/billing answers 404.
  { name: 'ANKANA_BILLING', value: appConfig.?billing ?? 'off' }
  { name: 'ANKANA_BILLING_PROVIDER', value: billingOn ? 'razorpay' : 'mock' }
  { name: 'ANKANA_SUPPLIER_NAME', value: appConfig.?supplierName ?? '' }
  { name: 'ANKANA_SUPPLIER_GSTIN', value: appConfig.?supplierGstin ?? '' }
  { name: 'ANKANA_SUPPLIER_STATE_CODE', value: appConfig.?supplierStateCode ?? '29' }
  { name: 'ANKANA_SUPPLIER_ADDRESS', value: appConfig.?supplierAddress ?? '' }
  { name: 'ANKANA_SUPPLIER_EMAIL', value: appConfig.?supplierEmail ?? '' }
]

var apiEnv = concat(commonEnv, [
  { name: 'ANKANA_ROLE', value: 'api' }
  { name: 'OTEL_SERVICE_NAME', value: 'ankana-api' }
  { name: 'AZURE_CLIENT_ID', value: idApiClientId }
  { name: 'AUTH_SIGNING_KEY_PEM', secretRef: 'auth-signing-key-pem' }
  { name: 'AUTH_BUILTIN_ISSUER', value: apiBase }
  { name: 'AUTH_WEB_BASE_URL', value: webBase }
  { name: 'AUTH_ALLOWED_ORIGINS', value: webBase }
  { name: 'AUTH_COOKIE_SECURE', value: '1' }
  { name: 'AUTH_TRUST_PROXY', value: '1' }
  { name: 'AUTH_SIGNUP_ENABLED', value: appConfig.?signupEnabled ?? '1' }
  { name: 'AUTH_MAILER', value: 'acs' }
  { name: 'AUTH_MAIL_FROM', value: '${appConfig.?mailFromName ?? 'Ankana'} <${mailFromAddress}>' }
  { name: 'ACS_EMAIL_CONNECTION_STRING', secretRef: 'acs-connection-string' }
  { name: 'AUTH_SMS', value: 'none' }
  { name: 'RAZORPAY_KEY_ID', secretRef: 'razorpay-key-id' }
  { name: 'RAZORPAY_KEY_SECRET', secretRef: 'razorpay-key-secret' }
  { name: 'RAZORPAY_WEBHOOK_SECRET', secretRef: 'razorpay-webhook-secret' }
])

var workerEnv = concat(commonEnv, [
  { name: 'ANKANA_ROLE', value: 'worker' }
  { name: 'OTEL_SERVICE_NAME', value: 'ankana-worker' }
  { name: 'AZURE_CLIENT_ID', value: idWorkerClientId }
  { name: 'NOTIFY_TICK_SECONDS', value: '300' }
  { name: 'WORKER_CONCURRENCY', value: '2' }
])

resource api 'Microsoft.App/containerApps@2024-03-01' = if (deployServices) {
  name: 'ca-${name}-api'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${idApiId}': {} }
  }
  properties: {
    managedEnvironmentId: env.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        { server: acrLoginServer, identity: idApiId }
      ]
      secrets: kvSecrets(kvUri, idApiId, apiSecretNames)
    }
    template: {
      containers: [
        {
          name: 'api'
          image: apiImage
          // The image entrypoint runs `python -m app.preflight --role api` (ANKANA_ROLE)
          // and exits with the full problem list, so a misconfigured revision never starts.
          resources: {
            cpu: json(sizing.apiCpu)
            memory: sizing.apiMemory
          }
          env: apiEnv
          probes: [
            { type: 'Startup', httpGet: { path: '/health/ready', port: 8000 }, periodSeconds: 5, failureThreshold: 30 }
            { type: 'Liveness', httpGet: { path: '/health', port: 8000 }, periodSeconds: 20 }
            // 503 while any required production env is missing or invalid (app.preflight).
            { type: 'Readiness', httpGet: { path: '/health/ready', port: 8000 }, periodSeconds: 10 }
          ]
        }
      ]
      scale: {
        minReplicas: sizing.apiMinReplicas
        maxReplicas: sizing.apiMaxReplicas
        rules: [
          { name: 'http', http: { metadata: { concurrentRequests: '30' } } }
        ]
      }
    }
  }
}

// Worker: same image, `python -m app.worker`. Runs PDF reports (Chromium), privacy
// export and erase jobs, reminder sends and the notification tick (NOTIFY_TICK_SECONDS).
// No ingress. Keep min replicas at 1 or more: it is the only queue consumer.
resource worker 'Microsoft.App/containerApps@2024-03-01' = if (deployServices && sizing.workerEnabled) {
  name: 'ca-${name}-worker'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${idWorkerId}': {} }
  }
  properties: {
    managedEnvironmentId: env.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      registries: [
        { server: acrLoginServer, identity: idWorkerId }
      ]
      secrets: kvSecrets(kvUri, idWorkerId, workerSecretNames)
    }
    template: {
      containers: [
        {
          name: 'worker'
          image: apiImage
          command: [entrypoint, 'python', '-m', 'app.worker']
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: workerEnv
        }
      ]
      scale: {
        minReplicas: sizing.workerMinReplicas
        maxReplicas: sizing.workerMaxReplicas
      }
    }
  }
}

resource web 'Microsoft.App/containerApps@2024-03-01' = if (deployServices) {
  name: 'ca-${name}-web'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${idWebId}': {} }
  }
  properties: {
    managedEnvironmentId: env.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 3000
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        { server: acrLoginServer, identity: idWebId }
      ]
    }
    template: {
      containers: [
        {
          name: 'web'
          image: webImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'NEXT_PUBLIC_GIT_SHA', value: gitSha }
            { name: 'ANKANA_SOURCE_URL', value: sourceUrl }
            { name: 'WEB_ORIGIN', value: webBase }
          ]
          probes: [
            { type: 'Liveness', httpGet: { path: '/', port: 3000 }, periodSeconds: 20 }
          ]
        }
      ]
      scale: {
        minReplicas: sizing.webMinReplicas
        maxReplicas: sizing.webMaxReplicas
        rules: [
          { name: 'http', http: { metadata: { concurrentRequests: '50' } } }
        ]
      }
    }
  }
}

// Manual-trigger job inside the VNet (Postgres is private, GitHub runners cannot
// reach it). Runs alembic as the OWNER role, then sets the ankana_app password.
// The apps themselves only ever hold the ankana_app connection string.
resource migrate 'Microsoft.App/jobs@2024-03-01' = if (deployApps) {
  name: 'caj-${name}-migrate'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${idMigrateId}': {} }
  }
  properties: {
    environmentId: env.id
    workloadProfileName: 'Consumption'
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 900
      replicaRetryLimit: 0
      manualTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
      }
      registries: [
        { server: acrLoginServer, identity: idMigrateId }
      ]
      secrets: [
        { name: 'db-migration-url', keyVaultUrl: '${kvUri}secrets/db-migration-url', identity: idMigrateId }
        { name: 'db-app-password', keyVaultUrl: '${kvUri}secrets/db-app-password', identity: idMigrateId }
        { name: 'ankana-master-key', keyVaultUrl: '${kvUri}secrets/ankana-master-key', identity: idMigrateId }
      ]
    }
    template: {
      containers: [
        {
          name: 'migrate'
          image: apiImage
          command: [entrypoint, 'sh', '-c', 'alembic upgrade head && python scripts/set_app_role_password.py']
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'ANKANA_ROLE', value: 'migrate' }
            { name: 'API_ENV', value: 'production' }
            // data migrations encrypt existing rows (0004, 0006): same master key as the api
            { name: 'ANKANA_MASTER_KEY', secretRef: 'ankana-master-key' }
            { name: 'ANKANA_MASTER_KEY_ID', value: 'env-1' }
            { name: 'API_MIGRATION_URL', secretRef: 'db-migration-url' }
            { name: 'APP_ROLE_PASSWORD', secretRef: 'db-app-password' }
          ]
        }
      ]
    }
  }
}

// Preflight: runs app.preflight for the api and worker roles with the exact env and
// secrets they will receive, and fails with the complete list of problems. deploy.yml
// runs it (stage 2a) BEFORE the api, worker and web revisions are created, so a missing
// secret stops the release before any traffic moves. It uses the api identity, whose
// secret access is a superset of the worker's.
resource preflight 'Microsoft.App/jobs@2024-03-01' = if (deployApps) {
  name: 'caj-${name}-preflight'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${idApiId}': {} }
  }
  properties: {
    environmentId: env.id
    workloadProfileName: 'Consumption'
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 300
      replicaRetryLimit: 0
      manualTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
      }
      registries: [
        { server: acrLoginServer, identity: idApiId }
      ]
      secrets: kvSecrets(kvUri, idApiId, apiSecretNames)
    }
    template: {
      containers: [
        {
          name: 'preflight'
          image: apiImage
          command: [
            entrypoint
            'sh'
            '-c'
            'rc=0; python -m app.preflight --role api || rc=1; python -m app.preflight --role worker || rc=1; exit $rc'
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: filter(apiEnv, e => e.name != 'ANKANA_ROLE')
        }
      ]
    }
  }
}

output environmentId string = env.id
output migrateJobName string = deployApps ? migrate!.name : ''
output preflightJobName string = deployApps ? preflight!.name : ''
output apiUrl string = deployServices ? 'https://${api!.properties.configuration.ingress.fqdn}' : ''
output webUrl string = deployServices ? 'https://${web!.properties.configuration.ingress.fqdn}' : ''
output apiBaseUrl string = apiBase
output webBaseUrl string = webBase
