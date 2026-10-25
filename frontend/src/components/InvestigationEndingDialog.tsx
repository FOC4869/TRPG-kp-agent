import { useEffect, useRef } from 'react'
import { Arrow, DoorMark, FrameCorners } from './Ornaments'

export function InvestigationEndingDialog({ open, summary, title = '调查结束', onDismiss }: {
  open: boolean; summary: string; title?: string; onDismiss: () => void
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    if (open && !dialog.current?.open) dialog.current?.showModal()
    if (!open && dialog.current?.open) dialog.current.close()
  }, [open])

  return <dialog className="investigation-ending" ref={dialog} aria-labelledby="investigation-ending-title" onClose={onDismiss}>
    <FrameCorners />
    <button className="ending-close" aria-label="关闭结案，回看记录" onClick={() => dialog.current?.close()}>×</button>
    <div className="ending-heading">
      <DoorMark /><p className="eyebrow">END OF THE INVESTIGATION</p>
      <h2 id="investigation-ending-title">{title}</h2><div className="ending-rule" aria-hidden="true">◆</div>
    </div>
    <div className="ending-summary" tabIndex={0} aria-label="本次调查总结"><p>{summary}</p></div>
    <div className="ending-footer"><a className="investigate-button" href="#/"><FrameCorners /><span>返回首页</span><Arrow /></a></div>
  </dialog>
}
