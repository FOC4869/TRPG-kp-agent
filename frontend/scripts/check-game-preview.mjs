import assert from 'node:assert/strict'
import { createServer } from 'vite'

const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
try {
  const { loadGamePreview, submitGameAction } = await server.ssrLoadModule('/src/api/game.ts')
  const context = { moduleId: 'darkness-beneath-the-hill', investigatorId: 'chris' }
  const signal = () => new AbortController().signal
  const initial = await loadGamePreview(context, signal())
  assert.equal(initial.investigator.id, 'chris')
  assert.equal(initial.facts.length, 0)
  assert.equal(initial.messages.length, 2)
  initial.investigator.resources.hp = -1
  initial.messages[0].text = 'changed'
  const fresh = await loadGamePreview(context, signal())
  assert.equal(fresh.investigator.resources.hp, 10)
  assert.notEqual(fresh.messages[0].text, 'changed')
  await assert.rejects(loadGamePreview({ ...context, investigatorId: 'missing' }, signal()))
  await assert.rejects(loadGamePreview({ ...context, moduleId: 'missing' }, signal()))
  const cancelled = new AbortController()
  cancelled.abort()
  await assert.rejects(loadGamePreview(context, cancelled.signal), { name: 'AbortError' })
  const action = { requestId: 'test-1', text: '询问隧道', kind: 'action' }
  const reply = await submitGameAction(context, action, signal())
  assert.equal(reply.facts[0].id, 'tunnel')
  assert.deepEqual(await submitGameAction(context, action, signal()), reply)
  const pending = new AbortController()
  const promise = submitGameAction(context, action, pending.signal)
  setTimeout(() => pending.abort(), 30)
  await assert.rejects(promise, { name: 'AbortError' })
  await assert.rejects(submitGameAction(context, { ...action, text: ' ' }, signal()))
  await assert.rejects(submitGameAction(context, { ...action, text: 'x'.repeat(1001) }, signal()))
  const preparation = await submitGameAction(context, { ...action, text: '准备装备' }, signal())
  assert.equal(preparation.facts[0].id, 'preparations')
  assert.deepEqual((await loadGamePreview(context, signal())).investigator.equipment, fresh.investigator.equipment)
  const unknown = await submitGameAction(context, { ...action, text: '飞到月球' }, signal())
  assert.match(unknown.messages[0].text, /不能完整裁定/)
  const check = await submitGameAction(context, { ...action, kind: 'check-preview' }, signal())
  assert.equal(check.messages[0].kind, 'check')
  assert.equal(check.messages[0].check.roll, 28)
  assert.deepEqual((await loadGamePreview(context, signal())).investigator.resources, fresh.investigator.resources)
  const ending = await submitGameAction(context, { ...action, kind: 'ending-preview' }, signal())
  assert.equal(ending.ended, true)
  assert.equal(ending.messages.at(-1).kind, 'keeper')
  assert.ok(ending.messages.at(-1).text.trim())
  assert.deepEqual(ending.facts, [])
  const endingWords = await submitGameAction(context, { ...action, text: '结束调查' }, signal())
  assert.notEqual(endingWords.ended, true, 'Player text must not decide that the game ended')
  assert.notEqual((await loadGamePreview(context, signal())).ended, true, 'Preview is not persisted')
  console.log('Game preview smoke passed: context, clones, cancellation, retry, bounds, facts, fixed check and explicit ending flag.')
} finally {
  await server.close()
}
