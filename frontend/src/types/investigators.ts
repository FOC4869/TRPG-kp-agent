/** Client-facing display projection, not a character template or game instance. */
export interface InvestigatorPortrait {
  url: string
  /** Optional atlas crop used only by preview assets; a real URL needs no crop. */
  sprite?: { column: number; row: number; columns: number; rows: number }
}

export interface InvestigatorSummary {
  playable?: boolean
  id: string
  name: string
  displayName: string
  occupation: string
  age: number | null
  portrait: InvestigatorPortrait
}

export interface InvestigatorSkill {
  name: string
  value: number | null
  highlighted?: boolean
}

export type AttributeKey = 'STR' | 'CON' | 'SIZ' | 'DEX' | 'APP' | 'INT' | 'POW' | 'EDU'

export interface InvestigatorDetail extends InvestigatorSummary {
  overview: string
  resources: {
    hp: number | null
    hpMax: number | null
    san: number | null
    mp: number | null
    mpMax: number | null
    luck: number | null
  }
  attributes: Record<AttributeKey, number | null>
  skills: InvestigatorSkill[]
  background: { title: string; text: string | null }[]
  equipment: { name: string; quantity: number | null; kind: 'carried' | 'owned'; note?: string }[]
  cash: { amount: number; currency: string } | null
}

export interface InvestigatorCatalogue {
  module: { id: string; title: string }
  items: InvestigatorSummary[]
  /** Adapter metadata. An eventual server does not need to supply this field. */
  source: 'mock' | 'api'
}
