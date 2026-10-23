import { createGame } from '../api/game'
import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { getInvestigator, InvestigatorRequestError, listInvestigators } from '../api/investigators'
import type { AttributeKey, InvestigatorCatalogue, InvestigatorDetail, InvestigatorSkill, InvestigatorSummary } from '../types/investigators'
import { Arrow, DoorMark, FrameCorners } from './Ornaments'
import { Portrait } from './Portrait'

type CatalogueState = { status: 'loading' } | { status: 'unavailable' } | { status: 'error' } | { status: 'ready'; data: InvestigatorCatalogue }
type DetailState = { status: 'idle' | 'loading' | 'error' } | { status: 'ready'; data: InvestigatorDetail }
const tabs = [{ id: 'overview', label: '人物概览' }, { id: 'stats', label: '属性技能' }, { id: 'background', label: '人物背景' }, { id: 'equipment', label: '初始物品' }] as const
type TabId = typeof tabs[number]['id']
const attributes: { key: AttributeKey; label: string }[] = [
  { key: 'STR', label: '力量' }, { key: 'CON', label: '体质' }, { key: 'SIZ', label: '体型' }, { key: 'DEX', label: '敏捷' },
  { key: 'APP', label: '外貌' }, { key: 'INT', label: '智力' }, { key: 'POW', label: '意志' }, { key: 'EDU', label: '教育' },
]

function resource(value: number | null, max?: number | null) {
  if (value === null) return '未提供'
  return max == null ? String(value) : `${value}/${max}`
}

function Skills({ skills }: { skills: InvestigatorSkill[] }) {
  if (!skills.length) return <p className="dossier-note">暂无技能资料。</p>
  return <dl className="investigator-skills">{skills.map((skill) => (
    <div key={skill.name}>
      <dt>{skill.name}</dt>
      <dd><span className="skill-track" aria-hidden="true"><span style={{ width: `${Math.min(100, Math.max(0, skill.value ?? 0))}%` }} /></span><span>{skill.value ?? '—'}</span></dd>
    </div>
  ))}</dl>
}

function InvestigatorDossier({ investigator, onConfirm }: { investigator: InvestigatorDetail; onConfirm: (investigator: InvestigatorDetail) => void }) {
  const [activeTab, setActiveTab] = useState<TabId>('overview')
  const tabButtons = useRef<(HTMLButtonElement | null)[]>([])
  const initial = investigator.resources

  function navigateTabs(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const positions: Record<string, number> = { ArrowRight: (index + 1) % tabs.length, ArrowLeft: (index + tabs.length - 1) % tabs.length, Home: 0, End: tabs.length - 1 }
    const next = positions[event.key]
    if (next === undefined) return
    event.preventDefault()
    setActiveTab(tabs[next].id)
    tabButtons.current[next]?.focus()
  }

  return (
    <>
      <p className="dossier-eyebrow">INVESTIGATOR DOSSIER</p>
      <div className="investigator-profile">
        <Portrait portrait={investigator.portrait} name={investigator.name} />
        <div><h2 id="investigator-title">{investigator.name}</h2><p>{investigator.occupation}<span>·</span>{investigator.age === null ? '年龄未提供' : `${investigator.age} 岁`}</p></div>
      </div>
      <div className="investigator-tabs" role="tablist" aria-label="调查员资料">
        {tabs.map((tab, index) => <button
          key={tab.id} ref={(element) => { tabButtons.current[index] = element }} role="tab"
          id={`investigator-tab-${tab.id}`} aria-controls={`investigator-panel-${tab.id}`}
          aria-selected={activeTab === tab.id} tabIndex={activeTab === tab.id ? 0 : -1}
          onClick={() => setActiveTab(tab.id)} onKeyDown={(event) => navigateTabs(event, index)}
        >{tab.label}</button>)}
      </div>
      <section className="investigator-tab-panel" role="tabpanel" tabIndex={0} id="investigator-panel-overview" aria-labelledby="investigator-tab-overview" hidden={activeTab !== 'overview'}>
        <p className="investigator-overview">{investigator.overview}</p>
        <dl className="investigator-resources">
          <div><dt>HP</dt><dd>{resource(initial.hp, initial.hpMax)}</dd></div><div><dt>SAN</dt><dd>{resource(initial.san)}</dd></div>
          <div><dt>MP</dt><dd>{resource(initial.mp, initial.mpMax)}</dd></div><div><dt>幸运</dt><dd>{resource(initial.luck)}</dd></div>
        </dl>
        <h3>主要技能</h3><Skills skills={investigator.skills.filter((skill) => skill.highlighted).slice(0, 4)} />
      </section>
      <section className="investigator-tab-panel" role="tabpanel" tabIndex={0} id="investigator-panel-stats" aria-labelledby="investigator-tab-stats" hidden={activeTab !== 'stats'}>
        <h3>基础属性</h3>
        <dl className="investigator-attributes">{attributes.map(({ key, label }) => <div key={key}><dt>{label}<span>{key}</span></dt><dd>{investigator.attributes[key] ?? '—'}</dd></div>)}</dl>
        <h3>技能一览</h3><Skills skills={investigator.skills} />
        <p className="dossier-note">“—”表示尚未提供，不代表数值为零。</p>
      </section>
      <section className="investigator-tab-panel" role="tabpanel" tabIndex={0} id="investigator-panel-background" aria-labelledby="investigator-tab-background" hidden={activeTab !== 'background'}>
        {investigator.background.length ? investigator.background.map((section) => <div className="background-section" key={section.title}><h3>{section.title}</h3><p className={!section.text ? 'unfilled' : undefined}>{section.text || '尚未填写'}</p></div>) : <p className="dossier-note">暂无背景资料。</p>}
      </section>
      <section className="investigator-tab-panel" role="tabpanel" tabIndex={0} id="investigator-panel-equipment" aria-labelledby="investigator-tab-equipment" hidden={activeTab !== 'equipment'}>
        <h3>初始物品</h3>
        {investigator.equipment.length ? <ul className="equipment-list">{investigator.equipment.map((item) => <li key={`${item.kind}-${item.name}`}><div><strong>{item.name}</strong><span className="equipment-quantity">{item.quantity === null ? '数量未提供' : `× ${item.quantity}`}</span></div><p>{item.kind === 'owned' ? '拥有资产' : '随身物品'}{item.note && ` · ${item.note}`}</p></li>)}</ul> : <p className="dossier-note">暂无物品资料。</p>}
        <p className="starting-cash">初始现金 <span>{investigator.cash ? `${investigator.cash.currency} ${investigator.cash.amount}` : '未提供'}</span></p>
        <p className="dossier-note">仅展示开局物品，不代表物品特例已实现。</p>
      </section>
      <div className="investigator-confirm">
        <button className="investigate-button dossier-action" onClick={() => onConfirm(investigator)} aria-haspopup="dialog"><FrameCorners /><span>确认调查员</span><Arrow /></button>
        <p className="next-step">你将以{investigator.displayName}的身份展开调查。</p>
      </div>
    </>
  )
}

export function InvestigatorSelection({ moduleId }: { moduleId: string | null }) {
  const [catalogue, setCatalogue] = useState<CatalogueState>(moduleId ? { status: 'loading' } : { status: 'unavailable' })
  const [selected, setSelected] = useState<InvestigatorSummary | null>(null)
  const [detail, setDetail] = useState<DetailState>({ status: 'idle' })
  const [listAttempt, setListAttempt] = useState(0)
  const [detailAttempt, setDetailAttempt] = useState(0)
  const [confirmed, setConfirmed] = useState<InvestigatorDetail | null>(null)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')
  const createController = useRef<AbortController | null>(null)
  useEffect(() => () => createController.current?.abort(), [])
  async function startGame() {
    if (!moduleId || !confirmed || createController.current) return
    const key = `pending-creation:${moduleId}:${confirmed.id}`
    const requestId = sessionStorage.getItem(key) || crypto.randomUUID()
    sessionStorage.setItem(key, requestId)
    const controller = new AbortController(); createController.current = controller
    setCreating(true); setCreateError('')
    try {
      const game = await createGame(requestId, moduleId, confirmed.id, controller.signal)
      sessionStorage.removeItem(key)
      window.location.hash = `/game?${new URLSearchParams({ game: game.gameId })}`
    } catch (error) {
      if (!controller.signal.aborted) setCreateError(error instanceof Error ? error.message : '暂时无法创建调查，请重试。')
    } finally { createController.current = null; if (!controller.signal.aborted) setCreating(false) }
  }
  const confirmation = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    if (!moduleId) return
    const controller = new AbortController()
    listInvestigators({ moduleId, signal: controller.signal })
      .then((data) => { if (!controller.signal.aborted) setCatalogue({ status: 'ready', data }) })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setCatalogue({ status: error instanceof InvestigatorRequestError && error.code === 'module-unavailable' ? 'unavailable' : 'error' })
      })
    return () => controller.abort()
  }, [moduleId, listAttempt])

  useEffect(() => {
    if (!moduleId || !selected) return
    const controller = new AbortController()
    getInvestigator({ moduleId, id: selected.id, signal: controller.signal })
      .then((data) => { if (!controller.signal.aborted) setDetail({ status: 'ready', data }) })
      .catch(() => { if (!controller.signal.aborted) setDetail({ status: 'error' }) })
    return () => controller.abort()
  }, [moduleId, selected, detailAttempt])

  const data = catalogue.status === 'ready' ? catalogue.data : null
  const ready = detail.status === 'ready' && detail.data.id === selected?.id ? detail.data : null

  function choose(investigator: InvestigatorSummary) {
    if (selected?.id === investigator.id) return
    setSelected(investigator)
    setDetail({ status: 'loading' })
  }

  function confirm(investigator: InvestigatorDetail) {
    setConfirmed(investigator)
    confirmation.current?.showModal()
  }

  return (
    <main id="main" className="investigators-main" tabIndex={-1}>
      <div className="investigators-heading">
        <p className="eyebrow">THE INVESTIGATORS</p><h1>选择调查员</h1><p>选择你将扮演的人，走进这场调查。</p>
      </div>
      <div className="investigator-context"><p>02 / 选择调查员</p><p>当前案件 <span>·</span> {data?.module.title ?? (catalogue.status === 'loading' ? '读取中…' : '未选择')}</p></div>
      <section className="investigator-gallery" aria-label="预设调查员" aria-busy={catalogue.status === 'loading'}>
        {catalogue.status === 'loading' && <div className="investigator-gallery-message" role="status"><DoorMark className="message-door" /><p>正在整理人物档案…</p></div>}
        {catalogue.status === 'unavailable' && <div className="investigator-gallery-message"><DoorMark className="message-door" /><h2>请先选择案件</h2><p>当前案件尚不可用，请返回模组库选择。</p><a className="text-button" href="#/modules">返回模组库 <Arrow /></a></div>}
        {catalogue.status === 'error' && <div className="investigator-gallery-message" role="alert"><p>暂时无法读取调查员档案。</p><button className="text-button" onClick={() => { setCatalogue({ status: 'loading' }); setListAttempt((value) => value + 1) }}>重新读取 ↗</button></div>}
        {data && (data.items.length ? <ul className="investigator-cards">{data.items.map((investigator) => <li key={investigator.id}>
          <button className={`investigator-card ${selected?.id === investigator.id ? 'selected' : ''}`} aria-label={`选择${investigator.displayName}，${investigator.occupation}`} aria-pressed={selected?.id === investigator.id} aria-controls="investigator-dossier" onClick={() => choose(investigator)}>
            <span className="investigator-photo"><Portrait portrait={investigator.portrait} name={investigator.name} decorative />{selected?.id === investigator.id && <span className="selected-seal" aria-hidden="true"><svg viewBox="0 0 16 16"><path d="m4 8 3 3 5-6" /></svg></span>}</span>
            <span className="investigator-card-name">{investigator.displayName}</span><span className="investigator-card-occupation">{investigator.occupation}</span>
          </button>
        </li>)}</ul> : <div className="investigator-gallery-message"><p>这个案件暂无可选调查员。</p><a className="text-button" href="#/modules">返回模组库</a></div>)}
      </section>
      <aside id="investigator-dossier" className="investigator-dossier" aria-labelledby="investigator-title" aria-busy={detail.status === 'loading'}>
        <FrameCorners />
        {ready ? <InvestigatorDossier key={ready.id} investigator={ready} onConfirm={confirm} /> : <div className="investigator-empty">
          <p className="dossier-eyebrow">INVESTIGATOR DOSSIER</p><DoorMark className="empty-investigator-mark" />
          <h2 id="investigator-title">{detail.status === 'loading' ? '正在展开档案…' : detail.status === 'error' ? '档案暂不可用' : '你将成为谁？'}</h2>
          <p role="status">{detail.status === 'loading' ? '请稍候，正在读取人物资料。' : detail.status === 'error' ? '请重新读取，或选择另一位调查员。' : '从左侧选择一位调查员，了解他的故事。'}</p>
          {detail.status === 'error' && <button className="text-button" onClick={() => { setDetail({ status: 'loading' }); setDetailAttempt((value) => value + 1) }}>重新读取 ↗</button>}
          <button className="investigate-button dossier-action" disabled><FrameCorners /><span>确认调查员</span><Arrow /></button>
          <p className="next-step">请选择并查看一位调查员</p>
        </div>}
      </aside>
      <p className="sr-only" aria-live="polite">{ready ? `已选择${ready.name}，人物资料已更新。` : ''}</p>
      <dialog className="folio-dialog" onCancel={(event) => { if (creating) event.preventDefault() }} ref={confirmation} aria-labelledby="investigation-ready-title">
        <div className="dialog-heading"><p className="eyebrow">YOUR NEXT CHAPTER</p><button className="close-button" aria-label="关闭调查准备" disabled={creating} onClick={() => confirmation.current?.close()}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg></button></div>
        <h2 id="investigation-ready-title">调查准备</h2>
        <dl className="ready-summary"><div><dt>案件</dt><dd>{data?.module.title}</dd></div><div><dt>调查员</dt><dd>{confirmed?.name}</dd></div><div><dt>职业</dt><dd>{confirmed?.occupation}</dd></div></dl>
        {createError && <p role="alert">{createError}</p>}{data && confirmed && <button className="dialog-action" disabled={creating} onClick={() => void startGame()}>{creating ? '正在创建调查…' : createError ? '重试创建调查' : '开始调查'} <Arrow /></button>}
      </dialog>
    </main>
  )
}
