// Offline resume boundary checks using real public character DTOs; no model calls.
import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { installCatalogueFixture } from './catalogue-fixture.mjs'

const fixture = installCatalogueFixture()
const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
const originalWindow = globalThis.window
try {
  const { RECENT_GAME_KEY, recentGameId, rememberGame, forgetRecentGame, loadRecentGame } = await server.ssrLoadModule('/src/state/recent-game.ts')
  const entries = new Map()
  const storage = { getItem: (key) => entries.get(key) ?? null, setItem: (key, value) => entries.set(key, value), removeItem: (key) => entries.delete(key) }
  globalThis.window = { localStorage: storage }
  const a = 'a'.repeat(32), b = 'b'.repeat(32)
  const state = {
    gameId: a, version: 3, module: { id: 'darkness-beneath-the-hill', title: '岭下暗影' },
    investigator: fixture.fixtures['/api/modules/darkness-beneath-the-hill/investigators/jessica'],
    scene: { id: 'winscott_house', name: '文斯考特宅', region: '普罗维登斯', backgroundUrl: `/api/games/${a}/assets/bg_winscott_house` },
    npc: null, npcs: [], inventory: [], messages: [{ id: 'opening', kind: 'keeper', speaker: '守秘人', text: '开场' }],
    facts: [], suggestions: [], ended: false, ending: null, endingSummary: null, status: 'active', pendingTurn: null,
  }
  const { isGameState } = await server.ssrLoadModule('/src/api/game.ts')
  const independentModule = { ...state, module: { id: 'silent-observatory', title: '沉寂天文台', englishTitle: 'The Silent Observatory' }, scene: { ...state.scene, id: 'lobby', name: '门厅', backgroundUrl: `/api/games/${a}/assets/bg-lobby` }, npcs: [{ id: 'curator', name: '管理员', role: '值班员', spriteUrl: `/api/games/${a}/assets/sprite-curator` }] }
  assert.equal(isGameState(independentModule), true, 'Another module and hyphenated asset IDs use the same public contract')
  assert.equal(isGameState({ ...independentModule, module: { ...independentModule.module, englishTitle: null } }), true)
  assert.equal(isGameState({ ...independentModule, module: { ...independentModule.module, englishTitle: 123 } }), false)
  assert.equal(isGameState({ ...independentModule, scene: { ...independentModule.scene, backgroundUrl: `/api/games/${a}/assets/../private` } }), false)
  const signal = () => new AbortController().signal
  let calls = []
  let reply = state
  let httpStatus = 200
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, method: options.method ?? 'GET' })
    options.signal?.throwIfAborted()
    return Response.json(reply, { status: httpStatus })
  }

  assert.deepEqual(await loadRecentGame(signal()), { status: 'empty' })
  assert.equal(calls.length, 0, 'No backend scan without a stored pointer')
  storage.setItem(RECENT_GAME_KEY, '../saves/private')
  assert.equal(recentGameId(), null)
  assert.equal(storage.getItem(RECENT_GAME_KEY), null)
  rememberGame(state)
  assert.equal(storage.getItem(RECENT_GAME_KEY), a, 'Only the ID is stored, never the state')
  assert.equal((await loadRecentGame(signal())).game.gameId, a)
  assert.deepEqual(calls, [{ url: `/api/games/${a}`, method: 'GET' }])

  const pending = { requestId: 'original-request', text: '原行动', stage: 'failed' }
  reply = { ...state, pendingTurn: pending }
  assert.deepEqual((await loadRecentGame(signal())).game.pendingTurn, pending)
  reply = { ...state, ended: true, ending: 'failed', status: 'ended', pendingTurn: pending }
  rememberGame(reply)
  assert.equal((await loadRecentGame(signal())).status, 'ready', 'Fatal result still needs the unfinished final narration')
  reply = { ...reply, pendingTurn: null, endingSummary: '结案' }
  assert.equal((await loadRecentGame(signal())).status, 'empty')
  assert.equal(recentGameId(), null)

  rememberGame({ ...state, gameId: b })
  rememberGame({ ...state, ended: true })
  forgetRecentGame(a)
  assert.equal(recentGameId(), b, 'Finishing an old game cannot erase a newer one')
  rememberGame(state)
  httpStatus = 404
  reply = { detail: { code: 'game_not_found', message: '找不到这场调查。' } }
  assert.equal((await loadRecentGame(signal())).status, 'empty')
  assert.equal(recentGameId(), null)

  rememberGame(state)
  for (const [status, code] of [[503, 'save_invalid'], [409, 'version_incompatible'], [503, 'game_not_found']]) {
    httpStatus = status
    reply = { detail: { code, message: '原文件已保留。' } }
    const result = await loadRecentGame(signal())
    assert.equal(result.status, 'error')
    assert.equal(result.message, '原文件已保留。')
    assert.equal(recentGameId(), a, 'Transient or incompatible saves retain the recovery pointer')
  }
  httpStatus = 200
  reply = { ...state, gameId: b, scene: { ...state.scene, backgroundUrl: `/api/games/${b}/assets/bg_winscott_house` } }
  assert.equal((await loadRecentGame(signal())).status, 'error', 'A different valid game must not become the resume target')
  assert.equal(recentGameId(), a)
  reply = { invalid: true }
  assert.equal((await loadRecentGame(signal())).status, 'error')
  assert.equal(recentGameId(), a)
  globalThis.fetch = async () => { throw new TypeError('offline') }
  assert.equal((await loadRecentGame(signal())).status, 'error')
  assert.equal(recentGameId(), a)

  const cancelled = new AbortController()
  globalThis.fetch = async () => { cancelled.abort(); return Response.json(state) }
  await assert.rejects(loadRecentGame(cancelled.signal), { name: 'AbortError' })
  assert.equal(recentGameId(), a, 'Cancelled checks leave the pointer intact')

  Object.defineProperty(globalThis.window, 'localStorage', { get() { throw new DOMException('Denied', 'SecurityError') } })
  assert.doesNotThrow(() => rememberGame(state))
  assert.doesNotThrow(() => forgetRecentGame(a))
  assert.equal(recentGameId(), null)
  assert.deepEqual(await loadRecentGame(signal()), { status: 'empty' })
  calls = []
  console.log('Recent game checks passed: active/pending/terminal, missing, errors, identity, abort, storage denial and multi-game cleanup; GET only.')
} finally {
  globalThis.window = originalWindow
  fixture.restore()
  await server.close()
}
