import { useEffect, useState } from 'react'
import type { GameCheck } from '../types/game'

export function GameCheckCard({ check }: { check: GameCheck }) {
  const rolling = check.display === 'rolling'
  const [digit, setDigit] = useState(1)
  useEffect(() => {
    if (!rolling || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const timer = window.setInterval(() => setDigit((value) => (value + 17) % 100 + 1), 65)
    return () => window.clearInterval(timer)
  }, [rolling])
  return <div className={`game-check check-${rolling ? 'rolling' : check.display === 'error' ? 'error' : check.success ? 'success' : 'failure'}`}>
    <div className="check-heading"><strong>{check.skill === 'DEX' ? '敏捷' : check.skill === 'EDU' ? '教育' : check.skill === 'STR' ? '力量' : check.skill === 'SAN' ? '理智' : check.skill}检定</strong><span>D100</span></div>
    <p className="check-reason">{check.reason}</p>
    <div className="check-result" aria-hidden={rolling}><span>目标值 <b>{check.target}</b></span><span>出目 <b>{rolling ? digit.toString().padStart(2, '0') : check.roll ?? '—'}</b></span><em>{rolling ? '掷骰中…' : check.display === 'error' ? '等待恢复' : check.success ? '✓ 成功' : '× 失败'}</em></div>
    {check.details?.map((detail, index) => <p className="check-detail" key={index}>{detail.resource.toUpperCase()} 损失 {detail.dice}＝{detail.amount}</p>)}
    <span className="sr-only" role="status">{rolling ? '' : check.display === 'error' ? '检定尚未确认，请恢复本轮。' : `${check.skill}检定，目标值${check.target}，出目${check.roll}，${check.result}。`}</span>
  </div>
}
