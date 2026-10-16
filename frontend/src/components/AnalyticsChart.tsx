import React from 'react';

interface AnalyticsChartProps {
  title: string;
  metric: 'deflection_rate' | 'cost_per_ticket' | 'escalation_breakdown' | 'channel_distribution';
  range: '24h' | '7d' | '30d';
  data?: Record<string, number> | Array<{ label: string; value: number }>;
}

export const AnalyticsChart: React.FC<AnalyticsChartProps> = ({
  title,
  metric,
  range,
  data,
}) => {
  if (metric === 'escalation_breakdown') {
    const defaultBreakdown: Record<string, number> = {
      'Refund > ₹2,000 threshold': 42,
      'Complex Technical Outage': 28,
      'Sentiment / Escalation flag': 18,
      'Account Security / 2FA flag': 12,
    };
    const breakdown = (data as Record<string, number>) || defaultBreakdown;
    const maxVal = Math.max(...Object.values(breakdown), 1);

    return (
      <div
        className="p-4 bg-[var(--bg-surface)] rounded-[4px] border border-[var(--border-hairline)] space-y-3"
      >
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold text-[var(--text-primary)]">{title}</h3>
          <span className="text-[0.6875rem] font-mono text-[var(--text-secondary)]">{range} window</span>
        </div>

        <div className="space-y-2.5 pt-1">
          {Object.entries(breakdown).map(([label, count]) => {
            const pct = Math.round((count / maxVal) * 100);
            return (
              <div key={label} className="space-y-1">
                <div className="flex justify-between text-[0.6875rem]">
                  <span className="text-[var(--text-secondary)] truncate">{label}</span>
                  <span className="font-mono font-medium text-[var(--text-primary)]">{count} ({pct}%)</span>
                </div>
                <div className="w-full h-2 rounded bg-[var(--bg-base)] overflow-hidden">
                  <div
                    className="h-full rounded transition-all duration-500"
                    style={{
                      width: `${pct}%`,
                      backgroundColor: 'var(--status-low)',
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  if (metric === 'deflection_rate') {
    // Generate trend bars for range
    const points = range === '24h' ? [68, 72, 70, 75, 78, 81] : range === '7d' ? [64, 69, 71, 74, 76, 78, 82] : [58, 62, 65, 70, 74, 78, 80, 84];
    const labels = range === '24h' ? ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00'] : range === '7d' ? ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] : ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7', 'W8'];

    return (
      <div
        className="p-4 bg-[var(--bg-surface)] rounded-[4px] border border-[var(--border-hairline)] space-y-3"
      >
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xs font-semibold text-[var(--text-primary)]">{title}</h3>
            <span className="text-[0.6875rem] text-[var(--text-secondary)]">Target: &gt;70% Autonomous Deflection</span>
          </div>
          <span className="text-xs font-mono font-semibold text-[var(--status-high)] bg-[var(--status-high-bg)] px-2 py-0.5 rounded">
            82% Current
          </span>
        </div>

        {/* SVG Sparkline/Bar Chart */}
        <div className="h-32 flex items-end gap-2 pt-4 border-b border-[var(--border-hairline)]">
          {points.map((val, idx) => {
            const heightPct = Math.round((val / 100) * 100);
            return (
              <div key={idx} className="flex-1 flex flex-col items-center gap-1 h-full justify-end group">
                <span className="text-[0.625rem] font-mono text-[var(--text-secondary)] opacity-0 group-hover:opacity-100 transition-opacity">
                  {val}%
                </span>
                <div
                  className="w-full rounded-t transition-all duration-300 hover:opacity-80"
                  style={{
                    height: `${heightPct}%`,
                    backgroundColor: val >= 75 ? 'var(--status-high)' : 'var(--status-medium)',
                  }}
                />
                <span className="text-[0.625rem] text-[var(--text-secondary)] mt-1">
                  {labels[idx]}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // Cost per ticket / general
  return (
    <div
      className="p-4 bg-[var(--bg-surface)] rounded-[4px] border border-[var(--border-hairline)] space-y-3"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-[var(--text-primary)]">{title}</h3>
        <span className="text-[0.6875rem] font-mono text-[var(--text-secondary)]">{range}</span>
      </div>

      <div className="grid grid-cols-2 gap-3 pt-2">
        <div className="p-3 bg-[var(--bg-base)] rounded border border-[var(--border-hairline)]">
          <span className="text-[0.6875rem] text-[var(--text-secondary)] block">AI Inference Cost</span>
          <span className="text-lg font-mono font-bold text-[var(--text-primary)]">₹3.42</span>
          <span className="text-[0.625rem] text-[var(--status-high)] block">↓ 94% vs human</span>
        </div>
        <div className="p-3 bg-[var(--bg-base)] rounded border border-[var(--border-hairline)]">
          <span className="text-[0.6875rem] text-[var(--text-secondary)] block">Human Handling Cost</span>
          <span className="text-lg font-mono font-bold text-[var(--text-secondary)]">₹500.00</span>
          <span className="text-[0.625rem] text-[var(--text-secondary)] block">Baseline tier-1</span>
        </div>
      </div>
    </div>
  );
};