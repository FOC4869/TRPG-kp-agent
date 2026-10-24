import { useEffect, useState } from 'react'
import type { GameChange } from '../state/game-changes'

export function GameStateFeedback({ changes, onDismiss }: { changes: GameChange[]; onDismiss: () => void }) {
  const [hovered, setHovered] = useState(false)
  const [focused, setFocused] = useState(false)
  useEffect(() => {
    if (hovered || focused) return
    const timer = window.setTimeout(onDismiss, 8000)
    return () => window.clearTimeout(timer)
  }, [hovered, focused, onDismiss])

  return <section className="game-state-feedback" aria-label="本轮变化" onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)} onFocusCapture={() => setFocused(true)} onBlurCapture={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setFocused(false) }}>
    <div className="game-feedback-heading"><span>本轮变化</span><button type="button" aria-label="关闭状态变化提示" onClick={onDismiss}>×</button></div>
    <div className="game-feedback-body" role="status" aria-atomic="true" tabIndex={0}><ul>{changes.map((change) => <li className={`game-change-${change.kind}`} key={change.id}><span aria-hidden="true">{change.kind === 'loss' ? '−' : change.kind === 'gain' ? '+' : change.kind === 'clue' ? '◇' : '·'}</span>{change.text}</li>)}</ul></div>
  </section>
}
