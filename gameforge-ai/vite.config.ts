import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    tailwindcss(),
    react(),
  ],
  server: {
    // Bind explicitly to the IPv4 loopback. Vite's default "localhost" host
    // resolves via Node's dns.lookup(), which on this machine (and any host
    // where IPv6 is preferred/verbatim-ordered) returns ::1 only -- leaving
    // the server unreachable at the 127.0.0.1 URL that start.bat opens and
    // reports.
    host: '127.0.0.1',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});
