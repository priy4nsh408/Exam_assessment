import { useState } from 'react'
import { Sparkles, Download, Send, CheckCircle } from 'lucide-react'
import { Header } from '../components/layout/Header'
import { BloomBadge } from '../components/ui/BloomBadge'

const SUBJECTS = ['Thermodynamics', 'Strength of Materials', 'Fluid Mechanics', 'Engineering Drawing']
const UNITS: Record<string, string[]> = {
  'Thermodynamics': ['Unit 1: Laws of Thermodynamics', 'Unit 2: Power Cycles', 'Unit 3: Refrigeration', 'Unit 4: Psychrometrics'],
  'Strength of Materials': ['Unit 1: Stress & Strain', 'Unit 2: Bending', 'Unit 3: Torsion', 'Unit 4: Columns'],
  'Fluid Mechanics': ['Unit 1: Fluid Properties', 'Unit 2: Bernoulli', 'Unit 3: Pipe Flow', 'Unit 4: Boundary Layer'],
  'Engineering Drawing': ['Unit 1: Orthographic', 'Unit 2: Sections', 'Unit 3: Isometric', 'Unit 4: GD&T'],
}
const BLOOM_LEVELS = [
  { level: 1, label: 'L1 — Remember' },
  { level: 2, label: 'L2 — Understand' },
  { level: 3, label: 'L3 — Apply' },
  { level: 4, label: 'L4 — Analyze' },
  { level: 5, label: 'L5 — Evaluate' },
  { level: 6, label: 'L6 — Create' },
]
const QUESTION_TYPES = ['theory', 'numerical', 'drawing']
const COs = ['CO1', 'CO2', 'CO3', 'CO4', 'CO5']

const MOCK_QUESTIONS = [
  {
    id: 'Q-052', text: 'State and derive the first law of thermodynamics for an open system operating under steady state conditions. Apply it to a steam nozzle and derive the expression for exit velocity.',
    bloomLevel: 4, type: 'theory', co: 'CO1', po: 'PO1', marks: 10, difficulty: 'hard', unit: 'Unit 1: Laws of Thermodynamics'
  },
  {
    id: 'Q-053', text: 'A Carnot engine operates between a source at 900 K and a sink at 300 K. The engine produces 200 kW of power. Calculate: (a) thermal efficiency, (b) heat supplied from source, (c) heat rejected to sink.',
    bloomLevel: 3, type: 'numerical', co: 'CO2', po: 'PO2', marks: 8, difficulty: 'medium', unit: 'Unit 2: Power Cycles'
  },
  {
    id: 'Q-054', text: 'Explain the significance of entropy in thermodynamic processes. How does the Clausius inequality establish the criterion for spontaneity of a process?',
    bloomLevel: 2, type: 'theory', co: 'CO1', po: 'PO1', marks: 6, difficulty: 'easy', unit: 'Unit 1: Laws of Thermodynamics'
  },
  {
    id: 'Q-055', text: 'For an air-standard Otto cycle with a compression ratio of 8, initial pressure 1 bar and temperature 300 K, heat added 800 kJ/kg — determine all state point conditions and plot the p-V diagram.',
    bloomLevel: 4, type: 'numerical', co: 'CO2', po: 'PO2', marks: 12, difficulty: 'hard', unit: 'Unit 2: Power Cycles'
  },
]

export default function QuestionGenerator() {
  const [subject, setSubject] = useState(SUBJECTS[0])
  const [unit, setUnit] = useState(UNITS[SUBJECTS[0]][0])
  const [bloomLevel, setBloomLevel] = useState(3)
  const [questionType, setQuestionType] = useState('theory')
  const [co, setCo] = useState('CO1')
  const [count, setCount] = useState(4)
  const [marks, setMarks] = useState(10)
  const [loading, setLoading] = useState(false)
  const [questions, setQuestions] = useState<any[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [agentStatuses, setAgentStatuses] = useState<Record<string, string>>({})
  const [publishing, setPublishing] = useState(false)
  const [publishDone, setPublishDone] = useState(false)

  const handleGenerate = async () => {
    setLoading(true)
    setQuestions([])
    setAgentStatuses({
      'BloomAnalyzer': 'idle', 'Scout': 'idle', 'Generator': 'idle',
      'QualityValidator': 'idle', 'DifficultyValidator': 'idle',
      'CorrectnessValidator': 'idle', 'PedagogyTagger': 'idle',
      'SyllabusGuardian': 'idle', 'Archivist': 'idle',
    })

    const params = new URLSearchParams({
      subject, unit, bloom_level: String(bloomLevel),
      question_type: questionType, co, count: String(count)
    })

    const eventSource = new EventSource(`/api/questions/generate/stream?${params}`)

    eventSource.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.agent) {
        setAgentStatuses(prev => ({ ...prev, [data.agent]: data.status }))
      }
      if (data.done) {
        setQuestions(data.questions || [])
        setSelected(new Set((data.questions || []).map((q: any) => q.id)))
        setLoading(false)
        eventSource.close()
      }
    }
    eventSource.onerror = () => {
      setLoading(false)
      eventSource.close()
    }
  }


  const BLOOM_LABELS: Record<number, string> = { 1: 'Remember', 2: 'Understand', 3: 'Apply', 4: 'Analyze', 5: 'Evaluate', 6: 'Create' }

  const handleExport = () => {
    const selectedQs = questions.filter(q => selected.has(q.id))
    const totalMarks = selectedQs.reduce((sum, q) => sum + (q.marks ?? 0), 0)
    const lines: string[] = [
      `RVCE — ${subject}`,
      `Exam Paper  |  ${unit}`,
      `Total Marks: ${totalMarks}  |  Questions: ${selectedQs.length}`,
      '═'.repeat(70),
      '',
    ]
    selectedQs.forEach((q, i) => {
      lines.push(`Q${i + 1}. [${q.id}] (${q.marks} marks)  CO: ${q.co}  Bloom: L${q.bloom_level ?? q.bloomLevel} — ${BLOOM_LABELS[q.bloom_level ?? q.bloomLevel] ?? ''}`)
      lines.push(q.text)
      lines.push('')
    })
    lines.push('─'.repeat(70))
    lines.push(`Generated by MechAssess  |  ${new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}`)

    const blob = new Blob([lines.join('\n')], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `exam_paper_${subject.replace(/\s+/g, '_')}_${Date.now()}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handlePublish = async () => {
    const selectedQs = questions.filter(q => selected.has(q.id))
    if (selectedQs.length === 0) { alert('No questions selected.'); return }
    setPublishing(true)
    setPublishDone(false)
    try {
      const res = await fetch('/api/exams', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: `${subject} — ${unit}`,
          subject,
          total_marks: selectedQs.reduce((s, q) => s + (q.marks ?? 0), 0),
          duration: 180,
          question_ids: selectedQs.map(q => q.id),
        })
      })
      if (!res.ok) throw new Error('Server error')
      setPublishDone(true)
      setTimeout(() => setPublishDone(false), 3000)
    } catch {
      alert('Publish failed — is the backend running?')
    }
    setPublishing(false)
  }

  const toggleSelect = (id: string) => {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelected(next)
  }

  return (
    <div>
      <Header
        title="Question Generator"
        subtitle="Bloom-Adaptive RAG pipeline — 11-agent LangGraph architecture"
        actions={
          questions.length > 0 ? (
            <div className="flex items-center gap-2">
              <button className="btn-secondary" onClick={handleExport}>
                <Download className="w-4 h-4" /> Export Paper
              </button>
              <button className="btn-primary" onClick={handlePublish} disabled={publishing || selected.size === 0}>
                {publishDone
                  ? <><CheckCircle className="w-4 h-4" /> Published!</>
                  : publishing
                    ? <><div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />Publishing...</>
                    : <><Send className="w-4 h-4" /> Publish to Students ({selected.size})</>
                }
              </button>
            </div>
          ) : null
        }
      />

      <div className="p-6 grid grid-cols-3 gap-6">
        {/* Config Panel */}
        <div className="col-span-1 space-y-4">
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-4">Generation Parameters</h2>
            <div className="space-y-4">
              <div>
                <label className="label">Subject</label>
                <select className="select" value={subject} onChange={e => { setSubject(e.target.value); setUnit(UNITS[e.target.value][0]) }}>
                  {SUBJECTS.map(s => <option key={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="label">Unit / Topic</label>
                <select className="select" value={unit} onChange={e => setUnit(e.target.value)}>
                  {UNITS[subject].map(u => <option key={u}>{u}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Bloom Level</label>
                  <select className="select" value={bloomLevel} onChange={e => setBloomLevel(+e.target.value)}>
                    {BLOOM_LEVELS.map(b => <option key={b.level} value={b.level}>{b.label}</option>)}
                  </select>
                </div>
                <div>
                  <label className="label">Question Type</label>
                  <select className="select" value={questionType} onChange={e => setQuestionType(e.target.value)}>
                    {QUESTION_TYPES.map(t => <option key={t} className="capitalize">{t}</option>)}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">CO Mapping</label>
                  <select className="select" value={co} onChange={e => setCo(e.target.value)}>
                    {COs.map(c => <option key={c}>{c}</option>)}
                  </select>
                </div>
                <div>
                  <label className="label">Marks per Q</label>
                  <input type="number" className="input" value={marks} min={1} max={20} onChange={e => setMarks(+e.target.value)} />
                </div>
              </div>
              <div>
                <label className="label">Number of Questions</label>
                <input type="number" className="input" value={count} min={1} max={20} onChange={e => setCount(+e.target.value)} />
              </div>
              <button
                onClick={handleGenerate}
                disabled={loading}
                className="btn-primary w-full justify-center"
              >
                {loading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Generating via LangGraph...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" /> Generate Questions
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Pipeline Status */}
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-3">Agent Pipeline</h2>
            <div className="space-y-2">
              {Object.entries(agentStatuses).map(([name, status]) => {
                const labels: Record<string, string> = {
                  BloomAnalyzer: 'Bloom Analyzer', Scout: 'Scout (RAG)',
                  Generator: 'Generator', QualityValidator: 'Quality Validator',
                  DifficultyValidator: 'Difficulty Validator', CorrectnessValidator: 'Correctness Validator',
                  PedagogyTagger: 'Pedagogy Tagger', SyllabusGuardian: 'Syllabus Guardian', Archivist: 'Archivist',
                }
                return (
                <div key={name} className="flex items-center justify-between">
                  <span className="text-xs text-gray-600">{labels[name] || name}</span>
                  <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
                    status === 'done' ? 'bg-emerald-50 text-emerald-600' :
                    status === 'running' ? 'bg-indigo-50 text-indigo-600 animate-pulse' :
                    'bg-gray-100 text-gray-400'
                  }`}>{status}</span>
                </div>
                )
              })}
              {Object.keys(agentStatuses).length === 0 && (
                <p className="text-xs text-gray-400">Pipeline idle — click Generate to start</p>
              )}
            </div>
          </div>
        </div>

        {/* Results */}
        <div className="col-span-2">
          {questions.length === 0 && !loading && (
            <div className="card h-full flex items-center justify-center p-12">
              <div className="text-center">
                <div className="w-14 h-14 bg-indigo-50 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Sparkles className="w-7 h-7 text-indigo-400" />
                </div>
                <p className="text-sm font-medium text-gray-700">Configure and generate questions</p>
                <p className="text-xs text-gray-400 mt-1">The LangGraph pipeline will retrieve context from ChromaDB<br />and generate syllabus-aligned questions with CO/PO tags</p>
              </div>
            </div>
          )}

          {loading && (
            <div className="card h-64 flex items-center justify-center">
              <div className="text-center">
                <div className="w-10 h-10 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mx-auto mb-4" style={{ borderWidth: 3, borderStyle: 'solid' }} />
                <p className="text-sm font-medium text-gray-700">Running 11-agent LangGraph pipeline...</p>
                <p className="text-xs text-gray-400 mt-1">Retrieving from ChromaDB · Generating · Validating · Tagging CO/PO</p>
              </div>
            </div>
          )}

          {questions.length > 0 && !loading && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-sm text-gray-600">{questions.length} questions generated · {selected.size} selected</p>
                <div className="flex items-center gap-2">
                  <button onClick={() => setSelected(new Set(questions.map(q => q.id)))} className="text-xs text-indigo-600 hover:underline">Select all</button>
                  <button onClick={() => setSelected(new Set())} className="text-xs text-gray-400 hover:underline">Deselect all</button>
                </div>
              </div>
              {questions.map(q => (
                <div
                  key={q.id}
                  className={`card p-4 cursor-pointer transition-all ${selected.has(q.id) ? 'ring-2 ring-indigo-400 border-indigo-200' : ''}`}
                  onClick={() => toggleSelect(q.id)}
                >
                  <div className="flex items-start gap-3">
                    <div className={`w-4 h-4 rounded border-2 mt-0.5 shrink-0 flex items-center justify-center transition-colors ${selected.has(q.id) ? 'bg-indigo-600 border-indigo-600' : 'border-gray-300'}`}>
                      {selected.has(q.id) && <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2 flex-wrap">
                        <span className="text-xs font-mono text-gray-400">{q.id}</span>
                        <BloomBadge level={q.bloom_level ?? q.bloomLevel} />
                        <span className="badge bg-gray-100 text-gray-600 capitalize">{q.question_type ?? q.type}</span>
                        <span className="badge bg-indigo-50 text-indigo-600">{q.co}</span>
                        <span className="badge bg-slate-50 text-slate-600">{q.po}</span>
                        <span className={`badge ${q.difficulty === 'hard' ? 'bg-red-50 text-red-600' : q.difficulty === 'medium' ? 'bg-amber-50 text-amber-600' : 'bg-green-50 text-green-600'}`}>
                          {q.difficulty}
                        </span>
                        <span className="ml-auto text-xs font-semibold text-gray-700">{q.marks} marks</span>
                      </div>
                      <p className="text-sm text-gray-700 leading-relaxed">{q.text}</p>
                      <p className="text-xs text-gray-400 mt-2">{q.unit}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
