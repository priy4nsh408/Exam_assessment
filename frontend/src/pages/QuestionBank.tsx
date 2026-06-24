import { useState, useEffect, Fragment } from 'react'
import { Search, Trash2, Download, ChevronDown, ChevronUp } from 'lucide-react'
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
  const [questions, setQuestions] = useState<any[]>(ALL_QUESTIONS)
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/questions')
      .then(r => r.json())
      .then(data => {
        const qs = data.questions || data || []
        setQuestions(qs.length > 0 ? qs : ALL_QUESTIONS)
        setLoading(false)
      })
      .catch(() => { setQuestions(ALL_QUESTIONS); setLoading(false) })
  }, [])

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this question from the bank?')) return
    try {
      await fetch(`/api/questions/${id}`, { method: 'DELETE' })
      setQuestions(prev => prev.filter(q => q.id !== id))
    } catch {
      alert('Failed to delete question.')
    }
  }

  const filtered = questions.filter(q => {
    const matchSearch = q.text.toLowerCase().includes(search.toLowerCase()) || q.id.toLowerCase().includes(search)
    const matchType = filterType === 'all' || q.type === filterType
    const matchSubject = filterSubject === 'all' || q.subject === filterSubject
    return matchSearch && matchType && matchSubject
  })

  return (
    <div>
      <Header
        title="Question Bank"
        subtitle={`${questions.length} questions · ChromaDB + SQLite persistence`}
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
              {filtered.map(q => {
                const bloomLevel = q.bloomLevel ?? q.bloom
                const hasValidation = q.generationExplanation || q.answerKeyExplanation || q.answerKey
                const isExpanded = expandedId === q.id
                return (
                <Fragment key={q.id}>
                <tr className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-mono text-xs text-gray-400">{q.id}</td>
                  <td className="px-4 py-3 max-w-xs">
                    <p className="text-sm text-gray-800 line-clamp-2">{q.text}</p>
                    <p className="text-xs text-gray-400 mt-0.5">{q.subject} · {q.unit}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`badge capitalize ${typeColor[q.type]}`}>{q.type}</span>
                  </td>
                  <td className="px-4 py-3"><BloomBadge level={bloomLevel} /></td>
                  <td className="px-4 py-3"><span className="badge bg-indigo-50 text-indigo-600">{q.co}</span></td>
                  <td className="px-4 py-3 text-sm font-semibold text-gray-700">{q.marks}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1 justify-end">
                      <button
                        onClick={() => setExpandedId(isExpanded ? null : q.id)}
                        disabled={!hasValidation}
                        className={`w-7 h-7 flex items-center justify-center rounded transition-colors ${hasValidation ? 'text-gray-400 hover:text-indigo-600 hover:bg-indigo-50' : 'text-gray-200 cursor-not-allowed'}`}
                        title={hasValidation ? 'View validation & answer key' : 'No validation data for this question'}
                      >
                        {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                      </button>
                      <button onClick={() => handleDelete(q.id)} className="w-7 h-7 flex items-center justify-center rounded text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
                {isExpanded && (
                  <tr className="bg-indigo-50/40">
                    <td colSpan={7} className="px-4 py-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <p className="text-[10px] font-semibold text-indigo-700 uppercase tracking-wide mb-1">
                            Document Validation — why / where generated
                          </p>
                          <p className="text-xs text-gray-700 leading-relaxed">
                            {q.generationExplanation || 'No generation explanation recorded for this question.'}
                          </p>
                          {q.sourceChunk && (
                            <details className="mt-2">
                              <summary className="text-[11px] text-indigo-600 cursor-pointer hover:underline">View raw source chunk</summary>
                              <p className="text-[11px] text-gray-500 mt-1 bg-white rounded p-2 border border-gray-100 whitespace-pre-wrap">{q.sourceChunk}</p>
                            </details>
                          )}
                        </div>
                        <div>
                          <p className="text-[10px] font-semibold text-emerald-700 uppercase tracking-wide mb-1">
                            Answer Key
                          </p>
                          <p className="text-xs text-gray-700 leading-relaxed whitespace-pre-wrap">
                            {q.answerKey || 'No answer key generated for this question.'}
                          </p>
                          {q.answerKeyExplanation && (
                            <p className="text-[11px] text-gray-500 mt-2 italic">{q.answerKeyExplanation}</p>
                          )}
                          {q.answerId && (
                            <p className="text-[11px] text-gray-400 mt-2 font-mono">Answer ID: {q.answerId}</p>
                          )}
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
                </Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
