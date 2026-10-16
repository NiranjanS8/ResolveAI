import React, { useEffect, useState } from 'react';
import { Icon } from './Icon';

interface NavbarProps {
  activeTab: 'queue' | 'analytics';
  onTabChange: (tab: 'queue' | 'analytics') => void;
  onOpenNewTicket: () => void;
  isBackendConnected: boolean;
  onRefresh: () => void;
  ticketCount: number;
  pendingReviewCount: number;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  onTabChange,
  onOpenNewTicket,
  isBackendConnected,
  onRefresh,
  ticketCount,
  pendingReviewCount,
}) => {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    if (typeof window === 'undefined') return 'dark';
    const saved = localStorage.getItem('resolveai-theme') as 'light' | 'dark' | null;
    return saved || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    const next = theme === 'light' ? 'dark' : 'light';
    setTheme(next);
    localStorage.setItem('resolveai-theme', next);
    document.documentElement.setAttribute('data-theme', next);
  };

  return (
    <header
      className="sticky top-0 z-40 border-b"
      style={{
        backgroundColor: 'var(--bg-surface)',
        borderColor: 'var(--border)',
      }}
    >
      <div
        className="max-w-screen-2xl mx-auto px-5 flex items-center gap-6"
        style={{ height: '52px' }}
      >
        {/* Brand */}
        <div className="flex items-center gap-2.5 shrink-0">
          <div
            className="w-7 h-7 rounded-md flex items-center justify-center text-white font-bold text-sm"
            style={{
              background: 'linear-gradient(135deg, var(--accent) 0%, var(--purple) 100%)',
            }}
          >
            R
          </div>
          <span className="font-semibold text-sm tracking-tight" style={{ color: 'var(--text-primary)' }}>
            ResolveAI
          </span>
        </div>

        {/* Nav Tabs */}
        <nav className="flex items-center gap-1 flex-1">
          <button
            id="nav-tab-queue"
            onClick={() => onTabChange('queue')}
            className="flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all"
            style={{
              backgroundColor: activeTab === 'queue' ? 'var(--bg-hover)' : 'transparent',
              color: activeTab === 'queue' ? 'var(--text-primary)' : 'var(--text-secondary)',
            }}
          >
            <span>Agent Queue</span>
            <span
              className="font-mono text-xs px-1.5 py-0.5 rounded-full"
              style={{
                backgroundColor: pendingReviewCount > 0 ? 'var(--yellow-dim)' : 'var(--bg-elevated)',
                color: pendingReviewCount > 0 ? 'var(--yellow)' : 'var(--text-muted)',
              }}
            >
              {ticketCount}
            </span>
          </button>

          <button
            id="nav-tab-analytics"
            onClick={() => onTabChange('analytics')}
            className="px-3 py-1.5 rounded-md text-sm font-medium transition-all"
            style={{
              backgroundColor: activeTab === 'analytics' ? 'var(--bg-hover)' : 'transparent',
              color: activeTab === 'analytics' ? 'var(--text-primary)' : 'var(--text-secondary)',
            }}
          >
            Analytics & ROI
          </button>
        </nav>

        {/* Right controls */}
        <div className="flex items-center gap-2 shrink-0">
          {/* Backend status pill */}
          <button
            onClick={onRefresh}
            title={isBackendConnected ? 'Live backend' : 'Demo mode — click to retry'}
            aria-label={isBackendConnected ? 'Backend live — refresh' : 'Demo mode — click to retry'}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs transition-colors"
            style={{
              backgroundColor: 'var(--bg-elevated)',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border)',
            }}
          >
            <span
              className="w-1.5 h-1.5 rounded-full"
              style={{
                backgroundColor: isBackendConnected ? 'var(--green)' : 'var(--yellow)',
                ...(isBackendConnected && { animation: 'pulseDot 2s ease infinite' }),
              }}
            />
            <span className="font-mono">{isBackendConnected ? 'Live' : 'Demo'}</span>
          </button>

          {/* Theme toggle */}
          <button
            id="btn-toggle-theme"
            onClick={toggleTheme}
            aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
            className="w-8 h-8 rounded-md flex items-center justify-center transition-colors"
            style={{
              backgroundColor: 'var(--bg-elevated)',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border)',
            }}
          >
            <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={15} />
          </button>

          {/* New Ticket */}
          <button
            id="btn-new-ticket"
            onClick={onOpenNewTicket}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium text-white transition-opacity hover:opacity-90"
            style={{
              background: 'linear-gradient(135deg, var(--accent) 0%, #4A9AFF 100%)',
            }}
          >
            <Icon name="plus" size={14} />
            <span>Ingest Ticket</span>
          </button>
        </div>
      </div>
    </header>
  );
};
