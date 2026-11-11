import { useState } from 'react'

/* Маленькая плашка в игре: показывает, что включён демо-режим, и по нажатию объясняет почему. */
export default function DemoBadge({ reason }) {
  const [open, setOpen] = useState(false)
  const code = reason.split(':')[0]
  return (
    <button className="demo-badge glass" type="button" onClick={() => setOpen((o) => !o)}>
      {open ? `Демо-режим. Причина: ${reason}` : `Демо · ${code.length > 12 ? 'ошибка' : code}`}
    </button>
  )
}
