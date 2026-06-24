import { useState, useEffect } from 'react'
import { CheckCircle, XCircle, AlertTriangle } from 'lucide-react'
import { Header } from '../components/layout/Header'

// No mock fixture - pending starts empty and is populated only by a real
// /api/submissions?status=flagged response. Previously seeded with four
// hand-written fake flagged submissions (including the same Q-052/Arjun
// Sharma data shown in TheoryEvaluator.tsx) that displayed permanently
// since nothing ever cleared them if the real fetch returned an empty list.

const flagConfig: Record<string, { label: string; color: string }> = {
  low_confidence: { label: 'Low Confidence', color: 'bg-amber-50 text-amber-700 border-amber-200' },
  student_dispute: { label: 'Student Dispute', color: 'bg-red-50 text-red-700 border-red-200' },
}

export default function FacultyOverride() {
  const [pending, setPending] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [overrides, setOverrides] = useState<Record<string, { score: string; reason: string; done: boolean }>>({})

  useEffect(() => {
    fetch('/api/submissions?status=flagged')
      .then(r => r.json())
      .then(data => {
        const arr = data.submissions || data
        if (Array.isArray(arr)) setPending(arr)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const setField = (id: string, field: 'score' | 'reason', value: string) => {
    setOverrides(prev => {
      const existing = prev[id] ?? { score: '', reason: '', done: false }
      return { ...prev, [id]: { ...existing, [field]: value } }
    })
  }
  const approve = (id: string) => setOverrides(prev => ({ ...prev, [id]: { ...prev[id], score: prev[id]?.score ?? '', reason: prev[id]?.reason ?? '', done: true } }))
  const acceptAI = (id: string) => setOverrides(prev => ({ ...prev, [id]: { ...prev[id], score: prev[id]?.score ?? '', reason: 'Accepted AI score', done: true } }))

  const applyOverride = async (id: string, score: string, reason: string) => {
    try {
      await fetch(`/api/submissions/${id}/override`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ score: parseFloat(score), reason }),
      })
    } catch {}
    approve(id)
  }

  return (
    <div>
      <Header title="Faculty Override Panel" subtitle="Human-in-the-loop review for low-confidence and disputed grades" />
      <div className="p-6 space-y-4">
        <div className="card p-4 flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <AlertTriangle className="w-4 h-4 text-amber-500" />
            <span><strong>{pending.length}</strong> submissions flagged for review</span>
          </div>
          <span className="text-gray-300">|</span>
          <p className="text-xs text-gray-500">Flagged when AI confidence is below 0.80 or student raises dispute</p>
        </div>

        <div className="space-y-3">
          {loading && <p className="text-sm text-gray-400">Loading flagged submissions…</p>}
          {!loading && pending.length === 0 && (
            <div className="card p-8 text-center">
              <p className="text-sm text-gray-400">No submissions currently flagged for review.</p>
            </div>
          )}
          {pending.map(sub => {
            const ov = overrides[sub.id]
            const done = ov?.done
            const flag = flagConfig[sub.flag]
            return (
              <div key={sub.id} className={`card p-5 ${done ? 'opacity-60' : ''}`}>
                <div className="flex items-start gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <span className="text-sm font-semibold text-gray-900">{sub.student}</span>
                      <span className="text-xs text-gray-400">{sub.usn}</span>
                      <span className={`badge border text-[11px] ${flag.color}`}>{flag.label}</span>
                      <span className="badge bg-gray-100 text-gray-600">{sub.type}</span>
                      <span className="badge bg-indigo-50 text-indigo-600">{sub.co}</span>
                      {done && <span className="badge bg-emerald-50 text-emerald-600">Reviewed</span>}
                    </div>
                    <div className="flex items-center gap-6 mb-3">
                      <div>
                        <p className="text-xs text-gray-500">Question</p>
                        <p className="text-sm font-medium text-gray-700">{sub.question}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">AI Score</p>
                        <p className="text-sm font-bold text-gray-800">{sub.aiScore}/{sub.maxScore}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">AI Confidence</p>
                        <p className={`text-sm font-bold ${sub.confidence < 0.80 ? 'text-amber-600' : 'text-emerald-600'}`}>
                          {(sub.confidence * 100).toFixed(0)}%
                        </p>
                      </div>
                    </div>
                    <div className="flex items-end gap-3">
                      <div>
                        <label className="label">Override Score (/{sub.maxScore})</label>
                        <input type="number" className="input w-28" placeholder={String(sub.aiScore)} value={ov?.score ?? ''} onChange={e => setField(sub.id, 'score', e.target.value)} disabled={done} min={0} max={sub.maxScore} step={0.5} />
                      </div>
                      <div className="flex-1">
                        <label className="label">Reason</label>
                        <input type="text" className="input" placeholder="Briefly explain override..." value={ov?.reason ?? ''} onChange={e => setField(sub.id, 'reason', e.target.value)} disabled={done} />
                      </div>
                      <button
                        className="btn-primary"
                        disabled={!ov?.score || done}
                        onClick={() => applyOverride(sub.id, ov?.score ?? '', ov?.reason ?? '')}
                      >
                        <CheckCircle className="w-4 h-4" /> Apply
                      </button>
                      <button className="btn-secondary" disabled={done} onClick={() => acceptAI(sub.id)}>
                        <XCircle className="w-4 h-4" /> Accept AI
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
