param name string
param location string
param tags object
param retentionDays int

resource law 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${name}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: retentionDays
    features: { disableLocalAuth: false }
  }
}

resource appi 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${name}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: law.id
    // Request bodies are never sent; see services/api-py/src/app/observability.py.
    DisableIpMasking: false
  }
}

output workspaceId string = law.id
output workspaceCustomerId string = law.properties.customerId
output appInsightsConnectionString string = appi.properties.ConnectionString
@secure()
output workspaceKey string = law.listKeys().primarySharedKey
