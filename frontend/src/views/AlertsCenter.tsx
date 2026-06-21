import { useEffect, useMemo, useState } from 'react';
import { api, type AlertItem } from '../api/client';
import { EmptyState, LoadingSpinner, OfflineState, StatusPill } from '../components/LoaderStates';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/time';
import { useTimedResource } from '../lib/useTimedResource';
import { useStore } from '../store/useStore';
import { useNavigate } from 'react-router-dom';

const tabs = ['All', 'Critical', 'Warning', 'Info', 'Resolved'] as const;

export function AlertsCenter() {
  const [filter, setFilter] = useState<(typeof tabs)[number]>('All');
  const navigate = useNavigate();
  const setAlertCount = useStore((state) => state.setAlertCount);
  const [lastSyncTime, setLastSyncTime] = useState<string>(new Date().toISOString());
  const { data, loading, timedOut, error, refresh } = useTimedResource(async () => {
    const [alerts, stats] = await Promise.all([api.getAlerts(), api.getStats()]);
    const unresolvedAlerts = alerts.filter((item) => !item.resolved).length;
    setAlertCount(unresolvedAlerts);
    setLastSyncTime(new Date().toISOString());
    return { alerts, stats };
  }, [setAlertCount]);
  const [updating, setUpdating] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setInterval(() => void refresh(), 30000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const alerts = (data?.alerts ?? []).slice().sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  const unresolvedCount = useMemo(() => alerts.filter((item) => !item.resolved).length, [alerts]);

  const filtered = alerts.filter((alert) => {
    if (filter === 'All') return true;
    if (filter === 'Resolved') return alert.resolved;
    return alert.type === filter;
  });

  const resolveAlert = async (alert: AlertItem) => {
    setUpdating(alert.id);
    try {
      await api.resolveAlert(alert.id);
      await refresh();
    } finally {
      setUpdating(null);
    }
  };

  if (loading) return <LoadingSpinner />;
  if (timedOut) return <OfflineState message="Alerts are taking too long to load." onAction={refresh} />;
  if (error) return <OfflineState message={error} onAction={refresh} />;
  if (!data) return <EmptyState message="No alerts were returned by the backend." />;

  return (
    <div className="space-y-6">
      <div className="section-heading">
        <div>
          <div className="eyebrow">Incident console</div>
          <h1>Alerts Center</h1>
        </div>
        <div className="section-meta">
          <StatusPill tone={unresolvedCount > 0 ? 'warn' : 'good'} label={`${unresolvedCount} unresolved`} />
          <span className="muted-text">Last sync {formatRelativeTime(lastSyncTime)}</span>
          <button type="button" className="btn btn--ghost" onClick={refresh}>
            Refresh
          </button>
        </div>
      </div>

      <div className="filter-row">
        {tabs.map((tab) => {
          const count =
            tab === 'All'
              ? alerts.length
              : tab === 'Resolved'
                ? alerts.filter((item) => item.resolved).length
                : alerts.filter((item) => item.type === tab).length;
          return (
            <button key={tab} type="button" className={filter === tab ? 'filter-pill active' : 'filter-pill'} onClick={() => setFilter(tab)}>
              {tab}
              <span>{count}</span>
            </button>
          );
        })}
      </div>

      {filtered.length === 0 ? (
        <EmptyState message="No alerts match the selected filter." />
      ) : (
        <div className="space-y-4">
          {filtered.map((alert) => (
            <article key={alert.id} className="panel-card panel-card--row">
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <StatusPill tone={alert.type === 'Critical' ? 'bad' : alert.type === 'Warning' ? 'warn' : 'neutral'} label={alert.type} />
                  {alert.resolved ? <StatusPill tone="good" label="Resolved" /> : <StatusPill tone="warn" label="Open" />}
                  <span className="muted-text">{formatAbsoluteTime(alert.timestamp)}</span>
                  <span className="muted-text">{formatRelativeTime(alert.timestamp)}</span>
                </div>
                <h3 className="text-xl font-semibold text-white">{alert.junction_name}</h3>
                <p className="max-w-4xl text-sm leading-6 text-slate-300">{alert.message}</p>
                <div className="grid gap-3 md:grid-cols-4">
                  <div className="stat-mini">
                    <span>Current risk</span>
                    <strong>{(alert.current_risk ?? 0).toFixed(1)}%</strong>
                  </div>
                  <div className="stat-mini">
                    <span>Predicted risk</span>
                    <strong>{(alert.predicted_risk ?? 0).toFixed(1)}%</strong>
                  </div>
                  <div className="stat-mini">
                    <span>ETA</span>
                    <strong>{alert.eta_minutes ?? 0} mins</strong>
                  </div>
                  <div className="stat-mini">
                    <span>Officers</span>
                    <strong>{alert.recommended_officers ?? 0}</strong>
                  </div>
                </div>
              </div>

              <div className="flex flex-col gap-3 self-start md:w-48">
                <button type="button" className="btn btn--ghost" onClick={() => navigate('/dispatch', { state: { hotspotId: alert.junction_id } })}>
                  Open dispatch
                </button>
                {!alert.resolved && (
                  <button type="button" className="btn btn--amber" disabled={updating === alert.id} onClick={() => void resolveAlert(alert)}>
                    {updating === alert.id ? 'Resolving...' : 'Resolve'}
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

