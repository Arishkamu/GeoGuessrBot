import { useCallback, useRef, useState } from 'react'
import * as api from '../api.js'
import { haptic } from '../telegram.js'

/* Вся логика игры в одном месте.
   phase: 'start' → 'play' ⇄ 'result' → 'final' */
export function useGame() {
  const [phase, setPhase] = useState('start')
  const [round, setRound] = useState(null)      // { round_no, rounds_total, token, image_url }
  const [guess, setGuess] = useState(null)      // { lat, lon } | null
  const [last, setLast] = useState(null)        // ответ сервера на последнюю догадку
  const [total, setTotal] = useState(0)
  const [history, setHistory] = useState([])    // [{ distance, score }]
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [demo, setDemo] = useState(api.isDemo())
  const [demoReason, setDemoReason] = useState(api.getDemoReason())
  const [mapBig, setMapBig] = useState(false)
  const [review, setReview] = useState('idle')   // разбор раунда: idle | sending | sent | error
  const countriesRef = useRef([])           // выбранные страны; «Ещё раз» на финальном экране играет с тем же выбором

  const begin = useCallback((r) => {
    setRound(r); setGuess(null); setLast(null); setMapBig(false); setError(null); setReview('idle'); setPhase('play')
  }, [])

  const start = useCallback(async (countries) => {
    // сюда может прийти событие клика (onClick={g.start}), поэтому берём только массив
    if (Array.isArray(countries)) countriesRef.current = countries
    setBusy(true); setError(null)
    try {
      const { round: r, demo: isDemo, reason } = await api.startGame(countriesRef.current)
      setDemo(isDemo); setDemoReason(reason || ''); setTotal(0); setHistory([])
      begin(r)
    } catch (e) {
      setError(e?.detail || 'Не получилось начать игру. Попробуй ещё раз.')
    } finally {
      setBusy(false)
    }
  }, [begin])

  const pick = useCallback((ll) => {
    if (phase !== 'play') return
    setGuess({ lat: ll.lat, lon: ll.lng })
    haptic('light')
  }, [phase])

  const submit = useCallback(async () => {
    if (!guess || phase !== 'play' || busy) return
    setBusy(true); setError(null)
    try {
      const r = await api.sendGuess(round.token, guess)
      setLast(r); setTotal(r.total)
      setHistory((h) => [...h, { distance: r.distance_km, score: r.score }])
      setPhase('result')
      haptic('medium')
    } catch (e) {
      setError('Не вышло, нажми ещё раз')
    } finally {
      setBusy(false)
    }
  }, [guess, phase, busy, round])

  const next = useCallback(async () => {
    if (last?.finished) { setPhase('final'); return }
    setBusy(true); setError(null)
    try {
      begin(await api.nextRound())
    } catch (e) {
      setError('Не вышло, нажми ещё раз')
    } finally {
      setBusy(false)
    }
  }, [last, begin])

  const finish = useCallback(async () => {
    try { await api.finishGame(round?.token) } catch (e) { /* результат уже сохранён после каждого раунда */ }
    setPhase('final')
  }, [round])

  const askReview = useCallback(async () => {
    if (review === 'sending' || review === 'sent') return
    setReview('sending')
    try { await api.requestReview(); setReview('sent') } catch (e) { setReview('error') }
  }, [review])

  const toggleMap = useCallback(() => setMapBig((b) => !b), [])

  return { phase, round, guess, last, total, history, busy, error, demo, demoReason, mapBig, review, askReview, start, pick, submit, next, finish, toggleMap }
}