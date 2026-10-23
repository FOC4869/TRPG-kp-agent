import { useEffect, useRef, useState } from 'react'
import { listPublicModules } from '../api/modules'
import type { ModulePage, PublicModule } from '../api/modules'
import { Arrow, DoorMark, FrameCorners } from './Ornaments'

const PAGE_SIZE = 3

type CatalogueState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'ready'; data: ModulePage }

export function ModuleLibrary({ onChooseInvestigator }: { onChooseInvestigator: (module: PublicModule) => void }) {
  const [page, setPage] = useState(1)
  const [attempt, setAttempt] = useState(0)
  const [catalogue, setCatalogue] = useState<CatalogueState>({ status: 'loading' })
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const firstCard = useRef<HTMLButtonElement>(null)
  const focusAfterPaging = useRef(false)

  useEffect(() => {
    const controller = new AbortController()
    listPublicModules({ page, pageSize: PAGE_SIZE, signal: controller.signal })
      .then((data) => {
        if (controller.signal.aborted) return
        setCatalogue({ status: 'ready', data })
        setSelectedId(data.items[0]?.id ?? null)
      })
      .catch(() => {
        if (!controller.signal.aborted) setCatalogue({ status: 'error' })
      })
    return () => controller.abort()
  }, [page, attempt])

  useEffect(() => {
    if (catalogue.status === 'ready' && focusAfterPaging.current) {
      firstCard.current?.focus()
      focusAfterPaging.current = false
    }
  }, [catalogue])

  const data = catalogue.status === 'ready' ? catalogue.data : null
  const selected = data?.items.find((module) => module.id === selectedId) ?? null
  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.pageSize)) : 1

  function changePage(nextPage: number) {
    focusAfterPaging.current = true
    setCatalogue({ status: 'loading' })
    setPage(nextPage)
  }

  return (
    <main id="main" className="library-main" tabIndex={-1}>
      <div className="library-intro">
        <div>
          <p className="eyebrow">THE CASE FILES</p>
          <h1>调查卷宗</h1>
          <p className="library-subtitle">翻阅卷宗，选择你的下一场调查。</p>
        </div>
        <p className="journey-step"><span>01</span> / 选择模组</p>
      </div>

      <div className="library-layout" aria-busy={catalogue.status === 'loading'}>
        <section className="catalogue" aria-label="模组列表">
          <div className="catalogue-browser">
            <button className="page-arrow previous-page" aria-label="上一页模组" disabled={!data || data.page <= 1} onClick={() => { if (data) changePage(data.page - 1) }}><Arrow /></button>
            {catalogue.status === 'loading' && <div className="catalogue-message" role="status"><DoorMark className="message-door" /><p>正在翻阅卷宗…</p></div>}
            {catalogue.status === 'error' && (
              <div className="catalogue-message" role="alert"><p>暂时无法读取卷宗。</p><button className="text-button" onClick={() => { setCatalogue({ status: 'loading' }); setAttempt((value) => value + 1) }}>重新读取 <span aria-hidden="true">↗</span></button></div>
            )}
            {data && data.items.length === 0 && <div className="catalogue-message"><DoorMark className="message-door" /><p>暂无可供调查的卷宗。</p></div>}
            {data && data.items.length > 0 && (
              <ul className="module-cards">
                {data.items.map((module, index) => (
                  <li key={module.id}>
                    <button
                      ref={index === 0 ? firstCard : undefined}
                      className={`case-card ${module.cover ? 'illustrated' : 'upcoming'} ${selectedId === module.id ? 'selected' : ''}`}
                      aria-label={`卷宗 ${module.caseNumber}：${module.title}${module.status === 'coming-soon' ? '，尚未开放' : '，单人改编'}`}
                      aria-pressed={selectedId === module.id}
                      aria-controls="module-details"
                      onClick={() => setSelectedId(module.id)}
                    >
                      {module.cover && <img className="case-cover" src={module.cover} alt="" width="1024" height="1536" />}
                      {!module.cover && <div className="placeholder-arch" aria-hidden="true"><DoorMark className="placeholder-door" /></div>}
                      <div className="case-cover-shade" aria-hidden="true" />
                      <FrameCorners />
                      <div className="case-label"><span className="case-number">CASE {module.caseNumber}</span><span className="case-title">{module.title}</span><span className="case-badge">{module.status === 'preview' ? '单人改编' : '尚未开放'}</span></div>
                      {selectedId === module.id && <span className="selected-seal" aria-hidden="true"><svg viewBox="0 0 16 16"><path d="m4 8 3 3 5-6" /></svg></span>}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <button className="page-arrow next-page" aria-label="下一页模组" disabled={!data || data.page >= totalPages} onClick={() => { if (data) changePage(data.page + 1) }}><Arrow /></button>
          </div>
          <div className="catalogue-pagination">
            <p className="page-label" aria-live="polite" aria-atomic="true"><span />第 {data?.page ?? page} 页{data && <small> / {totalPages}</small>}<span /></p>
            <p className="catalogue-hint">点击卷宗，查看案件详情</p>
            <p className="sample-note">预览目录 · 含待收录占位卷宗</p>
          </div>
        </section>

        <section id="module-details" className="module-dossier" aria-labelledby="module-title">
          <FrameCorners />
          {selected ? (
            <>
              <p className="dossier-eyebrow">SELECTED CASE <span>·</span> {selected.caseNumber}</p>
              <div className="dossier-title"><h2 id="module-title">{selected.title}</h2><span className="dossier-tag">{selected.status === 'preview' ? '单人改编' : '尚未开放'}</span></div>
              {selected.englishTitle && <p className="english-title" lang="en">{selected.englishTitle}</p>}
              <div className="dossier-rule" aria-hidden="true"><span /></div>
              <div className="dossier-introduction"><h3>案件引言</h3>{selected.introduction.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}</div>
              <dl className="dossier-metadata">
                <div><dt>时代背景</dt><dd>{selected.era}</dd></div><div><dt>调查地点</dt><dd>{selected.location}</dd></div>
                <div><dt>本作玩法</dt><dd>{selected.playStyle}</dd></div><div><dt>原作人数</dt><dd>{selected.originalPlayers}</dd></div>
              </dl>
              <div className="dossier-bottom">
                {selected.contentNote && <p className="content-note">内容提示：{selected.contentNote}</p>}
                <button className="investigate-button dossier-action" disabled={selected.status !== 'preview'} onClick={() => onChooseInvestigator(selected)}>
                  <FrameCorners /><span>选择调查员</span><Arrow />
                </button>
                <p className="next-step">{selected.status === 'preview' ? '下一步 · 确认你的调查员' : '这份卷宗尚未开放'}</p>
              </div>
            </>
          ) : <div className="dossier-empty"><DoorMark className="message-door" /><h2 id="module-title">等待开启的故事</h2><p>卷宗详情将在这里展开。</p></div>}
        </section>
      </div>
    </main>
  )
}
