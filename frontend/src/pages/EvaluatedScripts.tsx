import { useState, useEffect } from 'react'
import { Header } from '../components/layout/Header'
import { FileText, AlertTriangle, CheckCircle2, Edit3, X, Save, Loader2, Camera, Trash2 } from 'lucide-react'

interface QuestionResult {
  question_number?: string | number
  question_text?: string
  question_type?: string
  ai_score?: number
  max_score?: number
  feedback?: string
  explanation?: string
}

interface EvalRecord {
  id: string
  student_name: string
  question: string
  subject: string
  question_type: string
  ai_score: number
  max_score: number
  confidence: number
  ocr_used: boolean
  ocr_method: string
  feedback: string
  explanation: string
  overridden: boolean
  override_score?: number
  override_reason?: string
  overridden_by?: string
  overridden_at?: string
  evaluated_at: string
  script_file?: string
  question_results?: QuestionResult[]
}

export default function EvaluatedScripts() {
  const [records, setRecords] = useState<EvalRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [overrideId, setOverrideId] = useState<string | null>(null)
  const [overrideScore, setOverrideScore] = useState(0)
  const [overrideReason, setOverrideReason] = useState('')
  const [saving, setSaving] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const fetchHistory = () => {
    setLoading(true)
    fetch('/api/eval/history')
      .then(r => r.json())
      .then(data => {
        setRecords(data.evaluations || [])
        setLoading(false)
      })
      .catch(e => {
        setError(e.message)
        setLoading(false)
      })
  }

  useEffect(() => { fetchHistory() }, [])

  const handleOverride = async (id: string) => {
    setSaving(true)
    try {
      const res = await fetch(`/api/eval/history/${id}/override`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ score: overrideScore, reason: overrideReason }),
      })
      if (res.ok) {
        setOverrideId(null)
        setOverrideScore(0)
        setOverrideReason('')
        fetchHistory()
      }
    } catch (e: any) {
      setError(e.message)
    }
    setSaving(false)
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this evaluation record?')) return
    try {
      await fetch(`/api/eval/history/${id}`, { method: 'DELETE' })
      fetchHistory()
    } catch {}
  }

  const scoreColor = (score: number, max: number) => {
    const pct = (score / max) * 100
    if (pct >= 80) return 'text-emerald-600'
    if (pct >= 50) return 'text-amber-600'
    return 'text-red-600'
  }

  const confidenceBadge = (conf: number, ocrUsed: boolean) => {
    if (!ocrUsed) return null
    if (conf >= 0.7) return <span className="px-1.5 py-0.5 text-[10px] rounded bg-emerald-50 text-emerald-700 font-medium">High</span>
    if (conf >= 0.4) return <span className="px-1.5 py-0.5 text-[10px] rounded bg-amber-50 text-amber-700 font-medium">Medium</span>
    return (
      <span className="px-1.5 py-0.5 text-[10px] rounded bg-red-50 text-red-700 font-medium flex items-center gap-1">
        <AlertTriangle className="w-3 h-3" />Low
      </span>
    )
  }

  return (
    <div>
      <Header title="Evaluated Answer Scripts" subtitle="History of all evaluations with faculty override option" />

      <div className="p-6">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
          </div>
        ) : error ? (
          <div className="text-center py-20 text-red-500 text-sm">{error}</div>
        ) : records.length === 0 ? (
          <div className="text-center py-20 text-gray-400">
            <FileText className="w-10 h-10 mx-auto mb-3 opacity-40" />
            <p className="text-sm font-medium">No evaluations yet</p>
            <p className="text-xs mt-1">Evaluate answer scripts from the <a href="/evaluate" className="text-indigo-600 hover:underline">Answer Evaluator</a></p>
          </div>
        ) : (
          <div className="space-y-3">
            {records.map(rec => (
              <div key={rec.id} className="card">
                <div className="p-4 flex items-center gap-4 cursor-pointer" onClick={() => setExpandedId(expandedId === rec.id ? null : rec.id)}>
                  {/* Score */}
                  <div className="w-20 text-center">
                    {rec.overridden ? (
                      <div>
                        <span className="text-lg font-bold text-indigo-600">{rec.override_score}</span>
                        <span className="text-gray-400 text-sm">/{rec.max_score}</span>
                        <p className="text-[10px] text-gray-400 line-through">{rec.ai_score}</p>
                      </div>
                    ) : (
                      <div>
                        <span className={`text-lg font-bold ${scoreColor(rec.ai_score, rec.max_score)}`}>{rec.ai_score}</span>
                        <span className="text-gray-400 text-sm">/{rec.max_score}</span>
                      </div>
                    )}
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-sm font-semibold text-gray-900">{rec.student_name || 'Unknown Student'}</span>
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-indigo-50 text-indigo-700">{rec.question_type}</span>
                      {rec.ocr_used && (
                        <span className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-purple-50 text-purple-700">
                          <Camera className="w-3 h-3" />OCR
                        </span>
                      )}
                      {confidenceBadge(rec.confidence, rec.ocr_used)}
                      {rec.overridden && (
                        <span className="px-1.5 py-0.5 text-[10px] rounded bg-yellow-50 text-yellow-700 font-medium flex items-center gap-1">
                          <Edit3 className="w-3 h-3" />Overridden
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-500 truncate">{rec.question}</p>
                    <p className="text-[10px] text-gray-400 mt-0.5">
                      {rec.subject} &middot; {new Date(rec.evaluated_at).toLocaleString()}
                      {rec.script_file && <> &middot; {rec.script_file}</>}
                    </p>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={e => {
                        e.stopPropagation()
                        setOverrideId(rec.id)
                        setOverrideScore(rec.overridden ? rec.override_score! : rec.ai_score)
                        setOverrideReason(rec.override_reason || '')
                      }}
                      className="px-3 py-1.5 text-xs font-medium text-indigo-600 bg-indigo-50 rounded-lg hover:bg-indigo-100 transition-colors"
                    >
                      <Edit3 className="w-3 h-3 inline mr-1" />
                      Override
                    </button>
                    <button
                      onClick={e => { e.stopPropagation(); handleDelete(rec.id) }}
                      className="p-1.5 text-gray-400 hover:text-red-500 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Expanded Details */}
                {expandedId === rec.id && (
                  <div className="px-4 pb-4 border-t border-gray-100 pt-3">
                    {rec.question_results && rec.question_results.length > 0 ? (
                      <div className="border border-gray-200 rounded-lg overflow-hidden">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="bg-gray-50/50 border-b border-gray-100">
                              <th className="text-left py-1.5 px-3 font-semibold text-gray-500">Q#</th>
                              <th className="text-left py-1.5 px-3 font-semibold text-gray-500">Question</th>
                              <th className="text-left py-1.5 px-3 font-semibold text-gray-500">Type</th>
                              <th className="text-left py-1.5 px-3 font-semibold text-gray-500">Score</th>
                              <th className="text-left py-1.5 px-3 font-semibold text-gray-500">Feedback</th>
                            </tr>
                          </thead>
                          <tbody>
                            {rec.question_results.map((qr, qi) => (
                              <tr key={qi} className="border-b border-gray-50 last:border-b-0 hover:bg-gray-50/50">
                                <td className="py-1.5 px-3 font-medium text-gray-700 align-top">Q{qr.question_number}</td>
                                <td className="py-1.5 px-3 text-gray-600 align-top w-[28%] whitespace-normal break-words">{qr.question_text}</td>
                                <td className="py-1.5 px-3 align-top">
                                  <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-indigo-50 text-indigo-700">{qr.question_type}</span>
                                </td>
                                <td className="py-1.5 px-3 align-top">
                                  <span className={`font-bold ${scoreColor(qr.ai_score || 0, qr.max_score || 1)}`}>
                                    {qr.ai_score ?? '?'}/{qr.max_score}
                                  </span>
                                </td>
                                <td className="py-1.5 px-3 text-gray-500 align-top w-[36%] whitespace-normal break-words">
                                  {qr.feedback || '—'}
                                  {qr.explanation && <span className="block text-gray-400 mt-1">{qr.explanation}</span>}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <p className="text-[10px] font-semibold text-gray-500 uppercase mb-1">Feedback</p>
                          <p className="text-xs text-gray-700 whitespace-normal break-words">{rec.feedback}</p>
                        </div>
                        <div>
                          <p className="text-[10px] font-semibold text-gray-500 uppercase mb-1">Explanation</p>
                          <p className="text-xs text-gray-600 whitespace-normal break-words">{rec.explanation}</p>
                        </div>
                      </div>
                    )}
                    {rec.overridden && (
                      <div className="mt-3 p-2 bg-yellow-50 rounded-lg text-xs">
                        <p className="text-yellow-800"><strong>Override reason:</strong> {rec.override_reason}</p>
                        <p className="text-yellow-600 text-[10px] mt-0.5">
                          By {rec.overridden_by || 'faculty'} at {rec.overridden_at ? new Date(rec.overridden_at).toLocaleString() : '—'}
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {/* Override Modal */}
                {overrideId === rec.id && (
                  <div className="px-4 pb-4 border-t border-indigo-100 pt-3 bg-indigo-50/30">
                    <p className="text-xs font-semibold text-gray-800 mb-2">Faculty Score Override</p>
                    <div className="grid grid-cols-3 gap-3">
                      <div>
                        <label className="block text-[10px] font-medium text-gray-600 mb-1">New Score</label>
                        <input
                          type="number"
                          value={overrideScore}
                          onChange={e => setOverrideScore(Number(e.target.value))}
                          min={0} max={rec.max_score}
                          className="w-full px-2 py-1.5 text-sm border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-indigo-300"
                        />
                      </div>
                      <div className="col-span-2">
                        <label className="block text-[10px] font-medium text-gray-600 mb-1">Reason for override</label>
                        <input
                          type="text"
                          value={overrideReason}
                          onChange={e => setOverrideReason(e.target.value)}
                          placeholder="e.g. OCR misread handwriting, student answer is correct"
                          className="w-full px-2 py-1.5 text-sm border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-indigo-300"
                        />
                      </div>
                    </div>
                    <div className="flex items-center gap-2 mt-3">
                      <button
                        onClick={() => handleOverride(rec.id)}
                        disabled={saving || !overrideReason.trim()}
                        className="px-3 py-1.5 text-xs font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors flex items-center gap-1"
                      >
                        {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
                        Save Override
                      </button>
                      <button
                        onClick={() => setOverrideId(null)}
                        className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                      >
                        Cancel
                      </button>
                      {rec.ocr_used && rec.confidence < 0.5 && (
                        <span className="text-[10px] text-amber-600 flex items-center gap-1 ml-2">
                          <AlertTriangle className="w-3 h-3" />
                          Low OCR confidence — manual review recommended
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
