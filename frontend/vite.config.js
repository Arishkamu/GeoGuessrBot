import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

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
    proxy: { '/api': 'http://localhost:8080', '/photos': 'http://localhost:8080' },
  },
  preview: { host: true, port: 4173, allowedHosts: true },
})
