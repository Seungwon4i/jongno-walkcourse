import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  // GitHub Pages 하위경로 서빙: https://urbsn4i-sw.github.io/jongno-walkcourse/
  base: '/jongno-walkcourse/',
  plugins: [react()],
})
