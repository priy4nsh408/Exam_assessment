import { useState, useEffect } from 'react'
import { Header } from '../components/layout/Header'

type StudentRow = {
  usn: string; name: string; section: string
  theory: number | null; numerical: number | null; drawing: number | null
  co1: number | null; co2: number | null; co3: number | null; co4: number | null; co5: number | null
  avg: number | null
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

export default function Students() {
  const [students, setStudents] = useState<StudentRow[]>([])
  const [loading, setLoading] = useState(true)

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

  return (
    <div>
      <Header title="Students" subtitle="Per-student performance across all CO/PO dimensions" />
      <div className="p-6 space-y-4">
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
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {loading && (
                <tr><td colSpan={10} className="px-4 py-8 text-center text-sm text-gray-400">Loading student data…</td></tr>
              )}
              {!loading && students.length === 0 && (
                <tr><td colSpan={10} className="px-4 py-8 text-center text-sm text-gray-400">No student data yet.</td></tr>
              )}
              {students.map(s => {
                const atRisk = s.avg !== null && s.avg < 60
                return (
                  <tr key={s.usn} className={`hover:bg-gray-50 transition-colors ${atRisk ? 'bg-red-50/30' : ''}`}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center">
                          <span className="text-xs font-semibold text-indigo-600">{s.name.split(' ').map(n => n[0]).join('')}</span>
                        </div>
                        <div>
                          <p className="text-sm font-medium text-gray-800">{s.name}</p>
                          <p className="text-xs text-gray-400">{s.usn} · {s.section}</p>
                        </div>
                        {atRisk && <span className="badge bg-red-50 text-red-600">At Risk</span>}
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
                      {s.avg === null ? (
                        <span className="text-sm text-gray-300">—</span>
                      ) : (
                        <span className={`text-sm font-bold ${s.avg >= 70 ? 'text-emerald-600' : s.avg >= 50 ? 'text-amber-600' : 'text-red-600'}`}>{s.avg}%</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
