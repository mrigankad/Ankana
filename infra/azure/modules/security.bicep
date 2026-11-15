// Container registry, Key Vault and managed identities.
param name string
param nameShort string
param location string
param tags object
param acrSku string
param kvPurgeProtection bool
param peSubnetId string
param kvZoneId string

resource idApi 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${name}-api'
  location: location
  tags: tags
}
resource idWorker 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${name}-worker'
  location: location
  tags: tags
}
resource idWeb 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${name}-web'
  location: location
  tags: tags
}
// The migration job is the only identity allowed to read the owner connection string.
resource idMigrate 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${name}-migrate'
  location: location
  tags: tags
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'acr${nameShort}${uniqueString(resourceGroup().id)}'
  location: location
  tags: tags
  sku: { name: acrSku }
  properties: {
    adminUserEnabled: false
  }
}

var acrPull = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
resource pullApi 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, idApi.id, acrPull)
  properties: {
    principalId: idApi.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPull)
  }
}
resource pullWorker 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, idWorker.id, acrPull)
  properties: {
    principalId: idWorker.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPull)
  }
}
resource pullWeb 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, idWeb.id, acrPull)
  properties: {
    principalId: idWeb.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPull)
  }
}
resource pullMigrate 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, idMigrate.id, acrPull)
  properties: {
    principalId: idMigrate.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPull)
  }
}

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-${nameShort}-${uniqueString(resourceGroup().id)}'
  location: location
  tags: tags
  properties: {
    tenantId: tenant().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 30
    enablePurgeProtection: kvPurgeProtection ? true : null
    publicNetworkAccess: 'Disabled'
    networkAcls: { defaultAction: 'Deny', bypass: 'AzureServices' }
  }
}

module kvPe 'privateendpoint.bicep' = {
  name: 'pe-kv'
  params: {
    name: 'kv-${name}'
    location: location
    tags: tags
    subnetId: peSubnetId
    targetId: kv.id
    groupId: 'vault'
    zoneId: kvZoneId
  }
}

output acrName string = acr.name
output acrId string = acr.id
output acrLoginServer string = acr.properties.loginServer
output kvName string = kv.name
output kvUri string = kv.properties.vaultUri
output idApiId string = idApi.id
output idApiPrincipal string = idApi.properties.principalId
output idApiClientId string = idApi.properties.clientId
output idWorkerId string = idWorker.id
output idWorkerPrincipal string = idWorker.properties.principalId
output idWorkerClientId string = idWorker.properties.clientId
output idWebId string = idWeb.id
output idMigrateId string = idMigrate.id
output idMigratePrincipal string = idMigrate.properties.principalId
