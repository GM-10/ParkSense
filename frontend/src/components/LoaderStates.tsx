type ActionStateProps = {
  title?: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
};

export const LoadingSpinner = ({ message = 'Loading live data...' }: { message?: string }) => (
  <div className="panel-state min-h-[320px]">
    <div className="spinner-ring" />
    <div className="mt-4 text-sm font-semibold text-white">{message}</div>
  </div>
);

export const OfflineState = ({ title, message, actionLabel = 'Retry', onAction }: ActionStateProps) => (
  <div className="panel-state panel-state--error min-h-[320px]">
    <div className="panel-state__icon">Offline</div>
    <h4 className="text-sm text-slate-400">{title ?? 'Connection issue'}</h4>
    <h3 className="mt-4 text-xl font-semibold text-white">{message}</h3>
    {onAction && (
      <button type="button" className="mt-5 btn btn--amber" onClick={onAction}>
        {actionLabel}
      </button>
    )}
  </div>
);

export const EmptyState = ({ message = 'No data available.', title = 'Nothing to show' }: { message?: string; title?: string }) => (
  <div className="panel-state min-h-[260px]">
    <div className="panel-state__icon">No data</div>
    <h3 className="mt-4 text-lg font-semibold text-white">{title}</h3>
    <p className="mt-2 max-w-md text-sm text-slate-400">{message}</p>
  </div>
);

export const StatusPill = ({ label, tone = 'neutral' }: { label: string; tone?: 'neutral' | 'good' | 'warn' | 'bad' }) => (
  <span className={`status-pill status-pill--${tone}`}>{label}</span>
);

