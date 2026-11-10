import TopList from './TopList.jsx'
import globe from '../assets/globe.webp'

export default function StartScreen({ busy, error, demo, onPlay }) {
  return (
    <div className="screen" id="startScreen">
      <h1>GeoGuessr</h1>
      <p className="lead">Фото со всего мира. Отметь на карте, где оно сделано. Чем ближе, тем больше очков. Играй, сколько хочешь.</p>
      <div className="globe-wrap"><img src={globe} alt="" width="840" height="769" decoding="async" /></div>
      <TopList id="startTop" limit={3} />
      <div className="actions">
        <button className="btn" type="button" disabled={busy} onClick={onPlay}>{error || 'Играть'}</button>
      </div>
      {demo && <p className="notice">Сервер не отвечает, включён демо-режим с тестовыми картинками.</p>}
    </div>
  )
}
