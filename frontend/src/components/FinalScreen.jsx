import { share } from '../telegram.js'
import { fmt, plural, useAfterMount, useCountUp } from '../utils.js'
import TopList from './TopList.jsx'
import UserScore from './UserScore.jsx'

const C = 2 * Math.PI * 52

export default function FinalScreen({ total, profile, demo, history, onAgain }) {
  const n = history.length || 1
  const avg = total / n
  const share01 = Math.min(1, avg / 5000)
  const shown = useCountUp(total, 1300, 0)
  const ready = useAfterMount()
  const verdict = share01 >= 0.7 ? 'Отличный результат' : share01 >= 0.4 ? 'Хороший результат' : 'Есть куда расти'

  return (
    <div className="screen" id="finalScreen">
      <div className="ring">
        <svg viewBox="0 0 120 120">
          <defs>
            <linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="#ff3d78" /><stop offset="1" stopColor="#14a3a8" />
            </linearGradient>
          </defs>
          <circle className="track" cx="60" cy="60" r="52" />
          <circle className="fill" cx="60" cy="60" r="52" strokeDasharray={C} strokeDashoffset={ready ? C * (1 - share01) : C} />
        </svg>
        <div className="center">
          <div className="big num">{fmt(shown)}</div>
          <div className="of">{n} {plural(n, 'раунд', 'раунда', 'раундов')} · в среднем {fmt(avg)}</div>
        </div>
      </div>
      <div className="verdict">{verdict}</div>
      <UserScore profile={profile} demo={demo} />
      <ul className="list num">
        {history.map((h, i) => (
          <li key={i}>
            <span>Раунд {i + 1} · {fmt(h.distance)} км</span>
            <b>+{fmt(h.score)}</b>
            <div className="bar"><i style={{ width: `${Math.max(1, h.score / 50)}%` }} /></div>
          </li>
        ))}
      </ul>
      <TopList id="finalTop" limit={5} />
      <div className="grow" />
      <div className="actions">
        <button className="btn" type="button" onClick={onAgain}>Сыграть ещё</button>
      </div>
    </div>
  )
}
