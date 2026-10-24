import type { InvestigatorDetail } from './investigators'

export interface GameCheck {
  checkId: string
  skill: string
  target: number
  reason: string
  roll?: number
  success?: boolean
  result?: string
  details?: { resource: 'hp' | 'san'; dice: string; amount: number }[]
  display?: 'rolling' | 'resolved' | 'error'
}
export interface GameEffect {
  effectId: string
  resource: 'hp'
  dice: string
  amount: number
  before: number
  after: number
  reason: string
}
export interface GameMessage {
  id: string
  kind: 'keeper' | 'npc' | 'player' | 'check' | 'effect'
  speaker: string
  text: string
  check?: GameCheck
  effect?: GameEffect
  final?: boolean
}
export interface GameFact { id: string; title: string; text: string }
export interface GameNpc { id: string; name: string; role: string; spriteUrl: string }
export interface PendingTurn { requestId: string; text: string; stage: string; confirmationId?: string }
export interface GameState {
  gameId: string
  version: number
  module: { id: string; title: string; englishTitle?: string | null }
  investigator: InvestigatorDetail
  scene: { id: string; name: string; region: string; backgroundUrl: string }
  npc: GameNpc | null
  npcs: GameNpc[]
  inventory: (InvestigatorDetail['equipment'][number] & { id: string })[]
  messages: GameMessage[]
  facts: GameFact[]
  suggestions: string[]
  ended: boolean
  ending: 'completed' | 'retreated' | 'failed' | null
  endingSummary: string | null
  status: 'active' | 'ended'
  pendingTurn: PendingTurn | null
  pendingAction?: { id: string; prompt: string } | null
  nearbyItems?: GameState['inventory']
}
export interface GameAction { requestId: string; text: string; expectedVersion: number; confirmationId?: string }
export interface GameEvent {
  type: string
  turnId: string
  seq: number
  stage?: string
  state?: GameState
  check?: GameCheck
  effect?: GameEffect
  message?: GameMessage
  messageId?: string
  delta?: string
  code?: string
  messageText?: string
}
