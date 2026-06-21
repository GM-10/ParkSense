import React from 'react';

type Props = { children: React.ReactNode };
type State = { hasError: boolean; message: string };

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false, message: 'Something went wrong.' };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message || 'Something went wrong.' };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-[#050b12] px-6 py-10 text-white">
          <div className="mx-auto max-w-xl rounded-[28px] border border-white/10 bg-white/[0.04] p-8 shadow-2xl">
            <div className="text-xs uppercase tracking-[0.35em] text-amber-300">Application error</div>
            <h1 className="mt-3 text-2xl font-semibold">The workspace hit a snag</h1>
            <p className="mt-3 text-sm leading-6 text-slate-300">{this.state.message}</p>
            <button
              type="button"
              className="btn btn--amber mt-6"
              onClick={() => window.location.reload()}
            >
              Retry
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

