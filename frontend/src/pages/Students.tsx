import { Header } from '../components/layout/Header'

const STUDENTS = [
  { usn: '1RV23ME001', name: 'Arjun Sharma', section: 'ME-A', theory: 82, numerical: 75, drawing: 68, avg: 75, co1: 78, co2: 72, co3: 80, co4: 65, co5: 70 },
  { usn: '1RV23ME002', name: 'Priya Nair', section: 'ME-A', theory: 91, numerical: 88, drawing: 79, avg: 86, co1: 90, co2: 85, co3: 88, co4: 82, co5: 79 },
  { usn: '1RV23ME003', name: 'Rohan Das', section: 'ME-A', theory: 45, numerical: 52, drawing: 60, avg: 52, co1: 42, co2: 50, co3: 55, co4: 58, co5: 62 },
  { usn: '1RV23ME004', name: 'Kavitha Rao', section: 'ME-B', theory: 72, numerical: 48, drawing: 75, avg: 65, co1: 70, co2: 45, co3: 72, co4: 68, co5: 78 },
  { usn: '1RV23ME005', name: 'Suresh M', section: 'ME-B', theory: 65, numerical: 71, drawing: 82, avg: 73, co1: 65, co2: 70, co3: 75, co4: 72, co5: 84 },
]

function ScoreCell({ value }: { value: number }) {
  const color = value >= 70 ? 'text-emerald-600' : value >= 50 ? 'text-amber-600' : 'text-red-600'
  return <span className={`text-sm font-semibold ${color}`}>{value}%</span>
}

function COCell({ value }: { value: number }) {
  const cls = value >= 70 ? 'bg-emerald-50 text-emerald-700' : value >= 50 ? 'bg-amber-50 text-amber-700' : 'bg-red-50 text-red-600'
  return <div className={`inline-flex w-8 h-6 items-center justify-center rounded text-xs font-bold ${cls}`}>{value}</div>
}

export default function Students() {
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
              {STUDENTS.map(s => {
                const atRisk = s.avg < 60
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
                      <span className={`text-sm font-bold ${s.avg >= 70 ? 'text-emerald-600' : s.avg >= 50 ? 'text-amber-600' : 'text-red-600'}`}>{s.avg}%</span>
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
