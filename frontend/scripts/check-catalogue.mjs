import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { installCatalogueFixture } from './catalogue-fixture.mjs'

const fixture = installCatalogueFixture()
const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
const signal = () => new AbortController().signal
try {
  const modules = await server.ssrLoadModule('/src/api/modules.ts')
  const people = await server.ssrLoadModule('/src/api/investigators.ts')
  const moduleId = 'darkness-beneath-the-hill'
  const list = await modules.listPublicModules({ page: 1, pageSize: 3, signal: signal() })
  assert.equal(list.total, 2)
  assert.equal(list.items[0].title, '雨夜来信：书房与地下档案')
  assert.equal(list.items[1].title, '岭下暗影')
  assert.equal(list.items[0].playable, true)
  assert.equal(list.items[1].playable, false)
  assert.deepEqual(await modules.getPublicModule({ id: moduleId, signal: signal() }), list.items[1])
  assert.equal(await modules.getPublicModule({ id: 'missing', signal: signal() }), null)
  const catalogue = await people.listInvestigators({ moduleId, signal: signal() })
  assert.equal(catalogue.source, 'api')
  assert.equal(catalogue.items.length, 10)
  for (const item of catalogue.items) {
    const detail = await people.getInvestigator({ moduleId, id: item.id, signal: signal() })
    assert.equal(detail.name, item.name)
    assert.match(detail.portrait.url, /\/api\/modules\/.*\/portrait$/)
  }
  const chris = await people.getInvestigator({ moduleId, id: 'chris', signal: signal() })
  assert.equal(chris.resources.hp, 10)
  assert.equal(chris.background.find((s) => s.title === '思想与信念').text, null)
  await assert.rejects(people.listInvestigators({ moduleId: 'missing', signal: signal() }), { code: 'module-unavailable' })
  await assert.rejects(people.getInvestigator({ moduleId, id: 'missing', signal: signal() }), { code: 'investigator-unavailable' })
  const cancelled = new AbortController()
  cancelled.abort()
  await assert.rejects(modules.listPublicModules({ page: 1, pageSize: 3, signal: cancelled.signal }), { name: 'AbortError' })
  await assert.rejects(people.getInvestigator({ moduleId, id: 'chris', signal: cancelled.signal }), { name: 'AbortError' })
  globalThis.fetch = async () => Response.json({ detail: 'unavailable' }, { status: 503 })
  await assert.rejects(modules.listPublicModules({ page: 1, pageSize: 3, signal: signal() }), /HTTP 503/)
  await assert.rejects(people.listInvestigators({ moduleId, signal: signal() }), /HTTP 503/)
  globalThis.fetch = async () => { throw new TypeError('offline') }
  await assert.rejects(people.getInvestigator({ moduleId, id: 'chris', signal: signal() }), /offline/)
  globalThis.fetch = async () => Response.json({ items: [] })
  await assert.rejects(modules.listPublicModules({ page: 1, pageSize: 3, signal: signal() }), /Unexpected catalogue response/)
  globalThis.fetch = async () => Response.json({ ...chris, resources: { ...chris.resources, hp: '10' } })
  await assert.rejects(people.getInvestigator({ moduleId, id: 'chris', signal: signal() }), /Unexpected catalogue response/)
  globalThis.fetch = async () => Response.json({ ...chris, id: 'wrong' })
  await assert.rejects(people.getInvestigator({ moduleId, id: 'chris', signal: signal() }), /Unexpected investigator identity/)
  globalThis.fetch = async () => Response.json({ ...chris, portrait: { url: '/data/characters/chris/character.yaml' } })
  await assert.rejects(people.getInvestigator({ moduleId, id: 'chris', signal: signal() }), /Unexpected catalogue response/)
  console.log('Catalogue adapters passed: real DTOs, ten investigators, unknowns, HTTP/identity/schema errors and cancellation; no mock fallback.')
} finally {
  fixture.restore()
  await server.close()
}
