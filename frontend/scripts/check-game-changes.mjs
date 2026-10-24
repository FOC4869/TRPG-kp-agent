// Public snapshot differences only. No saves, backend, or paid model calls.
import assert from 'node:assert/strict'
import { createServer } from 'vite'

const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
try {
  const { gameChanges } = await server.ssrLoadModule('/src/state/game-changes.ts')
  const state = {
    gameId: 'a'.repeat(32), version: 1,
    investigator: { resources: { hp: 2, hpMax: 14, san: 65, mp: 13, mpMax: 13, luck: 60 } },
    inventory: [{ id: 'rope', name: '绳索', quantity: 2, kind: 'carried' }],
    facts: [{ id: 'known', title: '已知线索', text: '旧信息' }],
  }
  const next = structuredClone(state)
  next.version++
  next.investigator.resources.hp = 0 // Actual HP loss is capped at 2, even if a damage die rolled 6.
  next.investigator.resources.san = 62
  next.inventory.push({ id: 'light', name: '手电筒', quantity: 1, kind: 'carried' })
  next.facts.push({ id: 'new', title: '地下足迹', text: '公开事实' })
  assert.deepEqual(gameChanges(state, next).map(({ text }) => text), ['HP −2', 'SAN −3', '获得物品：手电筒', '发现线索：地下足迹'])

  assert.deepEqual(gameChanges(null, next), [], 'Opening or reloading a saved game does not replay old rewards')
  assert.deepEqual(gameChanges(next, structuredClone(next)), [], 'Completion and reconnect snapshots do not repeat committed effects')
  assert.deepEqual(gameChanges(next, state), [], 'Older snapshots do not reverse changes')
  assert.deepEqual(gameChanges(state, { ...next, gameId: 'b'.repeat(32) }), [], 'Different games are never compared')
  assert.deepEqual(gameChanges(state, { ...state, version: 2 }), [], 'Pure narration or movement has no resource notice')

  const quantities = structuredClone(state)
  quantities.version++
  quantities.inventory[0].quantity = 1
  assert.equal(gameChanges(state, quantities)[0].text, '消耗物品：绳索 ×1')
  quantities.inventory[0].quantity = 5
  assert.equal(gameChanges(state, quantities)[0].text, '获得物品：绳索 ×3')
  quantities.inventory = []
  assert.equal(gameChanges(state, quantities)[0].text, '物品移出：绳索')
  quantities.inventory = [{ id: 'rope', name: '绳索', quantity: null }]
  assert.deepEqual(gameChanges(state, quantities), [], 'Unknown quantities must not produce invented deltas')
  quantities.inventory = [{ id: 'rope', name: '绳索', quantity: 2 }, { id: 'tool', name: '工具', quantity: null }]
  assert.equal(gameChanges(state, quantities)[0].text, '获得物品：工具')

  const gains = structuredClone(state)
  gains.version++
  gains.investigator.resources.hp = 5
  gains.investigator.resources.mp = 0
  gains.investigator.resources.luck = 61
  assert.deepEqual(gameChanges(state, gains).map(({ text }) => text), ['HP +3', 'MP −13', '幸运 +1'])
  gains.investigator.resources = { ...state.investigator.resources, hpMax: 20, san: null }
  assert.deepEqual(gameChanges(state, gains), [], 'Missing values or a changed maximum are not resource gains')
  gains.facts[0].title = '标题修正'
  assert.deepEqual(gameChanges(state, gains), [], 'A known clue is not newly discovered when its text changes')
  assert.deepEqual(state.investigator.resources.hp, 2, 'Input snapshots stay unchanged')
  console.log('Game change checks passed: committed gains/losses, inventory, clues, initial/replay/version/game isolation and missing values.')
} finally {
  await server.close()
}
