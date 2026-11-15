param name string
param location string
param tags object

var addr = '10.40.0.0/16'

resource vnet 'Microsoft.Network/virtualNetworks@2024-01-01' = {
  name: 'vnet-${name}'
  location: location
  tags: tags
  properties: {
    addressSpace: { addressPrefixes: [addr] }
    subnets: [
      {
        name: 'snet-aca'
        properties: {
          addressPrefix: '10.40.0.0/23'
          delegations: [
            { name: 'aca', properties: { serviceName: 'Microsoft.App/environments' } }
          ]
        }
      }
      {
        name: 'snet-pg'
        properties: {
          addressPrefix: '10.40.2.0/28'
          delegations: [
            { name: 'pg', properties: { serviceName: 'Microsoft.DBforPostgreSQL/flexibleServers' } }
          ]
        }
      }
      {
        name: 'snet-pe'
        properties: { addressPrefix: '10.40.3.0/27' }
      }
    ]
  }
}

var zones = [
  'privatelink.postgres.database.azure.com'
  'privatelink.redis.cache.windows.net'
  'privatelink.blob.core.windows.net'
  'privatelink.vaultcore.azure.net'
]

resource dns 'Microsoft.Network/privateDnsZones@2024-06-01' = [for z in zones: {
  name: z
  location: 'global'
  tags: tags
}]

resource links 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = [for (z, i) in zones: {
  parent: dns[i]
  name: 'link-${name}'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: { id: vnet.id }
  }
}]

output vnetId string = vnet.id
output acaSubnetId string = '${vnet.id}/subnets/snet-aca'
output pgSubnetId string = '${vnet.id}/subnets/snet-pg'
output peSubnetId string = '${vnet.id}/subnets/snet-pe'
output pgZoneId string = dns[0].id
output redisZoneId string = dns[1].id
output blobZoneId string = dns[2].id
output kvZoneId string = dns[3].id
