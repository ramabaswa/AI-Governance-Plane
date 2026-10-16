targetScope = 'resourceGroup'

@description('Name for the Azure Container Apps deployment.')
param deploymentName string = 'ai-governance-plane'
@description('Resource ID of an existing Container Apps managed environment connected to the private network.')
param managedEnvironmentId string
@description('Resource ID of the Key Vault containing the Plane database secret.')
param keyVaultId string
@description('Resource ID of the Azure Container Registry containing the API and worker images.')
param containerRegistryId string
@description('Versioned Key Vault secret URI for the Plane PostgreSQL URL.')
param databaseSecretUri string
@description('Name of the Key Vault secret containing the PostgreSQL URL.')
param databaseSecretName string
@description('OIDC provider configuration JSON accepted by OIDC_PROVIDERS_JSON. Do not put client secrets here.')
param oidcProvidersJson string
@description('Comma-separated allowed browser origins for cross-origin console/API access, if needed.')
param corsAllowedOrigins string = ''
@description('OTLP HTTP endpoint for Control API traces; required by production startup.')
param otelTracesEndpoint string
@description('OTLP HTTP endpoint for Control API metrics; required by production startup.')
param otelMetricsEndpoint string
@description('Optional Tempo query endpoint for trace browsing.')
param tempoQueryUrl string = ''
@description('Optional Prometheus query endpoint for metrics/FinOps reads.')
param prometheusQueryUrl string = ''
@description('OCI image for the Control API, built from deploy/local/Dockerfile.api.')
param controlApiImage string
@description('OCI image for the reconciliation worker, built from deploy/local/Dockerfile.api.')
param workerImage string
@description('ACA app ingress visibility. Internal limits callers to the same ACA environment. Use external with an internal ACA environment for APIM/VNet callers.')
@allowed([
  'internal'
  'external'
])
param controlApiIngress string = 'internal'
@description('Must match the location of the existing Container Apps managed environment.')
param location string
param apiMinReplicas int = 1
param apiMaxReplicas int = 3

var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var commonTags = {
  application: 'ai-governance-plane'
  managedBy: 'bicep'
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: last(split(keyVaultId, '/'))
  scope: resourceGroup(split(keyVaultId, '/')[2], split(keyVaultId, '/')[4])
}

resource databaseSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' existing = {
  parent: keyVault
  name: databaseSecretName
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: last(split(containerRegistryId, '/'))
  scope: resourceGroup(split(containerRegistryId, '/')[2], split(containerRegistryId, '/')[4])
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

resource controlDatabaseSecretRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(databaseSecret.id, controlIdentity.id, keyVaultSecretsUserRoleId)
  scope: databaseSecret
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalId: controlIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource workerDatabaseSecretRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(databaseSecret.id, workerIdentity.id, keyVaultSecretsUserRoleId)
  scope: databaseSecret
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalId: workerIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource controlAcrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, controlIdentity.id, acrPullRoleId)
  scope: containerRegistry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
    principalId: controlIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource workerAcrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, workerIdentity.id, acrPullRoleId)
  scope: containerRegistry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
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
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: controlIdentity.id
        }
      ]
      secrets: [
        {
          name: 'database-url'
          keyVaultUrl: databaseSecretUri
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
            { name: 'OIDC_PROVIDERS_JSON', value: oidcProvidersJson }
            { name: 'CORS_ALLOWED_ORIGINS', value: corsAllowedOrigins }
            { name: 'OTEL_EXPORTER_OTLP_TRACES_ENDPOINT', value: otelTracesEndpoint }
            { name: 'OTEL_EXPORTER_OTLP_METRICS_ENDPOINT', value: otelMetricsEndpoint }
            { name: 'TEMPO_QUERY_URL', value: tempoQueryUrl }
            { name: 'PROMETHEUS_QUERY_URL', value: prometheusQueryUrl }
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
  dependsOn: [controlDatabaseSecretRole, controlAcrPullRole]
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
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: workerIdentity.id
        }
      ]
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
        minReplicas: 1
        maxReplicas: 1
        rules: []
      }
    }
  }
  dependsOn: [workerDatabaseSecretRole, workerAcrPullRole]
}

output controlApiName string = api.name
output workerName string = worker.name
output controlApiIdentityClientId string = controlIdentity.properties.clientId
output workerIdentityClientId string = workerIdentity.properties.clientId
