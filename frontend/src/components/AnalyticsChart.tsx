import React from 'react';

interface AnalyticsChartProps {
  title: string;
  metric: 'deflection_rate' | 'cost_per_ticket' | 'escalation_breakdown' | 'channel_distribution';
  range: '24h' | '7d' | '30d';
  data?: Record<string, number> | Array<{ label: string; value: number }>;
}

/* Bars carry no status colour: the confidence tones are reserved for ticket
   confidence tiers, so charts stay neutral and readable. */
const BAR_FILL = 'var(--text-secondary)';

const Panel: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div
    className="p-4 space-y-3"
    style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-hairline)' }}
  >
    {children}
  </div>
);

const PanelHeader: React.FC<{ title: string; meta?: string }> = ({ title, meta }) => (
  <div className="flex items-baseline justify-between gap-3">
    <h3 className="text-[13px] font-semibold" style={{ color: 'var(--text-primary)' }}>
      {title}
    </h3>
    {meta && (
      <span className="text-[12px] font-mono" style={{ color: 'var(--text-secondary)' }}>
        {meta}
      </span>
    )}
  </div>
);

export const AnalyticsChart: React.FC<AnalyticsChartProps> = ({ title, metric, range, data }) => {
  if (metric === 'escalation_breakdown') {
    const fallback: Record<string, number> = {
      'Refund over the ₹2,000 cap': 42,
      'Complex technical outage': 28,
      'Negative sentiment flag': 18,
      'Account security flag': 12,
    };
    const breakdown = (data as Record<string, number>) || fallback;
    const maxValue = Math.max(...Object.values(breakdown), 1);

    return (
      <Panel>
        <PanelHeader title={title} meta={`${range} window`} />
        <div className="space-y-2.5 pt-1">
          {Object.entries(breakdown).map(([label, count]) => {
            const pct = Math.round((count / maxValue) * 100);
            return (
              <div key={label} className="space-y-1">
                <div className="flex justify-between gap-3 text-[12px]">
                  <span className="truncate" style={{ color: 'var(--text-secondary)' }}>
                    {label}
                  </span>
                  <span className="font-mono shrink-0" style={{ color: 'var(--text-primary)' }}>
                    {count} ({pct}%)
                  </span>
                </div>
                <div className="w-full h-1.5 overflow-hidden" style={{ backgroundColor: 'var(--bg-base)' }}>
                  <div className="h-full transition-all duration-500" style={{ width: `${pct}%`, backgroundColor: BAR_FILL }} />
                </div>
              </div>
            );
          })}
        </div>
      </Panel>
    );
  }

  if (metric === 'deflection_rate') {
    const points = range === '24h' ? [68, 72, 70, 75, 78, 81] : range === '7d' ? [64, 69, 71, 74, 76, 78, 82] : [58, 62, 65, 70, 74, 78, 80, 84];
    const labels = range === '24h' ? ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00'] : range === '7d' ? ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] : ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7', 'W8'];
    const current = points[points.length - 1];

    return (
      <Panel>
        <div className="flex items-baseline justify-between gap-3">
          <div>
            <h3 className="text-[13px] font-semibold" style={{ color: 'var(--text-primary)' }}>
              {title}
            </h3>
            <span className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
              Target 70% autonomous deflection
            </span>
          </div>
          <span className="text-[13px] font-mono" style={{ color: 'var(--text-primary)' }}>
            {current}% now
          </span>
        </div>

        <div className="h-32 flex items-end gap-2 pt-4" style={{ borderBottom: '1px solid var(--border-hairline)' }}>
          {points.map((value, index) => (
            <div key={index} className="flex-1 flex flex-col items-center gap-1 h-full justify-end">
              <span className="text-[12px] font-mono" style={{ color: 'var(--text-secondary)' }}>
                {value}%
              </span>
              <div
                className="w-full transition-all duration-300"
                style={{ height: `${value}%`, backgroundColor: BAR_FILL }}
              />
              <span className="text-[12px] mt-1" style={{ color: 'var(--text-secondary)' }}>
                {labels[index]}
              </span>
            </div>
          ))}
        </div>
      </Panel>
    );
  }

  return (
    <Panel>
      <PanelHeader title={title} meta={range} />
      <div className="grid grid-cols-2 gap-4 pt-2">
        <div>
          <span className="text-[12px] block" style={{ color: 'var(--text-secondary)' }}>
            AI inference cost
          </span>
          <span className="text-[18px] font-mono" style={{ color: 'var(--text-primary)' }}>
            ₹3.42
          </span>
          <span className="text-[12px] block" style={{ color: 'var(--text-secondary)' }}>
            94% below human handling
          </span>
        </div>
        <div>
          <span className="text-[12px] block" style={{ color: 'var(--text-secondary)' }}>
            Human handling cost
          </span>
          <span className="text-[18px] font-mono" style={{ color: 'var(--text-secondary)' }}>
            ₹500.00
          </span>
          <span className="text-[12px] block" style={{ color: 'var(--text-secondary)' }}>
            Baseline tier-1
          </span>
        </div>
      </div>
    </Panel>
  );
};
