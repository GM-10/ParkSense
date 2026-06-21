import { createContext, useEffect, useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { GlobalHeader } from './components/GlobalHeader';
import { useStore } from './store/useStore';

export const ThemeContext = createContext<{ theme: 'dark' | 'light'; toggleTheme: () => void }>({
  theme: 'dark',
  toggleTheme: () => {},
});

const nav = [
  ['/command-center', 'Command Center'],
  ['/dispatch', 'Dispatch Center'],
  ['/alerts', 'Alerts Center'],
  ['/incidents', 'Incident Reporting'],
  ['/reports', 'Reports Center'],
  ['/ai-copilot', 'AI Copilot'],
] as const;

export default function Layout() {
  const bootstrapPlatform = useStore((state) => state.bootstrapPlatform);
  const alertCount = useStore((state) => state.alertCount);
  const [theme, setTheme] = useState<'dark' | 'light'>((localStorage.getItem('parksense_theme') as 'dark' | 'light') ?? 'dark');
  const [isCollapsed, setIsCollapsed] = useState(false);

  useEffect(() => {
    document.documentElement.classList.remove('light', 'dark');
    document.documentElement.classList.add(theme);
    localStorage.setItem('parksense_theme', theme);
    window.dispatchEvent(new CustomEvent('parksense-theme-change', { detail: theme }));
  }, [theme]);

  useEffect(() => {
    void bootstrapPlatform();
    const bootstrapTimer = window.setInterval(() => void bootstrapPlatform(), 30000);
    return () => {
      window.clearInterval(bootstrapTimer);
    };
  }, [bootstrapPlatform]);

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme: () => setTheme((value) => (value === 'dark' ? 'light' : 'dark')) }}>
      <div className={`app-frame ${isCollapsed ? 'collapsed' : ''}`}>
        <aside className="sidebar">
          <div className="brand">
            <div className="brand-mark">
              <span />
              <span />
              <span />
            </div>
            <div className={isCollapsed ? 'hidden' : ''}>
              <strong>PARKSENSE</strong>
              <small>TRAFFIC INTELLIGENCE PLATFORM</small>
            </div>
            <button
              className="sidebar-toggle"
              onClick={() => setIsCollapsed(!isCollapsed)}
              title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
            >
              {isCollapsed ? '→' : '←'}
            </button>
          </div>

          <nav>
            {nav.map(([to, label]) => (
              <NavLink key={to} to={to} end={to === '/command-center'} className={({ isActive }) => (isActive ? 'active' : '')}>
                <span className={isCollapsed ? 'hidden' : ''}>{label}</span>
                {label === 'Alerts Center' && alertCount > 0 && <b>{alertCount}</b>}
              </NavLink>
            ))}
          </nav>

          <div className="sidebar-bottom">
            <div className={`version ${isCollapsed ? 'hidden' : ''}`}>ParkSense v2.0 · Traffic Intelligence</div>
          </div>
        </aside>

        <div className="content">
          <GlobalHeader />
          <main className="page-shell">
            <Outlet />
          </main>
        </div>
      </div>
    </ThemeContext.Provider>
  );
}
