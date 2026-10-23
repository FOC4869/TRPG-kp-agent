import { getInvestigator, listInvestigators } from './investigators'
import { openingScene, previewReply } from '../data/game-preview'
import type { GameAction, GameContext, GamePreview, GameReply } from '../types/game'

function previewWait(signal: AbortSignal) {
  signal.throwIfAborted()
  return new Promise<void>((resolve, reject) => {
    const cancel = () => { clearTimeout(timer); reject(signal.reason) }
    const timer = setTimeout(() => { signal.removeEventListener('abort', cancel); resolve() }, 450)
    signal.addEventListener('abort', cancel, { once: true })
  })
}

/** Replace with confirmed HTTP projection; does not create a game or load saves. */
export async function loadGamePreview(context: GameContext, signal: AbortSignal): Promise<GamePreview> {
  const catalogue = await listInvestigators({ moduleId: context.moduleId, signal })
  const investigator = await getInvestigator({ moduleId: context.moduleId, id: context.investigatorId, signal })
  signal.throwIfAborted()
  return structuredClone({ module: catalogue.module, investigator, ...openingScene, facts: [], source: 'mock' })
}

/** Fixed offline examples only. No rolls, CoC calculations, model calls or persistence. */
export async function submitGameAction(context: GameContext, action: GameAction, signal: AbortSignal): Promise<GameReply> {
  if (!action.requestId || !action.text.trim() || action.text.length > 1000) throw new Error('invalid-action')
  await getInvestigator({ moduleId: context.moduleId, id: context.investigatorId, signal })
  await previewWait(signal)
  signal.throwIfAborted()
  return structuredClone(previewReply(action))
}
