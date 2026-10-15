const API_BASE = '/api/v1';
let accessToken = null;
let tenantId = '';
let latestCredential = '';

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
    document.getElementById('auth-status').textContent =
      `Authenticated as ${payload.data.subject} in tenant ${payload.data.tenant_id}.`;
    tenantId = payload.data.tenant_id;
    await refreshAll();
  } catch (error) {
    accessToken = null;
    document.getElementById('auth-status').textContent = 'Authentication failed.';
    showNotice(error.message);
  }
}

async function refreshAll() {
  if (!accessToken) {
    showNotice('Authenticate with the configured OIDC provider before loading tenant data.');
    return;
  }
  await Promise.all([
    loadApplications(),
    loadModels(),
    loadRoutes(),
    loadTraces(),
    loadMetrics(),
    loadAudit(),
  ]);
}

async function loadApplications() {
  const applications = await apiRequest('/applications');
  renderRows('applications-table', applications, app => [
    app.name, app.environment, app.allowed_models.join(', ') || 'No models',
    app.lifecycle_state, app.virtual_key_prefix || 'None',
  ]);
  document.getElementById('overview-apps').textContent = String(applications.length);
}

async function loadModels() {
  const models = await apiRequest('/models');
  renderRows('models-table', models, model => [
    model.name, model.provider, model.model_name, model.secret_ref,
    model.is_active ? 'approved' : 'inactive',
  ]);
  const selector = document.getElementById('route-model');
  selector.replaceChildren(...models.filter(model => model.is_active).map(model => {
    const option = document.createElement('option');
    option.value = model.id;
    option.textContent = `${model.name} (${model.provider})`;
    return option;
  }));
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
    document.getElementById('credential-value').textContent = latestCredential
      || 'No credential issued; production approval is not available in this MVP.';
    document.getElementById('credential-state').textContent =
      `Credential catalog state: ${payload.data.credential_state}; gateway observation: ${payload.data.gateway_observation}.`;
    document.getElementById('credential-result').hidden = false;
    event.target.reset();
    await loadApplications();
    showNotice(latestCredential
      ? 'Application registered. Copy the credential now; it will not be shown again.'
      : 'Production application saved as a draft. No credential was issued.');
  } catch (error) {
    showNotice(error.message);
  }
}

async function registerModel(event) {
  event.preventDefault();
  try {
    await apiRequest('/models', {
      method: 'POST',
      body: JSON.stringify({
        name: document.getElementById('model-name').value,
        provider: document.getElementById('model-provider').value,
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
  ['applications-table', 'models-table', 'routes-table', 'traces-table', 'audit-table']
    .forEach(id => renderRows(id, [], () => []));
}

function formatMetric(metric) {
  if (!metric?.available || !metric.series_found) return 'Unavailable';
  return metric.values.map(item => item.value).join(', ') || 'Unavailable';
}

function showNotice(message) {
  document.getElementById('notice').textContent = message;
}
