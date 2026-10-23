import { useEffect, useRef, useState } from 'react'
import { getHealth } from './api/health'

type Panel = 'modules' | 'settings' | null

function DoorMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 40 52" fill="none" aria-hidden="true">
      <path d="M3 49V21a17 17 0 0 1 34 0v28M7 49V21a13 13 0 0 1 26 0v28M11 49V21a9 9 0 0 1 18 0v28M15 49V22a5 5 0 0 1 10 0v27M1 49h38M20 1v7M1 21h10M29 21h10" />
      <path d="m15 49 10-5V22M21 33v3" />
    </svg>
  )
}

function Arrow() {
  return <svg viewBox="0 0 32 20" fill="none" aria-hidden="true"><path d="M1 10h28M21 2l8 8-8 8" /></svg>
}

function Lock() {
  return (
    <svg viewBox="0 0 20 24" fill="none" aria-hidden="true">
      <path d="M5 10V6a5 5 0 0 1 10 0v4" /><rect x="2" y="10" width="16" height="12" rx="2" /><path d="M10 14v4" />
    </svg>
  )
}

function Corner({ className = '' }: { className?: string }) {
  return (
    <svg className={`corner ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M1 23V8l7-7h15M5 23V10l5-5h13M1 15l9-9M9 1v8H1m9 9 3 3-3 3-3-3 3-3Z" />
    </svg>
  )
}

function ConnectionCheck() {
  const [connection, setConnection] = useState<'checking' | 'online' | 'offline'>('checking')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    let active = true
    const timeout = window.setTimeout(() => {
      controller.abort()
      if (active) setConnection('offline')
    }, 5000)
    getHealth(controller.signal)
      .then(() => { if (active) setConnection('online') })
      .catch(() => { if (active) setConnection('offline') })
      .finally(() => window.clearTimeout(timeout))
    return () => {
      active = false
      controller.abort()
      window.clearTimeout(timeout)
    }
  }, [attempt])

  return (
    <section className="connection-check" aria-labelledby="connection-title">
      <h3 id="connection-title">连接状态</h3>
      <p className={`connection-status ${connection}`} role="status">
        <span aria-hidden="true" />
        {connection === 'checking' && '正在检查连接…'}
        {connection === 'online' && '后端已连接'}
        {connection === 'offline' && '暂时无法连接后端'}
      </p>
      <p className="setting-hint">连接检查不影响首页浏览，也不会调用模型。</p>
      <button className="text-button" disabled={connection === 'checking'} onClick={() => {
        setConnection('checking')
        setAttempt((value) => value + 1)
      }}>重新检查 <span aria-hidden="true">↗</span></button>
    </section>
  )
}

function App() {
  const [panel, setPanel] = useState<Panel>(null)
  const [reduceMotion, setReduceMotion] = useState(
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  )
  const dialog = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    if (panel && !dialog.current?.open) dialog.current?.showModal()
    if (!panel && dialog.current?.open) dialog.current.close()
  }, [panel])

  function closePanel() {
    dialog.current?.close()
    setPanel(null)
  }

  return (
    <div className="home" data-reduced-motion={reduceMotion}>
      <a className="skip-link" href="#main">跳至主要内容</a>
      <div className="manor-background" aria-hidden="true" />
      <div className="scene-shade" aria-hidden="true" />
      <div className="dust" aria-hidden="true">
        {Array.from({ length: 7 }, (_, index) => <span key={index} />)}
      </div>

      <header className="site-header">
        <a className="brand" href="#main" aria-label="CoC AI Keeper 首页"><DoorMark /><span>CoC AI Keeper</span></a>
        <nav aria-label="主导航">
          <a className="nav-item active" href="#main" aria-current="page">首页</a>
          <button className="nav-item" aria-haspopup="dialog" onClick={() => setPanel('modules')}>模组库</button>
          <button className="nav-item" aria-haspopup="dialog" onClick={() => setPanel('settings')}>设置</button>
        </nav>
      </header>

      <main id="main" className="hero" tabIndex={-1}>
        <div className="hero-content">
          <p className="eyebrow">A CALL INTO THE UNKNOWN</p>
          <div className="title-rule" aria-hidden="true"><span /></div>
          <h1><span>CoC</span><span>AI Keeper</span></h1>
          <h2 className="hero-subtitle">你的下一场调查，<br className="compact-break" />从这里开始。</h2>
          <p className="hero-description">翻开卷宗，扮演调查员。<br />让 AI 守秘人带你走进未知。</p>
          <div className="hero-actions">
            <button className="investigate-button" aria-haspopup="dialog" onClick={() => setPanel('modules')}>
              <Corner /><Corner className="corner-tr" /><Corner className="corner-bl" /><Corner className="corner-br" />
              <span>开始调查</span><Arrow />
            </button>
            <button className="continue-button" disabled aria-describedby="continue-note">
              <Lock /><span>继续调查</span><span id="continue-note" className="unavailable">暂未开放</span>
            </button>
          </div>
        </div>
      </main>

      <footer className="site-footer">
        <Corner /><Corner className="corner-tr" /><Corner className="corner-bl" /><Corner className="corner-br" />
        <p>单人调查 <span>·</span> 自由行动 <span>·</span> AI 主持</p>
        <p className="project-credit">DSAI5205 <span>·</span> GROUP PROJECT</p>
      </footer>

      <dialog ref={dialog} className="folio-dialog" aria-labelledby="dialog-title" onClose={() => setPanel(null)}>
        <div className="dialog-heading">
          <p className="eyebrow">{panel === 'modules' ? 'THE CASE FILES' : 'PREFERENCES'}</p>
          <button className="close-button" aria-label="关闭" onClick={closePanel}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg>
          </button>
        </div>
        {panel === 'modules' && (
          <>
            <h2 id="dialog-title">调查卷宗</h2>
            <p className="dialog-intro">每一份卷宗，都是一扇通往未知的门。</p>
            <article className="module-preview">
              <p className="file-number">CASE FILE <span>001</span></p>
              <span className="module-tag">原创演示 · 预览</span>
              <h3>雨夜来信</h3>
              <p>一封神秘来信，将你带进一间旧书房。委托人的失踪，等待你的调查。</p>
              <div className="module-meta"><span>单人调查</span><span>预设调查员</span></div>
            </article>
            <p className="preview-notice">模组选择与游戏页面尚未开放。你可以先浏览首页，正式调查即将启程。</p>
            <button className="dialog-action" onClick={closePanel}>返回首页 <Arrow /></button>
          </>
        )}
        {panel === 'settings' && (
          <>
            <h2 id="dialog-title">设置</h2>
            <p className="dialog-intro">让这场调查，以你舒适的方式展开。</p>
            <label className="setting-row">
              <span><strong>减少动态效果</strong><span className="setting-hint">关闭入场与浮尘动画；仅本次浏览有效。</span></span>
              <input type="checkbox" checked={reduceMotion} onChange={(event) => setReduceMotion(event.target.checked)} />
            </label>
            <ConnectionCheck />
            <p className="preview-notice">存档与继续调查功能暂未开放。</p>
          </>
        )}
      </dialog>
    </div>
  )
}

export default App
