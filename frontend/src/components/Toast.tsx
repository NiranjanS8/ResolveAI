import React from 'react';

export interface ToastMessage {
  id: string;
  type: 'success' | 'warning' | 'error' | 'info';
  message: string;
}

interface ToastProps {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
}

export const ToastContainer: React.FC<ToastProps> = ({ toasts, onDismiss }) => {
  if (toasts.length === 0) return null;

  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm pointer-events-none"
      style={{ fontFamily: "'IBM Plex Sans', sans-serif" }}
    >
      {toasts.map((toast) => {
        const borderCol =
          toast.type === 'success'
            ? 'var(--status-high)'
            : toast.type === 'warning'
            ? 'var(--status-medium)'
            : toast.type === 'error'
            ? 'var(--status-low)'
            : 'var(--accent)';

        return (
          <div
            key={toast.id}
            className="pointer-events-auto p-3 rounded-[4px] bg-[var(--bg-surface)] border shadow-lg text-xs animate-fade-in flex items-start justify-between gap-3"
            style={{
              borderLeft: `4px solid ${borderCol}`,
              borderColor: 'var(--border-hairline)',
            }}
          >
            <div className="flex-1">
              <span className="font-semibold uppercase text-[0.625rem] text-[var(--text-secondary)] block">
                {toast.type}
              </span>
              <p className="text-[var(--text-primary)] mt-0.5 leading-snug">
                {toast.message}
              </p>
            </div>
            <button
              onClick={() => onDismiss(toast.id)}
              className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] text-xs"
            >
              ✕
            </button>
          </div>
        );
      })}
    </div>
  );
};
