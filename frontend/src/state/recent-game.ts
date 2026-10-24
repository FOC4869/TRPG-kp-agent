import { GameRequestError, getGame } from '../api/game'
import type { GameState } from '../types/game'

// Only a pointer belongs in the browser. The backend owns all game state.
export const RECENT_GAME_KEY = 'coc:last-active-game'
type ResumeState = Pick<GameState, 'gameId' | 'ended' | 'pendingTurn'>
export type RecentGame = { status: 'empty' } | { status: 'ready'; game: GameState } | { status: 'error'; message: string }

export function recentGameId(): string | null {
  try {
    const id = window.localStorage.getItem(RECENT_GAME_KEY)
    if (id === null || /^[a-f0-9]{32}$/.test(id)) return id
    window.localStorage.removeItem(RECENT_GAME_KEY)
  } catch { /* Browser storage may be disabled; address-based recovery still works. */ }
  return null
}

export function forgetRecentGame(gameId: string) {
  try {
    // An older game finishing in another tab must not erase a newer game's pointer.
    if (recentGameId() === gameId) window.localStorage.removeItem(RECENT_GAME_KEY)
  } catch { /* Storage failure must not interrupt gameplay. */ }
}

export function canResumeGame(game: ResumeState) {
  return !game.ended || game.pendingTurn !== null
}

export function rememberGame(game: ResumeState) {
  if (!canResumeGame(game)) { forgetRecentGame(game.gameId); return }
  if (!/^[a-f0-9]{32}$/.test(game.gameId)) return
  try { window.localStorage.setItem(RECENT_GAME_KEY, game.gameId) }
  catch { /* The game's URL remains usable without localStorage. */ }
}

export async function loadRecentGame(signal: AbortSignal): Promise<RecentGame> {
  signal.throwIfAborted()
  const id = recentGameId()
  if (!id) return { status: 'empty' }
  try {
    const game = await getGame(id, signal)
    signal.throwIfAborted()
    if (game.gameId !== id) throw new GameRequestError('invalid_response', '读取到的调查编号不匹配，请重试。')
    if (!canResumeGame(game)) { forgetRecentGame(id); return { status: 'empty' } }
    return { status: 'ready', game }
  } catch (error) {
    signal.throwIfAborted()
    if (error instanceof GameRequestError && error.status === 404 && error.code === 'game_not_found') {
      forgetRecentGame(id)
      return { status: 'empty' }
    }
    return { status: 'error', message: error instanceof GameRequestError ? error.message : '暂时无法读取调查进度，请重新检查。' }
  }
}
