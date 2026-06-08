import clsx from 'clsx'

const bloomConfig = {
  1: { label: 'Remember', color: 'bg-slate-100 text-slate-700' },
  2: { label: 'Understand', color: 'bg-blue-50 text-blue-700' },
  3: { label: 'Apply', color: 'bg-green-50 text-green-700' },
  4: { label: 'Analyze', color: 'bg-yellow-50 text-yellow-700' },
  5: { label: 'Evaluate', color: 'bg-orange-50 text-orange-700' },
  6: { label: 'Create', color: 'bg-purple-50 text-purple-700' },
}

export function BloomBadge({ level }: { level: number }) {
  const config = bloomConfig[level as keyof typeof bloomConfig] || bloomConfig[1]
  return (
    <span className={clsx('badge', config.color)}>
      L{level} &middot; {config.label}
    </span>
  )
}
