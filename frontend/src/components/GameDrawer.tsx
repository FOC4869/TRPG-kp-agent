import type { GameFact, GameMessage, GameState } from '../types/game'

import { GameCheckCard } from './GameCheckCard'

export type GamePanel = 'character' | 'inventory' | 'clues' | 'history'

export function GameMessages({ messages }: { messages: GameMessage[] }) {
  return <>{messages.map((message) => <article className={`game-message message-${message.kind}`} key={message.id}>
    <p className="game-speaker">{message.speaker}<span>{message.kind === 'keeper' ? 'KEEPER' : message.kind === 'npc' ? 'NPC' : message.kind === 'check' ? '规则'  : '调查员'}</span></p>
    {message.check ? <GameCheckCard check={message.check} /> : <p className="game-message-text">{message.text}</p>}
  </article>)}</>
}

export function GameDrawerContent({ panel, game, facts, messages }: {
  panel: GamePanel; game: GameState; facts: GameFact[]; messages: GameMessage[]
}) {
  const investigator = game.investigator
  if (panel === 'history') return <GameMessages messages={messages} />
  if (panel === 'clues') return facts.length ? <div className="game-facts">{facts.map((fact) => <article key={fact.id}><p className="eyebrow">已记录</p><h3>{fact.title}</h3><p>{fact.text}</p></article>)}</div> : <div className="game-drawer-empty"><p>还没有记录线索</p><span>与人物交谈、观察环境后，已获知的信息会出现在这里。</span></div>
  if (panel === 'inventory') return <><p className="game-drawer-intro">{investigator.displayName}的随身物品</p><ul className="equipment-list">{game.inventory.map((item) => <li key={`${item.kind}-${item.name}`}><div><strong>{item.name}</strong><span className="equipment-quantity">{item.quantity === null ? '数量未提供' : `× ${item.quantity}`}</span></div><p>{item.kind === 'owned' ? '拥有资产' : '随身物品'}{item.note && ` · ${item.note}`}</p></li>)}</ul></>
  return <><p className="game-drawer-intro">{investigator.name} · {investigator.occupation}</p><p className="game-drawer-prose">{investigator.overview}</p><h3>基础属性</h3><dl className="investigator-attributes">{Object.entries(investigator.attributes).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value ?? '—'}</dd></div>)}</dl><h3>技能</h3><dl className="game-drawer-skills">{investigator.skills.map((skill) => <div key={skill.name}><dt>{skill.name}</dt><dd>{skill.value ?? '—'}</dd></div>)}</dl>{investigator.background.map((section) => <section className="background-section" key={section.title}><h3>{section.title}</h3><p>{section.text || '尚未填写'}</p></section>)}</>
}
