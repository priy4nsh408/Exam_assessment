import { useState } from 'react'
import { Search, Trash2, Download, Eye } from 'lucide-react'
import { Header } from '../components/layout/Header'
import { BloomBadge } from '../components/ui/BloomBadge'

const ALL_QUESTIONS = [
  { id: 'Q-001', text: 'State and explain the zeroth law of thermodynamics.', type: 'theory', subject: 'Thermodynamics', unit: 'Unit 1', bloom: 1, co: 'CO1', marks: 4, difficulty: 'easy' },
  { id: 'Q-002', text: 'Derive the expression for work done in an isothermal process for an ideal gas.', type: 'theory', subject: 'Thermodynamics', unit: 'Unit 1', bloom: 4, co: 'CO1', marks: 8, difficulty: 'medium' },
  { id: 'Q-003', text: 'A Carnot engine operating between 800 K and 400 K produces 150 kW. Find heat supplied.', type: 'numerical', subject: 'Thermodynamics', unit: 'Unit 2', bloom: 3, co: 'CO2', marks: 8, difficulty: 'medium' },
  { id: 'Q-004', text: 'Draw the SFD and BMD for a simply supported beam with point load at center.', type: 'drawing', subject: 'Strength of Materials', unit: 'Unit 2', bloom: 3, co: 'CO3', marks: 10, difficulty: 'medium' },
  { id: 'Q-005', text: "Explain Bernoulli's theorem and its assumptions.", type: 'theory', subject: 'Fluid Mechanics', unit: 'Unit 2', bloom: 2, co: 'CO4', marks: 6, difficulty: 'easy' },
  { id: 'Q-006', text: 'Water flows through a pipe of diameter 200mm at 3 m/s. Find Reynolds number. (mu = 0.001 Pa·s)', type: 'numerical', subject: 'Fluid Mechanics', unit: 'Unit 4', bloom: 3, co: 'CO4', marks: 6, difficulty: 'easy' },
  { id: 'Q-007', text: 'Draw the first and third angle orthographic projections of a cylinder with a hole.', type: 'drawing', subject: 'Engineering Drawing', unit: 'Unit 1', bloom: 3, co: 'CO5', marks: 15, difficulty: 'hard' },
  { id: 'Q-008', text: 'Evaluate the change in entropy when 2 kg of steam at 200 deg C condenses at constant pressure.', type: 'numerical', subject: 'Thermodynamics', unit: 'Unit 1', bloom: 5, co: 'CO1', marks: 10, difficulty: 'hard' },
]

const typeColor: Record<string, string> = {
  theory: 'bg-blue-50 text-blue-700',
  numerical: 'bg-violet-50 text-violet-700',
  drawing: 'bg-pink-50 text-pink-700',
}

export default function QuestionBank() {
  const [search, setSearch] = useState('')
  const [filterType, setFilterType] = useState('all')
  const [filterSubject, setFilterSubject] = useState('all')

  const filtered = ALL_QUESTIONS.filter(q => {
    const matchSearch = q.text.toLowerCase().includes(search.toLowerCase()) || q.id.toLowerCase().includes(search)
    const matchType = filterType === 'all' || q.type === filterType
    const matchSubject = filterSubject === 'all' || q.subject === filterSubject
    return matchSearch && matchType && matchSubject
  })

  return (
    <div>
      <Header
        title="Question Bank"
        subtitle={`${ALL_QUESTIONS.length} questions · ChromaDB + SQLite persistence`}
        actions={
          <button className="btn-secondary"><Download className="w-4 h-4" /> Export Bank</button>
        }
      />
      <div className="p-6 space-y-4">
        {/* Filters */}
        <div className="card p-4 flex items-center gap-3">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input className="input pl-9" placeholder="Search questions..." value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <select className="select w-40" value={filterType} onChange={e => setFilterType(e.target.value)}>
            <option value="all">All Types</option>
            <option value="theory">Theory</option>
            <option value="numerical">Numerical</option>
            <option value="drawing">Drawing</option>
          </select>
          <select className="select w-52" value={filterSubject} onChange={e => setFilterSubject(e.target.value)}>
            <option value="all">All Subjects</option>
            <option>Thermodynamics</option>
            <option>Strength of Materials</option>
            <option>Fluid Mechanics</option>
            <option>Engineering Drawing</option>
          </select>
          <span className="text-xs text-gray-400 ml-auto">{filtered.length} results</span>
        </div>

        {/* Table */}
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">ID</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Question</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Type</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Bloom</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">CO</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Marks</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {filtered.map(q => (
                <tr key={q.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-mono text-xs text-gray-400">{q.id}</td>
                  <td className="px-4 py-3 max-w-xs">
                    <p className="text-sm text-gray-800 line-clamp-2">{q.text}</p>
                    <p className="text-xs text-gray-400 mt-0.5">{q.subject} · {q.unit}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`badge capitalize ${typeColor[q.type]}`}>{q.type}</span>
                  </td>
                  <td className="px-4 py-3"><BloomBadge level={q.bloom} /></td>
                  <td className="px-4 py-3"><span className="badge bg-indigo-50 text-indigo-600">{q.co}</span></td>
                  <td className="px-4 py-3 text-sm font-semibold text-gray-700">{q.marks}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1 justify-end">
                      <button className="w-7 h-7 flex items-center justify-center rounded text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors">
                        <Eye className="w-3.5 h-3.5" />
                      </button>
                      <button className="w-7 h-7 flex items-center justify-center rounded text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
