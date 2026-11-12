import { useCallback, useEffect, useRef, useState } from 'react'
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
  const [activeGame, setActiveGame] = useState(null)
  const [checkingActive, setCheckingActive] = useState(!api.isDemo())
  const [activeCheckError, setActiveCheckError] = useState(null)
  const countriesRef = useRef([])           // выбранные страны; «Ещё раз» на финальном экране играет с тем же выбором

  useEffect(() => {
    if (api.isDemo()) return
    let alive = true

    api.getActiveGame()
      .then((state) => { if (alive) setActiveGame(state) })
      .catch(() => {
        if (alive) setActiveCheckError('Не удалось проверить активную игру. Обнови страницу.')
      })
      .finally(() => { if (alive) setCheckingActive(false) })

    return () => { alive = false }
  }, [])

  const begin = useCallback((r) => {
    setRound(r); setGuess(null); setLast(null); setMapBig(false); setError(null); setPhase('play')
  }, [])

  const start = useCallback(async (countries) => {
    if (busy || checkingActive || activeCheckError) return
    // сюда может прийти событие клика (onClick={g.start}), поэтому берём только массив
    if (Array.isArray(countries)) countriesRef.current = countries
    setBusy(true); setError(null)
    try {
      if (activeGame) {
        const resumed = await api.resumeGame()
        if (!resumed) {
          setActiveGame(null)
          setError('Предыдущая игра уже завершена. Можно начать новую.')
          return
        }

        const { state, round: r } = resumed
        begin(r)
        setTotal(state.game_total)
        setHistory(state.history.map((h) => ({ distance: h.distance_km, score: h.score })))

        const lastAnswer = state.history.at(-1)
        if (lastAnswer && r.round_no === state.rounds_completed) {
          setLast({
            distance_km: lastAnswer.distance_km,
            score: lastAnswer.score,
            total: state.game_total,
            true: {
              lat: lastAnswer.true_coordinates.latitude,
              lon: lastAnswer.true_coordinates.longitude,
            },
            finished: state.is_finished,
          })
          setPhase('result')
        }

        setActiveGame(null)
        return
      }

      const { round: r, demo: isDemo, reason } = await api.startGame(countriesRef.current)
      setDemo(isDemo); setDemoReason(reason || ''); setTotal(r.total ?? 0); setHistory([])
      begin(r)
    } catch (e) {
      setError(e?.detail || 'Не получилось начать игру. Попробуй ещё раз.')
    } finally {
      setBusy(false)
    }
  }, [begin, busy, checkingActive, activeCheckError, activeGame])

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
      if (!api.isDemo()) {
        setProfile({
          total: r.user_total,
          error: false,
        })
      }
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

  const toggleMap = useCallback(() => setMapBig((b) => !b), [])

  const [profile, setProfile] = useState({
    total: null,
    error: false,
  })

  useEffect(() => {
    if (api.isDemo()) return

    let alive = true

    api.getProfile()
      .then((user) => {
        if (!alive) return

        setProfile((previous) => previous.total === null
          ? { total: user.total_score, error: false }
          : previous)
      })
      .catch(() => {
        if (!alive) return

        setProfile((previous) => previous.total === null
          ? { total: null, error: true }
          : previous)
      })

    return () => {
      alive = false
    }
  }, [])

  return { phase, round, guess, last, total, history, busy, error, demo, demoReason, mapBig, start, pick, submit, next, finish, toggleMap, profile, activeGame, checkingActive, activeCheckError }
}
