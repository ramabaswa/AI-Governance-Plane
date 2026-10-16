const API_BASE = '/api/v1';
let accessToken = null;
let tenantId = '';
let latestCredential = '';
let currentSubject = '';
let currentRoles = [];
let platformCapabilities = null;

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.nav-link').forEach(button => {
    button.addEventListener('click', () => showSection(button.dataset.section));
  });
  document.getElementById('auth-form').addEventListener('submit', signIn);
  document.getElementById('refresh-button').addEventListener('click', refreshAll);
  document.getElementById('application-form').addEventListener('submit', registerApplication);
  document.getElementById('model-form').addEventListener('submit', registerModel);
  document.getElementById('route-form').addEventListener('submit', registerRoute);
  document.getElementById('copy-credential').addEventListener('click', copyCredential);
  document.getElementById('clear-credential').addEventListener('click', clearCredential);
  document.getElementById('onboarding-form').addEventListener('submit', submitOnboarding);
  document.getElementById('approval-form').addEventListener('submit', submitApproval);
  document.getElementById('activation-form').addEventListener('submit', activateProductionApplication);
  document.getElementById('mcp-form').addEventListener('submit', registerMcpServer);
  document.getElementById('mcp-policy-form').addEventListener('submit', saveMcpPolicy);
  document.getElementById('budget-form').addEventListener('submit', saveBudget);
  document.getElementById('refresh-drift').addEventListener('click', loadOperations);
  document.getElementById('revisions-form').addEventListener('submit', loadRevisions);
  document.getElementById('rollback-button').addEventListener('click', rollbackRevision);
  renderEmptyTables();
});

function showSection(section) {
  document.querySelectorAll('.nav-link').forEach(button => {
    button.classList.toggle('active', button.dataset.section === section);
  });
  document.querySelectorAll('.tab-pane').forEach(panel => {
    panel.classList.toggle('active', panel.id === `section-${section}`);
  });
}

function requestHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  if (tenantId) headers['X-Tenant-ID'] = tenantId;
  return headers;
}

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...requestHeaders(), ...(options.headers || {}) },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = payload.error?.message || `Request failed (${response.status})`;
    throw new Error(message);
  }
  return payload;
}

async function signIn(event) {
  event.preventDefault();
  const enteredToken = document.getElementById('access-token').value.trim();
  tenantId = document.getElementById('tenant-context').value.trim();
  accessToken = enteredToken;
  document.getElementById('access-token').value = '';
  try {
    const payload = await apiRequest('/auth/me');
    currentSubject = payload.data.subject;
    currentRoles = payload.data.roles || [];
    document.getElementById('auth-status').textContent =
      `Authenticated as ${currentSubject} in tenant ${payload.data.tenant_id}.`;
    tenantId = payload.data.tenant_id;
    await refreshAll();
  } catch (error) {
    accessToken = null;
    currentSubject = '';
    currentRoles = [];
    document.getElementById('auth-status').textContent = 'Authentication failed.';
    showNotice(error.message);
  }
}

async function refreshAll() {
  if (!accessToken) {
    showNotice('Authenticate with the configured OIDC provider before loading tenant data.');
    return;
  }
  try {
    await loadPlatformCapabilities();
  } catch (error) {
    platformCapabilities = null;
    showNotice(`Platform capabilities could not be loaded: ${error.message}`);
  }
  const loaders = [
    loadApplications,
    loadModels,
    loadRoutes,
    loadTraces,
    loadMetrics,
    loadAudit,
    loadOnboarding,
    loadApprovals,
    loadMcpServers,
    loadBudget,
    loadOperations,
  ];
  const results = await Promise.allSettled(loaders.map(load => load()));
  const failures = results
    .map((result, index) => result.status === 'rejected'
      ? `${loaders[index].name}: ${result.reason.message || 'Request failed'}`
      : null)
    .filter(Boolean);
  if (failures.length) showNotice(`Some sources could not be loaded: ${failures.join('; ')}`);
}

async function loadApplications() {
  const applications = await apiRequest('/applications');
  renderRows('applications-table', applications, app => [
    app.name, app.id, app.environment, app.allowed_models.join(', ') || 'No models',
    app.lifecycle_state, app.virtual_key_prefix || 'None',
  ]);
  document.getElementById('overview-apps').textContent = String(applications.length);
}

async function loadModels() {
  const models = await apiRequest('/models');
  const supportedProviders = new Set(
    platformCapabilities?.gateway?.supported_providers || [],
  );
  renderRows('models-table', models, model => [
    model.name, model.provider, model.model_name, model.secret_ref,
    model.is_active ? 'approved' : 'inactive',
    supportedProviders.has(model.provider) ? 'Supported by translator' : 'Catalog only; not routeable',
  ]);
  const selector = document.getElementById('route-model');
  const routeModels = models.filter(model =>
    model.is_active && supportedProviders.has(model.provider),
  );
  selector.replaceChildren(...routeModels.map(model => {
    const option = document.createElement('option');
    option.value = model.id;
    option.textContent = `${model.name} (${model.provider})`;
    return option;
  }));
  if (!routeModels.length) {
    selector.disabled = true;
    document.getElementById('route-form').querySelector('[type="submit"]').disabled = true;
  } else {
    selector.disabled = false;
    document.getElementById('route-form').querySelector('[type="submit"]').disabled = false;
  }
  const providerSelect = document.getElementById('model-provider');
  [...providerSelect.options].forEach(option => {
    if (option.value) option.disabled = !supportedProviders.has(option.value);
  });
  document.getElementById('model-capability-note').textContent =
    `Route-supported by agentgateway ${platformCapabilities?.gateway?.release || 'unavailable'}: ${
      [...supportedProviders].join(', ') || 'unavailable'
    }. Other registered providers cannot be routed by this translator.`;
}

async function loadPlatformCapabilities() {
  const capabilities = await apiRequest('/platform/capabilities');
  platformCapabilities = capabilities;
  const gateway = capabilities.gateway;
  document.getElementById('control-plane-boundary').textContent =
    `The Control API is a management plane, not an inference proxy. It submits supported Kubernetes resources for agentgateway ${gateway.release}; live runtime behavior is ${
      gateway.runtime_verified ? 'verified' : 'not verified'
    }.`;

  const ingress = document.getElementById('ingress-capabilities');
  ingress.replaceChildren();
  [
    ['APIM → agentgateway', capabilities.ingress.apim.status],
    ['Approved private workload → agentgateway', capabilities.ingress.direct_private.status],
  ].forEach(([label, status]) => {
    const card = document.createElement('div');
    card.className = 'capability-card';
    const title = document.createElement('strong');
    title.textContent = label;
    const state = document.createElement('span');
    state.className = 'capability-state';
    state.textContent = capabilityStatusLabel(status);
    const explanation = document.createElement('p');
    explanation.className = 'text-muted';
    explanation.textContent =
      'Target only; both paths must converge on the same agentgateway security baseline.';
    card.append(title, state, explanation);
    ingress.append(card);
  });

  const integrations = document.getElementById('integration-capabilities');
  integrations.replaceChildren();
  Object.entries(capabilities.integrations).forEach(([name, details]) => {
    const item = document.createElement('li');
    const label = document.createElement('strong');
    label.textContent = `${name.replaceAll('_', ' ')}: `;
    item.append(label, document.createTextNode(capabilityStatusLabel(details.status)));
    integrations.append(item);
  });
}

function capabilityStatusLabel(status) {
  return ({
    target_only: 'Target only',
    configured_but_unverified: 'Configured, not verified',
    not_published_to_gateway: 'Not published to gateway',
    implemented: 'Implemented',
  })[status] || status;
}

async function loadRoutes() {
  const routes = await apiRequest('/routes');
  renderRows('routes-table', routes, route => {
    const state = route.lifecycle_state || 'draft';
    return [
      route.name, route.path_prefix, route.backend_model_id, state,
      state === 'observed_active' ? 'Observed' : state === 'pending' ? 'Refresh status' : 'Apply',
    ];
  }, (row, route) => {
    const action = row.lastElementChild;
    if (route.lifecycle_state === 'pending') {
      const button = document.createElement('button');
      button.className = 'btn btn-sm btn-outline';
      button.textContent = 'Refresh status';
      button.addEventListener('click', () => refreshRouteStatus(route.id));
      action.replaceChildren(button);
    } else if (route.lifecycle_state !== 'observed_active') {
      const button = document.createElement('button');
      button.className = 'btn btn-sm btn-outline';
      button.textContent = 'Apply';
      button.addEventListener('click', () => applyRoute(route.id));
      action.replaceChildren(button);
    }
  });
  const active = routes.filter(route => route.lifecycle_state === 'observed_active').length;
  document.getElementById('overview-routes').textContent = String(active);
}

async function loadTraces() {
  const traces = await apiRequest('/observability/traces');
  renderRows('traces-table', traces, trace => [
    trace.trace_id, trace.root_service_name || '—', trace.root_trace_name || '—',
    trace.duration_ms ?? 'Unavailable',
  ]);
}

async function loadMetrics() {
  const payload = await apiRequest('/dashboard/metrics');
  const metrics = payload.data.metrics;
  const requests = metrics.control_api_requests;
  document.getElementById('overview-api-requests').textContent =
    requests?.available && requests.series_found
      ? requests.values.map(item => item.value).join(', ')
      : 'Unavailable';
  const input = metrics.input_tokens;
  const output = metrics.output_tokens;
  document.getElementById('overview-tokens').textContent =
    input?.available && output?.available
      ? `${formatMetric(input)} input / ${formatMetric(output)} output`
      : 'Unavailable';
  document.getElementById('metrics-output').textContent = JSON.stringify(metrics, null, 2);
}

async function loadAudit() {
  const events = await apiRequest('/audit/events?limit=100');
  renderRows('audit-table', events, event => [
    new Date(event.timestamp * 1000).toISOString(),
    event.actor,
    event.action,
    `${event.resource_type}/${event.resource_id}`,
    event.event_hash,
  ]);
}

async function registerApplication(event) {
  event.preventDefault();
  const allowedModels = document.getElementById('application-models').value
    .split(',').map(value => value.trim()).filter(Boolean);
  try {
    const payload = await apiRequest('/applications', {
      method: 'POST',
      body: JSON.stringify({
        name: document.getElementById('application-name').value,
        environment: document.getElementById('application-environment').value,
        allowed_models: allowedModels,
      }),
    });
    latestCredential = payload.data.virtual_key || '';
    showCredential(
      latestCredential,
      `Credential catalog state: ${payload.data.credential_state}; gateway observation: ${payload.data.gateway_observation}.`,
    );
    event.target.reset();
    await loadApplications();
    showNotice(latestCredential
      ? 'Application registered. Copy the credential now; it will not be shown again.'
      : 'Production application saved as a draft. Request approval before activation.');
  } catch (error) {
    showNotice(error.message);
  }
}

async function registerModel(event) {
  event.preventDefault();
  const provider = document.getElementById('model-provider').value;
  if (!platformCapabilities?.gateway?.supported_providers?.includes(provider)) {
    showNotice('The selected provider is not supported by the current agentgateway translator.');
    return;
  }
  try {
    await apiRequest('/models', {
      method: 'POST',
      body: JSON.stringify({
        name: document.getElementById('model-name').value,
        provider,
        model_name: document.getElementById('provider-model').value,
        secret_ref: document.getElementById('provider-secret-ref').value,
      }),
    });
    event.target.reset();
    await loadModels();
    showNotice('Model registered.');
  } catch (error) {
    showNotice(error.message);
  }
}

async function registerRoute(event) {
  event.preventDefault();
  const pattern = document.getElementById('guard-pattern').value.trim();
  const dlpRules = pattern ? [{
    name: 'request-regex-guard',
    regex_patterns: [pattern],
    action: 'Mask',
  }] : [];
  try {
    const payload = await apiRequest('/routes/validate', {
      method: 'POST',
      body: JSON.stringify({
        name: document.getElementById('route-name').value,
        path_prefix: document.getElementById('route-path').value,
        backend_model_id: document.getElementById('route-model').value,
        dlp_rules: dlpRules,
      }),
    });
    if (payload.status !== 'validated') throw new Error('Route validation did not return validated status.');
    await apiRequest('/routes', {
      method: 'POST',
      body: JSON.stringify({
        name: document.getElementById('route-name').value,
        path_prefix: document.getElementById('route-path').value,
        backend_model_id: document.getElementById('route-model').value,
        dlp_rules: dlpRules,
      }),
    });
    event.target.reset();
    await loadRoutes();
    showNotice('Route saved as draft. Apply it to submit Kubernetes resources; controller observation is separate.');
  } catch (error) {
    showNotice(error.message);
  }
}

async function applyRoute(routeId) {
  try {
    const payload = await apiRequest(`/routes/${encodeURIComponent(routeId)}/apply`, { method: 'POST' });
    showNotice(`Route state: ${payload.data.state}. Controller observation is shown separately.`);
    await loadRoutes();
  } catch (error) {
    showNotice(error.message);
  }
}

async function refreshRouteStatus(routeId) {
  try {
    const payload = await apiRequest(`/routes/${encodeURIComponent(routeId)}/status`);
    showNotice(`Route state: ${payload.state}.`);
    await loadRoutes();
  } catch (error) {
    showNotice(error.message);
  }
}

async function copyCredential() {
  if (!latestCredential) return;
  try {
    await navigator.clipboard.writeText(latestCredential);
    showNotice('Credential copied.');
  } catch (error) {
    showNotice('Clipboard access failed. Select and copy the displayed credential manually.');
  }
}

function clearCredential() {
  latestCredential = '';
  document.getElementById('credential-value').textContent = '';
  document.getElementById('credential-result').hidden = true;
}

function showCredential(key, state) {
  latestCredential = key || '';
  document.getElementById('credential-value').textContent =
    latestCredential || 'No credential was issued.';
  document.getElementById('credential-state').textContent = state;
  document.getElementById('credential-result').hidden = false;
}

async function submitOnboarding(event) {
  event.preventDefault();
  try {
    await apiRequest('/onboarding/requests', {
      method: 'POST',
      body: JSON.stringify({
        application_name: document.getElementById('onboarding-name').value,
        environment: document.getElementById('onboarding-environment').value,
        requested_models: splitList(document.getElementById('onboarding-models').value),
        monthly_token_quota: Number(document.getElementById('onboarding-quota').value),
      }),
    });
    event.target.reset();
    await loadOnboarding();
    showNotice('Onboarding request submitted for review.');
  } catch (error) {
    showNotice(error.message);
  }
}

async function loadOnboarding() {
  const requests = await apiRequest('/onboarding/requests');
  renderRows('onboarding-table', requests, request => [
    request.application_name,
    request.environment,
    request.requested_by,
    request.status,
    request.application_id || '—',
    '',
  ], (row, request) => {
    const action = row.lastElementChild;
    if (request.status === 'pending' && request.requested_by !== currentSubject && canReview()) {
      action.append(
        makeButton('Approve', () => reviewOnboarding(request.id, 'approved')),
        makeButton('Deny', () => reviewOnboarding(request.id, 'denied')),
      );
    } else if (request.status === 'approved' && request.requested_by === currentSubject) {
      action.append(makeButton('Complete', () => completeOnboarding(request.id)));
    }
  });
}

async function reviewOnboarding(requestId, decision) {
  try {
    await apiRequest(`/onboarding/requests/${encodeURIComponent(requestId)}/review`, {
      method: 'POST',
      body: JSON.stringify({ decision }),
    });
    await loadOnboarding();
    showNotice(`Onboarding request ${decision}.`);
  } catch (error) {
    showNotice(error.message);
  }
}

async function completeOnboarding(requestId) {
  try {
    const payload = await apiRequest(`/onboarding/requests/${encodeURIComponent(requestId)}/complete`, {
      method: 'POST',
    });
    showCredential(
      payload.data.virtual_key,
      `Credential state: ${payload.data.credential_state}. Application ID: ${payload.data.request.application_id}.`,
    );
    await loadOnboarding();
    showNotice(payload.data.virtual_key
      ? 'Onboarding completed. Copy the credential now; it cannot be shown again.'
      : 'Production onboarding completed. Request a separate activation approval.');
  } catch (error) {
    showNotice(error.message);
  }
}

async function submitApproval(event) {
  event.preventDefault();
  try {
    await apiRequest('/approvals', {
      method: 'POST',
      body: JSON.stringify({
        policy_type: document.getElementById('approval-type').value,
        target_resource_id: document.getElementById('approval-resource').value,
        target_environment: 'production',
        change_summary: document.getElementById('approval-summary').value,
        proposed_diff: document.getElementById('approval-diff').value,
      }),
    });
    event.target.reset();
    await loadApprovals();
    showNotice('Approval request submitted.');
  } catch (error) {
    showNotice(error.message);
  }
}

async function loadApprovals() {
  const approvals = await apiRequest('/approvals');
  renderRows('approvals-table', approvals, approval => [
    `${approval.policy_type} / ${approval.target_resource_id}`,
    approval.requested_by,
    approval.status,
    approval.decision_comments || '—',
    '',
  ], (row, approval) => {
    if (approval.status !== 'pending' || approval.requested_by === currentSubject || !canReview()) return;
    const action = row.lastElementChild;
    action.append(
      makeButton('Approve', () => decideApproval(approval.id, 'approved')),
      makeButton('Deny', () => decideApproval(approval.id, 'denied')),
    );
  });
}

async function decideApproval(requestId, decision) {
  try {
    await apiRequest(`/approvals/${encodeURIComponent(requestId)}/decide`, {
      method: 'POST',
      body: JSON.stringify({ decision }),
    });
    await loadApprovals();
    showNotice(`Approval request ${decision}.`);
  } catch (error) {
    showNotice(error.message);
  }
}

async function activateProductionApplication(event) {
  event.preventDefault();
  const applicationId = document.getElementById('activation-app').value.trim();
  try {
    const payload = await apiRequest(`/applications/${encodeURIComponent(applicationId)}/lifecycle`, {
      method: 'POST',
      body: JSON.stringify({
        target_state: 'active',
        approval_request_id: document.getElementById('activation-approval').value.trim(),
      }),
    });
    showCredential(
      payload.data.virtual_key,
      `Gateway observation: ${payload.data.gateway_observation}. Application: ${payload.data.application.id}.`,
    );
    await loadApplications();
    await loadApprovals();
    showNotice(payload.data.virtual_key
      ? 'Production application activated. Copy the credential now; it will not be shown again.'
      : 'Application lifecycle updated without issuing a new credential.');
  } catch (error) {
    showNotice(error.message);
  }
}

async function registerMcpServer(event) {
  event.preventDefault();
  try {
    await apiRequest('/mcp/servers', {
      method: 'POST',
      body: JSON.stringify({
        name: document.getElementById('mcp-name').value,
        transport_url: document.getElementById('mcp-url').value,
      }),
    });
    event.target.reset();
    await loadMcpServers();
    showNotice('MCP server registered. Discovery is a separate outbound request.');
  } catch (error) {
    showNotice(error.message);
  }
}

async function loadMcpServers() {
  const servers = await apiRequest('/mcp/servers');
  renderRows('mcp-table', servers, server => [
    server.name,
    server.transport_url,
    server.discovery_state,
    server.discovered_tools.map(tool => tool.name).join(', ') || 'Not discovered',
    server.policy_enforcement_state,
    '',
  ], (row, server) => {
    row.lastElementChild.append(
      makeButton('Discover tools', () => discoverMcpServer(server.id)),
      makeButton('Use server ID', () => {
        document.getElementById('mcp-policy-server').value = server.id;
      }),
    );
  });
}

async function discoverMcpServer(serverId) {
  try {
    const server = await apiRequest(`/mcp/servers/${encodeURIComponent(serverId)}/discover`, {
      method: 'POST',
    });
    await loadMcpServers();
    showNotice(`Discovery ${server.discovery_state}. ${server.discovered_tools.length} tool(s) returned; gateway policy enforcement is not available.`);
  } catch (error) {
    showNotice(error.message);
  }
}

async function saveMcpPolicy(event) {
  event.preventDefault();
  const serverId = document.getElementById('mcp-policy-server').value.trim();
  try {
    const server = await apiRequest(`/mcp/servers/${encodeURIComponent(serverId)}/policy`, {
      method: 'PUT',
      body: JSON.stringify({
        policy: {
          tool_name: document.getElementById('mcp-policy-tool').value.trim(),
          cel_rule: document.getElementById('mcp-policy-cel').value.trim(),
          allowed_roles: splitList(document.getElementById('mcp-policy-roles').value),
          is_enabled: true,
        },
      }),
    });
    await loadMcpServers();
    showNotice(`Policy intent saved. Enforcement state: ${server.policy_enforcement_state}.`);
  } catch (error) {
    showNotice(error.message);
  }
}

async function loadBudget() {
  const budget = await apiRequest('/finops/budgets');
  document.getElementById('budget-monthly').value =
    budget.configured ? budget.monthly_budget_usd : '';
  document.getElementById('budget-threshold').value = budget.alert_threshold_pct;
  document.getElementById('budget-status').textContent = JSON.stringify({
    configured: budget.configured,
    monthly_budget_usd: budget.configured ? budget.monthly_budget_usd : 'Not configured',
    alert_threshold_pct: budget.alert_threshold_pct,
    observed_spend_usd: budget.current_spend_usd ?? 'Unknown',
    spend_source: budget.spend_source,
    hard_cap_enforcement: budget.hard_cap_enforcement,
  }, null, 2);
}

async function saveBudget(event) {
  event.preventDefault();
  try {
    await apiRequest('/finops/budgets', {
      method: 'PUT',
      body: JSON.stringify({
        monthly_budget_usd: Number(document.getElementById('budget-monthly').value),
        alert_threshold_pct: Number(document.getElementById('budget-threshold').value),
        hard_cap_enabled: false,
      }),
    });
    await loadBudget();
    showNotice('Advisory budget saved; no runtime hard cap is enforced.');
  } catch (error) {
    showNotice(error.message);
  }
}

async function loadOperations() {
  const observations = await apiRequest('/operations/drift');
  document.getElementById('operations-output').textContent = JSON.stringify(observations, null, 2);
}

async function loadRevisions(event) {
  if (event) event.preventDefault();
  const routeId = document.getElementById('revision-route').value.trim();
  if (!routeId) return;
  try {
    const revisions = await apiRequest(`/policies/routes/${encodeURIComponent(routeId)}/revisions`);
    const selector = document.getElementById('revision-source');
    selector.replaceChildren(...revisions.map(revision => {
      const option = document.createElement('option');
      option.value = revision.revision;
      option.textContent = `Revision ${revision.revision} (${revision.state}, ${revision.checksum.slice(0, 12)})`;
      return option;
    }));
    document.getElementById('revisions-output').textContent = JSON.stringify(revisions, null, 2);
    showNotice(`${revisions.length} route revision(s) loaded.`);
  } catch (error) {
    showNotice(error.message);
  }
}

async function rollbackRevision() {
  const routeId = document.getElementById('revision-route').value.trim();
  const sourceRevision = Number(document.getElementById('revision-source').value);
  if (!routeId || !sourceRevision) {
    showNotice('Load revisions and select a source revision before submitting rollback.');
    return;
  }
  try {
    const payload = await apiRequest(`/policies/routes/${encodeURIComponent(routeId)}/rollback`, {
      method: 'POST',
      body: JSON.stringify({ source_revision: sourceRevision }),
    });
    await loadRevisions();
    await loadRoutes();
    showNotice(`Rollback submitted. Route state: ${payload.data.state}; controller observation remains separate.`);
  } catch (error) {
    showNotice(error.message);
  }
}

function splitList(value) {
  return value.split(',').map(item => item.trim()).filter(Boolean);
}

function canReview() {
  return currentRoles.some(role => role === 'platform_admin' || role === 'tenant_admin');
}

function makeButton(label, action) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'btn btn-sm btn-outline';
  button.textContent = label;
  button.addEventListener('click', action);
  return button;
}

function renderRows(tableId, records, valuesForRecord, decorateRow) {
  const body = document.getElementById(tableId);
  body.replaceChildren();
  if (!records.length) {
    const row = body.insertRow();
    const cell = row.insertCell();
    cell.colSpan = body.closest('table').querySelectorAll('thead th').length;
    cell.textContent = 'No records returned by the connected source.';
    return;
  }
  records.forEach(record => {
    const row = body.insertRow();
    valuesForRecord(record).forEach(value => {
      const cell = row.insertCell();
      cell.textContent = String(value ?? 'Unavailable');
    });
    if (decorateRow) decorateRow(row, record);
  });
}

function renderEmptyTables() {
  ['applications-table', 'models-table', 'routes-table', 'traces-table', 'audit-table',
    'onboarding-table', 'approvals-table', 'mcp-table']
    .forEach(id => renderRows(id, [], () => []));
}

function formatMetric(metric) {
  if (!metric?.available || !metric.series_found) return 'Unavailable';
  return metric.values.map(item => item.value).join(', ') || 'Unavailable';
}

function showNotice(message) {
  document.getElementById('notice').textContent = message;
}
