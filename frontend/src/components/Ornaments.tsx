export function DoorMark({ className = 'brand-mark' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 40 52" fill="none" aria-hidden="true">
      <path d="M3 49V21a17 17 0 0 1 34 0v28M7 49V21a13 13 0 0 1 26 0v28M11 49V21a9 9 0 0 1 18 0v28M15 49V22a5 5 0 0 1 10 0v27M1 49h38M20 1v7M1 21h10M29 21h10" />
      <path d="m15 49 10-5V22M21 33v3" />
    </svg>
  )
}

export function Arrow() {
  return <svg viewBox="0 0 32 20" fill="none" aria-hidden="true"><path d="M1 10h28M21 2l8 8-8 8" /></svg>
}

export function Lock() {
  return (
    <svg viewBox="0 0 20 24" fill="none" aria-hidden="true">
      <path d="M5 10V6a5 5 0 0 1 10 0v4" /><rect x="2" y="10" width="16" height="12" rx="2" /><path d="M10 14v4" />
    </svg>
  )
}

function Corner({ className = '' }: { className?: string }) {
  return (
    <svg className={`corner ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M1 23V8l7-7h15M5 23V10l5-5h13M1 15l9-9M9 1v8H1m9 9 3 3-3 3-3-3 3-3Z" />
    </svg>
  )
}

export function FrameCorners() {
  return <><Corner /><Corner className="corner-tr" /><Corner className="corner-bl" /><Corner className="corner-br" /></>
}
