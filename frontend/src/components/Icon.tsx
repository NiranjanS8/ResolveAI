import React from 'react';

/**
 * Single outline icon family for the app (24px grid, currentColor stroke).
 * Replaces ad-hoc emoji glyphs so icons render consistently inside the
 * light/dark themes instead of inheriting platform emoji fonts.
 *
 * Icons are decorative by default (`aria-hidden`); an icon-only control must
 * carry its own accessible name via `aria-label`.
 */
export type IconName =
  | 'close'
  | 'plus'
  | 'search'
  | 'sun'
  | 'moon'
  | 'inbox'
  | 'sparkle'
  | 'check'
  | 'alert'
  | 'star';

interface IconProps {
  name: IconName;
  size?: number;
  className?: string;
  strokeWidth?: number;
}

const GLYPHS: Record<IconName, React.ReactNode> = {
  close: <path d="M18 6 6 18M6 6l12 12" />,
  plus: <path d="M12 5v14M5 12h14" />,
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </>
  ),
  moon: <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />,
  inbox: (
    <>
      <path d="M22 12h-6l-2 3h-4l-2-3H2" />
      <path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
    </>
  ),
  sparkle: (
    <>
      <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10z" />
      <path d="M19 15l.7 1.8 1.8.7-1.8.7L19 21l-.7-1.8-1.8-.7 1.8-.7z" />
    </>
  ),
  check: <path d="M20 6 9 17l-5-5" />,
  alert: (
    <>
      <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <path d="M12 9v4M12 17h.01" />
    </>
  ),
  star: (
    <path d="m12 3 2.9 5.88 6.49.94-4.7 4.58 1.11 6.46L12 17.77l-5.8 3.09 1.11-6.46-4.7-4.58 6.49-.94z" />
  ),
};

export const Icon: React.FC<IconProps> = ({ name, size = 16, className, strokeWidth = 1.75 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={strokeWidth}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
    focusable="false"
  >
    {GLYPHS[name]}
  </svg>
);
