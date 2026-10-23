import { useEffect, useRef, useState } from 'react'
import { ModuleLibrary } from './components/ModuleLibrary'
import { GamePage } from './components/GamePage'
import { InvestigatorSelection } from './components/InvestigatorSelection'
import { Arrow, DoorMark, FrameCorners, Lock } from './components/Ornaments'

function currentRoute() {
  const [path, query] = window.location.hash.split('?')
  const screen = path === '#/game' ? 'game' : path === '#/investigators' ? 'investigators' : path === '#/modules' ? 'modules' : 'home'
  return { screen, gameId: new URLSearchParams(query).get('game'), moduleId: new URLSearchParams(query).get('module'), investigatorId: new URLSearchParams(query).get('investigator') }
}

function App() {
  const [route, setRoute] = useState(currentRoute)
  const { screen, gameId, moduleId, investigatorId } = route
  const [reduceMotion] = useState(
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  )
  const previousScreen = useRef(`${screen}:${moduleId}:${investigatorId}`)

  useEffect(() => {
    function onHashChange() {
      setRoute(currentRoute())
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  useEffect(() => {
    if (previousScreen.current !== `${screen}:${moduleId}:${investigatorId}`) {
      document.getElementById('main')?.focus()
      window.scrollTo(0, 0)
      previousScreen.current = `${screen}:${moduleId}:${investigatorId}`
    }
    document.title = screen === 'game' ? '调查进行中 · CoC AI Keeper' : screen === 'investigators' ? '选择调查员 · CoC AI Keeper' : screen === 'modules' ? '调查卷宗 · CoC AI Keeper' : 'CoC AI Keeper · 你的下一场调查'
  }, [screen, moduleId, investigatorId])

  if (screen === 'game') return <div className="game-page" data-reduced-motion={reduceMotion}><a className="skip-link" href="#main" onClick={(event) => { event.preventDefault(); document.getElementById('main')?.focus() }}>跳至主要内容</a><GamePage key={gameId} gameId={gameId} /></div>

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
      </footer>

    </div>
  )
}

export default App
