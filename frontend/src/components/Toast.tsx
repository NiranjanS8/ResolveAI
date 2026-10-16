import React from 'react';
import { Icon } from './Icon';

export interface ToastMessage {
  id: string;
  type: 'success' | 'warning' | 'error' | 'info';
  message: string;
}

interface ToastProps {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
}

/* Severity is carried by the icon and the sentence-case label. Status tones stay
   reserved for confidence tiers and accent stays reserved for the primary
   action, the AI-draft border, and links, so a toast never borrows either. */
const TOAST_ICON = {
  success: 'check',
  warning: 'alert',
  error: 'alert',
  info: 'inbox',
} as const;

const TOAST_LABEL = {
  success: 'Success',
  warning: 'Warning',
  error: 'Error',
  info: 'Info',
} as const;

export const ToastContainer: React.FC<ToastProps> = ({ toasts, onDismiss }) => {
  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm pointer-events-none">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          role="status"
          className="pointer-events-auto p-3 text-[12px] animate-fade-in flex items-start justify-between gap-3"
          style={{
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-hairline)',
            borderRadius: 'var(--radius)',
          }}
        >
          <span className="mt-0.5 shrink-0" style={{ color: 'var(--text-secondary)' }}>
            <Icon name={TOAST_ICON[toast.type]} size={13} />
          </span>
          <div className="flex-1">
            <span className="block" style={{ color: 'var(--text-secondary)' }}>
              {TOAST_LABEL[toast.type]}
            </span>
            <p className="mt-0.5 leading-snug" style={{ color: 'var(--text-primary)' }}>
              {toast.message}
            </p>
          </div>
          <button
            onClick={() => onDismiss(toast.id)}
            aria-label="Dismiss notification"
            style={{ color: 'var(--text-secondary)' }}
          >
            <Icon name="close" size={13} />
          </button>
        </div>
      ))}
    </div>
  );
};
