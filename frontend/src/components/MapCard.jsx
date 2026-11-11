import { useEffect, useRef } from 'react'
import L from 'leaflet'
import { isDark, onThemeChange } from '../telegram.js'
import { reducedMotion } from '../utils.js'

const pinIcon = (cls) =>
  L.divIcon({ className: '', html: `<div class="pin ${cls} pop"></div>`, iconSize: [26, 26], iconAnchor: [13, 13] })

const WORLD = { center: [30, 10], zoom: 2 }

/* Карточка с картой. Leaflet подключён напрямую (без react-leaflet): так проще управлять
   булавками, линией и анимацией раскрытия.
   props:
     phase        'play' | 'result'
     guess        { lat, lon } | null     — догадка игрока
     truth        { lat, lon } | null     — настоящая точка (после ответа)
     roundToken   меняется в каждом раунде → карта возвращается к виду на весь мир
     sheetHeight  высота нижней панели, чтобы кадр не прятался под ней
     onPick(latlng), onToggle()  */
export default function MapCard({ phase, big, guess, truth, roundToken, sheetHeight, onPick, onToggle }) {
  const boxRef = useRef(null)
  const mapRef = useRef(null)
  const tilesRef = useRef(null)
  const guessMarker = useRef(null)
  const pickRef = useRef(onPick)
  const phaseRef = useRef(phase)
  pickRef.current = onPick
  phaseRef.current = phase

  // создаём карту один раз
  useEffect(() => {
    const map = L.map(boxRef.current, { zoomControl: false, worldCopyJump: true, minZoom: 2, maxZoom: 18 })
      .setView(WORLD.center, WORLD.zoom)
    map.on('click', (e) => { if (phaseRef.current === 'play') pickRef.current(e.latlng) })
    mapRef.current = map
    return () => { map.remove(); mapRef.current = null }
  }, [])

  // светлая или тёмная подложка по теме Telegram
  useEffect(() => {
    const apply = () => {
      const map = mapRef.current
      if (!map) return
      if (tilesRef.current) map.removeLayer(tilesRef.current)
      // тайлы OpenStreetMap (ключ не нужен); тёмная тема получается фильтром через CSS-класс dark-tiles
      tilesRef.current = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap', maxZoom: 19,
        className: isDark() ? 'dark-tiles' : '',
      }).addTo(map)
    }
    apply()
    return onThemeChange(apply)
  }, [])

  // булавка догадки
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (!guess) {
      if (guessMarker.current) { map.removeLayer(guessMarker.current); guessMarker.current = null }
      return
    }
    const ll = L.latLng(guess.lat, guess.lon)
    if (guessMarker.current) guessMarker.current.setLatLng(ll)
    else guessMarker.current = L.marker(ll, { icon: pinIcon('guess'), keyboard: false }).addTo(map)
  }, [guess])

  // новый раунд: вернуть вид на весь мир
  useEffect(() => {
    const id = setTimeout(() => {
      mapRef.current?.invalidateSize()
      mapRef.current?.setView(WORLD.center, WORLD.zoom)
    }, 520)
    return () => clearTimeout(id)
  }, [roundToken])

  // раскрытие: настоящая точка, линия, кадр по обеим точкам
  useEffect(() => {
    const map = mapRef.current
    if (!map || !truth || !guess) return undefined
    const g = L.latLng(guess.lat, guess.lon), t = L.latLng(truth.lat, truth.lon)
    const truthMarker = L.marker(t, { icon: pinIcon('truth'), keyboard: false }).addTo(map)
    const line = L.polyline([g, t], { className: 'link-line', interactive: false }).addTo(map)
    const timers = []
    timers.push(setTimeout(() => {
      map.invalidateSize()
      map.fitBounds(L.latLngBounds([g, t]), {
        paddingTopLeft: [48, 96], paddingBottomRight: [48, (sheetHeight || 230) + 36], maxZoom: 8, animate: true, duration: 0.9,
      })
      const path = line.getElement()
      if (path && !reducedMotion() && path.getTotalLength) {
        const len = path.getTotalLength()
        if (len) {
          path.style.strokeDasharray = len
          path.style.strokeDashoffset = len
          path.getBoundingClientRect()
          path.style.transition = 'stroke-dashoffset 1s ease .35s'
          path.style.strokeDashoffset = 0
          timers.push(setTimeout(() => { path.style.transition = ''; path.style.strokeDasharray = '' }, 1500))
        }
      }
    }, 560))
    return () => {
      timers.forEach(clearTimeout)
      map.removeLayer(truthMarker)
      map.removeLayer(line)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [truth])

  return (
    <section
      className="mapcard"
      id="mapcard"
      onTransitionEnd={(e) => { if (e.propertyName === 'top') mapRef.current?.invalidateSize() }}
    >
      <div id="map" ref={boxRef} />
      <div className={`pill glass hint${guess || phase !== 'play' ? ' gone' : ''}`}>Нажми на карту</div>
      <button className="chip glass toggle" type="button" aria-pressed={big} onClick={onToggle}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          {big
            ? <path d="M4 14h6v6M20 10h-6V4M14 10l7-7M3 21l7-7" />
            : <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />}
        </svg>
        <span>{big ? 'Свернуть' : 'Развернуть'}</span>
      </button>
    </section>
  )
}
