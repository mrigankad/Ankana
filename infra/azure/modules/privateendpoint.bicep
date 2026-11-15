param name string
param location string
param tags object
param subnetId string
param targetId string
param groupId string
param zoneId string

resource pe 'Microsoft.Network/privateEndpoints@2024-01-01' = {
  name: 'pe-${name}'
  location: location
  tags: tags
  properties: {
    subnet: { id: subnetId }
    privateLinkServiceConnections: [
      { name: name, properties: { privateLinkServiceId: targetId, groupIds: [groupId] } }
    ]
  }
}

resource zg 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-01-01' = {
  parent: pe
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      { name: 'zone', properties: { privateDnsZoneId: zoneId } }
    ]
  }
}
