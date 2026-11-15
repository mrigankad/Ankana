using '../main.bicep'

param environment = 'staging'
param pgAdminPassword = readEnvironmentVariable('PG_ADMIN_PASSWORD', '')
param pgAppPassword = readEnvironmentVariable('PG_APP_PASSWORD', '')

// Cheapest sensible footprint: burstable Postgres, Basic Redis, scale-to-zero apps.
param sizing = {
  pgSku: 'Standard_B1ms'
  pgTier: 'Burstable'
  pgStorageGb: 32
  pgHa: false
  pgBackupDays: 7
  redisSku: 'Basic'
  redisFamily: 'C'
  redisCapacity: 0
  storageSku: 'Standard_LRS'
  acrSku: 'Basic'
  logRetentionDays: 30
  apiMinReplicas: 0
  apiMaxReplicas: 2
  apiCpu: '0.5'
  apiMemory: '1Gi'
  webMinReplicas: 0
  webMaxReplicas: 2
  workerEnabled: true
  workerMinReplicas: 1
  workerMaxReplicas: 2
  kvPurgeProtection: false
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
