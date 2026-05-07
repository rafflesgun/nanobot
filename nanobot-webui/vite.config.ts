import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  root: '.',
  build: {
    outDir: 'dist/client',
    emptyOutDir: false
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:6060',
      '/socket.io': {
        target: 'ws://127.0.0.1:6060',
        ws: true
      }
    }
  }
})
