import { useEffect, useMemo, useState } from 'react';
import { useStore } from '../store/useStore';
import { LoadingSpinner, OfflineState } from '../components/LoaderStates';
import { formatRelativeTime } from '../lib/time';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from '../recharts';

export function HistoricalIntelligence() {
  const historical = useStore((state) => state.historical);
  const refreshHistorical = useStore((state) => state.refreshHistorical);
  const platformOnline = useStore((state) => state.platformOnline);
  const lastSync = useStore((state) => state.lastSync);
  const [range, setRange] = useState<'24h' | '7d' | '30d'>('24h');

  useEffect(() => {
    void refreshHistorical(range);
  }, [range, refreshHistorical]);

  const data = historical[range];

  const formatBucketLabel = useMemo(() => (label: string) => {
    try {
      const date = new Date(label);
      if (isNaN(date.getTime())) return label;
      if (range === '24h') return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      if (range === '7d') return date.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
      return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch {
      return label;
    }
  }, [range]);

  if (!platformOnline) return <OfflineState message="Start the API server to load Historical Intelligence data" onAction={() => void refreshHistorical(range)} />;
  if (!data) return <LoadingSpinner />;


  return (
    <div className="space-y-6 text-white p-2">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-xs uppercase tracking-[0.3em] text-amber-300 font-semibold">Audit Logs</span>
          <h1 className="text-3xl font-extrabold tracking-tight mt-1">Historical Intelligence</h1>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs text-slate-400">Last updated {lastSync ? formatRelativeTime(lastSync) : 'never'}</span>
          <button onClick={() => void refreshHistorical(range)} className="rounded-full bg-slate-800 hover:bg-slate-700 text-slate-300 p-2 text-sm px-4 transition-colors">
            Refresh
          </button>
          <div className="rounded-full border border-slate-800 bg-slate-900/60 p-1 flex gap-1">
            {(['24h', '7d', '30d'] as const).map((r) => (
              <button key={r} onClick={() => setRange(r)} className={`rounded-full px-5 py-1.5 text-xs font-bold uppercase transition-all ${range === r ? 'bg-amber-500 text-slate-950 shadow-md' : 'text-slate-300 hover:text-white'}`}>
                {r}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="rounded-3xl border border-slate-800 bg-slate-900/40 p-6 backdrop-blur-md">
        <h2 className="text-lg font-bold text-white mb-4">Enforcement Violations Trend</h2>
        <div className="h-[360px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.buckets}>
              <CartesianGrid stroke="#262626" strokeDasharray="3 3" />
              <XAxis dataKey="label" stroke="#b0b0b0" fontSize={11} tickFormatter={formatBucketLabel} />
              <YAxis stroke="#b0b0b0" fontSize={12} />
              <Tooltip contentStyle={{ backgroundColor: '#121212', borderColor: '#262626', borderRadius: '12px' }} />
              <Bar dataKey="violations" fill="#f59e0b" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="rounded-3xl border border-slate-800 bg-slate-900/40 p-6 backdrop-blur-md">
        <h2 className="text-xl font-bold tracking-tight text-white mb-4">Top 5 Hotspot Junctions for this period</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-950 text-xs uppercase tracking-wider text-slate-400 font-bold">
              <tr>
                <th className="px-6 py-4 rounded-l-2xl">Rank</th>
                <th className="px-6 py-4">Junction Name</th>
                <th className="px-6 py-4">Violations Count</th>
                <th className="px-6 py-4 rounded-r-2xl">Assigned Risk</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/40">
              {data.topJunctions.map((item, index) => (
                <tr key={item.name} className="hover:bg-slate-900/20">
                  <td className="px-6 py-4 font-mono font-bold text-amber-400">#{index + 1}</td>
                  <td className="px-6 py-4 font-semibold text-white">{item.name}</td>
                  <td className="px-6 py-4 font-mono">{item.violations}</td>
                  <td className="px-6 py-4"><span className="font-semibold text-amber-400 font-mono">{item.risk.toFixed(1)}%</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
