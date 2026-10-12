import React from 'react';
import './index.css';

/**
 * Phase 9: Placeholder analytics chart component
 * Will be rendered with actual charting library (e.g., recharts, chart.js)
 * when backend metrics data is available.
 */
interface AnalyticsChartProps {
  title: string;
  data: any[];
  metric: string;
  range: '24h' | '7d' | '30d';
}

export const AnalyticsChart: React.FC<AnalyticsChartProps> = ({
  title,
  data,
  metric,
  range,
}) => {
  return (
    <div
      style={{
        padding: '16px',
        backgroundColor: 'var(--bg-surface)',
        borderRadius: '4px',
        border: '1px solid var(--border-hairline)',
        fontFamily: "'IBM Plex Sans', -apple-system, 'Segoe UI', sans-serif",
      }}
    >
      <h3 style={{ margin: '0 0 12px 0', fontSize: '0.875rem', color: 'var(--text-primary)' }}>
        {title} ({range})
      </h3>
      <div style={{ height: '120px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
          No data available
          {metric === 'cost_per_ticket' && <span style={{ marginLeft: '8px' }}> (₹ per ticket)</span>
        }
      </div>
    </div>
  );
}