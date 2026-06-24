import { useState, useEffect } from 'react'
import { Header } from '../components/layout/Header'
import { X, Download, ChevronRight, AlertCircle } from 'lucide-react'

type StudentRow = {
  usn: string; name: string; section: string
  theory: number | null; numerical: number | null; drawing: number | null
  co1: number | null; co2: number | null; co3: number | null
  co4: number | null; co5: number | null; avg: number | null
}

type Submission = {
  id: string; type: string; question: string; questionId: string
  aiScore: number | null; maxScore: number | null; co: string
  confidence: number | null; isOverridden?: boolean; overriddenScore?: number
}

function ScoreCell({ value }: { value: number | null }) {
  if (value === null) return <span className="text-sm text-gray-300">—</span>
  const color = value >= 70 ? 'text-emerald-600' : value >= 50 ? 'text-amber-600' : 'text-red-600'
  return <span className={`text-sm font-semibold ${color}`}>{value}%</span>
}

function COCell({ value }: { value: number | null }) {
  if (value === null) return <span className="inline-flex w-8 h-6 items-center justify-center rounded text-xs text-gray-300">—</span>
  const cls = value >= 70 ? 'bg-emerald-50 text-emerald-700' : value >= 50 ? 'bg-amber-50 text-amber-700' : 'bg-red-50 text-red-600'
  return <div className={`inline-flex w-8 h-6 items-center justify-center rounded text-xs font-bold ${cls}`}>{value}</div>
}

function DrillDownModal({ student, onClose }: { student: StudentRow; onClose: () => void }) {
  const [submissions, setSubmissions] = useState<Submission[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`/api/submissions?student_usn=${encodeURIComponent(student.usn)}`)
      .then(r => r.json())
      .then(d => {
        const arr = d.submissions || d
        if (Array.isArray(arr)) setSubmissions(arr.filter((s: any) => s.usn === student.usn || !s.usn))
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [student.usn])

  const pct = student.avg
  const grade = pct == null ? '—' : pct >= 90 ? 'O' : pct >= 80 ? 'A+' : pct >= 70 ? 'A' : pct >= 60 ? 'B+' : pct >= 50 ? 'B' : pct >= 40 ? 'C' : 'F'

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div>
            <p className="text-base font-semibold text-gray-900">{student.name}</p>
            <p className="text-xs text-gray-400">{student.usn} · {student.section}</p>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <p className="text-xs text-gray-400">Overall</p>
              <p className={`text-xl font-bold ${(pct ?? 0) >= 70 ? 'text-emerald-600' : (pct ?? 0) >= 40 ? 'text-amber-600' : 'text-red-500'}`}>
                {pct != null ? `${pct}%` : '—'} <span className="text-base text-indigo-500">{grade}</span>
              </p>
            </div>
            <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors">
              <X className="w-5 h-5 text-gray-400" />
            </button>
          </div>
        </div>

        {/* CO summary */}
        <div className="px-6 py-3 bg-gray-50 border-b border-gray-100 grid grid-cols-5 gap-3">
          {(['co1','co2','co3','co4','co5'] as const).map(co => (
            <div key={co} className="text-center">
              <p className="text-[10px] text-gray-400 uppercase">{co.toUpperCase()}</p>
              <COCell value={student[co]} />
            </div>
          ))}
        </div>

        {/* Submissions list */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {loading && <p className="text-sm text-gray-400 text-center py-8">Loading submissions…</p>}
          {!loading && submissions.length === 0 && (
            <div className="text-center py-8">
              <AlertCircle className="w-8 h-8 text-gray-200 mx-auto mb-2" />
              <p className="text-sm text-gray-400">No individual submission data available for this student.</p>
              <p className="text-xs text-gray-300 mt-1">Aggregate scores are shown in the CO summary above.</p>
            </div>
          )}
          <div className="space-y-2">
            {submissions.map(sub => {
              const score = sub.isOverridden ? sub.overriddenScore : sub.aiScore
              const pctScore = sub.maxScore && score != null ? (score / sub.maxScore) * 100 : null
              const scoreColor = pctScore == null ? 'text-gray-400' : pctScore >= 70 ? 'text-emerald-600' : pctScore >= 40 ? 'text-amber-600' : 'text-red-500'
              const typeColor: Record<string, string> = {
                theory: 'bg-indigo-50 text-indigo-700',
                numerical: 'bg-amber-50 text-amber-700',
                drawing: 'bg-emerald-50 text-emerald-700',
              }
              return (
                <div key={sub.id} className="rounded-lg border border-gray-100 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className={`badge text-[10px] ${typeColor[sub.type] || 'bg-gray-100 text-gray-600'}`}>{sub.type}</span>
                        <span className="badge bg-indigo-50 text-indigo-600 text-[10px]">{sub.co}</span>
                        {sub.isOverridden && <span className="badge bg-violet-50 text-violet-600 text-[10px]">Overridden</span>}
                        <span className="text-[10px] text-gray-400 font-mono">{sub.id}</span>
                      </div>
                      <p className="text-xs text-gray-700 line-clamp-2">{sub.question}</p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className={`text-sm font-bold ${scoreColor}`}>
                        {score != null ? `${score}` : '—'}
                        <span className="text-gray-400 font-normal text-xs">/{sub.maxScore ?? '?'}</span>
                      </p>
                      {sub.confidence != null && (
                        <p className="text-[10px] text-gray-400">{Math.round(sub.confidence * 100)}% conf</p>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

export default function Students() {
  const [students, setStudents] = useState<StudentRow[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<StudentRow | null>(null)
  const [search, setSearch] = useState('')

  useEffect(() => {
    fetch('/api/students')
      .then(r => r.json())
      .then(data => {
        const arr = data.students || data
        if (Array.isArray(arr)) setStudents(arr)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const exportCSV = () => {
    const lines = ['USN,Name,Section,Theory%,Numerical%,Drawing%,CO1,CO2,CO3,CO4,CO5,Avg%']
    students.forEach(s => lines.push(
      `${s.usn},"${s.name}",${s.section},${s.theory ?? ''},${s.numerical ?? ''},${s.drawing ?? ''},${s.co1 ?? ''},${s.co2 ?? ''},${s.co3 ?? ''},${s.co4 ?? ''},${s.co5 ?? ''},${s.avg ?? ''}`
    ))
    const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob)
    a.download = 'student_grades.csv'; a.click()
  }

  const filtered = students.filter(s =>
    !search || s.name.toLowerCase().includes(search.toLowerCase()) || s.usn.toLowerCase().includes(search.toLowerCase())
  )

  const atRiskCount = students.filter(s => s.avg !== null && s.avg < 60).length

  return (
    <div>
      <Header title="Students" subtitle="Per-student performance across all CO/PO dimensions · click any row for details" />
      <div className="p-6 space-y-4">

        {atRiskCount > 0 && (
          <div className="card p-3 bg-red-50 border-red-200 flex items-center gap-3">
            <AlertCircle className="w-4 h-4 text-red-500 shrink-0" />
            <p className="text-xs text-red-700">
              <strong>{atRiskCount}</strong> student{atRiskCount > 1 ? 's' : ''} below 60% average — flagged at risk.
            </p>
          </div>
        )}

        <div className="flex items-center gap-3">
          <input
            type="text"
            placeholder="Search by name or USN…"
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
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Student</th>
                <th className="text-center px-3 py-3 text-xs font-semibold text-gray-500 uppercase">Theory</th>
                <th className="text-center px-3 py-3 text-xs font-semibold text-gray-500 uppercase">Numerical</th>
                <th className="text-center px-3 py-3 text-xs font-semibold text-gray-500 uppercase">Drawing</th>
                <th className="text-center px-3 py-3 text-xs font-semibold text-gray-500 uppercase">CO1</th>
                <th className="text-center px-3 py-3 text-xs font-semibold text-gray-500 uppercase">CO2</th>
                <th className="text-center px-3 py-3 text-xs font-semibold text-gray-500 uppercase">CO3</th>
                <th className="text-center px-3 py-3 text-xs font-semibold text-gray-500 uppercase">CO4</th>
                <th className="text-center px-3 py-3 text-xs font-semibold text-gray-500 uppercase">CO5</th>
                <th className="text-center px-3 py-3 text-xs font-semibold text-gray-500 uppercase">Avg</th>
                <th className="px-3 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {loading && (
                <tr><td colSpan={11} className="px-4 py-8 text-center text-sm text-gray-400">Loading…</td></tr>
              )}
              {!loading && filtered.length === 0 && (
                <tr><td colSpan={11} className="px-4 py-8 text-center text-sm text-gray-400">No students found.</td></tr>
              )}
              {filtered.map(s => {
                const atRisk = s.avg !== null && s.avg < 60
                return (
                  <tr
                    key={s.usn}
                    className={`hover:bg-indigo-50/40 cursor-pointer transition-colors ${atRisk ? 'bg-red-50/30' : ''}`}
                    onClick={() => setSelected(s)}
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center shrink-0">
                          <span className="text-xs font-semibold text-indigo-600">
                            {s.name.split(' ').map(n => n[0]).join('').slice(0, 2)}
                          </span>
                        </div>
                        <div>
                          <p className="text-sm font-medium text-gray-800">{s.name}</p>
                          <p className="text-xs text-gray-400">{s.usn} · {s.section}</p>
                        </div>
                        {atRisk && <span className="badge bg-red-50 text-red-600 text-[10px]">At Risk</span>}
                      </div>
                    </td>
                    <td className="px-3 py-3 text-center"><ScoreCell value={s.theory} /></td>
                    <td className="px-3 py-3 text-center"><ScoreCell value={s.numerical} /></td>
                    <td className="px-3 py-3 text-center"><ScoreCell value={s.drawing} /></td>
                    <td className="px-3 py-3 text-center"><COCell value={s.co1} /></td>
                    <td className="px-3 py-3 text-center"><COCell value={s.co2} /></td>
                    <td className="px-3 py-3 text-center"><COCell value={s.co3} /></td>
                    <td className="px-3 py-3 text-center"><COCell value={s.co4} /></td>
                    <td className="px-3 py-3 text-center"><COCell value={s.co5} /></td>
                    <td className="px-3 py-3 text-center">
                      {s.avg === null ? <span className="text-sm text-gray-300">—</span> : (
                        <span className={`text-sm font-bold ${s.avg >= 70 ? 'text-emerald-600' : s.avg >= 50 ? 'text-amber-600' : 'text-red-600'}`}>
                          {s.avg}%
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-3 text-center">
                      <ChevronRight className="w-4 h-4 text-gray-300" />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {selected && <DrillDownModal student={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
