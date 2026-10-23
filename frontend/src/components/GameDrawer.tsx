import type { GameFact, GameMessage, GamePreview } from '../types/game'

export type GamePanel = 'character' | 'inventory' | 'clues' | 'history' | 'settings'

export function GameMessages({ messages }: { messages: GameMessage[] }) {
  return <>{messages.map((message) => <article className={`game-message message-${message.kind}`} key={message.id}>
    <p className="game-speaker">{message.speaker}<span>{message.kind === 'keeper' ? 'KEEPER' : message.kind === 'npc' ? 'NPC' : message.kind === 'check' ? '检定示例' : '调查员'}</span></p>
    {message.check && <div className="game-check"><strong>{message.check.skill}</strong><span>目标值 {message.check.target}</span><span>D100 <b>{message.check.roll}</b></span><em>{message.check.result}</em></div>}
    <p className="game-message-text">{message.text}</p>
  </article>)}</>
}

export function GameDrawerContent({ panel, game, facts, messages, reduceMotion, onMotion, onCheck, onEnding, busy }: {
  panel: GamePanel; game: GamePreview; facts: GameFact[]; messages: GameMessage[]
  reduceMotion: boolean; onMotion: (value: boolean) => void; onCheck: () => void; onEnding: () => void; busy: boolean
}) {
  const investigator = game.investigator
  if (panel === 'history') return <GameMessages messages={messages} />
  if (panel === 'clues') return facts.length ? <div className="game-facts">{facts.map((fact) => <article key={fact.id}><p className="eyebrow">已记录</p><h3>{fact.title}</h3><p>{fact.text}</p></article>)}</div> : <div className="game-drawer-empty"><p>还没有记录线索</p><span>与人物交谈、观察环境后，已获知的信息会出现在这里。</span></div>
  if (panel === 'inventory') return <><p className="game-drawer-intro">{investigator.displayName}的开局物品 · 示例资料</p><ul className="equipment-list">{investigator.equipment.map((item) => <li key={`${item.kind}-${item.name}`}><div><strong>{item.name}</strong><span className="equipment-quantity">{item.quantity === null ? '数量未提供' : `× ${item.quantity}`}</span></div><p>{item.kind === 'owned' ? '拥有资产' : '随身物品'}{item.note && ` · ${item.note}`}</p></li>)}</ul><p className="dossier-note">准备装备的对话不会自动向背包添加物品。</p></>
  if (panel === 'settings') return <><label className="setting-row"><span><strong>减少动态效果</strong><span className="setting-hint">仅本次浏览有效。</span></span><input type="checkbox" checked={reduceMotion} onChange={(event) => onMotion(event.target.checked)} /></label><section className="game-preview-settings"><h3>开场界面预览</h3><p>当前使用示例人物与固定回复，不连接模型、不保存进度。刷新会回到开场。</p><button className="text-button" disabled={busy} onClick={onCheck}>查看检定展示示例 ↗</button><p>此操作只插入一张固定结果卡片，不会掷骰或改变状态。</p><button className="text-button ending-preview-button" disabled={busy} onClick={onEnding}>查看结案弹窗示例 ↗</button><p>示例会结束本次预览，刷新可重新开始。</p><p>存档功能暂未开放。</p><a className="text-button" href={`#/investigators?${new URLSearchParams({ module: game.module.id })}`}>返回调查员选择 ↗</a></section></>
  return <><p className="game-drawer-intro">{investigator.name} · {investigator.occupation}</p><p className="game-drawer-prose">{investigator.overview}</p><h3>基础属性</h3><dl className="investigator-attributes">{Object.entries(investigator.attributes).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value ?? '—'}</dd></div>)}</dl><h3>技能</h3><dl className="game-drawer-skills">{investigator.skills.map((skill) => <div key={skill.name}><dt>{skill.name}</dt><dd>{skill.value ?? '—'}</dd></div>)}</dl>{investigator.background.map((section) => <section className="background-section" key={section.title}><h3>{section.title}</h3><p>{section.text || '尚未填写'}</p></section>)}</>
}
