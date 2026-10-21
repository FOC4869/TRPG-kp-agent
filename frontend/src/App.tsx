import { useEffect, useState } from 'react'
import { getHealth } from './api/health'

type Connection = 'checking' | 'online' | 'offline'

function App() {
  const [connection, setConnection] = useState<Connection>('checking')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    const timeout = window.setTimeout(() => {
      controller.abort()
      if (active) setConnection('offline')
    }, 5000)
    getHealth(controller.signal)
      .then(() => { if (active) setConnection('online') })
      .catch(() => { if (active) setConnection('offline') })
      .finally(() => window.clearTimeout(timeout))
    return () => {
      active = false
      controller.abort()
      window.clearTimeout(timeout)
    }
  }, [attempt])

  return (
    <main>
      <p className="eyebrow">TRPG AI KP</p>
      <h1>一起构建下一场冒险</h1>
      <p>前后端工程已就绪。游戏目前可通过后端 CLI 试玩，网页游戏接口正在等待接入。</p>
      <section aria-labelledby="connection-heading">
        <h2 id="connection-heading">后端连接</h2>
        <p role="status">
          {connection === 'checking' && '正在连接…'}
          {connection === 'online' && '已连接'}
          {connection === 'offline' && '暂时无法连接，请确认后端已启动。'}
        </p>
        <button
          type="button"
          disabled={connection === 'checking'}
          onClick={() => {
            setConnection('checking')
            setAttempt((value) => value + 1)
          }}
        >
          重新检查
        </button>
      </section>
    </main>
  )
}

export default App
