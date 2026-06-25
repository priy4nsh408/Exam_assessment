import { useState, useEffect } from 'react'
import { Header } from '../components/layout/Header'
import { X, Download, ChevronRight, AlertCircle, FileText, Trash2 } from 'lucide-react'

interface EvalResult {
  id: string
  student_name: string
  student_usn: string
  subject: string
  total_score: number
  max_total: number
  percentage: number
  questions_evaluated: number
  evaluated_at: string
}

interface FullReport {
  student_name: string
  subject: string
  total_score: number
  max_total: number
  percentage: number
  answers: any[]
  avg_ocr_confidence: number
  ocr_pages: number
}

function grade(pct: number) {
  return pct >= 90 ? 'O' : pct >= 80 ? 'A+' : pct >= 70 ? 'A' : pct >= 60 ? 'B+' : pct >= 50 ? 'B' : pct >= 40 ? 'C' : 'F'
}

function ScoreBadge({ pct }: { pct: number }) {
  const color = pct >= 70 ? 'text-emerald-600' : pct >= 40 ? 'text-amber-600' : 'text-red-500'
  return <span className={`font-bold ${color}`}>{pct}%</span>
}

function ReportModal({ result, onClose }: { result: EvalResult; onClose: () => void }) {
  const [report, setReport] = useState<FullReport | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`/api/eval/results/${result.id}`)
      .then(r => r.json())
      .then(d => setReport(d))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [result.id])

  const scoreColor = 'text-indigo-700'

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div>
            <p className="text-base font-semibold text-gray-900">{result.student_name || '(unnamed)'}</p>
            <p className="text-xs text-gray-400">{result.subject} · {new Date(result.evaluated_at).toLocaleString()}</p>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <p className={`text-2xl font-bold ${scoreColor}`}>
                {result.total_score}<span className="text-sm text-gray-400 font-normal"> / {result.max_total} marks</span>
              </p>
            </div>
            <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded-lg">
              <X className="w-5 h-5 text-gray-400" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
          {loading && <p className="text-sm text-gray-400 text-center py-8">Loading…</p>}
          {!loading && !report && <p className="text-sm text-gray-400 text-center py-8">Could not load report.</p>}
          {report?.answers?.map((ans: any) => {
            const aPct = ans.max_score > 0 ? Math.round((ans.ai_score / ans.max_score) * 100) : 0
            const aColor = aPct >= 70 ? 'text-emerald-600' : aPct >= 40 ? 'text-amber-600' : 'text-red-500'
            const typeBg: Record<string, string> = {
              theory: 'bg-indigo-50 text-indigo-700',
              numerical: 'bg-amber-50 text-amber-700',
              drawing: 'bg-emerald-50 text-emerald-700',
            }
            return (
              <div key={ans.q_number} className="border border-gray-100 rounded-lg p-3 space-y-1">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-gray-700">Q{ans.q_number}</span>
                    <span className={`badge text-[10px] ${typeBg[ans.q_type] || 'bg-gray-100 text-gray-600'}`}>{ans.q_type}</span>
                    {ans.requires_faculty_review && (
                      <span className="badge bg-violet-50 text-violet-600 text-[10px]">Faculty review</span>
                    )}
                  </div>
                  <span className={`text-sm font-bold ${aColor}`}>
                    {ans.ai_score}<span className="text-gray-400 font-normal text-xs"> marks</span>
                  </span>
                </div>
                {ans.question && <p className="text-xs text-gray-500 line-clamp-1">{ans.question}</p>}
                {ans.feedback && <p className="text-xs text-gray-400 italic line-clamp-2">{ans.feedback}</p>}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default function Students() {
  const [results, setResults] = useState<EvalResult[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<EvalResult | null>(null)
  const [search, setSearch] = useState('')

  const deleteResult = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    if (!confirm('Delete this result?')) return
    await fetch(`/api/eval/results/${id}`, { method: 'DELETE' }).catch(() => {})
    setResults(prev => prev.filter(r => r.id !== id))
  }

  useEffect(() => {
    fetch('/api/eval/results')
      .then(r => r.json())
      .then(d => setResults(d.results || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const exportCSV = () => {
    const lines = ['Student,Subject,Score,MaxScore,Percentage,Grade,Questions,Date']
    results.forEach(r => {
      lines.push(`"${r.student_name}","${r.subject}",${r.total_score},${r.max_total},${r.percentage},${grade(r.percentage)},${r.questions_evaluated},"${new Date(r.evaluated_at).toLocaleString()}"`)
    })
    const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'student_results.csv'
    a.click()
  }

  const filtered = results.filter(r =>
    !search ||
    r.student_name.toLowerCase().includes(search.toLowerCase()) ||
    r.student_usn.toLowerCase().includes(search.toLowerCase()) ||
    r.subject.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div>
      <Header title="Student Results" subtitle="All evaluated answer scripts — click any row to see question-level breakdown" />
      <div className="p-6 space-y-4 max-w-5xl">

<div className="flex items-center gap-3">
          <input
            type="text"
            placeholder="Search by name, USN, or subject…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="input-field flex-1 text-sm"
          />
          <button onClick={exportCSV} className="btn-secondary flex items-center gap-2 text-sm shrink-0">
            <Download className="w-4 h-4" /> Export CSV
          </button>
        </div>

        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Student</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Subject</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Marks</th>
                <th className="text-center px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Qs</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Date</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {loading && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-sm text-gray-400">Loading…</td></tr>
              )}
              {!loading && filtered.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center">
                    <FileText className="w-8 h-8 text-gray-200 mx-auto mb-2" />
                    <p className="text-sm text-gray-400">No evaluated scripts yet.</p>
                    <p className="text-xs text-gray-300 mt-1">Go to Evaluate Scripts to upload and grade answer scripts.</p>
                  </td>
                </tr>
              )}
              {filtered.map(r => {
                return (
                  <tr
                    key={r.id}
                    className="hover:bg-indigo-50/40 cursor-pointer transition-colors"
                    onClick={() => setSelected(r)}
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center shrink-0">
                          <span className="text-xs font-semibold text-indigo-600">
                            {(r.student_name || '?').slice(0, 2).toUpperCase()}
                          </span>
                        </div>
                        <div>
                          <p className="text-sm font-medium text-gray-800">{r.student_name || '(unnamed)'}</p>
                          {r.student_usn && <p className="text-xs text-gray-400">{r.student_usn}</p>}
                        </div>
                        </div>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">{r.subject}</td>
                    <td className="px-4 py-3 text-right font-bold text-gray-800 text-base">{r.total_score}<span className="text-xs text-gray-400 font-normal"> / {r.max_total}</span></td>
                    <td className="px-4 py-3 text-center text-gray-500">{r.questions_evaluated}</td>
                    <td className="px-4 py-3 text-right text-xs text-gray-400">{new Date(r.evaluated_at).toLocaleDateString()}</td>
                    <td className="px-4 py-3 text-center flex items-center gap-2 justify-end">
                      <ChevronRight className="w-4 h-4 text-gray-300" />
                      <button
                        onClick={e => deleteResult(e, r.id)}
                        className="p-1 hover:bg-red-50 rounded transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5 text-gray-300 hover:text-red-500" />
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {results.length > 0 && (
          <div className="card p-4 flex items-center gap-2 text-sm text-gray-500">
            <span className="font-semibold text-gray-700">{results.length}</span> script{results.length !== 1 ? 's' : ''} evaluated
          </div>
        )}
      </div>

      {selected && <ReportModal result={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
