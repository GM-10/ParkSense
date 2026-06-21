import { useEffect, useMemo, useState } from 'react';
import { useStore } from '../store/useStore';
import { LoadingSpinner, OfflineState, EmptyState } from '../components/LoaderStates';
import { formatRelativeTime } from '../lib/time';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from '../recharts';

const colors = ['#f59e0b', '#22c55e', '#ef4444', '#a3a3a3', '#d97706'];

export function ForecastIntelligence() {
  const forecast = useStore((state) => state.forecast);
  const refreshAll = useStore((state) => state.refreshAll);
  const platformOnline = useStore((state) => state.platformOnline);
  const lastSync = useStore((state) => state.lastSync);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (forecast.length === 0) {
      setLoading(true);
      void refreshAll().finally(() => setLoading(false));
    }
  }, [forecast.length, refreshAll]);

  const top5Hotspots = useMemo(() => {
    const hotspotAverages = Array.from(
      forecast.reduce((acc, curr) => {
        const currentVal = acc.get(curr.hotspot_name) || { max: 0, id: curr.hotspot_id };
        acc.set(curr.hotspot_name, {
          max: Math.max(currentVal.max, curr.predictedRisk),
          id: curr.hotspot_id,
        });
        return acc;
      }, new Map<string, { max: number; id: string }>())
    );
    return hotspotAverages.sort((a, b) => b[1].max - a[1].max).slice(0, 5).map((item) => item[0]);
  }, [forecast]);

  const chartData = useMemo(() => Array.from({ length: 6 }, (_, i) => {
    const hour = i + 1;
    const row: any = { hour: `+${hour}h` };
    top5Hotspots.forEach((name) => {
      const match = forecast.find((item) => item.hotspot_name === name && item.hour_offset === hour);
      row[name] = match ? match.predictedRisk : null;
    });
    return row;
  }), [forecast, top5Hotspots]);

  const emerging = useMemo(() => forecast.filter((item) => item.predictedRisk >= 75), [forecast]);
  const uniqueEmerging = useMemo(() => Array.from(
    emerging.reduce((acc, curr) => {
      const existing = acc.get(curr.hotspot_name);
      if (!existing || existing.predictedRisk < curr.predictedRisk) acc.set(curr.hotspot_name, curr);
      return acc;
    }, new Map<string, typeof emerging[number]>()).values()
  ), [emerging]);

  if (loading) return <LoadingSpinner />;
  if (!platformOnline) return <OfflineState message="Start the API server to load Forecast Intelligence data" onAction={() => void refreshAll()} />;
  if (forecast.length === 0) return <EmptyState />;

  return (
    <div className="space-y-6 text-white p-2">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-xs uppercase tracking-[0.3em] text-amber-300 font-semibold">Risk Forecast</span>
          <h1 className="text-3xl font-extrabold tracking-tight mt-1">Forecast Intelligence</h1>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs text-slate-400">Last updated {lastSync ? formatRelativeTime(lastSync) : 'never'}</span>
          <button onClick={() => void refreshAll()} className="rounded-full bg-slate-800 hover:bg-slate-700 text-slate-300 p-2 text-sm px-4 transition-colors">
            Refresh Forecast
          </button>
        </div>
      </div>
      <div className="rounded-3xl border border-slate-800 bg-slate-900/40 p-6 backdrop-blur-md">
        <h2 className="text-lg font-bold text-white mb-4">6-Hour Risk Projections</h2>
        <div className="h-[420px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="#262626" strokeDasharray="3 3" />
              <XAxis dataKey="hour" stroke="#b0b0b0" fontSize={12} />
              <YAxis domain={[0, 100]} stroke="#b0b0b0" fontSize={12} />
              <Tooltip contentStyle={{ backgroundColor: '#121212', borderColor: '#262626', borderRadius: '12px' }} />
              <Legend />
              {top5Hotspots.map((name, idx) => (
                <Line key={name} type="monotone" dataKey={name} stroke={colors[idx % colors.length]} strokeWidth={2.5} dot={{ r: 4 }} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div>
        <h2 className="text-xl font-bold tracking-tight text-white mb-4">Emerging High-Risk Zones</h2>
        {uniqueEmerging.length === 0 ? (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/20 p-6 text-slate-400">No junctions are predicted to exceed the 75% risk threshold within the next 6 hours.</div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {uniqueEmerging.map((item) => (
              <div key={item.hotspot_id} className="rounded-2xl border border-amber-500/20 bg-amber-950/10 p-5 backdrop-blur-sm flex items-start justify-between gap-4">
                <div>
                  <h3 className="font-extrabold text-white text-lg">{item.hotspot_name}</h3>
                  <p className="text-sm text-slate-400 mt-1">Predicted to cross threshold by hour <span className="font-bold text-amber-300 font-mono">+{item.hour_offset}h</span></p>
                  <div className="mt-3 flex items-center gap-3">
                    <span className="text-xs text-slate-500 font-medium">Confidence Level</span>
                    <span className="text-xs font-bold font-mono px-2 py-0.5 rounded-full bg-slate-800 text-slate-300">{(item.confidence * 100).toFixed(0)}% Match</span>
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-xs text-slate-500 block uppercase font-bold">Predicted Risk</span>
                  <span className="text-2xl font-black text-amber-500 font-mono block mt-1">{item.predictedRisk.toFixed(1)}%</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
