import { useEffect, useMemo, useState } from 'react';
import { api, isBackendOfflineError } from '../api/client';
import { EmptyState, LoadingSpinner, OfflineState } from '../components/LoaderStates';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/time';
import { useTimedResource } from '../lib/useTimedResource';

type IncidentForm = {
  junction_name: string;
  latitude: string;
  longitude: string;
  incident_type: string;
  violation_count: string;
  congestion_level: string;
  severity: string;
  notes: string;
};

type IncidentPayload = {
  incident_id: string;
  status: string;
  junction_name?: string;
  updated_risk_score?: number | null;
};

export function IncidentReportingView() {
  const username = localStorage.getItem('parksense_username') ?? 'unknown';
  const [form, setForm] = useState<IncidentForm>({
    junction_name: '',
    latitude: '',
    longitude: '',
    incident_type: 'Wrong Parking',
    violation_count: '10',
    congestion_level: 'Moderate',
    severity: 'Moderate',
    notes: '',
  });
  const [confirmation, setConfirmation] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [suggestions, setSuggestions] = useState<{ id: string; name: string; lat: number; lng: number }[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);

  const { data, loading, timedOut, error, refresh } = useTimedResource(async () => {
    const [hotspots, incidents, stats] = await Promise.all([
      api.getHotspots({ mode: 'LIVE' }),
      api.getDispatchIncidents(),
      api.getStats(),
    ]);
    return { hotspots, incidents, stats };
  }, []);

  useEffect(() => {
    const firstHotspot = data?.hotspots[0];
    if (firstHotspot && !form.junction_name) {
      setForm((current) => ({
        ...current,
        junction_name: firstHotspot.name,
        latitude: String(firstHotspot.lat),
        longitude: String(firstHotspot.lng),
      }));
      setSearchTerm(firstHotspot.name);
    }
  }, [data?.hotspots, form.junction_name]);

  useEffect(() => {
    if (!searchTerm) {
      setSuggestions([]);
      return;
    }
    const delayDebounce = setTimeout(async () => {
      try {
        const matches = await api.searchHotspots(searchTerm);
        setSuggestions(matches);
      } catch (err) {
        console.error(err);
      }
    }, 250);
    return () => clearTimeout(delayDebounce);
  }, [searchTerm]);

  useEffect(() => {
    if (!confirmation) return;
    const timer = window.setTimeout(() => setConfirmation(null), 6000);
    return () => window.clearTimeout(timer);
  }, [confirmation]);

  const hotspotOptions = data?.hotspots ?? [];
  const incidents = data?.incidents ?? [];
  const todayKey = new Date().toISOString().slice(0, 10);

  const myIncidentsToday = useMemo(
    () => incidents.filter((item) => item.ingested_by === username && item.ingested_at?.startsWith(todayKey)),
    [incidents, username, todayKey],
  );

  const recentCitywide = useMemo(() => {
    const cutoff = Date.now() - 2 * 60 * 60 * 1000;
    return incidents.filter((item) => new Date(item.ingested_at).getTime() >= cutoff);
  }, [incidents]);

  const selectedHotspot = hotspotOptions.find((item) => item.name === form.junction_name) ?? hotspotOptions[0] ?? null;

  const handleSelectSuggestion = (item: { id: string; name: string; lat: number; lng: number }) => {
    setForm((current) => ({
      ...current,
      junction_name: item.name,
      latitude: String(item.lat),
      longitude: String(item.lng),
    }));
    setSearchTerm(item.name);
    setShowDropdown(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setConfirmation(null);
    try {
      const payload = {
        junction_name: form.junction_name,
        latitude: Number(form.latitude),
        longitude: Number(form.longitude),
        violation_count: Number(form.violation_count),
        congestion_level: form.congestion_level,
        severity: form.severity,
        incident_type: form.incident_type,
        notes: form.notes,
      };
      const result = (await api.createIncident(payload)) as IncidentPayload;
      await refresh();
      setConfirmation(
        `Incident filed for ${result.junction_name ?? payload.junction_name}. Updated risk: ${
          result.updated_risk_score != null ? `${result.updated_risk_score.toFixed(1)}%` : 'pending'
        }.`,
      );
      setForm((current) => ({
        ...current,
        violation_count: '10',
        notes: '',
      }));
    } catch (err) {
      setConfirmation(isBackendOfflineError(err) ? 'Backend offline. Start the API server and try again.' : 'Unable to submit incident right now.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <LoadingSpinner />;
  if (timedOut) return <OfflineState message="Incident data is taking too long to load." onAction={refresh} />;
  if (error) return <OfflineState message={error} onAction={refresh} />;
  if (!data) return <EmptyState message="No incident data could be loaded." />;

  return (
    <div className="space-y-6">
      <div className="section-heading">
        <div>
          <div className="eyebrow">Field operations</div>
          <h1>Incident Reporting</h1>
        </div>
          <div className="section-meta">
          <span className="status-pill status-pill--neutral">Last updated {formatRelativeTime(data.stats.timestamp)}</span>
          <button type="button" className="btn btn--ghost" onClick={refresh}>
            Refresh
          </button>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <section className="panel-card">
          <div className="panel-card__header">
            <h2>File new incident</h2>
            <span className="muted-text">Posts live incident data to the backend</span>
          </div>

          <form className="mt-5 space-y-4" onSubmit={handleSubmit}>
            <div className="form-field relative">
              <span>Junction / Location Name</span>
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value);
                  setShowDropdown(true);
                }}
                onFocus={() => setShowDropdown(true)}
                onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
                placeholder="Search junction..."
                className="w-full rounded-lg bg-black/40 px-3 py-2 text-white border border-white/10"
              />
              {showDropdown && suggestions.length > 0 && (
                <ul className="absolute left-0 right-0 z-50 mt-1 max-h-60 overflow-y-auto rounded-lg border border-white/10 bg-[#0d1117] p-1 shadow-lg pointer-events-auto">
                  {suggestions.map((item) => (
                    <li
                      key={item.id}
                      onClick={() => handleSelectSuggestion(item)}
                      className="cursor-pointer rounded-md px-3 py-2 text-sm text-slate-200 hover:bg-[#0d9488]/20 hover:text-white"
                    >
                      {item.name}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <label className="form-field">
                <span>Incident type</span>
                <select value={form.incident_type} onChange={(e) => setForm((current) => ({ ...current, incident_type: e.target.value }))}>
                  <option value="Wrong Parking">Wrong Parking</option>
                  <option value="Signal Violation">Signal Violation</option>
                  <option value="Accident">Accident</option>
                  <option value="Road Blockage">Road Blockage</option>
                  <option value="Congestion">Congestion</option>
                </select>
              </label>
              <label className="form-field">
                <span>Violation count</span>
                <input type="number" min={1} value={form.violation_count} onChange={(e) => setForm((current) => ({ ...current, violation_count: e.target.value }))} />
              </label>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <label className="form-field">
                <span>Congestion level</span>
                <select value={form.congestion_level} onChange={(e) => setForm((current) => ({ ...current, congestion_level: e.target.value }))}>
                  <option value="Low">Low</option>
                  <option value="Moderate">Moderate</option>
                  <option value="High">High</option>
                  <option value="Critical">Critical</option>
                </select>
              </label>
              <label className="form-field">
                <span>Severity</span>
                <select value={form.severity} onChange={(e) => setForm((current) => ({ ...current, severity: e.target.value }))}>
                  <option value="Low">Low</option>
                  <option value="Moderate">Moderate</option>
                  <option value="High">High</option>
                  <option value="Critical">Critical</option>
                </select>
              </label>
            </div>

            <label className="form-field">
              <span>Notes</span>
              <textarea
                rows={4}
                value={form.notes}
                onChange={(e) => setForm((current) => ({ ...current, notes: e.target.value }))}
                placeholder="Describe what was observed on site."
              />
            </label>

            <button type="submit" className="btn btn--amber w-full" disabled={submitting}>
              {submitting ? 'Submitting...' : 'Submit incident'}
            </button>
          </form>

          {confirmation && <div className="alert-banner mt-4">{confirmation}</div>}

          {selectedHotspot && (
            <div className="mt-5 panel-stat">
              <div className="muted-text">Selected junction</div>
              <strong>{selectedHotspot.name}</strong>
              <small>{selectedHotspot.riskScore.toFixed(1)}% risk · {selectedHotspot.violations} violations</small>
            </div>
          )}
        </section>

        <div className="space-y-6">
          <section className="panel-card">
            <div className="panel-card__header">
              <h2>My incidents today</h2>
              <span className="muted-text">{myIncidentsToday.length} records</span>
            </div>
            <div className="mt-4 space-y-3">
                  {myIncidentsToday.length === 0 ? (
                <EmptyState title="No incidents today" message="You have not filed any incidents yet." />
              ) : (
                myIncidentsToday.map((item) => (
                  <article key={item.id} className="list-row">
                    <div>
                      <strong>{item.junction_name || item.location_label || 'Unknown junction'}</strong>
                      <small>{item.violation_type}</small>
                    </div>
                    <div className="text-right">
                      <div className="font-semibold text-white">{item.severity}</div>
                      <small className="text-slate-400">{formatAbsoluteTime(item.ingested_at)}</small>
                    </div>
                  </article>
                ))
              )}
            </div>
          </section>

          <section className="panel-card">
            <div className="panel-card__header">
              <h2>Recent citywide incidents</h2>
              <span className="muted-text">Last 2 hours</span>
            </div>
            <div className="mt-4 space-y-3">
              {recentCitywide.length === 0 ? (
                <EmptyState title="No recent incidents" message="There were no incidents reported across the city in the last 2 hours." />
              ) : (
                recentCitywide.map((item) => (
                  <article key={item.id} className="list-row">
                    <div>
                      <strong>{item.junction_name || item.location_label || 'Unknown junction'}</strong>
                      <small>{item.violation_type}</small>
                    </div>
                    <div className="text-right">
                      <div className="font-semibold text-white">{item.ingested_by ?? 'Field Officer'}</div>
                      <small className="text-slate-400">{formatAbsoluteTime(item.ingested_at)}</small>
                    </div>
                  </article>
                ))
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

