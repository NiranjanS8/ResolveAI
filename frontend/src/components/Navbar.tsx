import React, { useEffect, useState } from 'react';
import { Icon } from './Icon';

interface NavbarProps {
  activeTab: 'queue' | 'analytics';
  onTabChange: (tab: 'queue' | 'analytics') => void;
  onOpenNewTicket: () => void;
  isBackendConnected: boolean;
  onRefresh: () => void;
}

const TABS: Array<{ id: 'queue' | 'analytics'; label: string }> = [
  { id: 'queue', label: 'Agent queue' },
  { id: 'analytics', label: 'Analytics' },
];

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  onTabChange,
  onOpenNewTicket,
  isBackendConnected,
  onRefresh,
}) => {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    if (typeof window === 'undefined') return 'light';
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
      className="sticky top-0 z-40"
      style={{ backgroundColor: 'var(--bg-surface)', borderBottom: '1px solid var(--border-hairline)' }}
    >
      <div className="app-gutter flex items-center gap-8" style={{ height: 52 }}>
        {/* Plain wordmark — no tile, no gradient */}
        <span className="text-[15px] font-semibold shrink-0" style={{ color: 'var(--text-primary)' }}>
          ResolveAI
        </span>

        {/* Tabs: active state is the text colour plus a 2px underline, never accent */}
        <nav className="flex items-stretch gap-6 self-stretch flex-1">
          {TABS.map((tab) => {
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                id={`nav-tab-${tab.id}`}
                onClick={() => onTabChange(tab.id)}
                aria-current={active ? 'page' : undefined}
                className="flex items-center text-[13px] font-medium"
                style={{
                  color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
                  borderBottom: `2px solid ${active ? 'var(--text-primary)' : 'transparent'}`,
                }}
              >
                {tab.label}
              </button>
            );
          })}
        </nav>

        <div className="flex items-center gap-3 shrink-0">
          {/* Connectivity — the single live/offline indicator in the app */}
          <button
            onClick={onRefresh}
            title={isBackendConnected ? 'Backend live — refresh' : 'Offline — click to retry'}
            aria-label={isBackendConnected ? 'Backend live, refresh' : 'Backend offline, retry'}
            className="flex items-center gap-2 text-xs"
            style={{ color: 'var(--text-secondary)' }}
          >
            <span
              className={isBackendConnected ? 'w-1.5 h-1.5 rounded-full animate-pulse-dot' : 'w-1.5 h-1.5 rounded-full'}
              style={{ backgroundColor: isBackendConnected ? 'var(--text-primary)' : 'var(--text-secondary)' }}
            />
            {isBackendConnected ? 'Live' : 'Offline'}
          </button>

          <button
            id="btn-toggle-theme"
            onClick={toggleTheme}
            aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
            className="w-7 h-7 flex items-center justify-center"
            style={{
              color: 'var(--text-secondary)',
              border: '1px solid var(--border-hairline)',
              borderRadius: 'var(--radius)',
            }}
          >
            <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={15} />
          </button>

          {/* Dev/test control: outline, never the screen's filled action */}
          <button
            id="btn-new-ticket"
            onClick={onOpenNewTicket}
            className="flex items-center gap-1.5 px-3 h-7 text-[13px] font-medium"
            style={{
              color: 'var(--text-primary)',
              border: '1px solid var(--border-hairline)',
              borderRadius: 'var(--radius)',
            }}
          >
            <Icon name="plus" size={14} />
            Ingest ticket
          </button>
        </div>
      </div>
    </header>
  );
};
