import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { loadGamePreview, submitGameAction } from '../api/game'
import type { GameAction, GameContext, GameFact, GameMessage, GamePreview } from '../types/game'
import { Arrow, DoorMark, FrameCorners } from './Ornaments'
import { Portrait } from './Portrait'
import { GameDrawerContent, GameMessages } from './GameDrawer'
import type { GamePanel } from './GameDrawer'

const gamePanelNames: Record<GamePanel, string> = { character: '人物档案', inventory: '随身物品', clues: '线索笔记', history: '对话记录', settings: '设置' }

function ToolIcon({ kind }: { kind: GamePanel }) {
  const paths = { character: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM4 22v-3a8 8 0 0 1 16 0v3Z', inventory: 'M8 6V3h8v3M3 7h18v15H3ZM3 12l9 4 9-4M12 13v6', clues: 'M5 2h14v20H5ZM8 7h8M8 11h8M8 15h5', history: 'M7 4h13v17H7ZM3 1v17M10 8h7M10 12h7M10 16h4', settings: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM12 1v4M12 19v4M1 12h4M19 12h4M4 4l3 3M17 17l3 3M4 20l3-3M17 7l3-3' }
  return <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d={paths[kind]} /></svg>
}

export function GamePage({ moduleId, investigatorId, reduceMotion, onMotion }: {
  moduleId: string | null; investigatorId: string | null; reduceMotion: boolean; onMotion: (value: boolean) => void
}) {
  const [game, setGame] = useState<GamePreview | null>(null)
  const [loadError, setLoadError] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [messages, setMessages] = useState<GameMessage[]>([])
  const [facts, setFacts] = useState<GameFact[]>([])
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState(false)
  const [failed, setFailed] = useState<GameAction | null>(null)
  const [panel, setPanel] = useState<GamePanel | null>(null)
  const [atBottom, setAtBottom] = useState(true)
  const [imageFailed, setImageFailed] = useState({ background: false, npc: false })
  const drawer = useRef<HTMLDialogElement>(null)
  const conversation = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const activeRequest = useRef<AbortController | null>(null)
  const followLatest = useRef(true)
  const context: GameContext | null = moduleId && investigatorId ? { moduleId, investigatorId } : null
  const returnUrl = moduleId ? `#/investigators?${new URLSearchParams({ module: moduleId })}` : '#/modules'

  useEffect(() => {
    if (!moduleId || !investigatorId) return
    const controller = new AbortController()
    loadGamePreview({ moduleId, investigatorId }, controller.signal).then((result) => {
      if (controller.signal.aborted) return
      setGame(result); setMessages(result.messages); setFacts(result.facts)
    }).catch(() => { if (!controller.signal.aborted) setLoadError(true) })
    return () => { controller.abort(); activeRequest.current?.abort() }
  }, [moduleId, investigatorId, attempt])

  useEffect(() => {
    if (followLatest.current && conversation.current) conversation.current.scrollTop = conversation.current.scrollHeight
  }, [messages, pending])

  function openPanel(value: GamePanel) {
    setPanel(value)
    drawer.current?.showModal()
  }

  async function send(action?: GameAction) {
    if (!context || !game || activeRequest.current || (!action && !draft.trim())) return
    const request: GameAction = action ?? { requestId: crypto.randomUUID(), text: draft.trim(), kind: 'action' }
    const controller = new AbortController()
    activeRequest.current = controller
    setPending(true); setFailed(null); followLatest.current = true; setAtBottom(true)
    if (!action) setMessages((items) => [...items, { id: `${request.requestId}-player`, kind: 'player', speaker: game.investigator.displayName, text: request.text }])
    const timeout = window.setTimeout(() => controller.abort(new Error('timeout')), 20000)
    try {
      const reply = await submitGameAction(context, request, controller.signal)
      if (controller.signal.aborted) return
      setMessages((items) => [...items, ...reply.messages.filter((item) => !items.some((previous) => previous.id === item.id))])
      setFacts((items) => [...items, ...reply.facts.filter((item) => !items.some((previous) => previous.id === item.id))])
      if (request.kind === 'action') setDraft('')
    } catch {
      // Unmount cancellation is silent; a timeout is actionable.
      if (!controller.signal.aborted || controller.signal.reason?.message === 'timeout') setFailed(request)
    } finally {
      clearTimeout(timeout)
      if (activeRequest.current === controller) { activeRequest.current = null; setPending(false) }
    }
  }

  function onSubmit(event: FormEvent) { event.preventDefault(); if (!failed) void send() }

  if (!context || loadError || !game) return <main className="game-unavailable" id="main" tabIndex={-1}><DoorMark /><h1>{!context ? '请先选择案件与调查员' : loadError ? '暂时无法展开这场调查' : '正在展开调查…'}</h1><p role="status">{loadError ? '请重新读取，或返回选择页面确认案件与人物。' : '开场界面预览 · 不保存进度'}</p>{loadError && <button className="text-button" onClick={() => { setLoadError(false); setAttempt((value) => value + 1) }}>重新读取 ↗</button>}<a href={returnUrl} className="text-button">返回选择 <Arrow /></a></main>

  const investigator = game.investigator
  const resources = investigator.resources
  return <main id="main" className="game-shell" tabIndex={-1}>
    <header className="game-header">
      <a className="brand" href="#/" aria-label="CoC AI Keeper 首页"><DoorMark /><span>CoC AI Keeper</span></a>
      <div className="game-case"><h1>{game.module.title}</h1><span>THE DARKNESS BENEATH THE HILL</span></div>
      <div className="game-header-tools">{(['history', 'settings'] as const).map((tool) => <button key={tool} onClick={() => openPanel(tool)} aria-label={gamePanelNames[tool]} aria-haspopup="dialog"><ToolIcon kind={tool} /><span>{gamePanelNames[tool]}</span></button>)}</div>
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
      <div className="game-sidebar-bottom"><a href={returnUrl}>← 返回调查员选择</a><p>开场预览 · 刷新将重置</p></div>
    </aside>
    <section className="game-stage" aria-label="当前场景">
      <div className="game-stage-fallback" aria-hidden="true"><DoorMark /><span>文斯考特宅</span></div>
      {!imageFailed.background && <img className="game-background" src={game.scene.backgroundUrl} alt="修缮中的文斯考特宅，厨房旁堆放着箱子与罩布家具" onError={() => setImageFailed((value) => ({ ...value, background: true }))} />}
      <div className="game-stage-shade" />
      <div className="game-location"><FrameCorners /><span>{game.scene.region}</span><h2>{game.scene.name}</h2></div>
      {!imageFailed.npc && <img className="game-npc" src={game.npc.spriteUrl} alt={`${game.npc.name}，当前交谈的 NPC`} onError={() => setImageFailed((value) => ({ ...value, npc: true }))} />}
      <div className="game-npc-name"><strong>{game.npc.name}</strong><span>NPC · {game.npc.role}</span></div>
      <span className="game-preview-tag">开场预览</span>
    </section>
    <section className="game-dialogue" aria-label="当前叙事">
      <div className="game-conversation" ref={conversation} tabIndex={0} aria-label="叙事内容，可滚动" onScroll={(event) => { const element = event.currentTarget; const bottom = element.scrollHeight - element.scrollTop - element.clientHeight < 30; followLatest.current = bottom; setAtBottom(bottom) }}>
        <GameMessages messages={messages} />
        {pending && <p className="keeper-wait" role="status"><span />守秘人正在回应…</p>}
      </div>
      {!atBottom && <button className="game-latest" onClick={() => { followLatest.current = true; conversation.current?.scrollTo({ top: conversation.current.scrollHeight }); setAtBottom(true) }}>最新内容 ↓</button>}
    </section>
    <form className="game-composer" onSubmit={onSubmit}>
      <div className="game-suggestions" aria-label="行动建议">{game.suggestions.map((suggestion) => <button key={suggestion} type="button" disabled={pending || !!failed} onClick={() => { setDraft(suggestion); input.current?.focus() }}>{suggestion}</button>)}<span>也可以自由描述行动</span></div>
      {failed && <div className="game-action-error" role="alert">回应未完成，行动内容已保留。<button type="button" onClick={() => void send(failed)}>重试</button><button type="button" onClick={() => setFailed(null)}>编辑行动</button></div>}
      <label className="sr-only" htmlFor="game-action">你的行动</label>
      <div className="game-input-row"><textarea id="game-action" ref={input} value={draft} maxLength={1000} rows={2} readOnly={pending} placeholder="你想做什么？可以行动、观察，或与乔什交谈……" onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing && event.nativeEvent.keyCode !== 229) { event.preventDefault(); if (!failed) void send() } }} /><button type="submit" disabled={!draft.trim() || pending || !!failed}><span>{pending ? '回应中' : '行动'}</span><Arrow /></button></div>
      <p className="game-input-hint"><span>Enter 发送 · Shift + Enter 换行</span><span>{draft.length} / 1000</span></p>
    </form>
    <p className="sr-only" role="status">{!pending && messages.at(-1)?.kind !== 'player' ? messages.at(-1)?.text : ''}</p>
    <dialog className="game-drawer" ref={drawer} aria-labelledby="game-drawer-title" onClose={() => setPanel(null)}>
      <div className="game-drawer-heading"><div><p className="eyebrow">INVESTIGATION JOURNAL</p><h2 id="game-drawer-title">{panel && gamePanelNames[panel]}</h2></div><button className="close-button" aria-label="关闭面板" onClick={() => drawer.current?.close()}>×</button></div>
      <div className="game-drawer-body">{panel && <GameDrawerContent panel={panel} game={game} facts={facts} messages={messages} reduceMotion={reduceMotion} onMotion={onMotion} busy={pending || !!failed} onCheck={() => { drawer.current?.close(); void send({ requestId: crypto.randomUUID(), text: '固定检定展示', kind: 'check-preview' }) }} />}</div>
    </dialog>
  </main>
}
