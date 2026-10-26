import { arrayOf, record, text } from './catalogue'
import { isDetail } from './investigators'
import type { GameAction, GameCheck, GameEffect, GameEvent, GameMessage, GameReview, GameState, RuleEvidence } from '../types/game'

export class GameRequestError extends Error {
  code: string
  status?: number
  constructor(code: string, message: string, status?: number) { super(message); this.name = 'GameRequestError'; this.code = code; this.status = status }
}
const integer = (n: unknown): n is number => typeof n === 'number' && Number.isSafeInteger(n) && n >= 0
const gameAsset = (url: unknown) => typeof url === 'string' && /^\/api\/games\/[a-f0-9]{32}\/assets\/[a-z0-9_-]+$/.test(url)
function isCheck(c: unknown): c is GameCheck {
  return record(c) && text(c.checkId) && text(c.skill) && integer(c.target) && text(c.reason)
    && (c.roll === undefined || (integer(c.roll) && c.roll >= 1 && c.roll <= 100))
    && (c.success === undefined || typeof c.success === 'boolean')
    && (c.result === undefined || text(c.result))
    && (c.details === undefined || arrayOf(c.details, (d): d is NonNullable<GameCheck['details']>[number] => record(d) && (d.resource === 'hp' || d.resource === 'san') && text(d.dice) && integer(d.amount)))
}
function isEffect(e: unknown): e is GameEffect {
  return record(e) && text(e.effectId) && e.resource === 'hp' && text(e.reason)
    && typeof e.dice === 'string' && /^1D[36]$/.test(e.dice) && integer(e.amount) && e.amount >= 1
    && integer(e.before) && integer(e.after) && e.after === Math.max(0, e.before - e.amount)
}
function isEvidence(e: unknown): e is RuleEvidence {
  const page = (value: unknown) => value === null || (integer(value) && value >= 1)
  return record(e) && text(e.evidence_id) && !!e.evidence_id.trim() && text(e.title) && !!e.title.trim()
    && text(e.source) && !!e.source.trim() && text(e.text) && page(e.pdf_page) && page(e.printed_page)
    && (e.edition == null || text(e.edition))
}
function isMessage(m: unknown): m is GameMessage {
  return record(m) && text(m.id) && ['keeper', 'npc', 'player', 'check', 'effect'].includes(String(m.kind)) && text(m.speaker) && text(m.text)
    && (m.check === undefined || isCheck(m.check)) && (m.effect === undefined || isEffect(m.effect)) && (m.kind !== 'effect' || isEffect(m.effect)) && (m.final === undefined || typeof m.final === 'boolean')
    && (m.evidence === undefined || arrayOf(m.evidence, isEvidence))
}
export function isGameState(value: unknown): value is GameState {
  if (!record(value) || !text(value.gameId) || !/^[a-f0-9]{32}$/.test(value.gameId) || !integer(value.version)) return false
  const { module, scene, pendingTurn } = value
  const npc = (n: unknown): n is GameState['npcs'][number] => record(n) && text(n.id) && text(n.name) && text(n.role) && gameAsset(n.spriteUrl) && String(n.spriteUrl).includes(`/games/${value.gameId}/`)
  return record(module) && text(module.id) && text(module.title) && (module.englishTitle === undefined || module.englishTitle === null || text(module.englishTitle)) && isDetail(value.investigator)
    && record(scene) && text(scene.id) && text(scene.name) && text(scene.region) && gameAsset(scene.backgroundUrl) && String(scene.backgroundUrl).includes(`/games/${value.gameId}/`)
    && (value.npc === null || npc(value.npc)) && arrayOf(value.npcs, npc)
    && arrayOf(value.messages, isMessage) && arrayOf(value.facts, (f): f is GameState['facts'][number] => record(f) && text(f.id) && text(f.title) && text(f.text))
    && arrayOf(value.inventory, (i): i is GameState['inventory'][number] => record(i) && text(i.id) && text(i.name) && (i.quantity === null || integer(i.quantity)) && (i.kind === 'carried' || i.kind === 'owned'))
    && arrayOf(value.suggestions, text) && typeof value.ended === 'boolean' && (value.ending === null || ['completed', 'retreated', 'failed'].includes(String(value.ending)))
    && (value.campaignEnding === undefined || value.campaignEnding === null || ['complete', 'retreat', 'incomplete'].includes(String(value.campaignEnding)))
    && (value.paused === undefined || typeof value.paused === 'boolean')
    && (value.endingSummary === null || text(value.endingSummary)) && (value.status === 'active' || value.status === 'ended')
    && (value.pendingAction === undefined || value.pendingAction === null || (record(value.pendingAction) && text(value.pendingAction.id) && text(value.pendingAction.prompt)))
    && (value.nearbyItems === undefined || arrayOf(value.nearbyItems, (i): i is GameState['inventory'][number] => record(i) && text(i.id) && text(i.name) && (i.quantity === null || integer(i.quantity)) && i.kind === 'carried'))
    && (pendingTurn === null || (record(pendingTurn) && text(pendingTurn.requestId) && text(pendingTurn.text) && text(pendingTurn.stage) && (pendingTurn.confirmationId === undefined || text(pendingTurn.confirmationId))))
}
async function responseError(response: Response): Promise<never> {
  const data: unknown = await response.json().catch(() => null)
  const detail = record(data) && record(data.detail) ? data.detail : null
  throw new GameRequestError(detail && text(detail.code) ? detail.code : 'http_error', detail && text(detail.message) ? detail.message : `游戏请求失败（${response.status}），请重新读取后恢复。`, response.status)
}
async function snapshot(url: string, signal: AbortSignal, body?: unknown): Promise<GameState> {
  const response = await fetch(url, { signal, ...(body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}) })
  if (!response.ok) return responseError(response)
  const data: unknown = await response.json()
  if (!isGameState(data)) throw new GameRequestError('invalid_response', '游戏资料格式不正确，请检查后端版本。')
  return data
}
export const getGame = (id: string, signal: AbortSignal) => snapshot(`/api/games/${encodeURIComponent(id)}`, signal)
export const createGame = (requestId: string, moduleId: string, investigatorId: string, signal: AbortSignal) => snapshot('/api/games', signal, { requestId, moduleId, investigatorId })
export async function getGameReview(id: string, signal: AbortSignal): Promise<GameReview> {
  const response = await fetch(`/api/games/${encodeURIComponent(id)}/review`, { signal })
  if (!response.ok) return responseError(response)
  const data: unknown = await response.json()
  const clue = (value: unknown): value is GameReview['discovered_clues'][number] => record(value) && text(value.id) && text(value.name) && text(value.description)
  if (!record(data) || !text(data.text) || !['complete', 'retreat', 'incomplete'].includes(String(data.ending))
    || !arrayOf(data.discovered_clues, clue) || !arrayOf(data.missed_clues, clue)) {
    throw new GameRequestError('invalid_review', '复盘资料格式不正确，请重新读取。')
  }
  return data as unknown as GameReview
}

/** Streaming TextDecoder preserves UTF-8 characters split across network chunks. */
export async function readGameEvents(body: ReadableStream<Uint8Array>, onEvent: (event: GameEvent) => void, signal: AbortSignal) {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  function parseFrames() {
    let boundary: number
    while ((boundary = buffer.indexOf('\n\n')) >= 0) {
      const frame = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 2)
      const data = frame.split('\n').filter((line) => line.startsWith('data:')).map((line) => line.slice(5).trimStart()).join('\n')
      if (!data) continue
      const event: unknown = JSON.parse(data)
      if (!record(event) || !text(event.type) || !text(event.turnId) || !integer(event.seq)) throw new GameRequestError('invalid_event', '事件流格式不正确。')
      if (event.state !== undefined && !isGameState(event.state)) throw new GameRequestError('invalid_state', '游戏状态格式不正确。')
      if (event.effect !== undefined && !isEffect(event.effect)) throw new GameRequestError('invalid_effect', '伤害结果格式不正确。')
      if (event.check !== undefined && !isCheck(event.check)) throw new GameRequestError('invalid_check', '检定资料格式不正确。')
      if (event.message !== undefined && event.type !== 'turn.failed' && !isMessage(event.message)) throw new GameRequestError('invalid_message', '叙事资料格式不正确。')
      if (event.type === 'message.delta' && (!text(event.messageId) || !text(event.delta))) throw new GameRequestError('invalid_delta', '叙事流格式不正确。')
      // Error text has a different shape from a narrative message.
      if (event.type === 'turn.failed') { event.messageText = event.message; delete event.message }
      onEvent(event as unknown as GameEvent)
    }
  }
  const cancel = () => { void reader.cancel().catch(() => undefined) }
  signal.addEventListener('abort', cancel, { once: true })
  try {
    for (;;) {
      signal.throwIfAborted()
      const { value, done } = await reader.read()
      if (done) break
      buffer = (buffer + decoder.decode(value, { stream: true })).replace(/\r\n/g, '\n')
      if (buffer.length > 2_000_000) throw new GameRequestError('event_too_large', '事件流过大。')
      parseFrames()
    }
    buffer += decoder.decode(); parseFrames(); signal.throwIfAborted()
    if (buffer.trim()) throw new GameRequestError('stream_truncated', '事件流中断，请恢复原回合。')
  } finally { signal.removeEventListener('abort', cancel); await reader.cancel().catch(() => undefined); reader.releaseLock() }
}
export async function submitGameAction(id: string, action: GameAction, signal: AbortSignal, onEvent: (event: GameEvent) => void) {
  const response = await fetch(`/api/games/${encodeURIComponent(id)}/actions`, { method: 'POST', signal, headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' }, body: JSON.stringify(action) })
  if (!response.ok) return responseError(response)
  if (!response.body || !response.headers.get('content-type')?.includes('text/event-stream')) throw new GameRequestError('invalid_stream', '未收到游戏事件流。')
  let terminal = false
  const seen = new Set<string>()
  await readGameEvents(response.body, (event) => {
    const key = `${event.turnId}:${event.seq}`
    if (seen.has(key)) return
    seen.add(key)
    if (event.type === 'turn.failed' || event.type === 'turn.completed') terminal = true
    onEvent(event)
  }, signal)
  if (!terminal) throw new GameRequestError('stream_interrupted', '连接中断，请恢复原回合。')
}
