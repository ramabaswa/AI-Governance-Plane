targetScope = 'resourceGroup'

@description('Name for the Azure Container Apps deployment.')
param deploymentName string = 'ai-governance-plane'
@description('Resource ID of an existing Container Apps managed environment connected to the private network.')
param managedEnvironmentId string
@description('Resource ID of the Key Vault containing the Plane secrets.')
param keyVaultId string
@description('Versioned Key Vault secret URI for the Plane PostgreSQL URL.')
param databaseSecretUri string
@description('Versioned Key Vault secret URI for the Control API JWT signing secret.')
param jwtSecretUri string
@description('OIDC provider configuration JSON accepted by OIDC_PROVIDERS_JSON. Do not put client secrets here.')
param oidcProvidersJson string
@description('Comma-separated allowed browser origins for cross-origin console/API access, if needed.')
param corsAllowedOrigins string = ''
@description('OCI image for the Control API, built from deploy/local/Dockerfile.api.')
param controlApiImage string
@description('OCI image for the reconciliation worker, built from deploy/local/Dockerfile.api.')
param workerImage string
@description('Optional ingress mode for the Control API. Keep internal for APIM and private callers.')
@allowed([
  'internal'
  'external'
])
param controlApiIngress string = 'internal'
param location string = resourceGroup().location
param apiMinReplicas int = 1
param apiMaxReplicas int = 3
param workerReplicas int = 1

var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'
var commonTags = {
  application: 'ai-governance-plane'
  managedBy: 'bicep'
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: last(split(keyVaultId, '/'))
  scope: resourceGroup(split(keyVaultId, '/')[2], split(keyVaultId, '/')[4])
}

resource controlIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${deploymentName}-api-identity'
  location: location
  tags: commonTags
}

resource workerIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${deploymentName}-worker-identity'
  location: location
  tags: commonTags
}

resource controlVaultRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, controlIdentity.id, keyVaultSecretsUserRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalId: controlIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource workerVaultRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, workerIdentity.id, keyVaultSecretsUserRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalId: workerIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource api 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${deploymentName}-api'
  location: location
  tags: commonTags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${controlIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: managedEnvironmentId
    configuration: {
      activeRevisionsMode: 'Single'
      secrets: [
        {
          name: 'database-url'
          keyVaultUrl: databaseSecretUri
          identity: controlIdentity.id
        }
        {
          name: 'jwt-secret'
          keyVaultUrl: jwtSecretUri
          identity: controlIdentity.id
        }
      ]
      ingress: {
        external: controlApiIngress == 'external'
        targetPort: 8000
        transport: 'http'
        allowInsecure: false
      }
    }
    template: {
      containers: [
        {
          name: 'control-api'
          image: controlApiImage
          resources: {
            cpu: 0.5
            memory: '1Gi'
          }
          env: [
            { name: 'ENVIRONMENT', value: 'production' }
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'JWT_SECRET', secretRef: 'jwt-secret' }
            { name: 'OIDC_PROVIDERS_JSON', value: oidcProvidersJson }
            { name: 'CORS_ALLOWED_ORIGINS', value: corsAllowedOrigins }
            { name: 'RECONCILE_INTERVAL', value: '15' }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/healthz', port: 8000, scheme: 'HTTP' }
              periodSeconds: 30
              initialDelaySeconds: 10
              timeoutSeconds: 5
            }
            {
              type: 'Readiness'
              httpGet: { path: '/readyz', port: 8000, scheme: 'HTTP' }
              periodSeconds: 10
              initialDelaySeconds: 5
              timeoutSeconds: 5
            }
          ]
        }
      ]
      scale: {
        minReplicas: apiMinReplicas
        maxReplicas: apiMaxReplicas
        rules: []
      }
    }
  }
  dependsOn: [controlVaultRole]
}

resource worker 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${deploymentName}-worker'
  location: location
  tags: commonTags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${workerIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: managedEnvironmentId
    configuration: {
      activeRevisionsMode: 'Single'
      secrets: [
        {
          name: 'database-url'
          keyVaultUrl: databaseSecretUri
          identity: workerIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'reconciliation-worker'
          image: workerImage
          command: ['python']
          args: ['-m', 'apps.worker.reconciliation_worker']
          resources: {
            cpu: 0.5
            memory: '1Gi'
          }
          env: [
            { name: 'ENVIRONMENT', value: 'production' }
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'RECONCILE_INTERVAL', value: '15' }
          ]
        }
      ]
      scale: {
        minReplicas: workerReplicas
        maxReplicas: workerReplicas
        rules: []
      }
    }
  }
  dependsOn: [workerVaultRole]
}

output controlApiName string = api.name
output workerName string = worker.name
output controlApiIdentityClientId string = controlIdentity.properties.clientId
output workerIdentityClientId string = workerIdentity.properties.clientId
