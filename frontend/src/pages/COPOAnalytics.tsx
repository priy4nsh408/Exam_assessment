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

const trendData = [
  { week: 'W1', CO1: 60, CO2: 52, CO3: 65 },
  { week: 'W2', CO1: 65, CO2: 55, CO3: 70 },
  { week: 'W3', CO1: 70, CO2: 58, CO3: 75 },
  { week: 'W4', CO1: 75, CO2: 60, CO3: 78 },
  { week: 'W5', CO1: 78, CO2: 65, CO3: 82 },
]

const poMatrix = [
  { po: 'PO1', co1: 3, co2: 2, co3: 2, co4: 1, co5: 0 },
  { po: 'PO2', co1: 2, co2: 3, co3: 3, co4: 2, co5: 1 },
  { po: 'PO3', co1: 1, co2: 2, co3: 2, co4: 3, co5: 2 },
  { po: 'PO4', co1: 2, co2: 2, co3: 1, co4: 2, co5: 3 },
  { po: 'PO5', co1: 1, co2: 1, co3: 2, co4: 2, co5: 3 },
]

const corr: Record<number, string> = {
  3: 'bg-indigo-600 text-white',
  2: 'bg-indigo-200 text-indigo-800',
  1: 'bg-indigo-50 text-indigo-400',
  0: 'bg-gray-50 text-gray-300'
}

export default function COPOAnalytics() {
  const [coData, setCoData] = useState<CoRow[]>(EMPTY_CO_DATA)
  const [loading, setLoading] = useState(true)

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
            <h2 className="text-sm font-semibold text-gray-900 mb-1">CO Attainment Trend</h2>
            <p className="text-xs text-gray-500 mb-4">Weekly progression over assessment period</p>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="week" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} unit="%" domain={[40, 100]} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line type="monotone" dataKey="CO1" stroke="#6366f1" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="CO2" stroke="#f59e0b" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="CO3" stroke="#10b981" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* CO-PO Matrix */}
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-1">CO-PO Correlation Matrix</h2>
            <p className="text-xs text-gray-500 mb-4">3 = Strong · 2 = Moderate · 1 = Weak · 0 = None</p>
            <div className="overflow-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr>
                    <th className="text-left py-2 pr-4 text-gray-500 font-medium">PO \ CO</th>
                    {['CO1','CO2','CO3','CO4','CO5'].map(co => (
                      <th key={co} className="py-2 px-2 text-center text-gray-600 font-medium">{co}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {poMatrix.map(row => (
                    <tr key={row.po}>
                      <td className="py-1.5 pr-4 font-medium text-gray-700">{row.po}</td>
                      {[row.co1, row.co2, row.co3, row.co4, row.co5].map((v, i) => (
                        <td key={i} className="py-1.5 px-2 text-center">
                          <span className={`inline-flex w-6 h-6 items-center justify-center rounded font-bold text-[11px] ${corr[v] ?? corr[0]}`}>{v || '-'}</span>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
