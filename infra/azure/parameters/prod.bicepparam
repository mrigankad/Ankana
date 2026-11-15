using '../main.bicep'

param environment = 'prod'
param pgAdminPassword = readEnvironmentVariable('PG_ADMIN_PASSWORD', '')
param pgAppPassword = readEnvironmentVariable('PG_APP_PASSWORD', '')

// Production: zone-redundant HA Postgres, Standard Redis, always-on API replicas.
param sizing = {
  pgSku: 'Standard_D2ds_v5'
  pgTier: 'GeneralPurpose'
  pgStorageGb: 128
  pgHa: true
  pgBackupDays: 35
  redisSku: 'Standard'
  redisFamily: 'C'
  redisCapacity: 1
  storageSku: 'Standard_ZRS'
  acrSku: 'Standard'
  logRetentionDays: 90
  apiMinReplicas: 2
  apiMaxReplicas: 6
  apiCpu: '1.0'
  apiMemory: '2Gi'
  webMinReplicas: 1
  webMaxReplicas: 4
  workerEnabled: true
  workerMinReplicas: 1
  workerMaxReplicas: 4
  kvPurgeProtection: true
}

// Non-secret production config. Secrets live in Key Vault (docs/deploy.md section 4).
// mailFromAddress must be a sender verified in Azure Communication Services Email.
// Billing stays off (unlimited usage) until the Razorpay secrets and supplier fields exist.
param appConfig = {
  aiProvider: 'anthropic'
  mailFromName: 'Ankana'
  mailFromAddress: readEnvironmentVariable('MAIL_FROM_ADDRESS', '')
  signupEnabled: '1'
  billing: 'off'
  supplierName: ''
  supplierGstin: ''
  supplierStateCode: '29'
  supplierAddress: ''
  supplierEmail: ''
}
