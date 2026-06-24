import { useState, useEffect } from 'react'
import { Header } from '../components/layout/Header'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  LineChart, Line, Legend, Cell
} from 'recharts'

type CoRow = {
  co: string; description: string
  attainment: number | null; target: number
  students: number | null; total: number | null
}

const EMPTY_CO_DATA: CoRow[] = []

const corr: Record<number, string> = {
  3: 'bg-indigo-600 text-white',
  2: 'bg-indigo-200 text-indigo-800',
  1: 'bg-indigo-50 text-indigo-400',
  0: 'bg-gray-50 text-gray-300'
}

const TREND_LINE_COLORS = ['#6366f1', '#f59e0b', '#10b981', '#ec4899', '#0ea5e9']

export default function COPOAnalytics() {
  const [coData, setCoData] = useState<CoRow[]>(EMPTY_CO_DATA)
  const [loading, setLoading] = useState(true)
  const [trend, setTrend] = useState<any[]>([])
  const [trendCos, setTrendCos] = useState<string[]>([])
  const [matrix, setMatrix] = useState<any[]>([])
  const [matrixCos, setMatrixCos] = useState<string[]>(['CO1', 'CO2', 'CO3', 'CO4', 'CO5'])
  const [matrixHasData, setMatrixHasData] = useState(false)

  useEffect(() => {
    fetch('/api/analytics/co')
      .then(r => r.json())
      .then(data => {
        const arr = data.co_analytics || data.co_data
        if (arr && Array.isArray(arr)) {
          setCoData(arr.map((c: any) => ({
            co: c.co,
            description: c.description,
            attainment: c.averageAttainment ?? (typeof c.attainment === 'number' ? c.attainment : null),
            target: c.target ?? 70,
            students: c.studentsAchieved ?? (typeof c.students === 'number' ? c.students : null),
            total: c.totalStudents ?? (typeof c.total === 'number' ? c.total : null),
          })))
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))

    fetch('/api/analytics/co-trend')
      .then(r => r.json())
      .then(d => { setTrend(d.trend || []); setTrendCos(d.cos || []) })
      .catch(() => {})

    fetch('/api/analytics/co-po-correlation')
      .then(r => r.json())
      .then(d => { setMatrix(d.matrix || []); setMatrixCos(d.cos || matrixCos); setMatrixHasData(!!d.hasData) })
      .catch(() => {})
  }, [])

  const computedCoData = coData.filter(c => c.attainment !== null)
  const radarData = computedCoData.map(c => ({ co: c.co, value: c.attainment, fullMark: 100 }))

  return (
    <div>
      <Header title="CO/PO Analytics" subtitle="Course Outcome attainment analysis and Program Outcome mapping" />
      <div className="p-6 space-y-6">
        {!loading && computedCoData.length === 0 && (
          <div className="card p-4 bg-amber-50 border-amber-200 text-xs text-amber-700">
            No CO attainment data available yet — this fills in once submissions have been graded.
          </div>
        )}
        {/* CO Summary Cards */}
        <div className="grid grid-cols-5 gap-3">
          {coData.map(co => (
            <div key={co.co} className="card p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-gray-700">{co.co}</span>
                <span className={`text-xs font-bold ${co.attainment === null ? 'text-gray-400' : co.attainment >= co.target ? 'text-emerald-600' : 'text-red-500'}`}>
                  {co.attainment === null ? '—' : `${co.attainment}%`}
                </span>
              </div>
              <div className="h-1.5 bg-gray-100 rounded-full mb-2 overflow-hidden">
                <div className={`h-full rounded-full ${co.attainment === null ? 'bg-gray-200' : co.attainment >= co.target ? 'bg-emerald-500' : 'bg-amber-400'}`} style={{ width: `${co.attainment ?? 0}%` }} />
              </div>
              <p className="text-[10px] text-gray-400 leading-tight">{co.description}</p>
              <p className="text-[10px] text-gray-500 mt-1">
                {co.students === null || co.total === null ? 'No data yet' : `${co.students}/${co.total} students achieved`}
              </p>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-3 gap-4">
          {/* Bar chart */}
          <div className="card p-5 col-span-2">
            <h2 className="text-sm font-semibold text-gray-900 mb-1">CO Attainment vs Target</h2>
            <p className="text-xs text-gray-500 mb-4">Percentage of students meeting the 70% threshold per CO</p>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={computedCoData} barCategoryGap="30%">
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="co" tick={{ fontSize: 12 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} domain={[0, 100]} unit="%" />
                <Tooltip formatter={(v: number) => `${v}%`} contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="attainment" name="Attainment" radius={[4, 4, 0, 0]}>
                  {computedCoData.map((entry, index) => (
                    <Cell key={index} fill={(entry.attainment ?? 0) >= entry.target ? '#10b981' : '#f59e0b'} />
                  ))}
                </Bar>
                <Bar dataKey="target" name="Target (70%)" fill="#e2e8f0" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Radar */}
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-4">CO Radar</h2>
            <ResponsiveContainer width="100%" height={220}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="#e2e8f0" />
                <PolarAngleAxis dataKey="co" tick={{ fontSize: 11 }} />
                <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 9 }} />
                <Radar name="Attainment" dataKey="value" stroke="#6366f1" fill="#6366f1" fillOpacity={0.2} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Trend + PO Matrix */}
        <div className="grid grid-cols-2 gap-4">
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-1">CO Coverage by Published Exam</h2>
            <p className="text-xs text-gray-500 mb-4">
              Share of each exam's total marks per CO, in publish order — not a performance trend
              (no per-exam student results exist yet, only coverage of what's been published).
            </p>
            {trend.length === 0 ? (
              <div className="h-[200px] flex items-center justify-center">
                <p className="text-xs text-gray-400">No exams published yet.</p>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={trend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} unit="%" domain={[0, 100]} />
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  {trendCos.map((co, i) => (
                    <Line key={co} type="monotone" dataKey={co} stroke={TREND_LINE_COLORS[i % TREND_LINE_COLORS.length]} strokeWidth={2} dot={{ r: 3 }} connectNulls />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* CO-PO Matrix */}
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-1">CO-PO Correlation Matrix</h2>
            <p className="text-xs text-gray-500 mb-4">
              3 = Strong (≥30% of published marks) · 2 = Moderate (≥15%) · 1 = Weak (&gt;0%) · 0 = None
            </p>
            {!matrixHasData ? (
              <p className="text-xs text-gray-400 py-8 text-center">No exams published yet — this fills in once questions are published into an exam paper.</p>
            ) : (
            <div className="overflow-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr>
                    <th className="text-left py-2 pr-4 text-gray-500 font-medium">PO \ CO</th>
                    {matrixCos.map(co => (
                      <th key={co} className="py-2 px-2 text-center text-gray-600 font-medium">{co}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {matrix.map(row => (
                    <tr key={row.po}>
                      <td className="py-1.5 pr-4 font-medium text-gray-700">{row.po}</td>
                      {matrixCos.map((co) => (
                        <td key={co} className="py-1.5 px-2 text-center">
                          <span className={`inline-flex w-6 h-6 items-center justify-center rounded font-bold text-[11px] ${corr[row[co]] ?? corr[0]}`}>{row[co] || '-'}</span>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
