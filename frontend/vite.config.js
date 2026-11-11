import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const apiTarget = process.env.API_PROXY_TARGET

// allowedHosts: true нужен, чтобы Vite пускал запросы с адресов туннеля (trycloudflare.com, ngrok).
export default defineConfig({
  plugins: [react()],
  base: './',
  server: {
    host: true,
    port: 5173,
    allowedHosts: true,
    // запросы /api уйдут на сервер игры (FastAPI). Он должен работать НА ДРУГОМ порту, не на порту Vite:
    // иначе прокси отправит запрос самому себе, и кнопки зависнут.
    proxy: { '/api': apiTarget, '/photos': apiTarget },
  },
  preview: {
    host: true,
    port: 8000,
    strictPort: true,
    allowedHosts: true,
    proxy: { '/api': apiTarget, '/photos': apiTarget },
  },
})
