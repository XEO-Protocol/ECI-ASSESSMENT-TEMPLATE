import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  base: './', // so the production build works from file:// inside Electron
  server: { port: 5173, strictPort: true },
  build: { outDir: 'dist' },
});
