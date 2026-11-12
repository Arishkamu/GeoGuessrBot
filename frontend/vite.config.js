import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Адрес бэкенда: в Docker его задаёт compose (http://backend:8080), локально это localhost:8080.
const apiTarget = process.env.API_PROXY_TARGET || 'http://localhost:8080'
const proxy = { '/api': apiTarget, '/photos': apiTarget }

// allowedHosts: true нужен, чтобы Vite пускал запросы с адресов туннеля (trycloudflare.com, ngrok).
export default defineConfig({
  plugins: [react()],
  base: './',
  server: { host: true, port: 5173, allowedHosts: true, proxy },
  preview: { host: true, port: 8000, allowedHosts: true, proxy },
})