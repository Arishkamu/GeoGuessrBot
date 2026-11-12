import { fmt, useCountUp } from '../utils.js'

export default function Hud({ roundNo, roundsTotal, phase, total }) {
  const shown = useCountUp(total, 900, 0)
  const segments = []
  for (let i = 1; roundsTotal && i <= roundsTotal; i++) {
    const done = i < roundNo || (i === roundNo && phase === 'result')
    segments.push(<i key={i} className={done ? 'done' : i === roundNo ? 'now' : ''} />)
  }
  return (
    <header className="hud">
      <div className="pill glass">
        <div className="rounds" aria-label="Раунды">{segments}</div>
        <span className="num">{roundsTotal ? `${roundNo}/${roundsTotal}` : `Раунд ${roundNo}`}</span>
      </div>
      <div className="pill glass">
        <span className="num">{fmt(shown)}</span>
        <small>за игру</small>
      </div>
    </header>
  )
}
