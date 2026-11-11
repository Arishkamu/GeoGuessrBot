import { useEffect, useState } from 'react'
import { getTop } from '../api.js'
import { fmt } from '../utils.js'

export default function TopList({ id, limit = 5 }) {
  const [rows, setRows] = useState([])
  useEffect(() => {
    let alive = true
    getTop().then((r) => { if (alive) setRows(r) }).catch(() => { /* рейтинг не критичен */ })
    return () => { alive = false }
  }, [])
  if (!rows.length) return <div id={id} />
  return (
    <div id={id}>
      <div className="sub">Лучшие игры</div>
      <ul className="list num">
        {rows.slice(0, limit).map((r, i) => (
          <li key={i}><span>{i + 1}. {r.name}</span><b>{fmt(r.best)}</b></li>
        ))}
      </ul>
    </div>
  )
}
