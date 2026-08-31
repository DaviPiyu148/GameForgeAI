import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

const backendPort = process.env.BACKEND_PORT || '8000';
const backendTarget = `http://127.0.0.1:${backendPort}`;

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
        target: backendTarget,
        changeOrigin: true,
      },
      '/docs': {
        target: backendTarget,
        changeOrigin: true,
      },
      '/openapi.json': {
        target: backendTarget,
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/phaser') || id.includes('src/runtime/PhaserCanvas') || id.includes('src/runtime/GameScene') || id.includes('src/runtime/behaviors') || id.includes('src/runtime/environmentSystem') || id.includes('src/runtime/vfxSystem') || id.includes('src/runtime/VehicleManager')) {
            return 'phaser-runtime';
          }
          if (id.includes('node_modules/react/') || id.includes('node_modules/react-dom/') || id.includes('node_modules/react-router') || id.includes('node_modules/react-router-dom/')) {
            return 'vendor-react';
          }
        },
      },
    },
  },
});
