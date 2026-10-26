import { useEffect, useRef } from 'react'

export function GameReviewDialog({ open, text, loading, error, onRetry, onDismiss }: {
  open: boolean
  text: string | null
  loading: boolean
  error: string
  onRetry: () => void
  onDismiss: () => void
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    if (open && !dialog.current?.open) dialog.current?.showModal()
    if (!open && dialog.current?.open) dialog.current.close()
  }, [open])

  return <dialog className="game-review-dialog" ref={dialog} aria-labelledby="game-review-title" onClose={onDismiss}>
    <header><h2 id="game-review-title">本次调查复盘</h2><button type="button" aria-label="关闭复盘，回看记录" onClick={() => dialog.current?.close()}>×</button></header>
    <div className="game-review-body" tabIndex={0}>
      {loading && <p role="status">正在读取已保存的复盘…</p>}
      {error && <div role="alert"><p>{error}</p><button type="button" disabled={loading} onClick={onRetry}>重新读取</button></div>}
      {text !== null && <p className="game-review-text">{text}</p>}
    </div>
    <footer><button type="button" onClick={() => dialog.current?.close()}>关闭复盘</button></footer>
  </dialog>
}
