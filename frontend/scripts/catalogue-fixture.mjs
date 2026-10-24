// Test-only HTTP transport built from the same real, public backend projections.
// No fallback from this file is imported by the product.
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

export function installCatalogueFixture() {
  const backend = fileURLToPath(new URL('../../backend/', import.meta.url))
  const python = process.env.PYTHON ?? fileURLToPath(new URL(process.platform === 'win32' ? '../../backend/.venv/Scripts/python.exe' : '../../backend/.venv/bin/python', import.meta.url))
  const code = `import json
from app.services.catalogue import Catalogue
c=Catalogue()
r={}
p=c.modules(1,3)
r['/api/modules?page=1&page_size=3']=p.model_dump()
for m in p.items:
 base='/api/modules/'+m.id
 r[base]=m.model_dump()
 people=c.investigators(m.id)
 r[base+'/investigators']=people.model_dump()
 for i in people.items:
  r[base+'/investigators/'+i.id]=c.investigator(m.id,i.id).model_dump()
print(json.dumps(r))`
  const fixtures = JSON.parse(execFileSync(python, ['-c', code], { cwd: backend, encoding: 'utf8' }))
  const original = globalThis.fetch
  const fetch = async (url, options = {}) => {
    options.signal?.throwIfAborted()
    const payload = fixtures[String(url)]
    return Response.json(payload ?? { detail: 'Catalogue entry not found' }, { status: payload ? 200 : 404 })
  }
  globalThis.fetch = fetch
  return { fixtures, fetch, restore: () => { globalThis.fetch = original } }
}
