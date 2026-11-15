// Ankana on Azure (Central India). Subscription-scope entry point.
//   az deployment sub create -l centralindia -f main.bicep -p parameters/staging.bicepparam \
//      -p pgAdminPassword=... pgAppPassword=...
// Creates one resource group per environment and deploys every module into it.
targetScope = 'subscription'

@allowed(['staging', 'prod'])
param environment string
param location string = 'centralindia'
@description('Short prefix for resource names, 3-8 lowercase letters/digits.')
@minLength(3)
@maxLength(8)
param prefix string = 'ankana'

@secure()
@description('Postgres owner (migration) password. Stored in Key Vault, never given to the app.')
param pgAdminPassword string
@secure()
@description('Password for the RLS-bound ankana_app role. Set by the migration job.')
param pgAppPassword string

@description('false on the first run: creates ACR, Key Vault, data tier. true (after scripts/bootstrap-secrets.sh) adds the migrate and preflight jobs and grants the apps their secrets.')
param deployApps bool = false
@description('false = stage 2a (jobs only, so preflight and migrations run first); true = also roll out api, worker and web.')
param deployServices bool = false
param imageTag string = 'latest'
param gitSha string = 'unknown'
param sourceUrl string = 'https://github.com/mrigankad/Ankana'
@description('Public origin(s) of the web app for CORS and auth redirects, once known.')
param webCustomDomain string = ''
@description('Ops email for the alert rules; empty creates the rules without an action group.')
param alertEmail string = ''
@description('Public https origin of the api (custom domain). Empty uses the default Container Apps host, which is cross-site to the web app.')
param apiCustomDomain string = ''

@description('Non-secret production config: aiProvider, billing (off|on), mailFromAddress (verified ACS sender), mailFromName, signupEnabled, supplierName/Gstin/StateCode/Address/Email. See parameters/*.bicepparam.')
param appConfig object = {}

@description('Sizing and HA knobs, see parameters/*.bicepparam.')
param sizing object

var rgName = 'rg-${prefix}-${environment}-cin'
var tags = {
  app: 'ankana'
  environment: environment
  license: 'AGPL-3.0-only'
}

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: rgName
  location: location
  tags: tags
}

module stack 'modules/stack.bicep' = {
  scope: rg
  name: 'stack-${environment}'
  params: {
    environment: environment
    location: location
    prefix: prefix
    tags: tags
    pgAdminPassword: pgAdminPassword
    pgAppPassword: pgAppPassword
    deployApps: deployApps
    deployServices: deployServices
    imageTag: imageTag
    gitSha: gitSha
    sourceUrl: sourceUrl
    webCustomDomain: webCustomDomain
    alertEmail: alertEmail
    apiCustomDomain: apiCustomDomain
    appConfig: appConfig
    sizing: sizing
  }
}

output resourceGroup string = rg.name
output acrName string = stack.outputs.acrName
output acrLoginServer string = stack.outputs.acrLoginServer
output migrateJobName string = stack.outputs.migrateJobName
output preflightJobName string = stack.outputs.preflightJobName
output apiUrl string = stack.outputs.apiUrl
output webUrl string = stack.outputs.webUrl
output keyVaultName string = stack.outputs.keyVaultName
