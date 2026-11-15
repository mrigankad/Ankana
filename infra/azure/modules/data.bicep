// Postgres Flexible Server (private), Azure Cache for Redis (private endpoint),
// Storage (private container), and the Key Vault secrets derived from them.
param name string
param nameShort string
param location string
param tags object
param sizing object
param pgSubnetId string
param pgZoneId string
param peSubnetId string
param redisZoneId string
param blobZoneId string
param kvName string
param idApiPrincipal string
param idWorkerPrincipal string
param idMigratePrincipal string
param appInsightsConnectionString string
@description('true once infra/azure/scripts/bootstrap-secrets.sh has created the generated secrets.')
param grantBootstrapped bool

@secure()
param pgAdminPassword string
@secure()
param pgAppPassword string

var pgAdminUser = 'ankana'
var pgName = 'psql-${name}'

resource pg 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: pgName
  location: location
  tags: tags
  sku: { name: sizing.pgSku, tier: sizing.pgTier }
  properties: {
    version: '16'
    administratorLogin: pgAdminUser
    administratorLoginPassword: pgAdminPassword
    storage: { storageSizeGB: sizing.pgStorageGb, autoGrow: 'Enabled' }
    backup: {
      backupRetentionDays: sizing.pgBackupDays
      geoRedundantBackup: 'Disabled' // keep data in India; enable only with a DPDP review
    }
    highAvailability: { mode: sizing.pgHa ? 'ZoneRedundant' : 'Disabled' }
    network: {
      delegatedSubnetResourceId: pgSubnetId
      privateDnsZoneArmResourceId: pgZoneId
      publicNetworkAccess: 'Disabled'
    }
    authConfig: { activeDirectoryAuth: 'Disabled', passwordAuth: 'Enabled' }
  }
}

resource pgDb 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: pg
  name: 'ankana'
  properties: { charset: 'UTF8', collation: 'en_US.utf8' }
}

resource pgSsl 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2024-08-01' = {
  parent: pg
  name: 'require_secure_transport'
  properties: { value: 'ON', source: 'user-override' }
  dependsOn: [pgDb]
}

resource redis 'Microsoft.Cache/redis@2024-03-01' = {
  name: 'redis-${name}'
  location: location
  tags: tags
  properties: {
    sku: { name: sizing.redisSku, family: sizing.redisFamily, capacity: sizing.redisCapacity }
    enableNonSslPort: false
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Disabled'
    redisConfiguration: { 'maxmemory-policy': 'allkeys-lru' }
  }
}

module redisPe 'privateendpoint.bicep' = {
  name: 'pe-redis'
  params: {
    name: 'redis-${name}'
    location: location
    tags: tags
    subnetId: peSubnetId
    targetId: redis.id
    groupId: 'redisCache'
    zoneId: redisZoneId
  }
}

resource st 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'st${nameShort}${uniqueString(resourceGroup().id)}'
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: { name: sizing.storageSku }
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false // managed identity only
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    // Report downloads are 15 minute read-only user-delegation SAS URLs opened by the
    // user's browser, so the blob endpoint must be reachable from the internet. There is
    // no anonymous access and no account key: only Entra-signed SAS tokens work. The apps
    // still reach it over the private endpoint.
    publicNetworkAccess: 'Enabled'
    networkAcls: { defaultAction: 'Allow', bypass: 'AzureServices' }
  }
}

resource blob 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: st
  name: 'default'
  properties: {
    deleteRetentionPolicy: { enabled: true, days: 14 }
    containerDeleteRetentionPolicy: { enabled: true, days: 14 }
  }
}

resource reports 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blob
  name: 'reports'
  properties: { publicAccess: 'None' }
}

module blobPe 'privateendpoint.bicep' = {
  name: 'pe-blob'
  params: {
    name: 'blob-${name}'
    location: location
    tags: tags
    subnetId: peSubnetId
    targetId: st.id
    groupId: 'blob'
    zoneId: blobZoneId
  }
}

var blobContributor = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
resource blobRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for p in [idApiPrincipal, idWorkerPrincipal]: {
  scope: st
  name: guid(st.id, p, blobContributor)
  properties: {
    principalId: p
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobContributor)
  }
}]

// ---- Key Vault secrets (connection strings built here so apps never see parts) ----
resource kv 'Microsoft.KeyVault/vaults@2023-07-01' existing = { name: kvName }

var pgHost = '${pgName}.postgres.database.azure.com'
resource sMigrate 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'db-migration-url'
  properties: { value: 'postgresql+psycopg://${pgAdminUser}:${uriComponent(pgAdminPassword)}@${pgHost}:5432/ankana?sslmode=require' }
}
resource sApp 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'db-app-url'
  properties: { value: 'postgresql+psycopg://ankana_app:${uriComponent(pgAppPassword)}@${pgHost}:5432/ankana?sslmode=require' }
}
resource sAppPw 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'db-app-password'
  properties: { value: pgAppPassword }
}
resource sRedis 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'redis-url'
  properties: { value: 'rediss://:${uriComponent(redis.listKeys().primaryKey)}@${redis.properties.hostName}:6380/0' }
}
resource sAppi 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'appinsights-connection-string'
  properties: { value: appInsightsConnectionString }
}
// Secrets NOT created here: infra/azure/scripts/bootstrap-secrets.sh generates or
// seeds them once (create-if-absent) so a redeploy never overwrites a signing or
// encryption key, or a value the founder entered. They are read by name below.
var bootstrapSecrets = [
  'auth-signing-key-pem'
  'ankana-secret-key'
  'ankana-master-key'
  'notify-link-secret'
  'anthropic-api-key'
  'acs-connection-string'
  'razorpay-key-id'
  'razorpay-key-secret'
  'razorpay-webhook-secret'
  'sentry-dsn'
]
// Least privilege: each identity reads only the secrets its process uses.
var apiSecrets = [
  'auth-signing-key-pem'
  'ankana-secret-key'
  'ankana-master-key'
  'notify-link-secret'
  'anthropic-api-key'
  'acs-connection-string'
  'razorpay-key-id'
  'razorpay-key-secret'
  'razorpay-webhook-secret'
  'sentry-dsn'
]
var workerSecrets = [
  'ankana-secret-key'
  'ankana-master-key'
  'notify-link-secret'
  'anthropic-api-key'
  'acs-connection-string'
  'sentry-dsn'
]
var migrateSecrets = [
  'ankana-master-key' // data migrations (0004, 0006) encrypt existing rows in place
]
var managedSecrets = [
  'db-app-url'
  'redis-url'
  'appinsights-connection-string'
]

// Per-secret read access (Key Vault Secrets User): the app identities cannot read
// db-migration-url; only the migration identity can.
var kvSecretsUser = '4633458b-17de-408a-b874-0445c86b69e6'

resource managedRefs 'Microsoft.KeyVault/vaults/secrets@2023-07-01' existing = [for s in managedSecrets: {
  parent: kv
  name: s
}]
resource bootstrapRefs 'Microsoft.KeyVault/vaults/secrets@2023-07-01' existing = [for s in bootstrapSecrets: {
  parent: kv
  name: s
}]

resource apiManagedRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for (s, i) in managedSecrets: {
  name: guid(kv.id, idApiPrincipal, s, kvSecretsUser)
  scope: managedRefs[i]
  properties: {
    principalId: idApiPrincipal
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsUser)
  }
  dependsOn: [sApp, sRedis, sAppi]
}]
resource workerManagedRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for (s, i) in managedSecrets: {
  name: guid(kv.id, idWorkerPrincipal, s, kvSecretsUser)
  scope: managedRefs[i]
  properties: {
    principalId: idWorkerPrincipal
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsUser)
  }
  dependsOn: [sApp, sRedis, sAppi]
}]

// Only once the bootstrap script has created the secrets (deployApps=true runs after it).
resource apiBootstrapRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for (s, i) in bootstrapSecrets: if (grantBootstrapped && contains(apiSecrets, s)) {
  name: guid(kv.id, idApiPrincipal, s, kvSecretsUser)
  scope: bootstrapRefs[i]
  properties: {
    principalId: idApiPrincipal
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsUser)
  }
}]
resource migrateBootstrapRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for (s, i) in bootstrapSecrets: if (grantBootstrapped && contains(migrateSecrets, s)) {
  name: guid(kv.id, idMigratePrincipal, s, kvSecretsUser)
  scope: bootstrapRefs[i]
  properties: {
    principalId: idMigratePrincipal
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsUser)
  }
}]
resource workerBootstrapRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for (s, i) in bootstrapSecrets: if (grantBootstrapped && contains(workerSecrets, s)) {
  name: guid(kv.id, idWorkerPrincipal, s, kvSecretsUser)
  scope: bootstrapRefs[i]
  properties: {
    principalId: idWorkerPrincipal
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsUser)
  }
}]

resource migrateRole1 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(kv.id, idMigratePrincipal, 'db-migration-url', kvSecretsUser)
  scope: sMigrate
  properties: {
    principalId: idMigratePrincipal
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsUser)
  }
  dependsOn: [sMigrate]
}
resource migrateRole2 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(kv.id, idMigratePrincipal, 'db-app-password', kvSecretsUser)
  scope: sAppPw
  properties: {
    principalId: idMigratePrincipal
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsUser)
  }
  dependsOn: [sAppPw]
}

output pgHost string = pgHost
output storageAccountName string = st.name
output blobEndpoint string = st.properties.primaryEndpoints.blob
