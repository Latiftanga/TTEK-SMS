import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [tailwindcss(), sveltekit()],
  server: {
    host: '0.0.0.0',
    port: 5173,
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
