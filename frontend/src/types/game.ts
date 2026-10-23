import type { InvestigatorDetail } from './investigators'

export interface GameContext { moduleId: string; investigatorId: string }
export interface GameMessage {
  id: string
  kind: 'keeper' | 'npc' | 'player' | 'check'
  speaker: string
  text: string
  check?: { skill: string; target: number; roll: number; result: string }
}
export interface GameFact { id: string; title: string; text: string }
export interface GamePreview {
  module: { id: string; title: string }
  investigator: InvestigatorDetail
  scene: { name: string; region: string; backgroundUrl: string }
  npc: { name: string; role: string; spriteUrl: string }
  messages: GameMessage[]
  facts: GameFact[]
  suggestions: string[]
  source: 'mock'
  ended?: boolean
}
export interface GameAction { requestId: string; text: string; kind: 'action' | 'check-preview' | 'ending-preview' }
export interface GameReply { messages: GameMessage[]; facts: GameFact[]; ended?: boolean }
