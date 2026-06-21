import { useContext, useEffect, useMemo, useState } from 'react';
import { CircleMarker, MapContainer, Popup, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { api, type ForecastPoint, type Hotspot, type StatsResponse } from '../api/client';
import { EmptyState, LoadingSpinner, OfflineState } from '../components/LoaderStates';
import { ThemeContext } from '../Layout';
import { useTimedResource } from '../lib/useTimedResource';
import { useStore } from '../store/useStore';
import { useNavigate } from 'react-router-dom';
import L from 'leaflet';

const center: [number, number] = [12.9716, 77.5946];
const tabs = ['Snapshot', 'Trend Forecast', 'Period Analysis'] as const;

const riskColor = (risk: number) => {
  if (risk >= 85) return '#ef4444';
  if (risk >= 70) return '#f97316';
  if (risk >= 40) return '#eab308';
  return '#22c55e';
};

const forecastRiskColor = (risk: number) => {
  if (risk >= 85) return '#a855f7'; // purple
  if (risk >= 70) return '#c084fc'; // light purple
  if (risk >= 45) return '#818cf8'; // indigo
  return '#60a5fa'; // blue
};

type TabState = {
  hotspots: Hotspot[];
  stats: StatsResponse | null;
  historical: unknown | null;
  forecast: ForecastPoint[];
  queue: import('../api/client').DispatchQueueItem[];
};

const formatTimelineMonth = (timeline: string) => {
  const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const parts = timeline.split('-');
  if (parts.length === 2) {
    const m = parseInt(parts[1], 10);
    return `${months[m - 1]} ${parts[0]}`;
  }
  return timeline;
};

export function CommandCenterView() {
  const { theme } = useContext(ThemeContext);
  const navigate = useNavigate();
  const tab = useStore((state) => state.activeTab);
  const setTab = useStore((state) => state.setActiveTab);
  const activeTimeline = useStore((state) => state.activeTimeline);
  
  // Debounce API states that trigger DBSCAN calculations on backend
  const [clusterRadius, setClusterRadius] = useState(330);
  const [minSamples, setMinSamples] = useState(10);
  
  // Responsive local slider states
  const [localClusterRadius, setLocalClusterRadius] = useState(330);
  const [localMinSamples, setLocalMinSamples] = useState(10);

  const [riskThreshold, setRiskThreshold] = useState(0);
  const [impactThreshold, setImpactThreshold] = useState(0);
  const [dayOfWeek] = useState<number | ''>('');
  const [timeOfDay] = useState<'ALL' | 'PEAK' | 'OFF_PEAK'>('ALL');
  const [range, setRange] = useState<'daily' | 'weekly' | 'full'>('daily');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [mapRef, setMapRef] = useState<L.Map | null>(null);

  // Debouncing logic to delay heavy clustering requests
  useEffect(() => {
    const handler = setTimeout(() => {
      setClusterRadius(localClusterRadius);
    }, 400);
    return () => clearTimeout(handler);
  }, [localClusterRadius]);

  useEffect(() => {
    const handler = setTimeout(() => {
      setMinSamples(localMinSamples);
    }, 400);
    return () => clearTimeout(handler);
  }, [localMinSamples]);

  const isDark = theme === 'dark';
  const overlayBg = isDark ? 'rgba(13, 17, 23, 0.85)' : 'rgba(255, 255, 255, 0.95)';
  const overlayBorder = isDark ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid rgba(0, 0, 0, 0.15)';
  const overlayText = isDark ? '#ffffff' : '#0f172a';
  const overlaySubtext = isDark ? '#94a3b8' : '#475569';
  const overlayShadow = isDark ? '0 8px 24px rgba(0, 0, 0, 0.7)' : '0 8px 24px rgba(0, 0, 0, 0.15)';
  const overlayItemBg = isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)';

  const { data, loading, timedOut, error, refresh } = useTimedResource(async () => {
    const queuePromise = api.getDispatchQueue({ timeline: activeTimeline });
    
    if (tab === 'Snapshot') {
      const [snapshot, queue] = await Promise.all([
        api.getCommandCenterSnapshot({
          ...(dayOfWeek === '' ? {} : { day_of_week: dayOfWeek }),
          timeline: activeTimeline,
        }),
        queuePromise,
      ]);
      return {
        hotspots: snapshot.hotspots,
        stats: snapshot.stats,
        historical: null,
        forecast: [],
        queue,
      } satisfies TabState;
    }

    if (tab === 'Trend Forecast') {
      const [hotspots, stats, forecast, queue] = await Promise.all([
        api.getHotspots({
          radius_m: clusterRadius,
          min_samples: minSamples,
          mode: 'FORECAST',
          ...(dayOfWeek === '' ? {} : { day_of_week: dayOfWeek }),
          time_of_day: timeOfDay,
          timeline: activeTimeline,
        }),
        api.getStats({ day_of_week: dayOfWeek === '' ? undefined : dayOfWeek, time_of_day: timeOfDay, timeline: activeTimeline }),
        api.getForecast({ timeline: activeTimeline }),
        queuePromise,
      ]);
      return {
        hotspots,
        stats,
        historical: null,
        forecast,
        queue,
      } satisfies TabState;
    }

    // Period Analysis tab
    const [hotspots, stats, historical, queue] = await Promise.all([
      api.getHotspots({
        radius_m: clusterRadius,
        min_samples: minSamples,
        mode: 'HISTORICAL',
        ...(dayOfWeek === '' ? {} : { day_of_week: dayOfWeek }),
        time_of_day: timeOfDay,
        range,
        timeline: activeTimeline,
      }),
      api.getStats({ day_of_week: dayOfWeek === '' ? undefined : dayOfWeek, time_of_day: timeOfDay, timeline: activeTimeline }),
      api.getHistorical(range, { timeline: activeTimeline }),
      queuePromise,
    ]);

    return { hotspots, stats, forecast: [], historical, queue } satisfies TabState;
  }, [tab, clusterRadius, minSamples, dayOfWeek, timeOfDay, range, activeTimeline]);

  const currentHotspots = data?.hotspots ?? [];
  const visibleHotspots = useMemo(() => {
    const source = currentHotspots
      .filter((item) => item.riskScore >= riskThreshold)
      .filter((item) => item.violations >= localMinSamples)
      .filter((item) => (item.economicImpact ?? 0) >= impactThreshold);

    if (tab === 'Trend Forecast') {
      return source.map((item) => {
        const forecastMatch = data?.forecast.find((entry) => entry.hotspot_name === item.name && entry.hour_offset === 1);
        return {
          ...item,
          riskScore: forecastMatch ? forecastMatch.predictedRisk : item.riskScore,
          violations: forecastMatch ? forecastMatch.predictedViolations : item.violations,
        };
      });
    }

    return source;
  }, [currentHotspots, data?.forecast, impactThreshold, localMinSamples, riskThreshold, tab]);

  const stats = data?.stats ?? null;
  const queue = (data?.queue ?? []).slice(0, 3);
  const selected = currentHotspots.find((item) => item.id === selectedId) ?? currentHotspots[0] ?? null;
  const selectedColor = selected ? (tab === 'Trend Forecast' ? forecastRiskColor(selected.riskScore) : riskColor(selected.riskScore)) : '#94a3b8';

  const emergingList = useMemo(() => {
    if (tab !== 'Trend Forecast' || !data?.forecast) return [];
    return data.forecast
      .filter((entry) => entry.hour_offset === 3)
      .sort((a, b) => b.predictedRisk - a.predictedRisk)
      .slice(0, 3);
  }, [tab, data?.forecast]);

  const panToHotspot = (lat: number, lng: number, id: string) => {
    setSelectedId(id);
    if (mapRef) {
      mapRef.setView([lat, lng], 14, { animate: true });
    }
  };

  if (loading) return <LoadingSpinner message="Loading mission map..." />;
  if (timedOut) return <OfflineState message="Command Center data is taking too long to load." onAction={refresh} />;
  if (error) return <OfflineState message={error} onAction={refresh} />;
  if (!data) return <EmptyState message="No command center data could be loaded." />;

  return (
    <div className="command-center-container">
      <MapContainer
        center={center}
        zoom={12}
        zoomControl={false}
        style={{ height: '100%', width: '100%', zIndex: 1 }}
        ref={setMapRef}
      >
        <TileLayer
          url={theme === 'dark' ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png' : 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'}
          attribution='&copy; CartoDB'
        />
        {visibleHotspots.map((hotspot) => (
          <CircleMarker
            key={hotspot.id}
            center={[hotspot.lat, hotspot.lng]}
            radius={tab === 'Period Analysis' ? 12 : 8}
            pathOptions={{
              color: tab === 'Trend Forecast' ? forecastRiskColor(hotspot.riskScore) : riskColor(hotspot.riskScore),
              fillColor: tab === 'Trend Forecast' ? forecastRiskColor(hotspot.riskScore) : riskColor(hotspot.riskScore),
              fillOpacity: tab === 'Period Analysis' ? 0.55 : 0.9,
              weight: tab === 'Period Analysis' ? 1 : 2
            }}
            eventHandlers={{ click: () => setSelectedId(hotspot.id) }}
          >
            <Popup>
              <div className="popup-card" style={{ color: 'var(--text-primary)' }}>
                <strong style={{ fontSize: '1rem', display: 'block', marginBottom: '4px', color: 'var(--text-primary)' }}>{hotspot.name}</strong>
                <div style={{ fontSize: '0.85rem', marginBottom: '2px', color: 'var(--text-primary)' }}>Risk Score: <strong>{(hotspot.riskScore ?? 0).toFixed(1)}%</strong></div>
                <div style={{ fontSize: '0.85rem', marginBottom: '2px', color: 'var(--text-primary)' }}>Violations: <strong>{hotspot.violations}</strong></div>
                <div style={{ fontSize: '0.85rem', marginBottom: '2px', color: 'var(--text-primary)' }}>Congestion: <strong>{hotspot.congestionLevel}</strong></div>
                <div style={{ fontSize: '0.85rem', marginBottom: '2px', color: 'var(--text-primary)' }}>Trend: <strong>{hotspot.trend}</strong></div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '6px' }}>First Detected: {hotspot.raw?.first_detected_at ? String(hotspot.raw.first_detected_at).slice(0, 19) : 'N/A'}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '8px' }}>Last Updated: {hotspot.raw?.last_updated_at ? String(hotspot.raw.last_updated_at).slice(0, 19) : 'N/A'}</div>
                <button
                  type="button"
                  className="btn btn--amber btn-sm w-full"
                  onClick={() => navigate('/dispatch', { state: { hotspotId: hotspot.id } })}
                  style={{ padding: '4px 8px', fontSize: '0.8rem' }}
                >
                  Dispatch
                </button>
              </div>
            </Popup>
          </CircleMarker>
        ))}
        {selected && <CircleMarker center={[selected.lat, selected.lng]} radius={14} pathOptions={{ color: selectedColor, fillColor: selectedColor, fillOpacity: 0.15, weight: 3 }} />}
      </MapContainer>

      {/* OVERLAYS AND CONTROLS */}
      <div className="absolute inset-0 pointer-events-none" style={{ zIndex: 10 }}>
        
        {/* TOP LEFT OVERLAY - Unified Sidebar Panel (Stats + Filters) */}
        <div 
          className="absolute left-4 top-4 w-[240px] flex flex-col gap-4 pointer-events-none"
          style={{ zIndex: 10, maxHeight: 'calc(100% - 32px)', overflowY: 'auto' }}
        >
          {/* Stats Bar */}
          <div 
            className="p-4 rounded-xl pointer-events-auto"
            style={{ background: overlayBg, border: overlayBorder, color: overlayText, boxShadow: overlayShadow }}
          >
            <div style={{ fontSize: '0.75rem', color: overlaySubtext, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '8px' }}>
              {tab === 'Snapshot' ? `Peak Activity — ${formatTimelineMonth(activeTimeline)}` : tab === 'Trend Forecast' ? `Risk Trend — ${formatTimelineMonth(activeTimeline)}` : `Period Analysis — ${formatTimelineMonth(activeTimeline)}`}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div>
                <div style={{ fontSize: '0.7rem', color: overlaySubtext }}>Total Violations</div>
                <strong style={{ fontSize: '1.2rem', color: '#0d9488' }}>{stats?.totalViolations ?? 0}</strong>
              </div>
              <div>
                <div style={{ fontSize: '0.7rem', color: overlaySubtext }}>Avg Risk Score</div>
                <strong style={{ fontSize: '1.2rem', color: '#0d9488' }}>{(stats?.avgRiskScore ?? 0).toFixed(1)}%</strong>
              </div>
              <div>
                <div style={{ fontSize: '0.7rem', color: overlaySubtext }}>Critical Zones</div>
                <strong style={{ fontSize: '1.2rem', color: '#0d9488' }}>{stats?.criticalZones ?? 0}</strong>
              </div>
              <div>
                <div style={{ fontSize: '0.7rem', color: overlaySubtext }}>Active Officers</div>
                <strong style={{ fontSize: '1.2rem', color: '#0d9488' }}>{stats?.activeOfficers ?? 0}</strong>
              </div>
            </div>
          </div>

          {/* Collapsible Filters Panel */}
          <div className="flex flex-col gap-2 pointer-events-auto">
            <button
              type="button"
              onClick={() => setFiltersOpen(!filtersOpen)}
              style={{
                background: overlayBg,
                border: overlayBorder,
                borderRadius: '8px',
                color: overlayText,
                padding: '10px 16px',
                cursor: 'pointer',
                fontSize: '0.8rem',
                fontWeight: 600,
                boxShadow: overlayShadow,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px',
                width: '100%'
              }}
            >
              Filters {filtersOpen ? '▲' : '▼'}
            </button>
            
            {filtersOpen && (
              <div 
                style={{
                  background: overlayBg,
                  border: overlayBorder,
                  borderRadius: '12px',
                  padding: '16px 20px',
                  color: overlayText,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '16px',
                  boxShadow: overlayShadow,
                  width: '100%'
                }}
              >
                <div style={{ fontSize: '0.85rem', fontWeight: 600, textTransform: 'uppercase', borderBottom: isDark ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.1)', paddingBottom: '6px' }}>
                  Refine Search
                </div>
                <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <span style={{ fontSize: '0.75rem', color: overlaySubtext }}>Risk Threshold: {riskThreshold}%</span>
                  <input type="range" min={0} max={100} value={riskThreshold} onChange={(e) => setRiskThreshold(Number(e.target.value))} style={{ cursor: 'pointer' }} />
                </label>
                <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <span style={{ fontSize: '0.75rem', color: overlaySubtext }}>Violation Minimum: {localMinSamples}</span>
                  <input type="range" min={0} max={100} value={localMinSamples} onChange={(e) => setLocalMinSamples(Number(e.target.value))} style={{ cursor: 'pointer' }} />
                </label>
                <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <span style={{ fontSize: '0.75rem', color: overlaySubtext }}>Impact Threshold: {impactThreshold}</span>
                  <input type="range" min={0} max={100} value={impactThreshold} onChange={(e) => setImpactThreshold(Number(e.target.value))} style={{ cursor: 'pointer' }} />
                </label>
                <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <span style={{ fontSize: '0.75rem', color: overlaySubtext }}>Cluster Radius: {localClusterRadius}m</span>
                  <input type="range" min={50} max={1000} step={50} value={localClusterRadius} onChange={(e) => setLocalClusterRadius(Number(e.target.value))} style={{ cursor: 'pointer' }} />
                </label>
              </div>
            )}
          </div>
        </div>

        {/* TOP RIGHT OVERLAY - Priority Queue */}
        <div 
          className="absolute right-4 top-4 w-[280px] p-4 rounded-xl pointer-events-auto"
          style={{ background: overlayBg, border: overlayBorder, color: overlayText, boxShadow: overlayShadow, maxHeight: '350px', overflowY: 'auto' }}
        >
          <div style={{ fontSize: '0.75rem', color: overlaySubtext, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.15em', marginBottom: '10px' }}>
            PRIORITY QUEUE
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {queue.map((item, index) => {
              const spot = currentHotspots.find(h => h.id === item.hotspot_id);
              return (
                <div 
                  key={item.hotspot_id}
                  onClick={() => spot && panToHotspot(spot.lat, spot.lng, item.hotspot_id)}
                  style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'space-between', 
                    padding: '8px', 
                    borderRadius: '8px', 
                    background: overlayItemBg, 
                    cursor: 'pointer',
                    border: overlayBorder
                  }}
                  className="queue-item-overlay"
                >
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '2px', overflow: 'hidden' }}>
                    <span style={{ fontSize: '0.8rem', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {index + 1}. {item.hotspot_name}
                    </span>
                    <span style={{ fontSize: '0.65rem', color: overlaySubtext }}>
                      Trend: {item.trend === 'up' ? '↗' : item.trend === 'down' ? '↘' : '→'}
                    </span>
                  </div>
                  <span 
                    style={{ 
                      fontSize: '0.75rem', 
                      padding: '2px 6px', 
                      borderRadius: '4px', 
                      background: riskColor(item.risk_score), 
                      color: '#000', 
                      fontWeight: 'bold',
                      marginLeft: '8px'
                    }}
                  >
                    {(item.risk_score ?? 0).toFixed(0)}
                  </span>
                </div>
              );
            })}
            {queue.length === 0 && (
              <div style={{ fontSize: '0.75rem', color: '#64748b' }}>No priorities listed.</div>
            )}
          </div>
        </div>

        {/* FLOATING TAB SWITCHER - Pill toggle */}
        <div 
          className="absolute left-1/2 top-4 -translate-x-1/2 rounded-full p-[4px] pointer-events-auto"
          style={{ background: overlayBg, border: overlayBorder, boxShadow: overlayShadow, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}
        >
          <div style={{ display: 'flex', gap: '2px' }}>
            {tabs.map((item) => (
              <button 
                key={item} 
                type="button" 
                onClick={() => setTab(item)}
                style={{
                  borderRadius: '9999px',
                  background: tab === item ? '#0d9488' : 'transparent',
                  color: tab === item ? '#fff' : overlayText,
                  padding: '6px 16px',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  border: 'none',
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
              >
                {item}
              </button>
            ))}
          </div>
          {tab === 'Period Analysis' && (
            <div style={{ display: 'flex', gap: '4px', borderTop: isDark ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.1)', paddingTop: '4px', width: '100%', justifyContent: 'center' }}>
              {(['daily', 'weekly', 'full'] as const).map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setRange(r)}
                  style={{
                    borderRadius: '9999px',
                    background: range === r ? (isDark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.08)') : 'transparent',
                    color: overlayText,
                    padding: '2px 8px',
                    fontSize: '0.65rem',
                    border: 'none',
                    cursor: 'pointer'
                  }}
                >
                  {r === 'full' ? 'Full Month' : r.charAt(0).toUpperCase() + r.slice(1)}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* BOTTOM OVERLAY - Emerging hotspots in Forecast Mode */}
        {tab === 'Trend Forecast' && emergingList.length > 0 && (
          <div 
            className="absolute bottom-4 left-1/2 -translate-x-1/2 w-[340px] p-4 rounded-xl pointer-events-auto"
            style={{ background: overlayBg, border: overlayBorder, color: overlayText, boxShadow: overlayShadow }}
          >
            <div style={{ fontSize: '0.75rem', color: '#a855f7', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '8px' }}>
              Trending zones in this period
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {emergingList.map((item, idx) => (
                <div key={item.hotspot_id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', background: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.03)', padding: '4px 8px', borderRadius: '4px', border: overlayBorder }}>
                  <span>{idx + 1}. {item.hotspot_name}</span>
                  <span style={{ color: '#c084fc', fontWeight: 'bold' }}>Risk: {(item.predictedRisk ?? 0).toFixed(0)}%</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* BOTTOM LEFT OVERLAY - Freshness */}
        <div 
          className="absolute left-4 bottom-4 p-3 rounded-xl pointer-events-auto"
          style={{ background: overlayBg, border: overlayBorder, color: overlayText, boxShadow: overlayShadow, display: 'flex', alignItems: 'center', gap: '10px' }}
        >
          <span style={{ fontSize: '0.75rem', color: overlaySubtext }}>Viewing: {formatTimelineMonth(activeTimeline)} data</span>
          <button 
            type="button" 
            onClick={refresh}
            style={{
              background: '#0d9488',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              padding: '4px 8px',
              fontSize: '0.7rem',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            Refresh
          </button>
        </div>

      </div>
    </div>
  );
}
