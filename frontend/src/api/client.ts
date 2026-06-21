import axios from 'axios';

export class BackendOfflineError extends Error {
  constructor(message = 'Backend offline') {
    super(message);
    this.name = 'BackendOfflineError';
  }
}

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000',
  headers: { 'Content-Type': 'application/json' },
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('parksense_token');
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('parksense_token');
      localStorage.removeItem('parksense_username');
      window.location.assign('/login');
    }
    return Promise.reject(error);
  },
);

function is401(err: unknown) {
  return axios.isAxiosError(err) && err.response?.status === 401;
}

function isNetworkFailure(err: unknown) {
  return axios.isAxiosError(err) && (!err.response || err.code === 'ERR_NETWORK' || err.code === 'ECONNABORTED');
}

function offlineError(err: unknown): never {
  if (is401(err)) throw err;
  if (isNetworkFailure(err)) throw new BackendOfflineError();
  throw err;
}

async function request<T>(
  method: 'get' | 'post' | 'patch' | 'put' | 'delete',
  url: string,
  options: { params?: Record<string, unknown>; data?: unknown } = {},
): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 15000);
  try {
    const params = { ...options.params };
    if (!url.startsWith('/auth/') && !params.timeline) {
      params.timeline = localStorage.getItem('parksense_timeline') ?? '2024-04';
    }
    const response = await apiClient.request<T>({
      method,
      url,
      params,
      data: options.data,
      signal: controller.signal,
    });
    return response.data;
  } catch (err) {
    if (axios.isCancel(err)) {
      throw new BackendOfflineError('Request timed out after 15 seconds');
    }
    return offlineError(err);
  } finally {
    window.clearTimeout(timeout);
  }
}

export type Hotspot = {
  id: string;
  name: string;
  lat: number;
  lng: number;
  riskScore: number;
  violations: number;
  congestionLevel: string;
  status: string;
  trend: string;
  peakHour?: number;
  cluster_id: string;
  economicImpact?: number;
  raw?: Record<string, unknown>;
};

export type StatsResponse = {
  totalViolations: number;
  avgRiskScore: number;
  criticalZones: number;
  activeOfficers: number;
  timestamp: string;
  city: string;
  revenueLeakagePrevented?: number;
  avgResponseTimeMins?: number;
  congestionReductionPct?: number;
  hotspotsMitigated?: number;
};

export type CommandCenterSnapshotBucket = {
  timeOfDay: 'ALL' | 'PEAK' | 'OFF_PEAK';
  totalViolations: number;
  avgRiskScore: number;
  criticalZones: number;
  activeOfficers: number;
  city: string;
  timestamp: string;
  hotspots: Hotspot[];
};

export type CommandCenterSnapshotResponse = {
  timeOfDay: 'ALL' | 'PEAK' | 'OFF_PEAK';
  buckets: CommandCenterSnapshotBucket[];
  summary: {
    totalViolations: number;
    avgRiskScore: number;
    criticalZones: number;
    activeOfficers: number;
    city: string;
    timestamp: string;
  };
};

export type ForecastPoint = {
  hotspot_id: string;
  hotspot_name: string;
  hour_offset: number;
  predictedRisk: number;
  predictedViolations: number;
  confidence: number;
};

export type HistoricalResponse = {
  range: '24h' | '7d' | '30d';
  bucketLabel: string;
  buckets: { label: string; violations: number }[];
  topJunctions: { name: string; violations: number; risk: number }[];
  totalViolations: number;
  avgRisk: number;
  peakHour: number;
  peakDay: string;
  hotspotCount: number;
};

export type AlertItem = {
  id: string;
  type: 'Critical' | 'Warning' | 'Info';
  junction_id: string;
  junction_name: string;
  message: string;
  timestamp: string;
  resolved: boolean;
  state?: 'New' | 'Acknowledged' | 'Assigned' | 'Resolved' | 'Archived';
  current_risk?: number;
  predicted_risk?: number;
  eta_minutes?: number;
  recommended_officers?: number;
};

export type AnalyticsResponse = {
  violations_by_hour: number[];
  risk_distribution: { low: number; medium: number; high: number; critical: number };
  top_junctions: { name: string; violations: number }[];
  weekly_trend: { date: string; violations: number }[];
};

export type PeakWindowItem = {
  day: string;
  peakHour: number;
  peakWindow: string;
  violations: number;
};

export type DispatchResourcesResponse = {
  teams: { resource_type: string; total_count: number; available_count: number; updated_at: string } | null;
  towVehicles: { resource_type: string; total_count: number; available_count: number; updated_at: string } | null;
  summary: {
    availableOfficers: number;
    totalOfficers: number;
    availablePatrolVehicles: number;
    totalPatrolVehicles: number;
    activeDeployments: number;
    resolvedDeploymentsToday: number;
  };
};

export type DispatchQueueItem = {
  hotspot_id: string;
  hotspot_name: string;
  risk_score: number;
  current_violations: number;
  predicted_violations_next_hour: number;
  severity: 'Low' | 'Moderate' | 'High' | 'Critical';
  recommended_officers: number;
  recommended_patrol_vehicles: number;
  priority_score: number;
  status: string;
  deployment_id?: string | null;
  action_recommendation: string;
  first_detected_at?: string;
  last_updated_at?: string;
  active_minutes?: number;
  trend?: string;
};

export type DeploymentItem = {
  id: string;
  hotspot_id: string;
  hotspot_name: string;
  risk_score: number;
  current_violations: number;
  predicted_violations_next_hour: number;
  severity: string;
  recommended_officers: number;
  recommended_patrol_vehicles: number;
  assigned_officers: number;
  assigned_vehicles: number;
  status: string;
  priority_score: number;
  created_at: string;
  updated_at: string;
  assigned_by?: string;
  notes?: string | null;
  outcome?: string;
};

export type IncidentRecord = {
  id: string;
  latitude: number;
  longitude: number;
  violation_type: string;
  vehicle_type: string;
  severity: string;
  location_label?: string | null;
  junction_name?: string | null;
  police_station?: string | null;
  occurred_at: string;
  ingested_at: string;
  ingested_by?: string | null;
};

export type ReportDaily = {
  type: 'daily';
  generatedAt: string;
  date: string;
  datasetWindow: string;
  forecastHorizon: string;
  totalViolations: number;
  topHotspots: { name: string; riskScore: number; violations: number }[];
  officerDeploymentSummary: { activeOfficers: number; shift: string };
  peakHour: number;
  peakWindow: string;
  criticalAlerts: number;
};

export type ReportWeekly = {
  type: 'weekly';
  generatedAt: string;
  datasetWindow: string;
  trend: { date: string; violations: number }[];
  mostImprovedJunction: string | null;
  worstJunction: string | null;
  totalEnforcementActions: number;
  officerUtilization: number;
};

export type ReportRisk = {
  type: 'risk';
  generatedAt: string;
  datasetWindow: string;
  forecastHorizon: string;
  currentRiskScores: { name: string; riskScore: number }[];
  recommendedDeploymentPositions: { name: string; lat: number; lng: number }[];
  predictedHotspotsNext24h: { name: string; predictedRisk: number }[];
};

export type OfficerTeam = {
  id: string;
  team_name: string;
  total_strength: number;
  available: number;
  status: 'Available' | 'On Duty' | 'Off Shift' | 'On Leave';
  timeline: string;
};

export type Vehicle = {
  id: string;
  vehicle_id: string;
  type: string;
  status: 'Available' | 'Deployed' | 'Maintenance' | 'Offline';
  assigned_to: string;
  timeline: string;
};

export const api = {
  login: (username: string, password: string) =>
    request<{ token: string; username: string; role: string }>('post', '/auth/login', { data: { username, password } }),
  logout: () => request<{ status: string }>('post', '/auth/logout'),
  getCommandCenterSnapshot: (params: Record<string, unknown> = {}) =>
    request<{ hotspots: Hotspot[]; stats: StatsResponse; queue: DispatchQueueItem[] }>('get', '/command-center/snapshot', { params }),
  getHotspots: (params: Record<string, unknown> = {}) => request<Hotspot[]>('get', '/hotspots', { params }),
  getStats: (params: Record<string, unknown> = {}) => request<StatsResponse>('get', '/stats', { params }),
  getForecast: (params: Record<string, unknown> = {}) => request<ForecastPoint[]>('get', '/forecast', { params }),
  getHistorical: (range: '24h' | '7d' | '30d' | 'daily' | 'weekly' | 'full', params: Record<string, unknown> = {}) => request<HistoricalResponse>('get', '/historical', { params: { range, ...params } }),
  getAlerts: (params: Record<string, unknown> = {}) => request<AlertItem[]>('get', '/alerts', { params }),
  resolveAlert: (id: string) => request<AlertItem>('post', `/alerts/${id}/resolve`),
  updateAlertState: (id: string, state: 'New' | 'Acknowledged' | 'Assigned' | 'Resolved' | 'Archived') =>
    request<AlertItem>('patch', `/alerts/${id}/state`, { data: { state } }),
  getAnalytics: () => request<AnalyticsResponse>('get', '/analytics'),
  getPeakWindows: () => request<PeakWindowItem[]>('get', '/analytics/peak-windows'),
  getDispatchResources: () => request<DispatchResourcesResponse>('get', '/dispatch/resources'),
  updateDispatchResources: (payload: { resource_type: 'team' | 'tow_vehicle'; total_count: number; available_count: number }) =>
    request<DispatchResourcesResponse>('patch', '/dispatch/resources', { data: payload }),
  getDispatchQueue: (params: Record<string, unknown> = {}) => request<DispatchQueueItem[]>('get', '/queue', { params }),
  getDispatchDeployments: (params: Record<string, unknown> = {}) => request<DeploymentItem[]>('get', '/deployments', { params }),
  getDispatchIncidents: () => request<IncidentRecord[]>('get', '/dispatch/incidents'),
  createIncident: (payload: {
    junction_name: string;
    latitude: number;
    longitude: number;
    violation_count: number;
    congestion_level: string;
    severity: string;
    incident_type: string;
    notes: string;
  }) => request<{ incident_id: string; status: string; junction_name?: string; updated_risk_score?: number | null }>('post', '/incidents', { data: payload }),
  assignDispatch: (hotspot_id: string, officers: number, patrol_vehicles: number, notes = '', team_ids?: string[], vehicle_ids?: string[]) =>
    request<{ deployment_id: string; status: string }>('post', '/deployments', {
      data: { hotspot_id, officers, patrol_vehicles, notes, team_ids, vehicle_ids },
    }),
  updateDispatchStatus: (deployment_id: string, status: string, outcome?: string) =>
    request<{ deployment_id: string; status: string }>('patch', `/deployments/${deployment_id}`, {
      data: { status, outcome },
    }),
  deleteDeployment: (id: string) =>
    request<{ status: string }>('delete', `/deployments/${id}`),
  searchHotspots: (q: string) =>
    request<{ id: string; name: string; lat: number; lng: number }[]>('get', '/hotspots/search', { params: { q } }),
  getDispatchRecommendation: (hotspotId: string) =>
    request<any>('get', '/dispatch/recommendation', { params: { hotspot_id: hotspotId } }),
  getImpact: (hotspotId: string) =>
    request<any>('get', '/impact', { params: { hotspot_id: hotspotId } }),
  queryCopilot: (message: string, context: object, language: 'en' | 'kn' = 'en') =>
    request<{ reply: string }>('post', '/copilot/query', { data: { message, context, language } }),
  getDailyReport: (params: Record<string, unknown> = {}) => request<ReportDaily>('get', '/reports/daily', { params }),
  getWeeklyReport: (params: Record<string, unknown> = {}) => request<ReportWeekly>('get', '/reports/weekly', { params }),
  getRiskReport: (params: Record<string, unknown> = {}) => request<ReportRisk>('get', '/reports/risk', { params }),
  getWhatIf: (hotspot_id: string, officers: number, signal_improvement: number) =>
    request<{
      hotspot_id: string;
      original_risk: number;
      new_risk: number;
      risk_reduction_pct: number;
      economic_savings_inr: number;
      new_congestion_level: string;
      reasons: string[];
    }>('get', '/analytics/what-if', { params: { hotspot_id, officers, signal_improvement } }),
  getOfficers: (params: Record<string, unknown> = {}) => request<OfficerTeam[]>('get', '/resources/officers', { params }),
  addOfficer: (payload: Omit<OfficerTeam, 'id' | 'timeline'>, params: Record<string, unknown> = {}) =>
    request<{ id: string; status: string }>('post', '/resources/officers', { data: payload, params }),
  editOfficer: (id: string, payload: Omit<OfficerTeam, 'id' | 'timeline'>) =>
    request<{ status: string }>('patch', `/resources/officers/${id}`, { data: payload }),
  deleteOfficer: (id: string) =>
    request<{ status: string }>('delete', `/resources/officers/${id}`),
  getVehicles: (params: Record<string, unknown> = {}) => request<Vehicle[]>('get', '/resources/vehicles', { params }),
  addVehicle: (payload: Omit<Vehicle, 'id' | 'timeline'>, params: Record<string, unknown> = {}) =>
    request<{ id: string; status: string }>('post', '/resources/vehicles', { data: payload, params }),
  editVehicle: (id: string, payload: Omit<Vehicle, 'id' | 'timeline'>) =>
    request<{ status: string }>('patch', `/resources/vehicles/${id}`, { data: payload }),
  deleteVehicle: (id: string) =>
    request<{ status: string }>('delete', `/resources/vehicles/${id}`),
};

export function isBackendOfflineError(err: unknown) {
  return err instanceof BackendOfflineError || (err as { name?: string })?.name === 'BackendOfflineError';
}
