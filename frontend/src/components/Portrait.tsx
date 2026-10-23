import { useState } from 'react'
import type { InvestigatorPortrait } from '../types/investigators'
import { DoorMark } from './Ornaments'

export function Portrait({ portrait, name, decorative = false }: {
  portrait: InvestigatorPortrait
  name: string
  decorative?: boolean
}) {
  const [failed, setFailed] = useState(false)
  const sprite = portrait.sprite
  const style = sprite ? {
    backgroundImage: `url("${portrait.url}")`,
    backgroundSize: `${sprite.columns * 100}% ${sprite.rows * 100}%`,
    backgroundPosition: `${sprite.columns > 1 ? sprite.column / (sprite.columns - 1) * 100 : 0}% ${sprite.rows > 1 ? sprite.row / (sprite.rows - 1) * 100 : 0}%`,
  } : undefined

  return (
    <span className="portrait-frame" aria-hidden={decorative || undefined}>
      <span className="portrait-fallback" aria-hidden="true"><DoorMark /></span>
      {sprite ? <span className="portrait-crop" style={style} role={decorative ? undefined : 'img'} aria-label={decorative ? undefined : `${name}的示例头像`} />
        : !failed && <img src={portrait.url} alt={decorative ? '' : `${name}的头像`} onError={() => setFailed(true)} />}
      {failed && !decorative && <span className="sr-only">{name}的头像暂不可用</span>}
    </span>
  )
}
