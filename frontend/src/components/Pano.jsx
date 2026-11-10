import { useEffect, useRef, useState } from 'react'

/* 360-панорама на весь экран (библиотека Pannellum, лежит в public/vendor и подгружается при первой панораме).
   Крутится пальцем, приближается щипком. key={url} в App пересоздаёт компонент в каждом раунде. */
const asset = (p) => new URL(p, document.baseURI).href
let loader = null
function loadPannellum() {
  if (window.pannellum) return Promise.resolve()
  if (!loader) {
    loader = new Promise((resolve, reject) => {
      const css = document.createElement('link')
      css.rel = 'stylesheet'
      css.href = asset('vendor/pannellum/pannellum.css')
      document.head.appendChild(css)
      const s = document.createElement('script')
      s.src = asset('vendor/pannellum/pannellum.js')
      s.onload = resolve
      s.onerror = () => { loader = null; reject(new Error('pannellum')) }
      document.head.appendChild(s)
    })
  }
  return loader
}

export default function Pano({ url }) {
  const box = useRef(null)
  const [state, setState] = useState('loading')   // loading | ready | error
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let viewer = null
    let dead = false
    setState('loading')
    loadPannellum()
      .then(() => {
        if (dead || !box.current) return
        viewer = window.pannellum.viewer(box.current, {
          type: 'equirectangular',
          panorama: url,
          autoLoad: true,
          showControls: false, showFullscreenCtrl: false, showZoomCtrl: false, compass: false,
          hfov: 100, minHfov: 45, maxHfov: 120,
          pitch: 0, yaw: Math.random() * 360 - 180,     // в каждом раунде смотрим в случайную сторону
          mouseZoom: true, keyboardZoom: false, friction: 0.2,
          crossOrigin: 'anonymous',
        })
        viewer.on('load', () => !dead && setState('ready'))
        viewer.on('error', () => !dead && setState('error'))
      })
      .catch(() => !dead && setState('error'))
    return () => { dead = true; try { viewer?.destroy() } catch (e) { /* уже уничтожен */ } }
  }, [url, attempt])

  return (
    <section className="photo pano" data-state={state}>
      <div ref={box} className="pano-box" aria-label="Панорама 360°, крутите пальцем" />
      {state === 'loading' && <div className="pano-msg">Загружаем панораму…</div>}
      {state === 'error' && (
        <div className="pano-msg">
          Не удалось загрузить панораму
          <button className="chip glass" type="button" onClick={() => setAttempt((a) => a + 1)}>Повторить</button>
        </div>
      )}
    </section>
  )
}
