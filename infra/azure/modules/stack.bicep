// Everything inside the environment resource group.
param environment string
param location string
param prefix string
param tags object
param sizing object
@secure()
param pgAdminPassword string
@secure()
param pgAppPassword string
param deployApps bool
param deployServices bool
param imageTag string
param gitSha string
param sourceUrl string
param webCustomDomain string
@description('Ops email for alert rules (infra/monitoring/alerts.bicep). Empty creates the rules without notifications.')
param alertEmail string = ''
param apiCustomDomain string
param appConfig object

var name = '${prefix}-${environment}-cin'
var nameShort = '${prefix}${environment == 'prod' ? 'p' : 's'}'

module monitoring 'monitoring.bicep' = {
  name: 'monitoring'
  params: {
    name: name
    location: location
    tags: tags
    retentionDays: sizing.logRetentionDays
  }
}

module network 'network.bicep' = {
  name: 'network'
  params: {
    name: name
    location: location
    tags: tags
  }
}

module security 'security.bicep' = {
  name: 'security'
  params: {
    name: name
    nameShort: nameShort
    location: location
    tags: tags
    acrSku: sizing.acrSku
    kvPurgeProtection: sizing.kvPurgeProtection
    peSubnetId: network.outputs.peSubnetId
    kvZoneId: network.outputs.kvZoneId
  }
}

module alerts '../../monitoring/alerts.bicep' = {
  name: 'alerts'
  params: {
    name: name
    location: location
    tags: tags
    workspaceId: monitoring.outputs.workspaceId
    alertEmail: alertEmail
  }
}

module data 'data.bicep' = {
  name: 'data'
  params: {
    name: name
    nameShort: nameShort
    location: location
    tags: tags
    sizing: sizing
    pgSubnetId: network.outputs.pgSubnetId
    pgZoneId: network.outputs.pgZoneId
    peSubnetId: network.outputs.peSubnetId
    redisZoneId: network.outputs.redisZoneId
    blobZoneId: network.outputs.blobZoneId
    kvName: security.outputs.kvName
    idApiPrincipal: security.outputs.idApiPrincipal
    idWorkerPrincipal: security.outputs.idWorkerPrincipal
    idMigratePrincipal: security.outputs.idMigratePrincipal
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    // The generated secrets exist once the bootstrap script has run (before deployApps=true).
    grantBootstrapped: deployApps
    pgAdminPassword: pgAdminPassword
    pgAppPassword: pgAppPassword
  }
}

module apps 'apps.bicep' = {
  name: 'apps'
  params: {
    name: name
    location: location
    tags: tags
    sizing: sizing
    acaSubnetId: network.outputs.acaSubnetId
    workspaceCustomerId: monitoring.outputs.workspaceCustomerId
    workspaceKey: monitoring.outputs.workspaceKey
    acrLoginServer: security.outputs.acrLoginServer
    kvUri: security.outputs.kvUri
    idApiId: security.outputs.idApiId
    idWorkerId: security.outputs.idWorkerId
    idWebId: security.outputs.idWebId
    idApiClientId: security.outputs.idApiClientId
    idWorkerClientId: security.outputs.idWorkerClientId
    idMigrateId: security.outputs.idMigrateId
    storageAccountName: data.outputs.storageAccountName
    deployApps: deployApps
    deployServices: deployServices
    imageTag: imageTag
    gitSha: gitSha
    sourceUrl: sourceUrl
    webCustomDomain: webCustomDomain
    apiCustomDomain: apiCustomDomain
    appConfig: appConfig
  }
}

output acrName string = security.outputs.acrName
output acrLoginServer string = security.outputs.acrLoginServer
output keyVaultName string = security.outputs.kvName
output migrateJobName string = apps.outputs.migrateJobName
output preflightJobName string = apps.outputs.preflightJobName
output apiUrl string = apps.outputs.apiUrl
output webUrl string = apps.outputs.webUrl
