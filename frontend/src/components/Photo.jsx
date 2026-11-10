import { useState } from 'react'

/* Фото на весь экран. key={url} в App пересоздаёт компонент в каждом раунде,
   поэтому «загружено» сбрасывается само. */
export default function Photo({ url, onOpen }) {
  const [ready, setReady] = useState(false)
  return (
    <section className="photo">
      <img
        id="photo"
        src={url}
        alt="Фото места, которое нужно найти на карте"
        className={ready ? 'ready' : ''}
        onLoad={() => setReady(true)}
        onClick={onOpen}
      />
    </section>
  )
}
