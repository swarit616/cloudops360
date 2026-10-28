export const PROJECTS = [
  {
    id: 'cloudops360',
    name: 'CloudOps360',
    kicker: 'Infrastructure monitoring & diagnostics',
    summary:
      'A Linux infrastructure monitoring platform. A FastAPI service and Node Exporter feed Prometheus, Grafana visualises the result, and guarded remediation controls keep operational actions safe.',
    points: [
      'Linux infrastructure monitoring',
      'FastAPI service with diagnostics endpoints',
      'Prometheus metrics and alert rules',
      'Grafana dashboard with Node Exporter host metrics',
      'Safe, guarded remediation controls',
      'Optional AWS / Azure integrations',
    ],
    tags: ['FastAPI', 'Prometheus', 'Grafana', 'Node Exporter'],
  },
  {
    id: 'cloudrescue',
    name: 'CloudRescue',
    kicker: 'Incident response & tracking',
    summary:
      'An incident tracker that receives authenticated Alertmanager webhooks, records the incident lifecycle, and also ships a separate demo simulation for exploring the workflow safely.',
    points: [
      'Incident tracking and lifecycle',
      'Alertmanager webhook integration',
      'Resolved notifications update incident status',
      'Separate demo simulation mode',
      'Already deployed on Render',
    ],
    tags: ['Incident tracking', 'Webhooks', 'Render'],
  },
]

export const ARCHITECTURE_LANES = [
  {
    id: 'metrics',
    label: 'Metrics path',
    nodes: [
      { title: 'CloudOps360', detail: 'FastAPI + Node Exporter' },
      { title: 'Prometheus', detail: 'Scrapes and stores metrics' },
      { title: 'Grafana', detail: 'Dashboards and visualisation' },
    ],
  },
  {
    id: 'alerts',
    label: 'Alert path',
    nodes: [
      { title: 'Prometheus', detail: 'Evaluates alert rules' },
      { title: 'Alertmanager', detail: 'Groups and routes alerts' },
      { title: 'Authenticated webhook', detail: 'Secret-protected delivery', accent: true },
      { title: 'CloudRescue', detail: 'Incident tracking' },
    ],
  },
]

export const DASHBOARD_PANELS = [
  'CPU and memory',
  'Disk and swap',
  'Network traffic',
  'Disk I/O',
  'Host health',
  'Active alerts',
  'Cloud integration status',
  'API traffic',
  'Remediation counters',
]

export const INCIDENT_STEPS = [
  {
    title: 'Prometheus alert fires',
    text: 'An alert rule on CloudOps360 metrics evaluates to firing.',
  },
  {
    title: 'Alertmanager routes it',
    text: 'The notification is grouped and routed to the CloudRescue receiver.',
  },
  {
    title: 'Authenticated webhook',
    text: 'CloudRescue accepts the payload only when the shared secret is valid.',
  },
  {
    title: 'Incident appears',
    text: 'The incident shows up in CloudRescue’s Live Monitoring view.',
  },
  {
    title: 'Resolved updates status',
    text: 'When Prometheus resolves the alert, the incident status is updated.',
  },
]

export const TECH_GROUPS = [
  {
    title: 'Frontend',
    items: [
      { name: 'React', note: 'UI components' },
      { name: 'Vite', note: 'Build tooling' },
    ],
  },
  {
    title: 'Backend & infrastructure',
    items: [
      { name: 'Python', note: 'Application language' },
      { name: 'FastAPI', note: 'API service' },
      { name: 'Docker', note: 'Containers' },
      { name: 'Docker Compose', note: 'Local orchestration' },
      { name: 'Prometheus', note: 'Metrics & alert rules' },
      { name: 'Grafana', note: 'Dashboards' },
      { name: 'Alertmanager', note: 'Alert routing' },
      { name: 'Node Exporter', note: 'Host metrics' },
    ],
  },
  {
    title: 'Cloud & automation',
    items: [
      { name: 'AWS SDK', note: 'Optional integration' },
      { name: 'Azure SDK', note: 'Optional integration' },
      { name: 'Terraform', note: 'Infrastructure as code' },
      { name: 'GitHub Actions', note: 'CI automation' },
    ],
  },
]

export const SAFETY_ITEMS = [
  {
    title: 'Dry-run by default',
    text: 'Remediation actions only describe what they would do until execution is deliberately enabled.',
  },
  {
    title: 'Allow-listed actions',
    text: 'Only a fixed set of named actions can ever be requested; arbitrary commands are not accepted.',
  },
  {
    title: 'Guarded execution',
    text: 'Real execution sits behind explicit guards so that a stray request cannot change a host.',
  },
  {
    title: 'Secret handling',
    text: 'Credentials and webhook secrets come from environment configuration and are never committed.',
  },
  {
    title: 'Internal-only admin endpoints',
    text: 'Administrative endpoints are intended for the internal network, not the public internet.',
  },
  {
    title: 'Read-only public access (goal)',
    text: 'The deployment goal is a read-only public view of monitoring data. This is a goal, not yet live.',
  },
]
