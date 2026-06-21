import { useEffect, useState } from 'react';
import { api, type Hotspot, type StatsResponse } from '../api/client';
import { LoadingSpinner, OfflineState, EmptyState } from '../components/LoaderStates';
import { formatRelativeTime } from '../lib/time';

const colorForRisk = (risk: number) => {
  if (risk < 40) return 'bg-green-950/40 text-green-400 border-green-500/20';
  if (risk < 70) return 'bg-yellow-950/40 text-yellow-400 border-yellow-500/20';
  if (risk < 85) return 'bg-orange-950/40 text-orange-400 border-orange-500/20';
  return 'bg-rose-950/40 text-rose-400 border-rose-500/20';
};

const trendArrow = (trend: string) => {
  if (trend === 'increasing') return '📈 Increasing';
  if (trend === 'decreasing') return '📉 Decreasing';
  if (trend === 'stable') return '➡️ Stable';
  return '❓ Unknown';
};

export function LiveIntelligence() {
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [congestionFilter, setCongestionFilter] = useState('ALL');

  const fetchData = async () => {
    setLoading(true);
    setOffline(false);
    try {
      const [statsData, hotspotsData] = await Promise.all([
        api.getStats(),
        api.getHotspots({ mode: 'LIVE' }),
      ]);
      setStats(statsData);
      setHotspots(hotspotsData);
    } catch (err) {
      setOffline(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const filteredHotspots = hotspots
    .filter((h) => {
      const matchesSearch = h.name.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesCongestion =
        congestionFilter === 'ALL' ||
        h.congestionLevel.toUpperCase() === congestionFilter.toUpperCase();
      return matchesSearch && matchesCongestion;
    })
    .sort((a, b) => b.riskScore - a.riskScore);

  if (loading) return <LoadingSpinner />;
  if (offline) return <OfflineState message="Backend is offline. Start the API server to load Live Intelligence data." onAction={fetchData} />;
  if (!stats) return <EmptyState message="No live data available yet." />;

  return (
    <div className="space-y-6 text-white p-2">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-xs uppercase tracking-[0.3em] text-amber-300 font-semibold">Live Feed</span>
          <h1 className="text-3xl font-extrabold tracking-tight mt-1">Live Traffic Intelligence</h1>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs text-slate-400">Last updated {formatRelativeTime(stats.timestamp)}</span>
          <button
            onClick={fetchData}
            className="rounded-full bg-slate-800 hover:bg-slate-700 text-slate-300 p-2 text-sm flex items-center gap-2 px-4 transition-colors"
          >
            🔄 Refresh Feed
          </button>
        </div>
      </div>

      {/* Top row: 4 stat cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: 'Total Violations', value: stats.totalViolations, desc: 'Across current active period' },
          { label: 'Avg Risk Score', value: `${stats.avgRiskScore.toFixed(1)}%`, desc: 'Average of active hotspots' },
          { label: 'Critical Zones', value: stats.criticalZones, desc: 'Hotspots requiring immediate dispatch' },
          { label: 'Active Officers', value: stats.activeOfficers, desc: 'Deployed enforcement officers' },
        ].map((item, idx) => (
          <div key={idx} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-md">
            <div className="text-xs uppercase tracking-wider text-slate-500 font-bold">{item.label}</div>
            <div className="mt-3 text-3xl font-black text-white">{item.value}</div>
            <div className="mt-2 text-xs text-slate-400">{item.desc}</div>
          </div>
        ))}
      </div>

      {/* Search / Filter Bar */}
      <div className="flex flex-col sm:flex-row gap-4 p-4 rounded-3xl border border-slate-800 bg-slate-900/40 backdrop-blur-md">
        <input
          type="text"
          placeholder="Search by junction or locality..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="flex-1 rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm text-white focus:border-amber-500 focus:outline-none"
        />
        <select
          value={congestionFilter}
          onChange={(e) => setCongestionFilter(e.target.value)}
          className="rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm text-white focus:border-amber-500 focus:outline-none min-w-[160px]"
        >
          <option value="ALL">All Congestion</option>
          <option value="CRITICAL">Critical</option>
          <option value="HIGH">High</option>
          <option value="MODERATE">Moderate</option>
          <option value="LOW">Low</option>
        </select>
      </div>

      {/* Hotspots Grid */}
      {filteredHotspots.length === 0 ? (
        <EmptyState message="No hotspots found matching your search criteria." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filteredHotspots.map((item) => (
            <div key={item.id} className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5 backdrop-blur-sm hover:border-slate-700 transition-all flex flex-col justify-between space-y-4">
              <div className="flex items-start justify-between gap-4">
                <strong className="text-base font-extrabold tracking-tight text-white line-clamp-1">{item.name}</strong>
                <span className={`text-xs font-mono font-bold px-2.5 py-1 rounded-full border ${colorForRisk(item.riskScore)}`}>
                  {item.riskScore.toFixed(1)}% Risk
                </span>
              </div>
              <div className="space-y-2 text-sm text-slate-300">
                <div className="flex justify-between border-b border-slate-800/40 pb-1">
                  <span className="text-slate-500">Violations:</span>
                  <span className="font-semibold text-white">{item.violations}</span>
                </div>
                <div className="flex justify-between border-b border-slate-800/40 pb-1">
                  <span className="text-slate-500">Congestion:</span>
                  <span className="font-semibold text-white">{item.congestionLevel}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Trend Status:</span>
                  <span className="font-semibold text-white">{trendArrow(item.trend)}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
