import { useEffect, useRef, useState } from 'react'
import { initTelegram } from './telegram.js'
import { useGame } from './hooks/useGame.js'
import Photo from './components/Photo.jsx'
import Pano from './components/Pano.jsx'
import DemoBadge from './components/DemoBadge.jsx'
import Hud from './components/Hud.jsx'
import MapCard from './components/MapCard.jsx'
import Dock from './components/Dock.jsx'
import StartScreen from './components/StartScreen.jsx'
import FinalScreen from './components/FinalScreen.jsx'

export default function App() {
  const g = useGame()
  const dockRef = useRef(null)
  const [viewer, setViewer] = useState(false)
  const [sheetHeight, setSheetHeight] = useState(230)

  useEffect(() => { initTelegram() }, [])
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') setViewer(false) }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])
  // запоминаем высоту панели результата, чтобы карта не прятала точки под ней
  useEffect(() => {
    if (g.phase === 'result' && dockRef.current) setSheetHeight(dockRef.current.offsetHeight)
  }, [g.phase, g.last])

  const isPano = g.round?.kind === 'pano'
  const inGame = g.phase === 'play' || g.phase === 'result'
  const mapPhase = g.phase === 'result' ? 'result' : 'play'

  return (
    <>
      <div id="app" data-phase={g.phase} className={[g.mapBig && 'map-big', isPano && 'is-pano'].filter(Boolean).join(' ')}>
        {g.round && (isPano
          ? <Pano key={g.round.token} url={g.round.image_url} />
          : <Photo key={g.round.image_url} url={g.round.image_url} onOpen={() => setViewer(true)} />)}

        <Hud roundNo={g.round?.round_no ?? 1} roundsTotal={g.round?.rounds_total ?? null} phase={g.phase} total={g.total} />

        {isPano ? (
          <div className="chip glass zoom pano-hint">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12a9 9 0 1 1-3-6.7M21 4v5h-5" />
            </svg>
            Крутите панораму 360°
          </div>
        ) : (
          <button className="chip glass zoom" type="button" onClick={() => setViewer(true)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="7" /><path d="M20 20l-4-4M11 8v6M8 11h6" />
            </svg>
            Приблизить фото
          </button>
        )}

        <MapCard
          phase={mapPhase}
          big={g.mapBig}
          guess={g.guess}
          truth={g.phase === 'result' ? g.last?.true : null}
          roundToken={g.round?.token}
          sheetHeight={sheetHeight}
          onPick={g.pick}
          onToggle={g.toggleMap}
        />

        {inGame && (
          <Dock
            ref={dockRef}
            phase={g.phase}
            guess={g.guess}
            last={g.last}
            busy={g.busy}
            error={g.error}
            onSubmit={g.submit}
            onNext={g.next}
            onFinish={g.finish}
          />
        )}
      </div>

      {g.demo && g.phase !== 'start' && g.demoReason && <DemoBadge reason={g.demoReason} />}
      {g.phase === 'start' && (
        <StartScreen busy={g.busy} error={g.error} demo={g.demo} demoReason={g.demoReason} profile={g.profile} onPlay={g.start}/>
      )}
      {g.phase === 'final' && (
        <FinalScreen total={g.total} profile={g.profile} demo={g.demo} history={g.history} onAgain={g.start} />
      )}

      {viewer && g.round && !isPano && (
        <div id="viewer">
          <img src={g.round.image_url} alt="Фото в большом размере" />
          <button className="close" type="button" onClick={() => setViewer(false)}>Закрыть</button>
        </div>
      )}
    </>
  )
}
