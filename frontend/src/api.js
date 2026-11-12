/* Общение с сервером.
   POST /api/game/start {countries?: ['FR','JP']} -> { round_no, rounds_total: null, token, image_url, kind: 'pano' | 'photo' }
   GET  /api/round       -> { round_no, rounds_total: null, token, image_url }
   POST /api/guess {token, lat, lon}
                         -> { distance_km, score, total, true:{lat,lon}, author, license, source_url, finished }
   POST /api/game/finish -> {}   (необязательно)
   GET  /api/top         -> [ { name, best } ]
   GET  /api/countries   -> [ { code: 'FR', count: 12 } ]   страны, по которым есть снимки
   Каждый запрос идёт с заголовком X-Init-Data (подпись Telegram).
   Если сервер недоступен, включается демо-режим с тестовыми картинками. */
import { initData } from './telegram.js'

let demo = new URLSearchParams(window.location.search).has('mock')
let demoReason = ''   // почему включился демо-режим (код ответа сервера или «нет связи»)
export const isDemo = () => demo
export const getDemoReason = () => demoReason

/* Короткое объяснение ошибки для экрана: «401: неверная подпись», «таймаут», «нет связи». */
function reasonOf(e) {
  if (e?.name === 'AbortError') return 'сервер не ответил за 8 секунд'
  if (e?.status) return e.detail ? `${e.status}: ${e.detail}` : String(e.status)
  return 'нет связи с сервером'
}

export function haversine(la1, lo1, la2, lo2) {
  const R = 6371, rad = Math.PI / 180
  const dp = (la2 - la1) * rad, dl = (lo2 - lo1) * rad
  const a = Math.sin(dp / 2) ** 2 + Math.cos(la1 * rad) * Math.cos(la2 * rad) * Math.sin(dl / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(a))
}

async function request(method, path, body) {
  if (demo) return mockRequest(method, path, body)
  // если сервер молчит дольше 8 секунд, считаем его недоступным (иначе кнопка зависнет навсегда)
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), 8000)
  try {
    const res = await fetch(path, {
      method,
      headers: { 'Content-Type': 'application/json', 'X-Init-Data': initData() },
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
    })
    if (!res.ok) {
      const body = await res.json().catch(() => null)   // FastAPI кладёт причину в поле detail
      const err = new Error(`${path} ${res.status}`)
      err.status = res.status
      const d = body?.detail
      err.detail = typeof d === 'string' ? d
        : Array.isArray(d) ? d.map((x) => `${(x.loc || []).join('.')}: ${x.msg}`).join('; ')   // 422: какое поле не подошло
        : ''
      throw err
    }
    return await res.json()
  } finally {
    clearTimeout(timer)
  }
}

/* ---------- демо-режим ---------- */
const PLACES = [
  { lat: 48.8584, lon: 2.2945, a: '#2f6f8f' },
  { lat: 35.0116, lon: 135.7681, a: '#6f8f2f' },
  { lat: -33.9249, lon: 18.4241, a: '#8f5a2f' },
  { lat: -34.6037, lon: -58.3816, a: '#5a2f8f' },
  { lat: 64.1466, lon: -21.9426, a: '#2f8f7a' },
]
const mock = { n: 0, total: 0 }

function mockImage(p, n) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1800"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${p.a}"/><stop offset="1" stop-color="#10222b"/></linearGradient></defs><rect width="1200" height="1800" fill="url(#g)"/><text x="600" y="800" text-anchor="middle" font-family="sans-serif" font-size="64" fill="#fff" fill-opacity=".85">Демо-фото ${n}</text></svg>`
  return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg)
}

async function mockRequest(method, path, body) {
  await new Promise((r) => setTimeout(r, 150))
  const place = () => PLACES[mock.n % PLACES.length]
  // в демо-режиме чётные раунды (2, 4, …) показываем как обычные фото, остальные как 360-панорамы
  const round = () => mock.n % 2 === 1
    ? { round_no: mock.n + 1, rounds_total: null, token: 'demo' + mock.n, kind: 'photo', image_url: mockImage(place(), mock.n + 1) }
    : { round_no: mock.n + 1, rounds_total: null, token: 'demo' + mock.n, kind: 'pano', image_url: new URL('demo-pano.jpg', document.baseURI).href }
  if (path === '/api/game/start') { mock.n = 0; mock.total = 0; return round() }
  if (path === '/api/round') return round()
  if (path === '/api/game/finish') return {}
  if (path === '/api/guess') {
    const p = place()
    const d = haversine(body.lat, body.lon, p.lat, p.lon)
    const score = Math.round(5000 * Math.exp(-d / 1500))
    mock.total += score; mock.n += 1
    return { distance_km: d, score, total: mock.total, true: { lat: p.lat, lon: p.lon }, author: 'Демо', license: 'CC0', source_url: '', finished: false }
  }
  if (path === '/api/countries') return [{ code: 'FR', count: 12 }, { code: 'JP', count: 9 }, { code: 'ZA', count: 6 }, { code: 'AR', count: 5 }, { code: 'IS', count: 4 }]
  if (path === '/api/top') return [{ name: 'Аня', best: 21840 }, { name: 'Игорь', best: 19320 }, { name: 'Мария', best: 17105 }]
  throw new Error('mock: ' + path)
}

/* ---------- то, чем пользуется интерфейс ---------- */
/* Ручки бэкенда команды:
     POST /api/game/start          -> { game_id }
     GET  /api/round/{game_id}     -> { round_id, round_no, image_url }
     POST /api/guess/{game_id}     { round_id, latitude, longitude }
                                   -> { true_coordinates:{latitude,longitude}, distance_km, score, is_game_finished }
     POST /api/game/finish?game_id=
   Интерфейсу нужен другой вид (token, true, total), поэтому здесь они переводятся друг в друга.
   В демо-режиме ходим по старым путям: их знает mockRequest. */
const live = { gameId: null, roundId: null, total: 0 }

const asRound = (r) => ({
  round_no: r.round_no, rounds_total: null, token: String(r.round_id), image_url: r.image_url, kind: r.kind || 'pano',
})

async function liveRound() {
  const r = await request('GET', `/api/round/${live.gameId}`)
  live.roundId = r.round_id
  return asRound(r)
}

async function liveStart() {
  const g = await request('POST', '/api/game/start')
  live.gameId = g.game_id
  live.total = 0
  return liveRound()
}

export async function startGame(countries = []) {
  const body = countries.length ? { countries } : undefined   // сервер пока не использует, ручка start ждёт без тела
  const run = () => (demo ? request('POST', '/api/game/start', body) : liveStart())
  try {
    return { round: await run(), demo, reason: demoReason }
  } catch (e) {
    if (demo) throw e
    if (e?.status >= 400 && e.status < 500 && e.status !== 401) throw e   // например «для выбранных стран нет снимков»: сервер жив, демо не нужно
    demo = true // сервер недоступен: играем на тестовых данных
    demoReason = reasonOf(e)
    console.warn('[geoguessr] демо-режим:', demoReason, e)
    return { round: await run(), demo, reason: demoReason }
  }
}

export const nextRound = () => (demo ? request('GET', '/api/round') : liveRound())

export async function sendGuess(token, g) {
  if (demo) return request('POST', '/api/guess', { token, lat: g.lat, lon: g.lon })
  const payload = { round_id: Number(live.roundId ?? token), latitude: g.lat, longitude: g.lon }   // ровно поля GuessRequest
  let r
  try {
    r = await request('POST', `/api/guess/${live.gameId}`, payload)
  } catch (e) {
    console.warn('[geoguessr] догадка не принята:', e.status, e.detail, payload)
    throw e
  }
  live.total += r.score
  return {
    distance_km: r.distance_km, score: r.score, total: live.total,
    true: { lat: r.true_coordinates.latitude, lon: r.true_coordinates.longitude },
    author: '', license: '', source_url: '', finished: !!r.is_game_finished,
  }
}

export const finishGame = () => (demo
  ? request('POST', '/api/game/finish')
  : request('POST', `/api/game/finish?game_id=${live.gameId}`))
export const getCountries = () => request('GET', '/api/countries')
export const getTop = () => request('GET', '/api/top')