import { useEffect, useRef, useState } from 'react'
import { getHealth } from './api/health'
import { ModuleLibrary } from './components/ModuleLibrary'
import { InvestigatorSelection } from './components/InvestigatorSelection'
import { Arrow, DoorMark, FrameCorners, Lock } from './components/Ornaments'

type Panel = 'settings' | null

function currentRoute() {
  const [path, query] = window.location.hash.split('?')
  const screen = path === '#/investigators' ? 'investigators' : path === '#/modules' ? 'modules' : 'home'
  return { screen, moduleId: new URLSearchParams(query).get('module') }
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
  const [route, setRoute] = useState(currentRoute)
  const { screen, moduleId } = route
  const [panel, setPanel] = useState<Panel>(null)
  const [reduceMotion, setReduceMotion] = useState(
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  )
  const dialog = useRef<HTMLDialogElement>(null)
  const previousScreen = useRef(`${screen}:${moduleId}`)

  useEffect(() => {
    function onHashChange() {
      dialog.current?.close()
      setPanel(null)
      setRoute(currentRoute())
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  useEffect(() => {
    if (previousScreen.current !== `${screen}:${moduleId}`) {
      document.getElementById('main')?.focus()
      window.scrollTo(0, 0)
      previousScreen.current = `${screen}:${moduleId}`
    }
    document.title = screen === 'investigators' ? '选择调查员 · CoC AI Keeper' : screen === 'modules' ? '调查卷宗 · CoC AI Keeper' : 'CoC AI Keeper · 你的下一场调查'
  }, [screen, moduleId])

  useEffect(() => {
    if (panel && !dialog.current?.open) dialog.current?.showModal()
    if (!panel && dialog.current?.open) dialog.current.close()
  }, [panel])

  function closePanel() {
    dialog.current?.close()
    setPanel(null)
  }

  return (
    <div className={`home ${screen !== 'home' ? 'library-page' : ''} ${screen === 'investigators' ? 'investigators-page' : ''}`} data-reduced-motion={reduceMotion}>
      <a className="skip-link" href="#main" onClick={(event) => {
        event.preventDefault()
        document.getElementById('main')?.focus()
      }}>跳至主要内容</a>
      <div className="manor-background" aria-hidden="true" />
      <div className="scene-shade" aria-hidden="true" />
      <div className="dust" aria-hidden="true">
        {Array.from({ length: 7 }, (_, index) => <span key={index} />)}
      </div>

      <header className="site-header">
        <a className="brand" href="#/" aria-label="CoC AI Keeper 首页"><DoorMark /><span>CoC AI Keeper</span></a>
        <nav aria-label="主导航">
          <a className={`nav-item ${screen === 'home' ? 'active' : ''}`} href="#/" aria-current={screen === 'home' ? 'page' : undefined}>首页</a>
          <a className={`nav-item ${screen !== 'home' ? 'active' : ''}`} href="#/modules" aria-current={screen === 'modules' ? 'page' : undefined}>模组库</a>
          <button className="nav-item" aria-haspopup="dialog" onClick={() => setPanel('settings')}>设置</button>
        </nav>
      </header>

      {screen === 'home' ? (
        <main id="main" className="hero" tabIndex={-1}>
          <div className="hero-content">
            <p className="eyebrow">A CALL INTO THE UNKNOWN</p>
            <div className="title-rule" aria-hidden="true"><span /></div>
            <h1><span>CoC</span><span>AI Keeper</span></h1>
            <h2 className="hero-subtitle">你的下一场调查，<br className="compact-break" />从这里开始。</h2>
            <p className="hero-description">翻开卷宗，扮演调查员。<br />让 AI 守秘人带你走进未知。</p>
            <div className="hero-actions">
              <a className="investigate-button" href="#/modules"><FrameCorners /><span>开始调查</span><Arrow /></a>
              <button className="continue-button" disabled aria-describedby="continue-note">
                <Lock /><span>继续调查</span><span id="continue-note" className="unavailable">暂未开放</span>
              </button>
            </div>
          </div>
        </main>
      ) : screen === 'modules' ? (
        <ModuleLibrary onChooseInvestigator={(module) => {
          window.location.hash = `/investigators?${new URLSearchParams({ module: module.id })}`
        }} />
      ) : <InvestigatorSelection key={moduleId ?? 'missing-module'} moduleId={moduleId} />}

      <footer className={`site-footer ${screen !== 'home' ? 'library-footer' : ''}`}>
        <FrameCorners />
        {screen !== 'home' ? <a className="back-home" href={screen === 'investigators' ? '#/modules' : '#/'}><Arrow />{screen === 'investigators' ? '返回模组库' : '返回首页'}</a> : <p>单人调查 <span>·</span> 自由行动 <span>·</span> AI 主持</p>}
        <p className="project-credit">DSAI5205 <span>·</span> GROUP PROJECT</p>
      </footer>

      <dialog ref={dialog} className="folio-dialog" aria-labelledby="dialog-title" onClose={() => setPanel(null)}>
        <div className="dialog-heading">
          <p className="eyebrow">PREFERENCES</p>
          <button className="close-button" aria-label="关闭" onClick={closePanel}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg>
          </button>
        </div>
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
