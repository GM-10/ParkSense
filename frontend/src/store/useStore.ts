import { create } from 'zustand';
import { api, isBackendOfflineError, type AlertItem, type DeploymentItem, type DispatchQueueItem, type DispatchResourcesResponse, type ForecastPoint, type Hotspot, type HistoricalResponse, type StatsResponse } from '../api/client';

export type Language = 'en' | 'kn';
export type HistoricalRange = '24h' | '7d' | '30d' | 'daily' | 'weekly' | 'full';

type PlatformSnapshot = {
  lastSync: string | null;
  hotspots: Hotspot[];
  forecast: ForecastPoint[];
  historical: Record<HistoricalRange, HistoricalResponse | null>;
  alerts: AlertItem[];
  queue: DispatchQueueItem[];
  deployments: DeploymentItem[];
  resources: DispatchResourcesResponse['summary'] | null;
  stats: StatsResponse | null;
  selectedHotspotId: string | null;
};

interface AppState extends PlatformSnapshot {
  language: Language;
  platformOnline: boolean;
  activeTimeline: string;
  setActiveTimeline: (timeline: string) => Promise<void>;
  activeTab: 'Snapshot' | 'Trend Forecast' | 'Period Analysis';
  setActiveTab: (tab: 'Snapshot' | 'Trend Forecast' | 'Period Analysis') => void;
  alertCount: number;
  setAlertCount: (count: number) => void;
  bootstrapPlatform: () => Promise<void>;
  refreshAll: () => Promise<void>;
  refreshHistorical: (range: HistoricalRange) => Promise<void>;
  syncHistorical: () => Promise<void>;
  setSelectedHotspotId: (hotspotId: string | null) => void;
  submitIncident: (payload: {
    junction_name: string;
    latitude: number;
    longitude: number;
    violation_count: number;
    congestion_level: string;
    severity: string;
    incident_type: string;
    notes: string;
  }) => Promise<void>;
  assignDispatch: (payload: { hotspot_id: string; officers: number; patrol_vehicles: number; notes?: string }) => Promise<{ deployment_id: string; status: string }>;
  updateAlertState: (id: string, state: 'New' | 'Acknowledged' | 'Assigned' | 'Resolved' | 'Archived') => Promise<void>;
  updateResourceCounts: (payload: { resource_type: 'team' | 'tow_vehicle'; total_count: number; available_count: number }) => Promise<void>;
  setLanguage: (lang: Language) => void;
}

const emptySnapshot: PlatformSnapshot = {
  lastSync: null,
  hotspots: [],
  forecast: [],
  historical: { '24h': null, '7d': null, '30d': null, 'daily': null, 'weekly': null, 'full': null },
  alerts: [],
  queue: [],
  deployments: [],
  resources: null,
  stats: null,
  selectedHotspotId: null,
};

async function loadPlatformState(timeline: string) {
  const [hotspots, alerts, queue, deployments, resources, stats, forecast] = await Promise.all([
    api.getHotspots({ mode: 'SNAPSHOT', timeline }),
    api.getAlerts({ timeline }),
    api.getDispatchQueue(),
    api.getDispatchDeployments(),
    api.getDispatchResources(),
    api.getStats({ timeline }).catch(() => null),
    api.getForecast({ timeline }).catch(() => []),
  ]);
  return { hotspots, forecast, alerts, queue, deployments, resources: resources.summary, stats };
}

export const useStore = create<AppState>((set, get) => ({
  ...emptySnapshot,
  language: 'en',
  platformOnline: true,
  activeTimeline: localStorage.getItem('parksense_timeline') ?? '2024-04',
  activeTab: 'Snapshot',
  alertCount: 0,
  setActiveTimeline: async (timeline) => {
    localStorage.setItem('parksense_timeline', timeline);
    set({ activeTimeline: timeline });
    await get().refreshAll();
  },
  setActiveTab: (activeTab) => set({ activeTab }),
  setAlertCount: (alertCount) => set({ alertCount }),
  setLanguage: (lang) => set({ language: lang }),
  setSelectedHotspotId: (selectedHotspotId) => set({ selectedHotspotId }),
  bootstrapPlatform: async () => {
    try {
      const timeline = get().activeTimeline;
      const snapshot = await loadPlatformState(timeline);
      const unresolvedAlerts = snapshot.alerts.filter((item: AlertItem) => !item.resolved).length;
      set({
        ...snapshot,
        alertCount: unresolvedAlerts,
        lastSync: new Date().toISOString(),
        platformOnline: true,
      });
    } catch (err) {
      if (!isBackendOfflineError(err)) throw err;
      set({ platformOnline: false });
    }
  },
  syncHistorical: async () => {
    await Promise.all([
      get().refreshHistorical('24h'),
      get().refreshHistorical('7d'),
      get().refreshHistorical('30d'),
    ]);
  },
  refreshAll: async () => {
    await get().bootstrapPlatform();
  },
  refreshHistorical: async (range) => {
    try {
      const timeline = get().activeTimeline;
      const historical = await api.getHistorical(range, { timeline });
      set((state) => ({
        historical: { ...state.historical, [range]: historical },
        lastSync: new Date().toISOString(),
      }));
    } catch (err) {
      if (!isBackendOfflineError(err)) throw err;
      set({ platformOnline: false });
    }
  },
  submitIncident: async (payload) => {
    await api.createIncident(payload);
    await get().refreshAll();
  },
  assignDispatch: async ({ hotspot_id, officers, patrol_vehicles, notes = '' }) => {
    const res = await api.assignDispatch(hotspot_id, officers, patrol_vehicles, notes);
    await get().refreshAll();
    return res;
  },
  updateAlertState: async (id, state) => {
    await api.updateAlertState(id, state);
    await get().refreshAll();
  },
  updateResourceCounts: async (payload) => {
    await api.updateDispatchResources(payload);
    await get().refreshAll();
  },
}));
