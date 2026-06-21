import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactElement } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import Layout from './Layout';
import { ErrorBoundary } from './components/ErrorBoundary';
import { LoginPage } from './views/LoginPage';
import { CommandCenterView } from './views/CommandCenterView';
import { DispatchCenterView } from './views/DispatchCenterView';
import { AlertsCenter } from './views/AlertsCenter';
import { IncidentReportingView } from './views/IncidentReportingView';
import { ReportsCenter } from './views/ReportsCenter';
import { AIAgentView } from './views/AIAgentView';
import './App.css';
import './gis.css';

const queryClient = new QueryClient();

function RequireAuth({ children }: { children: ReactElement }) {
  const token = localStorage.getItem('parksense_token');
  if (!token) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ErrorBoundary>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/"
              element={
                <RequireAuth>
                  <Layout />
                </RequireAuth>
              }
            >
              <Route index element={<Navigate to="/command-center" replace />} />
              <Route path="command-center" element={<CommandCenterView />} />
              <Route path="dispatch" element={<DispatchCenterView />} />
              <Route path="alerts" element={<AlertsCenter />} />
              <Route path="incidents" element={<IncidentReportingView />} />
              <Route path="reports" element={<ReportsCenter />} />
              <Route path="ai-copilot" element={<AIAgentView />} />
              <Route path="*" element={<Navigate to="/command-center" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ErrorBoundary>
    </QueryClientProvider>
  );
}

