import { useState, useEffect, useCallback } from 'react'
import { Header } from '../components/layout/Header'
import { CheckCircle, AlertCircle, BarChart3, ChevronDown, ChevronRight, Trash2 } from 'lucide-react'

interface KappaData {
  kappa: number | null
  p_observed: number
  p_expected: number
  n_pairs: number
  n_agreement: number
  interpretation: string
  target: string
  target_met: boolean
  theory_accuracy: number | null
  numerical_accuracy: number | null
  drawing_accuracy: number | null
  pairs: any[]
  note: string
}

interface QuestionEntry {
  q_number: number
  q_type: string
  question: string
  ai_score: number
  max_score: number
  already_scored: boolean
}

interface SubmissionEntry {
  id: string
  student_name: string
  student_usn: string
  subject: string
  total_score: number
  max_total: number
  percentage: number
  evaluated_at: string
  answers: QuestionEntry[]
}

export default function ValidationMetrics() {
  const [data, setData]           = useState<KappaData | null>(null)
  const [subs, setSubs]           = useState<SubmissionEntry[]>([])
  const [loading, setLoading]     = useState(true)
  const [subsLoading, setSubsLoading] = useState(true)
  const [expanded, setExpanded]   = useState<string | null>(null)
  const [scores, setScores]       = useState<Record<string, string>>({})   // key: `${resultId}_${qNum}`
  const [saving, setSaving]       = useState<string | null>(null)

  const loadKappa = useCallback(() => {
    fetch('/api/eval/validate/kappa')
      .then(r => r.json())
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const loadSubs = useCallback(() => {
    setSubsLoading(true)
    fetch('/api/eval/validate/kappa/submissions')
      .then(r => r.json())
      .then(d => setSubs(d.submissions || []))
      .catch(() => {})
      .finally(() => setSubsLoading(false))
  }, [])

  useEffect(() => { loadKappa(); loadSubs() }, [loadKappa, loadSubs])

  const submitScore = async (resultId: string, qNum: number) => {
    const key = `${resultId}_${qNum}`
    const val = parseFloat(scores[key] ?? '')
    if (isNaN(val)) return
    setSaving(key)
    try {
      const r = await fetch('/api/eval/validate/kappa/score', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ result_id: resultId, q_number: qNum, faculty_score: val }),
      })
      if (!r.ok) { const e = await r.json(); alert(e.detail); return }
      setScores(s => { const n = { ...s }; delete n[key]; return n })
      loadKappa()
      loadSubs()
    } finally {
      setSaving(null)
    }
  }

  const deleteScore = async (resultId: string, qNum: number) => {
    // find the kappa pair id from data.pairs
    const pair = data?.pairs?.find(p => p.result_id === resultId && p.q_number === qNum)
    if (!pair?.id) return
    await fetch(`/api/eval/validate/kappa/score/${pair.id}`, { method: 'DELETE' })
    loadKappa(); loadSubs()
  }

  const scoredCount = subs.reduce((s, sub) => s + sub.answers.filter(a => a.already_scored).length, 0)

  return (
    <div>
      <Header
        title="Validation Metrics"
        subtitle="Cohen's Kappa inter-rater agreement · AI vs Faculty scores · Target κ ≥ 0.75"
      />
      <div className="p-6 space-y-6 max-w-5xl">

        {/* ── Kappa summary ─────────────────────────────────────── */}
        {loading
          ? <div className="card p-8 flex items-center justify-center gap-3">
              <div className="w-5 h-5 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
              <p className="text-sm text-gray-500">Computing Kappa…</p>
            </div>
          : data && data.n_pairs === 0
          ? <div className="card p-6 bg-indigo-50 border-indigo-200">
              <p className="text-sm font-semibold text-indigo-800 mb-1">No faculty scores yet</p>
              <p className="text-xs text-indigo-600">
                Enter your own scores for AI-evaluated questions below. Once you have at least 2 questions scored,
                Kappa will be computed automatically.
              </p>
            </div>
          : data && (
            <>
              <div className="grid grid-cols-4 gap-4">
                <div className={`card p-5 col-span-1 ${data.target_met ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'}`}>
                  <p className="text-xs font-medium text-gray-600 mb-1">Cohen's κ</p>
                  <p className={`text-4xl font-bold ${data.target_met ? 'text-emerald-600' : 'text-amber-600'}`}>
                    {data.kappa ?? '—'}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">{data.target} · {data.target_met ? 'Target met ✓' : 'Below target'}</p>
                </div>
                <div className="card p-5">
                  <p className="text-xs font-medium text-gray-600 mb-1">Observed Agreement</p>
                  <p className="text-2xl font-bold text-gray-800">{data.p_observed != null ? `${(data.p_observed * 100).toFixed(1)}%` : '—'}</p>
                  <p className="text-xs text-gray-400">{data.n_agreement}/{data.n_pairs} questions agreed</p>
                </div>
                <div className="card p-5">
                  <p className="text-xs font-medium text-gray-600 mb-1">Theory</p>
                  <p className="text-2xl font-bold text-indigo-600">
                    {data.theory_accuracy != null ? `${(data.theory_accuracy * 100).toFixed(0)}%` : '—'}
                  </p>
                  <p className="text-xs text-gray-400">bucket agreement</p>
                </div>
                <div className="card p-5">
                  <p className="text-xs font-medium text-gray-600 mb-1">Numerical</p>
                  <p className="text-2xl font-bold text-indigo-600">
                    {data.numerical_accuracy != null ? `${(data.numerical_accuracy * 100).toFixed(0)}%` : '—'}
                  </p>
                  <p className="text-xs text-gray-400">bucket agreement</p>
                </div>
              </div>

              <div className={`card p-4 flex items-start gap-3 ${data.target_met ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'}`}>
                {data.target_met
                  ? <CheckCircle className="w-5 h-5 text-emerald-600 mt-0.5 flex-shrink-0" />
                  : <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />}
                <div>
                  <p className={`text-sm font-semibold ${data.target_met ? 'text-emerald-800' : 'text-amber-800'}`}>
                    {data.interpretation}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">{data.note}</p>
                </div>
              </div>

              {data.pairs?.length > 0 && (
                <div className="card p-5">
                  <h3 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-indigo-500" />
                    Per-Question Comparison (AI vs Faculty)
                  </h3>
                  <div className="overflow-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-gray-100">
                          <th className="text-left py-2 pr-3 font-medium text-gray-500">Student</th>
                          <th className="text-center py-2 pr-3 font-medium text-gray-500">Q</th>
                          <th className="text-left py-2 pr-3 font-medium text-gray-500">Type</th>
                          <th className="text-right py-2 pr-3 font-medium text-gray-500">AI</th>
                          <th className="text-right py-2 pr-3 font-medium text-gray-500">Faculty</th>
                          <th className="text-left py-2 pr-3 font-medium text-gray-500">AI Bucket</th>
                          <th className="text-left py-2 pr-3 font-medium text-gray-500">Faculty Bucket</th>
                          <th className="text-center py-2 pr-3 font-medium text-gray-500">Agree</th>
                          <th className="py-2"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.pairs.map((p: any, i: number) => {
                          const sub = subs.find(s => s.id === p.result_id)
                          return (
                            <tr key={i} className="border-b border-gray-50">
                              <td className="py-2 pr-3 text-gray-600">{sub?.student_name || p.result_id.slice(0, 8)}</td>
                              <td className="py-2 pr-3 text-center font-medium text-gray-700">Q{p.q_number}</td>
                              <td className="py-2 pr-3 capitalize text-gray-500">{p.q_type}</td>
                              <td className="py-2 pr-3 text-right font-medium text-gray-800">{p.ai_score}/{p.max_score}</td>
                              <td className="py-2 pr-3 text-right font-medium text-gray-800">{p.faculty_score}/{p.max_score}</td>
                              <td className="py-2 pr-3">
                                <span className={`badge text-[10px] ${p.ai_bucket.startsWith('High') ? 'bg-emerald-50 text-emerald-700' : p.ai_bucket.startsWith('Low') ? 'bg-red-50 text-red-600' : 'bg-amber-50 text-amber-700'}`}>
                                  {p.ai_bucket}
                                </span>
                              </td>
                              <td className="py-2 pr-3">
                                <span className={`badge text-[10px] ${p.faculty_bucket.startsWith('High') ? 'bg-emerald-50 text-emerald-700' : p.faculty_bucket.startsWith('Low') ? 'bg-red-50 text-red-600' : 'bg-amber-50 text-amber-700'}`}>
                                  {p.faculty_bucket}
                                </span>
                              </td>
                              <td className="py-2 pr-3 text-center">
                                {p.agreement ? <span className="text-emerald-600 font-bold">✓</span> : <span className="text-red-500 font-bold">✗</span>}
                              </td>
                              <td className="py-2">
                                <button onClick={() => deleteScore(p.result_id, p.q_number)} className="p-1 hover:bg-red-50 rounded">
                                  <Trash2 className="w-3 h-3 text-gray-300 hover:text-red-500" />
                                </button>
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )
        }

        {/* ── Faculty scoring panel ─────────────────────────────── */}
        <div className="card p-5 space-y-4">
          <div>
            <p className="text-sm font-semibold text-gray-800">Enter Faculty Scores</p>
            <p className="text-xs text-gray-400 mt-0.5">
              Grade the same questions yourself — Kappa updates automatically.
              {scoredCount > 0 && <span className="text-indigo-600 ml-1">{scoredCount} question{scoredCount > 1 ? 's' : ''} scored so far.</span>}
            </p>
          </div>

          {subsLoading && <p className="text-sm text-gray-400 py-4 text-center">Loading…</p>}
          {!subsLoading && subs.length === 0 && (
            <p className="text-xs text-gray-400 py-4 text-center">No evaluated scripts yet — evaluate some scripts first.</p>
          )}

          <div className="space-y-2">
            {subs.map(sub => {
              const isOpen = expanded === sub.id
              const scored = sub.answers.filter(a => a.already_scored).length
              return (
                <div key={sub.id} className="border border-gray-100 rounded-lg overflow-hidden">
                  <button
                    className="w-full flex items-center justify-between gap-3 p-3 hover:bg-gray-50 text-left"
                    onClick={() => setExpanded(isOpen ? null : sub.id)}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      {isOpen ? <ChevronDown className="w-4 h-4 text-gray-400 shrink-0" /> : <ChevronRight className="w-4 h-4 text-gray-400 shrink-0" />}
                      <div>
                        <p className="text-sm font-medium text-gray-800">{sub.student_name || '(unnamed)'}</p>
                        <p className="text-xs text-gray-400">{sub.subject} · {sub.answers.length} questions · {new Date(sub.evaluated_at).toLocaleDateString()}</p>
                      </div>
                    </div>
                    <span className="text-xs text-gray-400 shrink-0">
                      {scored}/{sub.answers.length} scored
                    </span>
                  </button>

                  {isOpen && (
                    <div className="border-t border-gray-100 px-4 py-3 space-y-2 bg-gray-50">
                      {sub.answers.map(ans => {
                        const key = `${sub.id}_${ans.q_number}`
                        return (
                          <div key={ans.q_number} className="bg-white rounded-lg border border-gray-100 p-3">
                            <div className="flex items-start justify-between gap-4">
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-2 mb-1">
                                  <span className="text-xs font-semibold text-gray-700">Q{ans.q_number}</span>
                                  <span className="badge bg-indigo-50 text-indigo-600 text-[10px]">{ans.q_type}</span>
                                  {ans.already_scored && <span className="badge bg-emerald-50 text-emerald-600 text-[10px]">Scored ✓</span>}
                                </div>
                                {ans.question && (
                                  <p className="text-xs text-gray-500 line-clamp-2">{ans.question}</p>
                                )}
                                <p className="text-xs text-indigo-600 mt-1">
                                  AI gave: <strong>{ans.ai_score}/{ans.max_score}</strong>
                                </p>
                              </div>
                              <div className="flex items-center gap-2 shrink-0">
                                <div>
                                  <p className="text-[10px] text-gray-400 mb-1">Your score (0–{ans.max_score})</p>
                                  <input
                                    type="number"
                                    min={0}
                                    max={ans.max_score}
                                    step={0.5}
                                    className="input-field w-20 text-sm text-center"
                                    placeholder={`/${ans.max_score}`}
                                    value={scores[key] ?? ''}
                                    onChange={e => setScores(s => ({ ...s, [key]: e.target.value }))}
                                    onKeyDown={e => e.key === 'Enter' && submitScore(sub.id, ans.q_number)}
                                  />
                                </div>
                                <button
                                  onClick={() => submitScore(sub.id, ans.q_number)}
                                  disabled={!scores[key] || saving === key}
                                  className="btn-primary text-xs py-1.5 px-3 mt-4 disabled:opacity-40"
                                >
                                  {saving === key ? '…' : ans.already_scored ? 'Update' : 'Save'}
                                </button>
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* ── Methodology note ──────────────────────────────────── */}
        <div className="card p-4 bg-gray-50">
          <p className="text-xs font-medium text-gray-500 mb-1">Methodology</p>
          <p className="text-xs text-gray-500">
            Scores are bucketed into three ordinal levels — Low (0–30%), Mid (31–60%), High (61–100%) of max marks —
            before Kappa is computed, following standard practice for continuous grading scales.
            Cohen's κ = (P_o − P_e) / (1 − P_e) where P_o is the fraction of pairs where AI and faculty agree on
            the bucket, and P_e is expected agreement by chance. Landis & Koch (1977): κ ≥ 0.80 = almost perfect,
            κ ≥ 0.75 = substantial (project target), κ ≥ 0.60 = moderate, κ ≥ 0.40 = fair.
          </p>
        </div>

      </div>
    </div>
  )
}
