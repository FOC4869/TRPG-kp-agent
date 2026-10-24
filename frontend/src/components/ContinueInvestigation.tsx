import { useEffect, useState } from 'react'
import { loadRecentGame, RECENT_GAME_KEY } from '../state/recent-game'
import type { RecentGame } from '../state/recent-game'
import { Arrow, Lock } from './Ornaments'

export function ContinueInvestigation() {
  const [state, setState] = useState<RecentGame | { status: 'loading' }>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let controller: AbortController
    function refresh() {
      controller?.abort()
      const request = new AbortController()
      controller = request
      setState({ status: 'loading' })
      void loadRecentGame(request.signal).then((value) => {
        if (!request.signal.aborted) setState(value)
      }).catch(() => { /* Superseded or unmounted requests are intentionally cancelled. */ })
    }
    function onStorage(event: StorageEvent) {
      if (event.key === RECENT_GAME_KEY || event.key === null) refresh()
    }
    refresh()
    window.addEventListener('focus', refresh)
    window.addEventListener('storage', onStorage)
    return () => {
      controller.abort()
      window.removeEventListener('focus', refresh)
      window.removeEventListener('storage', onStorage)
    }
  }, [attempt])

  const note = state.status === 'ready'
    ? `${state.game.module.title} · ${state.game.investigator.displayName}${state.game.pendingTurn ? ' · 有未完成回合' : ''}`
    : state.status === 'loading' ? '正在读取调查进度…'
    : state.status === 'error' ? state.message : '暂无进行中的调查'

  return <div className="continue-investigation">
    {state.status === 'ready' ? (
      <a className="continue-button available" href={`#/game?game=${state.game.gameId}`} aria-describedby="continue-note"><span>继续调查</span><Arrow /></a>
    ) : state.status === 'error' ? (
      <button className="continue-button available" onClick={() => setAttempt((value) => value + 1)} aria-describedby="continue-note"><span>重新检查</span><Arrow /></button>
    ) : (
      <button className="continue-button" disabled aria-describedby="continue-note"><Lock /><span>继续调查</span></button>
    )}
    <p id="continue-note" className={`continue-note ${state.status === 'error' ? 'has-error' : ''}`} role="status">{note}</p>
  </div>
}
