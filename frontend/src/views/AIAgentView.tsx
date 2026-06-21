import { useEffect, useState } from 'react';
import { api, isBackendOfflineError } from '../api/client';
import { EmptyState, LoadingSpinner, OfflineState, StatusPill } from '../components/LoaderStates';
import { formatRelativeTime } from '../lib/time';
import { useTimedResource } from '../lib/useTimedResource';
import { useStore } from '../store/useStore';

type Language = 'ENG' | 'KAN';
type Message = { role: 'user' | 'ai'; content: string };

function cleanReply(content: string): string {
  return content.replace(/\*?\(Trust\s+Score:\s*\d+%\)\*?/gi, '').trim();
}

export function AIAgentView() {
  const [language, setLanguage] = useState<Language>('ENG');
  const [input, setInput] = useState('');
  const [history, setHistory] = useState<Message[]>([]);
  const [sending, setSending] = useState(false);
  const [offline, setOffline] = useState<string | null>(null);
  
  const activeTimeline = useStore((state) => state.activeTimeline);
  const activeTab = useStore((state) => state.activeTab);

  const { data, loading, timedOut, error, refresh } = useTimedResource(async () => {
    const [stats, alerts] = await Promise.all([
      api.getStats({ timeline: activeTimeline }),
      api.getAlerts({ timeline: activeTimeline }),
    ]);
    return { stats, alerts };
  }, [activeTimeline]);

  useEffect(() => {
    if (history.length === 0) {
      setHistory([{ role: 'ai', content: `Welcome to ParkSense Copilot. The active data timeline is ${activeTimeline}. I can answer questions using live backend traffic, alerts, and forecast data.` } as Message]);
    }
  }, [history.length, activeTimeline]);

  const send = async () => {
    const text = input.trim();
    if (!text) return;
    const nextHistory = [...history, { role: 'user', content: text } as Message];
    setHistory(nextHistory);
    setInput('');
    setSending(true);
    setOffline(null);
    try {
      const reply = await api.queryCopilot(text, {
        activeTimeline,
        activeTab,
        stats: data?.stats ?? {},
        alerts: (data?.alerts ?? []).slice(0, 3),
        conversation: nextHistory.slice(-6).map(h => ({ role: h.role, content: cleanReply(h.content) })),
      }, language === 'ENG' ? 'en' : 'kn');
      setHistory([...nextHistory, { role: 'ai', content: cleanReply(reply.reply) } as Message]);
    } catch (err) {
      setOffline(isBackendOfflineError(err) ? 'Copilot is waiting for the backend connection.' : 'Copilot could not answer this request right now.');
    } finally {
      setSending(false);
    }
  };

  if (loading) return <LoadingSpinner />;
  if (timedOut) return <OfflineState message="Copilot context is taking too long to load." onAction={refresh} />;
  if (error) return <OfflineState message={error} onAction={refresh} />;
  if (!data) return <EmptyState message="No copilot context is available yet." />;

  return (
    <div className="copilot-shell">
      <div className="section-heading">
        <div>
          <div className="eyebrow">{language === 'ENG' ? 'AI copilot' : 'AI copilot'}</div>
          <h1>{language === 'ENG' ? 'ParkSense Copilot' : 'ParkSense Copilot'}</h1>
        </div>
        <div className="section-meta">
          <StatusPill tone="good" label={language === 'ENG' ? `Stats updated ${formatRelativeTime(data.stats.timestamp)}` : `Stats updated ${formatRelativeTime(data.stats.timestamp)}`} />
          <div className="language-toggle">
            <button type="button" className={language === 'ENG' ? 'active' : ''} onClick={() => setLanguage('ENG')}>
              ENG
            </button>
            <button type="button" className={language === 'KAN' ? 'active' : ''} onClick={() => setLanguage('KAN')}>
              KAN
            </button>
          </div>
        </div>
      </div>

      <section className="panel-card chat-panel">
        <div className="chat-history">
          {history.map((message, index) => (
            <div key={index} className={message.role === 'user' ? 'chat-bubble chat-bubble--user' : 'chat-bubble chat-bubble--ai'}>
              {message.content}
            </div>
          ))}
          {sending && <div className="chat-bubble chat-bubble--typing">{language === 'ENG' ? 'Thinking...' : 'Thinking...'}</div>}
          {offline && <div className="alert-banner">{offline}</div>}
        </div>

        <div className="chat-input-row">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                void send();
              }
            }}
            placeholder={language === 'ENG' ? 'Ask for a briefing, summary, or recommendation...' : 'Ask for a briefing, summary, or recommendation...'}
          />
          <button type="button" className="btn btn--amber" onClick={() => void send()}>
            {language === 'ENG' ? 'Send' : 'Send'}
          </button>
        </div>
      </section>
    </div>
  );
}
