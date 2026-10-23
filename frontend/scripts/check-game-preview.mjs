// The former mock-preview smoke now verifies the real stream adapter offline.
import assert from 'node:assert/strict'
import { createServer } from 'vite'
const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
try {
  const { readGameEvents, submitGameAction } = await server.ssrLoadModule('/src/api/game.ts')
  const encoder = new TextEncoder()
  const events = [
    { type:'turn.started', turnId:'t', seq:1 },
    { type:'check.started', turnId:'t', seq:2, check:{checkId:'c1',skill:'侦查',target:45,reason:'寻找线索'} },
    { type:'check.resolved', turnId:'t', seq:3, check:{checkId:'c1',skill:'侦查',target:45,reason:'寻找线索',roll:28,success:true,result:'成功',details:[]} },
    { type:'message.started', turnId:'t', seq:4, message:{id:'m',kind:'keeper',speaker:'守秘人',text:''} },
    { type:'message.delta', turnId:'t', seq:5, messageId:'m',delta:'你好，调查员。' },
    { type:'turn.completed', turnId:'t', seq:6 },
  ]
  const bytes=encoder.encode(': heartbeat\r\n\r\n'+events.map(e=>`event: ${e.type}\r\ndata: ${JSON.stringify(e)}\r\n\r\n`).join(''))
  const stream=()=>new ReadableStream({start(controller){for(let i=0;i<bytes.length;i++)controller.enqueue(bytes.slice(i,i+1));controller.close()}})
  const received=[]
  await readGameEvents(stream(),e=>received.push(e),new AbortController().signal)
  assert.deepEqual(received,events,'Chinese UTF-8 and CRLF survive one-byte splits')
  const savedFetch=globalThis.fetch
  globalThis.fetch=async()=>new Response(new ReadableStream({start(c){c.enqueue(encoder.encode([...events,events[4]].map(e=>`data: ${JSON.stringify(e)}\n\n`).join('')));c.close()}}),{headers:{'content-type':'text/event-stream'}})
  const dedup=[]
  await submitGameAction('a'.repeat(32),{requestId:'t',text:'行动',expectedVersion:1},new AbortController().signal,e=>dedup.push(e))
  assert.equal(dedup.length,6)
  globalThis.fetch=async()=>new Response('data: {"type":"message.delta","turnId":"t","seq":1,"messageId":"m","delta":"中"}\n\n',{headers:{'content-type':'text/event-stream'}})
  await assert.rejects(submitGameAction('a'.repeat(32),{},new AbortController().signal,()=>{}),/中断/)
  globalThis.fetch=savedFetch
  const aborted=new AbortController();aborted.abort()
  await assert.rejects(readGameEvents(stream(),()=>{},aborted.signal),{name:'AbortError'})
  console.log('Game SSE checks passed: byte splits, UTF-8, CRLF, heartbeat, duplicate events, premature EOF and abort.')
} finally {await server.close()}
