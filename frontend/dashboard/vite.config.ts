import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
  optimizeDeps: {
    include: ['react', 'react-dom', 'react-router-dom', 'socket.io-client'],
  },
  resolve: {
    alias: {
      '@lib': path.resolve(import.meta.url, '../src/lib'),
    },
  },
});
