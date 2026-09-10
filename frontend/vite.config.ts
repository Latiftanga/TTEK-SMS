import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [tailwindcss(), sveltekit()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // The `playwright` screenshot-tool container (docker-compose.yml, `tools`
    // profile) reaches this dev server via the docker-network service name,
    // which Vite's DNS-rebinding protection doesn't recognize by default.
    allowedHosts: ['frontend'],
    proxy: {
      // In Docker, the browser hits localhost:5173 and we proxy /api to the backend.
      '/api': {
        target: process.env.PUBLIC_API_URL || 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
        changeOrigin: true,
      },
    },
  },
});
