import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { getGame, submitGameAction } from '../api/game'
import type { GameAction, GameEvent, GameMessage, GameState } from '../types/game'
import { Arrow, DoorMark, FrameCorners } from './Ornaments'
import { InvestigationEndingDialog } from './InvestigationEndingDialog'
import { Portrait } from './Portrait'
import { GameDrawerContent, GameMessages } from './GameDrawer'
import type { GamePanel } from './GameDrawer'

const gamePanelNames: Record<GamePanel, string> = { character: '人物档案', inventory: '随身物品', clues: '线索笔记', history: '对话记录' }
function ToolIcon({ kind }: { kind: GamePanel }) {
  const paths = { character: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM4 22v-3a8 8 0 0 1 16 0v3Z', inventory: 'M8 6V3h8v3M3 7h18v15H3ZM3 12l9 4 9-4M12 13v6', clues: 'M5 2h14v20H5ZM8 7h8M8 11h8M8 15h5', history: 'M7 4h13v17H7ZM3 1v17M10 8h7M10 12h7M10 16h4' }
  return <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d={paths[kind]} /></svg>
}
function replaceMessage(items: GameMessage[], message: GameMessage) {
  return items.some((item) => item.id === message.id) ? items.map((item) => item.id === message.id ? message : item) : [...items, message]
}
function pause(ms: number, signal: AbortSignal) {
  return new Promise<void>((resolve) => {
    const done = () => { clearTimeout(timer); signal.removeEventListener('abort', done); resolve() }
    const timer = window.setTimeout(done, ms)
    signal.addEventListener('abort', done, { once: true })
  })
}
export function GamePage({ gameId }: { gameId: string | null }) {
  const [game, setGame] = useState<GameState | null>(null)
  const [loadError, setLoadError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [messages, setMessages] = useState<GameMessage[]>([])
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState(false)
  const [phase, setPhase] = useState('守秘人正在回应…')
  const [failed, setFailed] = useState<GameAction | null>(null)
  const [errorText, setErrorText] = useState('')
  const [endingSummary, setEndingSummary] = useState<string | null>(null)
  const [endingOpen, setEndingOpen] = useState(false)
  const [panel, setPanel] = useState<GamePanel | null>(null)
  const [atBottom, setAtBottom] = useState(true)
  const [imageFailed, setImageFailed] = useState({ background: '', npc: '' })
  const drawer = useRef<HTMLDialogElement>(null)
  const conversation = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const activeRequest = useRef<AbortController | null>(null)
  const followLatest = useRef(true)
  const returnUrl = '#/modules'
  const facts = game?.facts ?? []

  function applySnapshot(state: GameState) {
    setGame(state); setMessages(state.messages)
    if (state.ended && state.endingSummary) {
      setEndingSummary(state.endingSummary); setEndingOpen(true); drawer.current?.close()
    }
  }
  useEffect(() => {
    if (!gameId) return
    const controller = new AbortController()
    getGame(gameId, controller.signal).then((state) => {
      if (controller.signal.aborted) return
      applySnapshot(state)
      if (state.pendingTurn) setFailed({ requestId: state.pendingTurn.requestId, text: state.pendingTurn.text, expectedVersion: state.version })
    }).catch((error: unknown) => { if (!controller.signal.aborted) setLoadError(error instanceof Error ? error.message : '读取失败。') })
    return () => { controller.abort(); activeRequest.current?.abort() }
  }, [gameId, attempt])
  useEffect(() => {
    if (followLatest.current && conversation.current) conversation.current.scrollTop = conversation.current.scrollHeight
  }, [messages, pending])
  function openPanel(value: GamePanel) { setPanel(value); drawer.current?.showModal() }

  async function send(retry?: GameAction) {
    if (!gameId || !game || endingSummary !== null || activeRequest.current || (!retry && !draft.trim())) return
    const request = { ...(retry ?? { requestId: crypto.randomUUID(), text: draft.trim(), expectedVersion: game.version }) }
    const controller = new AbortController(); activeRequest.current = controller
    setPending(true); setFailed(null); setErrorText(''); followLatest.current = true; setAtBottom(true)
    let queue = Promise.resolve()
    let queueError: unknown = null
    const shownChecks = new Set(game.messages.filter((m) => m.check?.roll !== undefined).map((m) => m.check!.checkId))
    const starts = new Map<string, number>()
    async function display(event: GameEvent) {
      if (controller.signal.aborted) return
      if (event.type === 'turn.status') setPhase(({ understanding: '守秘人正在理解行动…', resolving: '正在结算行动…', narrating: '守秘人正在讲述…' } as Record<string, string>)[event.stage ?? ''] ?? '正在恢复调查…')
      if (event.type === 'check.started' && event.check && !shownChecks.has(event.check.checkId)) {
        starts.set(event.check.checkId, performance.now())
        const message: GameMessage = { id: event.check.checkId, kind: 'check', speaker: '规则检定', text: event.check.reason, check: { ...event.check, display: 'rolling' } }
        setMessages((items) => replaceMessage(items, message))
      }
      if (event.type === 'check.resolved' && event.check) {
        const check = event.check
        const animate = !shownChecks.has(check.checkId) && !window.matchMedia('(prefers-reduced-motion: reduce)').matches
        if (animate) await pause(Math.max(0, 800 - (performance.now() - (starts.get(check.checkId) ?? 0))), controller.signal)
        if (controller.signal.aborted) return
        shownChecks.add(check.checkId)
        setMessages((items) => replaceMessage(items, { id: check.checkId, kind: 'check', speaker: '规则检定', text: check.reason, check: { ...check, display: 'resolved' } }))
        if (animate) await pause(250, controller.signal)
      }
      if (event.type === 'state.updated' && event.state) applySnapshot(event.state)
      if (event.type === 'message.started' && event.message) setMessages((items) => replaceMessage(items, event.message!))
      if (event.type === 'message.delta') setMessages((items) => items.map((item) => item.id === event.messageId ? { ...item, text: item.text + event.delta } : item))
      if (event.type === 'message.completed' && event.message) setMessages((items) => replaceMessage(items, event.message!))
      if (event.type === 'turn.completed' && event.state) { applySnapshot(event.state); setDraft(''); setFailed(null) }
      if (event.type === 'turn.failed') throw new Error(event.messageText || '回应未完成，请恢复原回合。')
    }
    try {
      if (retry) {
        const fresh = await getGame(gameId, controller.signal)
        if (controller.signal.aborted) return
        applySnapshot(fresh)
        fresh.messages.filter((m) => m.check?.roll !== undefined).forEach((m) => shownChecks.add(m.check!.checkId))
        if (!fresh.pendingTurn && fresh.messages.some((m) => m.id === request.requestId + ':keeper')) { setDraft(''); return }
        if (fresh.pendingTurn && fresh.pendingTurn.requestId !== request.requestId) {
          setFailed({ requestId: fresh.pendingTurn.requestId, text: fresh.pendingTurn.text, expectedVersion: fresh.version })
          setErrorText('另一行动正在处理中，请先恢复该回合。')
          return
        }
        if (!fresh.pendingTurn) request.expectedVersion = fresh.version
      } else setMessages((items) => replaceMessage(items, { id: request.requestId + ':player', kind: 'player', speaker: game.investigator.displayName, text: request.text }))
      await submitGameAction(gameId, request, controller.signal, (event) => {
        // Continue reading bytes while dice and earlier messages are being presented.
        queue = queue.then(async () => { if (!queueError) await display(event) }).catch((error: unknown) => { queueError = error })
      })
      await queue
      if (queueError) throw queueError
    } catch (error) {
      await queue
      if (!controller.signal.aborted) {
        setFailed(request); setErrorText(error instanceof TypeError ? '网络连接中断，请恢复原回合。' : error instanceof Error ? error.message : '连接中断，请恢复原回合。')
        setMessages((items) => items.map((m) => m.check?.display === 'rolling' ? { ...m, check: { ...m.check, display: 'error' } } : m))
      }
    } finally {
      if (activeRequest.current === controller) { activeRequest.current = null; setPending(false) }
    }
  }
  function onSubmit(event: FormEvent) { event.preventDefault(); if (!failed) void send() }
  if (!gameId || loadError || !game) return <main className="game-unavailable" id="main" tabIndex={-1}><DoorMark /><h1>{!gameId ? '请先创建调查' : loadError ? '暂时无法展开这场调查' : '正在恢复调查…'}</h1><p role="status">{loadError || '正在读取已保存的游戏状态。'}</p>{loadError && <button className="text-button" onClick={() => { setLoadError(''); setAttempt((value) => value + 1) }}>重新读取 ↗</button>}<a href={returnUrl} className="text-button">返回模组库 <Arrow /></a></main>

  const investigator = game.investigator
  const resources = investigator.resources
  return <main id="main" className="game-shell" tabIndex={-1}>
    <header className="game-header">
      <a className="brand" href="#/" aria-label="CoC AI Keeper 首页"><DoorMark /><span>CoC AI Keeper</span></a>
      <div className="game-case"><h1>{game.module.title}</h1><span>THE DARKNESS BENEATH THE HILL</span></div>
      <div className="game-header-tools">{(['history'] as const).map((tool) => <button key={tool} onClick={() => openPanel(tool)} aria-label={gamePanelNames[tool]} aria-haspopup="dialog"><ToolIcon kind={tool} /><span>{gamePanelNames[tool]}</span></button>)}</div>
    </header>
    <aside className="game-sidebar" aria-label="调查员与工具">
      <p className="eyebrow">调查员</p><div className="game-investigator"><Portrait portrait={investigator.portrait} name={investigator.displayName} /><h2>{investigator.displayName}</h2><p>{investigator.occupation}</p></div>
      <dl className="game-resources">{[
        { label: 'HP', value: resources.hp, max: resources.hpMax, color: 'hp' },
        { label: 'SAN', value: resources.san, max: null, color: 'san' },
        { label: 'MP', value: resources.mp, max: resources.mpMax, color: 'mp' },
        { label: '幸运', value: resources.luck, max: null, color: 'luck' },
      ].map(({ label, value, max, color }) => <div key={label}><dt>{label}</dt><dd><span className={`game-resource-mark ${color}`} aria-hidden="true" /><span>{value ?? '—'}{max !== null && ` / ${max}`}</span></dd></div>)}</dl>
      <nav aria-label="调查工具">{(['character', 'inventory', 'clues'] as const).map((tool) => <button key={tool} onClick={() => openPanel(tool)} aria-label={gamePanelNames[tool]} aria-haspopup="dialog"><ToolIcon kind={tool} />{gamePanelNames[tool]}{tool === 'clues' && facts.length > 0 && <span className="fact-count">{facts.length}</span>}</button>)}</nav>
      <div className="game-sidebar-bottom"><a href="#/">← 返回首页</a><p>自动保存 · 此地址可恢复调查</p></div>
    </aside>
    <section className="game-stage" aria-label="当前场景">
      <div className="game-stage-fallback" aria-hidden="true"><DoorMark /><span>{game.scene.name}</span></div>
      {imageFailed.background !== game.scene.backgroundUrl && <img className="game-background" src={game.scene.backgroundUrl} alt={game.scene.name} onError={() => setImageFailed((value) => ({ ...value, background: game.scene.backgroundUrl }))} />}
      <div className="game-stage-shade" />
      <div className="game-location"><FrameCorners /><span>{game.scene.region}</span><h2>{game.scene.name}</h2></div>
      {game.npc && imageFailed.npc !== game.npc.spriteUrl && <img className="game-npc" src={game.npc.spriteUrl} alt={`${game.npc.name}，当前交谈的 NPC`} onError={() => setImageFailed((value) => ({ ...value, npc: game.npc?.spriteUrl ?? '' }))} />}
      <>{game.npc && <div className="game-npc-name"><strong>{game.npc.name}</strong><span>NPC · {game.npc.role}</span></div>}</>

    </section>
    <section className="game-dialogue" aria-label="当前叙事">
      <div className="game-conversation" ref={conversation} tabIndex={0} aria-label="叙事内容，可滚动" onScroll={(event) => { const element = event.currentTarget; const bottom = element.scrollHeight - element.scrollTop - element.clientHeight < 30; followLatest.current = bottom; setAtBottom(bottom) }}>
        <GameMessages messages={messages} />
        {pending && <p className="keeper-wait" role="status"><span />{phase}</p>}
      </div>
      {!atBottom && <button className="game-latest" onClick={() => { followLatest.current = true; conversation.current?.scrollTo({ top: conversation.current.scrollHeight }); setAtBottom(true) }}>最新内容 ↓</button>}
    </section>
    <form className="game-composer" onSubmit={onSubmit}>
      {endingSummary !== null ? <div className="game-ended-bar"><p>本次调查已结束</p><button type="button" onClick={() => setEndingOpen(true)}>查看结案 <Arrow /></button></div> : <>
      <div className="game-suggestions" aria-label="行动建议">{game.suggestions.map((suggestion) => <button key={suggestion} type="button" disabled={pending || !!failed} onClick={() => { setDraft(suggestion); input.current?.focus() }}>{suggestion}</button>)}<span>也可以自由描述行动</span></div>
      {failed && <div className="game-action-error" role="alert">{errorText || '本轮尚未完成，请恢复原行动。'}<button type="button" disabled={pending} onClick={() => void send(failed)}>恢复本轮</button></div>}
      <label className="sr-only" htmlFor="game-action">你的行动</label>
      <div className="game-input-row"><textarea id="game-action" ref={input} value={draft} maxLength={1000} rows={2} readOnly={pending || !!failed} placeholder="你想做什么？可以行动、观察，或与在场人物交谈……" onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing && event.nativeEvent.keyCode !== 229) { event.preventDefault(); if (!failed) void send() } }} /><button type="submit" disabled={!draft.trim() || pending || !!failed}><span>{pending ? '回应中' : '行动'}</span><Arrow /></button></div>
      <p className="game-input-hint"><span>Enter 发送 · Shift + Enter 换行</span><span>{draft.length} / 1000</span></p>
      </>}
    </form>
    <p className="sr-only" role="status">{!pending && messages.at(-1)?.kind !== 'player' ? messages.at(-1)?.text : ''}</p>
    <dialog className="game-drawer" ref={drawer} aria-labelledby="game-drawer-title" onClose={() => setPanel(null)}>
      <div className="game-drawer-heading"><div><p className="eyebrow">INVESTIGATION JOURNAL</p><h2 id="game-drawer-title">{panel && gamePanelNames[panel]}</h2></div><button className="close-button" aria-label="关闭面板" onClick={() => drawer.current?.close()}>×</button></div>
      <div className="game-drawer-body">{panel && <GameDrawerContent panel={panel} game={game} facts={facts} messages={messages} />}</div>
    </dialog>
    <InvestigationEndingDialog open={endingOpen} summary={endingSummary ?? ''} onDismiss={() => setEndingOpen(false)} />
  </main>
}
