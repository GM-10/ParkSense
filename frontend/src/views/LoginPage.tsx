import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, isBackendOfflineError } from '../api/client';
import { useStore } from '../store/useStore';

export function LoginPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const doLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await api.login(username.trim(), password.trim());
      localStorage.setItem('parksense_token', res.token);
      localStorage.setItem('parksense_username', res.username);
      await useStore.getState().bootstrapPlatform();
      navigate('/command-center', { replace: true });
    } catch (err) {
      setError(isBackendOfflineError(err) ? 'Backend offline. Start the API server to sign in.' : 'Invalid username or password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-screen">
      <section className="login-hero">
        <div className="eyebrow">ParkSense platform</div>
        <h1>Traffic operations, dispatch, and copilot in one secure workspace.</h1>
        <p>
          Sign in to monitor live hotspots, manage active deployments, file incidents, and generate city reports from the same real-time backend.
        </p>
      </section>
      <section className="login-card">
        <div className="eyebrow">Secure access</div>
        <h2>Sign in</h2>
        <form onSubmit={doLogin} className="mt-6 space-y-4">
          <label className="form-field">
            <span>Username</span>
            <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Enter your username" autoComplete="username" />
          </label>
          <label className="form-field">
            <span>Password</span>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Enter your password" autoComplete="current-password" />
          </label>
          {error && <div className="alert-banner">{error}</div>}
          <button type="submit" className="btn btn--amber w-full" disabled={loading}>
            {loading ? 'Signing in...' : 'Enter Workspace'}
          </button>
        </form>
        <p className="login-footnote">Use the backend-provisioned credentials to continue.</p>
      </section>
    </div>
  );
}

