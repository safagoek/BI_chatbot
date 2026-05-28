/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // High-end Cyber-Obsidian & Neon-Violet Palette
        gh: {
          bg:       "var(--color-bg)",
          canvas:   "var(--color-canvas)",
          surface:  "var(--color-surface)",
          border:   "var(--color-border)",
          border2:  "var(--color-border2)",
          text:     "var(--color-text)",
          muted:    "var(--color-muted)",
          faint:    "var(--color-faint)",
          accent:   "var(--color-accent)",
          "accent-subtle": "var(--color-accent-subtle)",
          "accent-fg":     "var(--color-accent-fg)",
          success:  "var(--color-success)",
          "success-subtle": "var(--color-success-subtle)",
          warning:  "var(--color-warning)",
          danger:   "var(--color-danger)",
          done:     "var(--color-done)",
          "done-subtle": "var(--color-done-subtle)",
        },
      },
      fontFamily: {
        sans: ['"Inter"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Fira Code"', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.65rem', { lineHeight: '1rem' }],
      },
      boxShadow: {
        'overlay': '0 12px 40px rgba(0,0,0,0.85)',
        'inset-subtle': 'inset 0 1px 0 rgba(255,255,255,0.05)',
        'neon-glow': '0 0 20px rgba(99, 102, 241, 0.25)',
      },
      animation: {
        'slide-up':  'slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        'fade-in':   'fadeIn 0.25s ease-out',
        'spin-slow': 'spin 2s linear infinite',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        slideUp: {
          '0%':   { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
      borderRadius: {
        'sm':  '6px',
        DEFAULT: '8px',
        'md':  '12px',
        'lg':  '16px',
        'xl':  '24px',
      },
    },
  },
  plugins: [],
}
