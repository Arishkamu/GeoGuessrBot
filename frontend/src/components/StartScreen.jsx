import { useEffect, useState } from 'react'
import TopList from './TopList.jsx'
import globe from '../assets/globe.webp'
import { getCountries } from '../api.js'
import { COUNTRIES } from '../countries.js'   // запасной список, если сервер не ответил
import UserScore from './UserScore.jsx'

const KEY = 'geoguessr.countries'

const flagOf = (cc) => String.fromCodePoint(...[...cc.toUpperCase()].map((c) => 0x1f1a5 + c.charCodeAt(0)))

const nameOf = (() => {
  let dn = null
  try { dn = new Intl.DisplayNames(['ru'], { type: 'region' }) } catch { /* без названий */ }
  return (cc) => { try { return dn?.of(cc) || cc } catch { return cc } }
})()

function loadSaved() {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || '[]')
    return Array.isArray(v) ? v.slice(0, 1) : []
  } catch { return [] }
}
function save(list) {
  try { localStorage.setItem(KEY, JSON.stringify(list)) } catch { /* хранилище недоступно: не страшно */ }
}

export default function StartScreen({ busy, error, demo, demoReason, onPlay, profile, activeGame, checkingActive, activeCheckError }) {
  const [list, setList] = useState(COUNTRIES)        // пока грузится или при ошибке: запасной список
  const [picked, setPicked] = useState(loadSaved)    // одна выбранная страна; пусто = весь мир

  useEffect(() => {
    let alive = true
    getCountries()
      .then((r) => {
        if (alive && Array.isArray(r) && r.length) {
          setList(r.map((c) => ({ code: c.code, name: nameOf(c.code) })))
        }
      })
      .catch(() => {})   // сервер недоступен: остаётся запасной список
    return () => { alive = false }
  }, [])

  // сохранённая страна могла пропасть из списка
  const codes = new Set(list.map((c) => c.code))
  const valid = picked.filter((c) => codes.has(c))

  const toggle = (code) => {
    const next = valid.includes(code) ? [] : [code]   // один выбор; повторный клик снимает его
    setPicked(next); save(next)
  }
  const reset = () => { setPicked([]); save([]) }

  return (
    <div className="screen" id="startScreen">
      <UserScore profile={profile} demo={demo} />
      <h1>GeoGuessr</h1>
      <p className="lead">Фото со всего мира. Отметь на карте, где оно сделано. Чем ближе, тем больше очков. Играй, сколько хочешь.</p>
      <div className="globe-wrap"><img src={globe} alt="" width="840" height="769" decoding="async" /></div>
      <div className="countries" role="group" aria-label="Страны">
        <button type="button" className={`cchip${valid.length === 0 ? ' on' : ''}`} aria-pressed={valid.length === 0} onClick={reset}>🌍 Весь мир</button>
        {list.map((c) => (
          <button key={c.code} type="button" className={`cchip${valid.includes(c.code) ? ' on' : ''}`}
            aria-pressed={valid.includes(c.code)} onClick={() => toggle(c.code)}>
            {flagOf(c.code)} {c.name}
          </button>
        ))}
      </div>
      <TopList id="startTop" limit={3} />
      <div className="actions">
        {activeGame && (
          <p>Пройдено {activeGame.rounds_completed} из {activeGame.rounds_total} раундов · {activeGame.game_total} очков</p>
        )}
        <button className="btn" type="button" disabled={busy || checkingActive || !!activeCheckError} onClick={() => onPlay(valid)}>
          {checkingActive ? 'Проверяем игру…' : error || (activeGame ? 'Продолжить игру' : 'Играть')}
        </button>
        {activeCheckError && <p className="notice" role="alert">{activeCheckError}</p>}
      </div>
      {demo && <p className="notice">Сервер не отвечает, включён демо-режим с тестовыми картинками.{demoReason ? ` Причина: ${demoReason}.` : ''}</p>}
    </div>
  )
}
