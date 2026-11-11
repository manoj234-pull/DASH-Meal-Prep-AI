/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './*.{js,ts,jsx,tsx}',
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './Animated UI/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        walnut: {
          950: '#110904',
          900: '#23150D',
          800: '#3D2314', // Primary dark walnut wood
          700: '#54321E',
          600: '#6E4229',
        },
        saffron: {
          500: '#F59E0B', // Primary bright amber/saffron
          600: '#D97706',
        },
        persimmon: {
          500: '#EA580C', // Alert/highlight accent
        },
        cream: {
          50: '#FFFDF9',
          100: '#FFF8F5', // Canvas base background
          200: '#FDEEE5', // Subtle card container background
          300: '#F7E1D2', // Border tone
        },
        muted: {
          espresso: '#4A3B32',
          clay: '#7C6A5F',
        }
      },
      fontFamily: {
        serif: ['Georgia', 'serif'],
        sans: ['Plus Jakarta Sans', 'sans-serif'],
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        fadeIn: 'fadeIn 0.35s ease-out forwards',
      },
      borderRadius: {
        '2xl': '1.25rem',
        '3xl': '1.75rem',
      }
    },
  },
  plugins: [],
}
