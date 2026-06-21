import { useContext, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ThemeContext } from '../Layout';
import { useStore } from '../store/useStore';
import { formatRelativeTime } from '../lib/time';
import { api } from '../api/client';

const titles: Record<string, string> = {
  '/command-center': 'Command Center',
  '/dispatch': 'Dispatch Center',
  '/alerts': 'Alerts Center',
  '/incidents': 'Incident Reporting',
  '/reports': 'Reports Center',
  '/ai-copilot': 'AI Copilot',
};

export function GlobalHeader() {
  const location = useLocation();
  const navigate = useNavigate();
  const { theme, toggleTheme } = useContext(ThemeContext);
  const lastSync = useStore((state) => state.lastSync);
  const activeTimeline = useStore((state) => state.activeTimeline);
  const setActiveTimeline = useStore((state) => state.setActiveTimeline);
  const activeTitle = useMemo(() => titles[location.pathname] ?? 'ParkSense', [location.pathname]);
  const username = localStorage.getItem('parksense_username') ?? 'Signed in user';

  const timelineOptions = [
    { value: '2023-11', label: 'November 2023' },
    { value: '2023-12', label: 'December 2023' },
    { value: '2024-01', label: 'January 2024' },
    { value: '2024-02', label: 'February 2024' },
    { value: '2024-03', label: 'March 2024' },
    { value: '2024-04', label: 'April 2024' },
  ];

  const logout = async () => {
    try {
      await api.logout();
    } catch {
      // Network or offline logout failures still clear the local session.
    } finally {
      localStorage.removeItem('parksense_token');
      localStorage.removeItem('parksense_username');
      navigate('/login', { replace: true });
    }
  };

  return (
    <header className="global-header">
      <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
        <h1>{activeTitle}</h1>
        <div className="timeline-selector-wrapper" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '0.8rem', opacity: 0.7, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Timeline:</span>
          <select
            value={activeTimeline}
            onChange={(e) => void setActiveTimeline(e.target.value)}
            style={{
              background: 'var(--bg-card, #121212)',
              color: 'var(--text-primary, #ffffff)',
              border: '1px solid var(--border-color, #262626)',
              borderRadius: '6px',
              padding: '6px 12px',
              cursor: 'pointer',
              fontSize: '0.85rem',
              fontWeight: 500,
              outline: 'none',
            }}
          >
            {timelineOptions.map((opt) => (
              <option
                key={opt.value}
                value={opt.value}
                style={{
                  background: 'var(--bg-card, #121212)',
                  color: 'var(--text-primary, #ffffff)',
                }}
              >
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="global-header__meta">
        <span className="muted-text">{lastSync ? `Updated ${formatRelativeTime(lastSync)}` : 'Waiting for data'}</span>
        <span className="muted-text">{username}</span>
        <button type="button" className="btn btn--ghost btn-sm" onClick={logout}>
          Logout
        </button>
        <button type="button" className="theme-button" onClick={toggleTheme}>
          {theme === 'dark' ? 'Light' : 'Dark'}
        </button>
      </div>
    </header>
  );
}
