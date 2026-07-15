import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:4173',
      '/data': 'http://127.0.0.1:4173',
    },
  },
  build: { outDir: 'dist', sourcemap: false },
})
