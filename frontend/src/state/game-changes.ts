import type { GameState } from '../types/game'

export interface GameChange {
  id: string
  text: string
  kind: 'loss' | 'gain' | 'item' | 'clue'
}

/** Compare committed public snapshots, never a model's description of effects. */
export function gameChanges(previous: GameState | null, current: GameState): GameChange[] {
  if (!previous || previous.gameId !== current.gameId || current.version <= previous.version) return []
  const changes: GameChange[] = []
  const labels = { hp: 'HP', san: 'SAN', mp: 'MP', luck: '幸运' } as const
  for (const key of ['hp', 'san', 'mp', 'luck'] as const) {
    const before = previous.investigator.resources[key], after = current.investigator.resources[key]
    if (before === null || after === null || before === after) continue
    const delta = after - before
    changes.push({ id: `resource:${key}`, text: `${labels[key]} ${delta > 0 ? '+' : '−'}${Math.abs(delta)}`, kind: delta > 0 ? 'gain' : 'loss' })
  }
  const oldItems = new Map(previous.inventory.map((item) => [item.id, item]))
  const newItems = new Map(current.inventory.map((item) => [item.id, item]))
  for (const item of current.inventory) {
    const before = oldItems.get(item.id)
    if (!before) {
      changes.push({ id: `item:${item.id}`, text: `获得物品：${item.name}${item.quantity !== null && item.quantity > 1 ? ` ×${item.quantity}` : ''}`, kind: 'item' })
    } else if (before.quantity !== null && item.quantity !== null && before.quantity !== item.quantity) {
      const delta = item.quantity - before.quantity
      changes.push({ id: `item:${item.id}`, text: `${delta > 0 ? '获得' : '消耗'}物品：${item.name} ×${Math.abs(delta)}`, kind: 'item' })
    }
  }
  for (const item of previous.inventory) {
    if (!newItems.has(item.id)) changes.push({ id: `item:${item.id}`, text: `物品移出：${item.name}`, kind: 'item' })
  }
  const oldFacts = new Set(previous.facts.map((fact) => fact.id))
  for (const fact of current.facts) {
    if (!oldFacts.has(fact.id)) changes.push({ id: `clue:${fact.id}`, text: `发现线索：${fact.title}`, kind: 'clue' })
  }
  return changes
}
