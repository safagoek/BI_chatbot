/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Microsoft Fluent Design System 2 — Communication Blue + Neutral Ground
        gh: {
          bg:              "var(--color-bg)",
          canvas:          "var(--color-canvas)",
          surface:         "var(--color-surface)",
          surface2:        "var(--color-surface2)",
          border:          "var(--color-border)",
          border2:         "var(--color-border2)",
          text:            "var(--color-text)",
          "text-2":        "var(--color-text-2)",
          muted:           "var(--color-muted)",
          faint:           "var(--color-faint)",
          disabled:        "var(--color-disabled)",
          accent:          "var(--color-accent)",
          "accent-hover":  "var(--color-accent-hover)",
          "accent-subtle": "var(--color-accent-subtle)",
          "accent-subtle2":"var(--color-accent-subtle2)",
          "accent-fg":     "var(--color-accent-fg)",
          success:         "var(--color-success)",
          "success-subtle":"var(--color-success-subtle)",
          warning:         "var(--color-warning)",
          "warning-subtle":"var(--color-warning-subtle)",
          danger:          "var(--color-danger)",
          "danger-subtle": "var(--color-danger-subtle)",
          done:            "var(--color-done)",
          info:            "var(--color-info)",
        },
      },
      fontFamily: {
        // Fluent-approved type stack
        sans: ['"Plus Jakarta Sans"', '"Outfit"', '"Inter"', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"Cascadia Code"', '"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.65rem', { lineHeight: '1rem' }],
      },
      boxShadow: {
        'fluent-2':  'var(--shadow-2)',
        'fluent-4':  'var(--shadow-4)',
        'fluent-8':  'var(--shadow-8)',
        'fluent-16': 'var(--shadow-16)',
        'fluent-28': 'var(--shadow-28)',
      },
      borderRadius: {
        'sm':  '4px',
        DEFAULT: '8px',
        'md':  '8px',
        'lg':  '12px',
        'xl':  '16px',
      },
      transitionTimingFunction: {
        'fluent':       'cubic-bezier(0.1, 0.9, 0.2, 1)',
        'fluent-accel': 'cubic-bezier(0.9, 0.1, 1.0, 0.2)',
        'fluent-std':   'cubic-bezier(0.8, 0, 0.2, 1)',
      },
      transitionDuration: {
        'fast':   '100ms',
        'normal': '200ms',
        'slow':   '350ms',
      },
      animation: {
        'slide-up':   'slideUp 200ms cubic-bezier(0.1, 0.9, 0.2, 1)',
        'fade-in':    'fadeIn 100ms cubic-bezier(0.1, 0.9, 0.2, 1)',
        'slide-right':'slideRight 200ms cubic-bezier(0.1, 0.9, 0.2, 1)',
        'spin-slow':  'spin 2s linear infinite',
      },
      keyframes: {
        slideUp: {
          '0%':   { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideRight: {
          '0%':   { opacity: '0', transform: 'translateX(10px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
      },
    },
  },
  plugins: [],
}
