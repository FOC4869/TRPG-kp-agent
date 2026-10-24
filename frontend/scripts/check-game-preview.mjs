// The former mock-preview smoke now verifies the real stream adapter offline.
import assert from 'node:assert/strict'
import { createServer } from 'vite'
const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
try {
  const { readGameEvents, submitGameAction } = await server.ssrLoadModule('/src/api/game.ts')
  const encoder = new TextEncoder()
  const effect={effectId:'t:damage',resource:'hp',dice:'1D6',amount:3,before:10,after:7,reason:'大砍刀造成的伤害'}
  const events = [
    { type:'turn.started', turnId:'t', seq:1 },
    { type:'check.started', turnId:'t', seq:2, check:{checkId:'c1',skill:'侦查',target:45,reason:'寻找线索'} },
    { type:'check.resolved', turnId:'t', seq:3, check:{checkId:'c1',skill:'侦查',target:45,reason:'寻找线索',roll:28,success:true,result:'成功',details:[]} },
    { type:'message.started', turnId:'t', seq:4, message:{id:'m',kind:'keeper',speaker:'守秘人',text:''} },
    { type:'message.delta', turnId:'t', seq:5, messageId:'m',delta:'你好，调查员。' },
    { type:'turn.completed', turnId:'t', seq:6 },
  ]
  events.splice(3,0,{type:'effect.resolved',turnId:'t',seq:4,effect})
  events.forEach((event,index)=>{event.seq=index+1})
  const bytes=encoder.encode(': heartbeat\r\n\r\n'+events.map(e=>`event: ${e.type}\r\ndata: ${JSON.stringify(e)}\r\n\r\n`).join(''))
  const stream=()=>new ReadableStream({start(controller){for(let i=0;i<bytes.length;i++)controller.enqueue(bytes.slice(i,i+1));controller.close()}})
  const received=[]
  await readGameEvents(stream(),e=>received.push(e),new AbortController().signal)
  assert.deepEqual(received,events,'Chinese UTF-8 and CRLF survive one-byte splits')
  const savedFetch=globalThis.fetch
  let submitted
  globalThis.fetch=async(_url,options)=>{
    submitted=JSON.parse(options.body)
    return new Response(new ReadableStream({start(c){c.enqueue(encoder.encode([...events,events[3]].map(e=>`data: ${JSON.stringify(e)}\n\n`).join('')));c.close()}}),{headers:{'content-type':'text/event-stream'}})
  }
  const dedup=[]
  const action={requestId:'t',text:'确认执行',expectedVersion:1,confirmationId:'original-action'}
  await submitGameAction('a'.repeat(32),action,new AbortController().signal,e=>dedup.push(e))
  assert.deepEqual(submitted,action,'confirmation identity survives POST and retry')
  assert.equal(dedup.length,7)
  assert.equal(dedup.filter(e=>e.type==='effect.resolved').length,1)
  const invalid=encoder.encode(`data: ${JSON.stringify({type:'effect.resolved',turnId:'t',seq:1,effect:{...effect,after:20}})}\n\n`)
  await assert.rejects(readGameEvents(new ReadableStream({start(c){c.enqueue(invalid);c.close()}}),()=>{},new AbortController().signal),/伤害结果/)
  globalThis.fetch=async()=>new Response('data: {"type":"message.delta","turnId":"t","seq":1,"messageId":"m","delta":"中"}\n\n',{headers:{'content-type':'text/event-stream'}})
  await assert.rejects(submitGameAction('a'.repeat(32),{},new AbortController().signal,()=>{}),/中断/)
  globalThis.fetch=savedFetch
  const aborted=new AbortController();aborted.abort()
  await assert.rejects(readGameEvents(stream(),()=>{},aborted.signal),{name:'AbortError'})
  console.log('Game SSE checks passed: byte splits, UTF-8, CRLF, heartbeat, checks/effects, confirmation payload, duplicates, invalid effects, premature EOF and abort.')
} finally {await server.close()}
