import { forwardRef } from 'react'
import { fmt, useAfterMount, useCountUp } from '../utils.js'

function ResultPanel({ result, busy, error, review, onReview, onNext, onFinish }) {
  const dist = useCountUp(result.distance_km, 1000, 0)
  const ready = useAfterMount()
  const width = ready ? Math.max(2, Math.min(100, result.score / 50)) : 0
  return (
    <div className="result">
      <div className="main">
        <div className="dist num"><span>{fmt(dist)}</span><small>км от цели</small></div>
        <div className="pts num">+{fmt(result.score)}<small>очков за раунд</small></div>
      </div>
      <div className="meter" aria-hidden="true"><i style={{ width: `${width}%` }} /></div>
      <div className="credit">
        {(result.author ? `Фото: ${result.author}` : 'Фото') + (result.license ? `, ${result.license}` : '')}
        {result.source_url && <> · <a href={result.source_url} target="_blank" rel="noopener noreferrer">источник</a></>}
      </div>
      <button className="btn" type="button" disabled={busy} onClick={onNext}>
        {error || (result.finished ? 'Итоги' : 'Дальше')}
      </button>
      {onReview && (
        <button className="btn secondary small" type="button" disabled={review === 'sending' || review === 'sent'} onClick={onReview}>
          {review === 'sent' ? 'Разбор отправлен в чат ✓'
            : review === 'sending' ? 'Отправляю…'
            : review === 'error' ? 'Не вышло, повторить'
            : 'Прислать разбор в чат'}
        </button>
      )}
      {!result.finished && (
        <button className="btn secondary small" type="button" onClick={onFinish}>Завершить игру</button>
      )}
    </div>
  )
}

/* Нижняя панель: кнопка «Угадать» во время раунда, панель с результатом после ответа. */
const Dock = forwardRef(function Dock({ phase, guess, last, busy, error, review, onReview, onSubmit, onNext, onFinish }, ref) {
  const isResult = phase === 'result' && last
  return (
    <footer className={`dock${isResult ? ' sheet' : ''}`} id="dock" ref={ref}>
      {phase === 'play' && (
        <button className="btn" type="button" disabled={!guess || busy} onClick={onSubmit}>
          {busy ? 'Считаю…' : error || (guess ? 'Угадать' : 'Отметь точку на карте')}
        </button>
      )}
      {isResult && <ResultPanel result={last} busy={busy} error={error} review={review} onReview={onReview} onNext={onNext} onFinish={onFinish} />}
    </footer>
  )
})

export default Dock