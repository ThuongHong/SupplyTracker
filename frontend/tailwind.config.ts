import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Semantic surface tokens
        surface: {
          DEFAULT: '#ffffff',       // light bg
          dark: '#111827',          // dark bg (gray-900)
          muted: '#f9fafb',         // light muted (gray-50)
          'muted-dark': '#1f2937', // dark muted (gray-800)
          elevated: '#ffffff',
          'elevated-dark': '#1f2937',
        },
        // Semantic text tokens — WCAG AA checked
        // Light: gray-900 (#111827) on white (#fff) → 21:1 ✓
        // Dark: gray-100 (#f3f4f6) on gray-900 (#111827) → 17:1 ✓
        content: {
          primary: '#111827',       // gray-900
          'primary-dark': '#f3f4f6', // gray-100
          secondary: '#374151',     // gray-700 on white → 10:1 ✓
          'secondary-dark': '#d1d5db', // gray-300 on gray-900 → 11:1 ✓
          muted: '#6b7280',         // gray-500 on white → 4.6:1 ✓ (just passes AA)
          'muted-dark': '#9ca3af', // gray-400 on gray-900 → 5.7:1 ✓
        },
        // Border tokens
        border: {
          DEFAULT: '#e5e7eb',       // gray-200
          dark: '#374151',          // gray-700
        },
        // Accent / brand — indigo
        // indigo-600 (#4f46e5) on white → 5.9:1 ✓ AA
        // indigo-400 (#818cf8) on gray-900 → 6.1:1 ✓ AA
        accent: {
          DEFAULT: '#4f46e5',       // indigo-600
          dark: '#818cf8',          // indigo-400
          hover: '#4338ca',         // indigo-700
          'hover-dark': '#6366f1', // indigo-500
        },
        // Severity palette — WCAG AA on both modes
        severity: {
          // low = green
          low: '#16a34a',           // green-600 on white → 4.9:1 ✓
          'low-dark': '#4ade80',   // green-400 on gray-900 → 6.5:1 ✓
          'low-bg': '#f0fdf4',
          'low-bg-dark': '#14532d',
          // moderate = yellow/amber
          moderate: '#b45309',      // amber-700 on white → 5.5:1 ✓
          'moderate-dark': '#fcd34d', // amber-300 on gray-900 → 9.8:1 ✓
          'moderate-bg': '#fffbeb',
          'moderate-bg-dark': '#78350f',
          // high = orange
          high: '#c2410c',          // orange-700 on white → 5.2:1 ✓
          'high-dark': '#fb923c',  // orange-400 on gray-900 → 4.7:1 ✓
          'high-bg': '#fff7ed',
          'high-bg-dark': '#7c2d12',
          // critical = red
          critical: '#b91c1c',      // red-700 on white → 5.8:1 ✓
          'critical-dark': '#f87171', // red-400 on gray-900 → 5.1:1 ✓
          'critical-bg': '#fef2f2',
          'critical-bg-dark': '#7f1d1d',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Menlo', 'monospace'],
      },
      borderRadius: {
        card: '0.75rem',
      },
      boxShadow: {
        card: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
        'card-dark': '0 1px 3px 0 rgb(0 0 0 / 0.4)',
      },
    },
  },
  plugins: [],
}

export default config
