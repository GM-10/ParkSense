import { useEffect, useState, useContext, useMemo } from 'react';
import { MapContainer, Marker, Polyline, Popup, TileLayer } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useLocation } from 'react-router-dom';
import { api, type DeploymentItem } from '../api/client';
import { EmptyState, LoadingSpinner, OfflineState, StatusPill } from '../components/LoaderStates';
import { ThemeContext } from '../Layout';
import { formatAbsoluteTime, formatRelativeTime } from '../lib/time';
import { useTimedResource } from '../lib/useTimedResource';

const station: [number, number] = [12.9716, 77.5946];

const icon = (fill: string) =>
  L.divIcon({
    className: 'parksense-marker',
    html: `<div style="background:${fill};box-shadow:0 0 18px ${fill}66"></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
    popupAnchor: [0, -9],
  });

const routeDistanceKm = (a: [number, number], b: [number, number]) => {
  const radius = 6371;
  const dLat = ((b[0] - a[0]) * Math.PI) / 180;
  const dLng = ((b[1] - a[1]) * Math.PI) / 180;
  const startLat = (a[0] * Math.PI) / 180;
  const endLat = (b[0] * Math.PI) / 180;
  const value = Math.sin(dLat / 2) ** 2 + Math.cos(startLat) * Math.cos(endLat) * Math.sin(dLng / 2) ** 2;
  return 2 * radius * Math.atan2(Math.sqrt(value), Math.sqrt(1 - value));
};

type OfficerRow = {
  id: string;
  team_name: string;
  total_strength: number;
  available: number;
  status: 'Available' | 'On Duty' | 'Off Shift' | 'On Leave';
  editing?: boolean;
};

type VehicleRow = {
  id: string;
  vehicle_id: string;
  type: string;
  status: 'Available' | 'Deployed' | 'Maintenance' | 'Offline';
  assigned_to: string;
  editing?: boolean;
};

export function DispatchCenterView() {
  const { theme } = useContext(ThemeContext);
  const location = useLocation();
  const [selectedQueueId, setSelectedQueueId] = useState<string | null>(null);
  const [officerRows, setOfficerRows] = useState<OfficerRow[]>([]);
  const [vehicleRows, setVehicleRows] = useState<VehicleRow[]>([]);
  const [selectedTeams, setSelectedTeams] = useState<string[]>([]);
  const [selectedVehicles, setSelectedVehicles] = useState<string[]>([]);
  const [notes, setNotes] = useState('');
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [updatingStatus, setUpdatingStatus] = useState<string | null>(null);

  const { data, loading, timedOut, error, refresh } = useTimedResource(async () => {
    const [queue, deployments, resources, hotspots, stats, officers, vehicles] = await Promise.all([
      api.getDispatchQueue(),
      api.getDispatchDeployments(),
      api.getDispatchResources(),
      api.getHotspots({ mode: 'LIVE' }),
      api.getStats(),
      api.getOfficers(),
      api.getVehicles(),
    ]);
    return { queue, deployments, resources, hotspots, stats, officers, vehicles };
  }, []);

  useEffect(() => {
    const state = location.state as { hotspotId?: string } | null;
    if (state?.hotspotId) setSelectedQueueId(state.hotspotId);
  }, [location.state]);

  useEffect(() => {
    if (!data) return;
    if (!selectedQueueId && data.queue.length > 0) setSelectedQueueId(data.queue[0].hotspot_id);
    setOfficerRows(data.officers.map(o => ({ ...o, editing: false })));
    setVehicleRows(data.vehicles.map(v => ({ ...v, editing: false })));
  }, [data, selectedQueueId]);

  useEffect(() => {
    if (!statusMessage) return;
    const timer = window.setTimeout(() => setStatusMessage(null), 5000);
    return () => window.clearTimeout(timer);
  }, [statusMessage]);

  useEffect(() => {
    if (selectedQueueId) {
      const element = document.getElementById(`queue-item-${selectedQueueId}`);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }
  }, [selectedQueueId]);

  const queue = data?.queue ?? [];
  const deployments = data?.deployments ?? [];
  const hotspots = data?.hotspots ?? [];
  const resources = data?.resources;
  const selectedQueue = queue.find((item) => item.hotspot_id === selectedQueueId) ?? null;
  const selectedHotspot = hotspots.find((item) => item.id === selectedQueueId) ?? null;
  const route = selectedHotspot ? ([station, [selectedHotspot.lat, selectedHotspot.lng]] as [number, number][]) : [];
  const routeKm = selectedHotspot ? routeDistanceKm(station, [selectedHotspot.lat, selectedHotspot.lng]) : 0;
  const etaMinutes = selectedHotspot ? Math.max(4, Math.round(routeKm * 4.2 + (selectedHotspot.riskScore ?? 0) / 20)) : 0;

  const totalOfficers = officerRows.reduce((sum, row) => sum + (row.total_strength ?? 0), 0);
  const availableOfficers = officerRows.reduce((sum, row) => sum + (row.available ?? 0), 0);
  const totalVehicles = vehicleRows.length;
  const availableVehicles = vehicleRows.filter((row) => row.status === 'Available').length;

  const assignedOfficers = useMemo(() => {
    return officerRows
      .filter((row) => selectedTeams.includes(row.id))
      .reduce((sum, row) => sum + (row.available ?? 0), 0);
  }, [officerRows, selectedTeams]);

  const assignedVehicles = useMemo(() => {
    return vehicleRows
      .filter((row) => selectedVehicles.includes(row.id))
      .length;
  }, [vehicleRows, selectedVehicles]);

  const submitDispatch = async () => {
    if (!selectedQueue) return;
    if (assignedOfficers === 0 && assignedVehicles === 0) {
      setStatusMessage('Please select at least one available team or vehicle from the tables.');
      return;
    }
    if (assignedOfficers > availableOfficers || assignedVehicles > availableVehicles) {
      setStatusMessage('Cannot over-assign resources beyond available count.');
      return;
    }
    try {
      const response = await api.assignDispatch(
        selectedQueue.hotspot_id,
        assignedOfficers,
        assignedVehicles,
        notes,
        selectedTeams,
        selectedVehicles
      );
      setStatusMessage(`Deployment ${response.deployment_id.slice(0, 8).toUpperCase()} created.`);
      setNotes('');
      setSelectedTeams([]);
      setSelectedVehicles([]);
      await refresh();
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : 'Unable to create deployment.');
    }
  };

  const updateDeploymentStatus = async (deployment: DeploymentItem, nextStatus: string) => {
    setUpdatingStatus(deployment.id);
    try {
      let outcome: string | undefined;
      if (nextStatus === 'Resolved') {
        outcome = prompt('Enter resolution outcome:', 'Situation cleared and resolved') || 'Situation cleared';
      }
      await api.updateDispatchStatus(deployment.id, nextStatus, outcome);
      await refresh();
    } finally {
      setUpdatingStatus(null);
    }
  };

  const handleDeleteDeployment = async (id: string) => {
    if (!confirm('Are you sure you want to delete this deployment?')) return;
    try {
      await api.deleteDeployment(id);
      setStatusMessage('Deployment deleted successfully.');
      await refresh();
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : 'Unable to delete deployment.');
    }
  };

  const saveOfficerRow = async (row: OfficerRow) => {
    try {
      const payload = {
        team_name: row.team_name,
        total_strength: row.total_strength,
        available: row.available,
        status: row.status,
      };
      if (row.id.startsWith('temp-')) {
        await api.addOfficer(payload);
      } else {
        await api.editOfficer(row.id, payload);
      }
      setStatusMessage('Team details saved.');
      await refresh();
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : 'Unable to save team.');
    }
  };

  const saveVehicleRow = async (row: VehicleRow) => {
    try {
      const payload = {
        vehicle_id: row.vehicle_id,
        type: row.type,
        status: row.status,
        assigned_to: row.assigned_to,
      };
      if (row.id.startsWith('temp-')) {
        await api.addVehicle(payload);
      } else {
        await api.editVehicle(row.id, payload);
      }
      setStatusMessage('Vehicle details saved.');
      await refresh();
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : 'Unable to save vehicle.');
    }
  };

  const deleteOfficerRow = async (id: string) => {
    if (id.startsWith('temp-')) {
      setOfficerRows((prev) => prev.filter((row) => row.id !== id));
      return;
    }
    if (!confirm('Delete this team?')) return;
    try {
      await api.deleteOfficer(id);
      setStatusMessage('Team deleted.');
      await refresh();
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : 'Unable to delete team.');
    }
  };

  const deleteVehicleRow = async (id: string) => {
    if (id.startsWith('temp-')) {
      setVehicleRows((prev) => prev.filter((row) => row.id !== id));
      return;
    }
    if (!confirm('Delete this vehicle?')) return;
    try {
      await api.deleteVehicle(id);
      setStatusMessage('Vehicle deleted.');
      await refresh();
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : 'Unable to delete vehicle.');
    }
  };

  const addOfficerRow = () =>
    setOfficerRows((current) => [
      ...current,
      { id: `temp-team-${Date.now()}`, team_name: 'New Team', total_strength: 0, available: 0, status: 'Off Shift', editing: true },
    ]);

  const addVehicleRow = () =>
    setVehicleRows((current) => [
      ...current,
      { id: `temp-veh-${Date.now()}`, vehicle_id: 'New Vehicle', type: 'Patrol', status: 'Offline', assigned_to: 'Unassigned', editing: true },
    ]);

  if (loading) return <LoadingSpinner />;
  if (timedOut) return <OfflineState message="Dispatch data is taking too long to load." onAction={refresh} />;
  if (error) return <OfflineState message={error} onAction={refresh} />;
  if (!data) return <EmptyState message="No dispatch data could be loaded." />;

  return (
    <div className="space-y-6">
      <div className="section-heading">
        <div>
          <div className="eyebrow">Tactical command</div>
          <h1>Dispatch Center</h1>
        </div>
        <div className="section-meta">
          <StatusPill tone="neutral" label={`Last updated ${formatRelativeTime(data.stats.timestamp)}`} />
          <button type="button" className="btn btn--ghost" onClick={refresh}>
            Refresh
          </button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <div className="panel-stat"><span>Available officers</span><strong>{availableOfficers}</strong><small>of {totalOfficers}</small></div>
        <div className="panel-stat"><span>Available vehicles</span><strong>{availableVehicles}</strong><small>of {totalVehicles}</small></div>
        <div className="panel-stat"><span>Active deployments</span><strong>{resources?.summary.activeDeployments ?? 0}</strong><small>Currently in the field</small></div>
        <div className="panel-stat"><span>Resolved today</span><strong>{resources?.summary.resolvedDeploymentsToday ?? 0}</strong><small>Closed this shift</small></div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.4fr_0.6fr]">
        <section className="panel-card">
          <div className="panel-card__header">
            <h2>Priority queue</h2>
            <span className="muted-text">Top 5 hotspots</span>
          </div>
          <div className="mt-4 space-y-3" style={{ maxHeight: '400px', overflowY: 'auto' }}>
            {queue.slice(0, 5).map((item, index) => (
              <button key={item.hotspot_id} id={`queue-item-${item.hotspot_id}`} type="button" className={selectedQueueId === item.hotspot_id ? 'queue-card active' : 'queue-card'} onClick={() => setSelectedQueueId(item.hotspot_id)}>
                <div>
                  <strong>#{index + 1} {item.hotspot_name}</strong>
                  <small>{item.current_violations} violations · {item.first_detected_at ? `first detected ${formatRelativeTime(item.first_detected_at)}` : 'live'}</small>
                </div>
                <div className="text-right">
                  <strong>{(item.priority_score ?? 0).toFixed(1)}</strong>
                  <small>{item.severity}</small>
                </div>
              </button>
            ))}
          </div>
        </section>

        <section className="panel-card">
          <div className="panel-card__header">
            <h2>Live Dispatch Map</h2>
            <span className="muted-text">Station marker, hotspots, route line</span>
          </div>
          <div className="map-shell mt-5">
            <MapContainer center={station} zoom={12} style={{ height: '100%', width: '100%' }}>
              <TileLayer
                url={theme === 'dark' ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png' : 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'}
                attribution='&copy; CartoDB'
              />
              <Marker position={station} icon={icon('#38bdf8')}>
                <Popup>Dispatch station</Popup>
              </Marker>
              {hotspots.map((hotspot) => (
                <Marker key={hotspot.id} position={[hotspot.lat, hotspot.lng]} icon={icon(hotspot.riskScore >= 85 ? '#ef4444' : hotspot.riskScore >= 70 ? '#f97316' : '#eab308')}>
                  <Popup>
                    <strong>{hotspot.name}</strong>
                    <div>{(hotspot.riskScore ?? 0).toFixed(1)}% risk</div>
                    <div>{hotspot.violations} violations</div>
                  </Popup>
                </Marker>
              ))}
              {selectedHotspot && <Polyline positions={route} pathOptions={{ color: '#38bdf8', weight: 3 }} />}
            </MapContainer>
          </div>
          {selectedHotspot && (
            <div className="mt-4 grid gap-4 md:grid-cols-4">
              <div className="stat-mini"><span>Distance</span><strong>{(routeKm ?? 0).toFixed(2)} km</strong></div>
              <div className="stat-mini"><span>ETA</span><strong>{etaMinutes} mins</strong></div>
              <div className="stat-mini"><span>Risk</span><strong>{(selectedHotspot.riskScore ?? 0).toFixed(1)}%</strong></div>
              <div className="stat-mini"><span>Status</span><strong>{selectedQueue?.severity ?? 'Queued'}</strong></div>
            </div>
          )}
        </section>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.4fr_0.6fr]">
        <section className="panel-card">
          <div className="panel-card__header">
            <div>
              <h2>Create Deployment</h2>
              <span className="muted-text">Select available teams/vehicles from the tables below to assign them.</span>
            </div>
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <div className="panel-stat"><span>Assigned officers</span><strong>{assignedOfficers}</strong></div>
            <div className="panel-stat"><span>Assigned vehicles</span><strong>{assignedVehicles}</strong></div>
            <div className="panel-stat"><span>Route ETA</span><strong>{etaMinutes} mins</strong></div>
          </div>
          <label className="form-field mt-4">
            <span>Notes</span>
            <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} placeholder="Add dispatch notes or instructions." />
          </label>
          <button type="button" className="btn btn--amber mt-4 w-full" onClick={() => void submitDispatch()} disabled={!selectedQueue || (assignedOfficers === 0 && assignedVehicles === 0)}>
            Create deployment
          </button>
        </section>

        <section className="panel-card">
          <div className="panel-card__header">
            <h2>Active Hotspot Recommendations</h2>
          </div>
          {selectedQueue ? (
            <div className="mt-4 space-y-3">
              <div className="rounded-2xl border border-white/5 bg-white/5 p-4">
                <h4 className="text-md font-semibold text-white mb-2">{selectedQueue.hotspot_name} Recommended Resources</h4>
                <div className="grid grid-cols-2 gap-4 text-sm mt-3">
                  <div>
                    <span className="text-slate-400">Officers Needed:</span>
                    <strong className="block text-lg text-white mt-1">{selectedQueue.recommended_officers}</strong>
                  </div>
                  <div>
                    <span className="text-slate-400">Patrol Vehicles Needed:</span>
                    <strong className="block text-lg text-white mt-1">{selectedQueue.recommended_patrol_vehicles}</strong>
                  </div>
                </div>
                <div className="mt-4 border-t border-white/5 pt-3">
                  <span className="text-xs text-slate-400 uppercase tracking-wider block mb-1">Recommended Actions</span>
                  <p className="text-sm text-slate-200 italic">"{selectedQueue.action_recommendation}"</p>
                </div>
              </div>
            </div>
          ) : (
            <EmptyState message="No hotspot selected from queue." />
          )}
        </section>
      </div>

      <section className="panel-card">
        <div className="panel-card__header">
          <h2>Resource Management</h2>
          <span className="muted-text">Add, edit, or delete operational units in real-time.</span>
        </div>
        <div className="mt-5 grid gap-6 xl:grid-cols-2">
          <div>
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-white">Officer Teams</h3>
              <button type="button" className="btn btn--ghost btn--sm" onClick={addOfficerRow}>
                Add New Team
              </button>
            </div>
            <div className="overflow-hidden rounded-3xl border border-white/5">
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ width: '40px' }}>Select</th>
                    <th>Team Name</th>
                    <th>Total Strength</th>
                    <th>Available</th>
                    <th>Status</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {officerRows.map((row, index) => (
                    <tr key={row.id}>
                      <td>
                        <input
                          type="checkbox"
                          checked={selectedTeams.includes(row.id)}
                          onChange={() => {
                            if (row.status !== 'Available') return;
                            setSelectedTeams((prev) =>
                              prev.includes(row.id) ? prev.filter((id) => id !== row.id) : [...prev, row.id]
                            );
                          }}
                          disabled={row.status !== 'Available' || row.id.startsWith('temp-')}
                        />
                      </td>
                      <td>{row.editing ? <input className="w-full rounded-lg bg-[var(--bg-app)] border border-[var(--border-color)] px-2 py-1 text-[var(--text-primary)]" value={row.team_name} onChange={(e) => setOfficerRows((current) => current.map((item, idx) => idx === index ? { ...item, team_name: e.target.value } : item))} /> : row.team_name}</td>
                      <td>{row.editing ? <input type="number" className="w-24 rounded-lg bg-[var(--bg-app)] border border-[var(--border-color)] px-2 py-1 text-[var(--text-primary)]" value={row.total_strength} onChange={(e) => setOfficerRows((current) => current.map((item, idx) => idx === index ? { ...item, total_strength: Number(e.target.value) } : item))} /> : row.total_strength}</td>
                      <td>{row.editing ? <input type="number" className="w-24 rounded-lg bg-[var(--bg-app)] border border-[var(--border-color)] px-2 py-1 text-[var(--text-primary)]" value={row.available} onChange={(e) => setOfficerRows((current) => current.map((item, idx) => idx === index ? { ...item, available: Number(e.target.value) } : item))} /> : row.available}</td>
                      <td>{row.editing ? <select className="rounded-lg bg-[var(--bg-app)] border border-[var(--border-color)] px-2 py-1 text-[var(--text-primary)]" value={row.status} onChange={(e) => setOfficerRows((current) => current.map((item, idx) => idx === index ? { ...item, status: e.target.value as OfficerRow['status'] } : item))}><option style={{ background: 'var(--bg-card)', color: 'var(--text-primary)' }}>Available</option><option style={{ background: 'var(--bg-card)', color: 'var(--text-primary)' }}>On Duty</option><option style={{ background: 'var(--bg-card)', color: 'var(--text-primary)' }}>Off Shift</option><option style={{ background: 'var(--bg-card)', color: 'var(--text-primary)' }}>On Leave</option></select> : row.status}</td>
                      <td className="space-x-2">
                        {row.editing ? (
                          <button type="button" className="btn btn--ghost btn--sm" onClick={() => void saveOfficerRow(row)}>
                            Save
                          </button>
                        ) : (
                          <button type="button" className="btn btn--ghost btn--sm" onClick={() => setOfficerRows((current) => current.map((item, idx) => idx === index ? { ...item, editing: true } : item))}>
                            Edit
                          </button>
                        )}
                        <button type="button" className="btn btn--ghost btn--sm" onClick={() => void deleteOfficerRow(row.id)}>
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-white">Patrol Vehicles</h3>
              <button type="button" className="btn btn--ghost btn--sm" onClick={addVehicleRow}>
                Add New Vehicle
              </button>
            </div>
            <div className="overflow-hidden rounded-3xl border border-white/5">
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ width: '40px' }}>Select</th>
                    <th>Vehicle ID</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Assigned To</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {vehicleRows.map((row, index) => (
                    <tr key={row.id}>
                      <td>
                        <input
                          type="checkbox"
                          checked={selectedVehicles.includes(row.id)}
                          onChange={() => {
                            if (row.status !== 'Available') return;
                            setSelectedVehicles((prev) =>
                              prev.includes(row.id) ? prev.filter((id) => id !== row.id) : [...prev, row.id]
                            );
                          }}
                          disabled={row.status !== 'Available' || row.id.startsWith('temp-')}
                        />
                      </td>
                      <td>{row.editing ? <input className="w-full rounded-lg bg-[var(--bg-app)] border border-[var(--border-color)] px-2 py-1 text-[var(--text-primary)]" value={row.vehicle_id} onChange={(e) => setVehicleRows((current) => current.map((item, idx) => idx === index ? { ...item, vehicle_id: e.target.value } : item))} /> : row.vehicle_id}</td>
                      <td>{row.editing ? <input className="w-full rounded-lg bg-[var(--bg-app)] border border-[var(--border-color)] px-2 py-1 text-[var(--text-primary)]" value={row.type} onChange={(e) => setVehicleRows((current) => current.map((item, idx) => idx === index ? { ...item, type: e.target.value } : item))} /> : row.type}</td>
                      <td>{row.editing ? <select className="rounded-lg bg-[var(--bg-app)] border border-[var(--border-color)] px-2 py-1 text-[var(--text-primary)]" value={row.status} onChange={(e) => setVehicleRows((current) => current.map((item, idx) => idx === index ? { ...item, status: e.target.value as VehicleRow['status'] } : item))}><option style={{ background: 'var(--bg-card)', color: 'var(--text-primary)' }}>Available</option><option style={{ background: 'var(--bg-card)', color: 'var(--text-primary)' }}>Deployed</option><option style={{ background: 'var(--bg-card)', color: 'var(--text-primary)' }}>Maintenance</option><option style={{ background: 'var(--bg-card)', color: 'var(--text-primary)' }}>Offline</option></select> : row.status}</td>
                      <td>{row.editing ? <select className="rounded-lg bg-[var(--bg-app)] border border-[var(--border-color)] px-2 py-1 text-[var(--text-primary)]" value={row.assigned_to} onChange={(e) => setVehicleRows((current) => current.map((item, idx) => idx === index ? { ...item, assigned_to: e.target.value } : item))}><option style={{ background: 'var(--bg-card)', color: 'var(--text-primary)' }}>Unassigned</option>{deployments.map((deployment) => <option key={deployment.id} style={{ background: 'var(--bg-card)', color: 'var(--text-primary)' }}>{deployment.hotspot_name}</option>)}</select> : row.assigned_to}</td>
                      <td className="space-x-2">
                        {row.editing ? (
                          <button type="button" className="btn btn--ghost btn--sm" onClick={() => void saveVehicleRow(row)}>
                            Save
                          </button>
                        ) : (
                          <button type="button" className="btn btn--ghost btn--sm" onClick={() => setVehicleRows((current) => current.map((item, idx) => idx === index ? { ...item, editing: true } : item))}>
                            Edit
                          </button>
                        )}
                        <button type="button" className="btn btn--ghost btn--sm" onClick={() => void deleteVehicleRow(row.id)}>
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>

      <section className="panel-card">
        <div className="panel-card__header">
          <h2>Deployment history</h2>
          <span className="muted-text">Outcome included</span>
        </div>
        <div className="mt-4 overflow-hidden rounded-3xl border border-white/5">
          <table className="data-table">
            <thead>
              <tr>
                <th>Junction</th>
                <th>Status</th>
                <th>Outcome</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {deployments.length === 0 ? (
                <tr>
                  <td colSpan={5}>
                    <EmptyState message="No deployments have been created yet." />
                  </td>
                </tr>
              ) : (
                deployments.map((deployment) => (
                  <tr key={deployment.id}>
                    <td>{deployment.hotspot_name}</td>
                    <td>{deployment.status}</td>
                    <td>{deployment.outcome || 'Pending'}</td>
                    <td>{formatAbsoluteTime(deployment.created_at)}</td>
                    <td className="space-x-2">
                      {deployment.status !== 'Resolved' ? (
                        <div className="flex flex-wrap gap-2">
                          {(['En Route', 'On Site', 'Resolved'] as const).map((next) => (
                            <button key={next} type="button" className="btn btn--ghost btn--sm" onClick={() => void updateDeploymentStatus(deployment, next)} disabled={updatingStatus === deployment.id && deployment.status === next}>
                              {updatingStatus === deployment.id && deployment.status === next ? 'Updating...' : next}
                            </button>
                          ))}
                          <button type="button" className="btn btn--ghost btn--sm btn--danger" onClick={() => void handleDeleteDeployment(deployment.id)}>
                            Delete
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2">
                          <StatusPill tone="good" label="Closed" />
                          <button type="button" className="btn btn--ghost btn--sm btn--danger" onClick={() => void handleDeleteDeployment(deployment.id)}>
                            Delete
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {statusMessage && <div className="alert-banner alert-banner--floating">{statusMessage}</div>}
    </div>
  );
}
