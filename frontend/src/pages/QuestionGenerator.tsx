import { useState } from 'react'
import { Sparkles, Download, Send, CheckCircle, Plus, Trash2, ChevronDown, ChevronUp } from 'lucide-react'
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
const BLOOM_LABELS: Record<number, string> = { 1: 'Remember', 2: 'Understand', 3: 'Apply', 4: 'Analyze', 5: 'Evaluate', 6: 'Create' }

type SpecRow = { id: string; co: string; bloomLevel: number; marks: number }

let rowCounter = 0
function newRow(co = 'CO1', bloomLevel = 3, marks = 10): SpecRow {
  rowCounter += 1
  return { id: `row-${rowCounter}`, co, bloomLevel, marks }
}

const PIPELINE_STEPS = [
  'BloomAnalyzer', 'Scout', 'Generator', 'QualityValidator', 'DifficultyValidator',
  'CorrectnessValidator', 'PedagogyTagger', 'SyllabusGuardian', 'ProvenanceExplainer',
  'AnswerKey', 'Archivist',
]

export default function QuestionGenerator() {
  const [subject, setSubject] = useState(SUBJECTS[0])
  const [unit, setUnit] = useState(UNITS[SUBJECTS[0]][0])
  const [questionType, setQuestionType] = useState('theory')
  const [count, setCount] = useState(4)

  // One CO/Bloom/marks row pool, expanded across `count` questions either
  // sequentially (cycling through the pool in order) or randomly (one pool
  // entry picked at random per slot). A single row behaves exactly like the
  // old "one CO/Bloom level" mode - no separate single/multi toggle needed.
  const [specRows, setSpecRows] = useState<SpecRow[]>([newRow()])
  const [assignment, setAssignment] = useState<'sequential' | 'random'>('sequential')

  const [loading, setLoading] = useState(false)
  const [questions, setQuestions] = useState<any[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [agentStatuses, setAgentStatuses] = useState<Record<string, string>>({})
  const [publishing, setPublishing] = useState(false)
  const [publishDone, setPublishDone] = useState(false)
  const [warning, setWarning] = useState<string | null>(null)

  const addSpecRow = () => setSpecRows(prev => [...prev, newRow(COs[prev.length % COs.length])])
  const removeSpecRow = (id: string) => setSpecRows(prev => prev.length > 1 ? prev.filter(r => r.id !== id) : prev)
  const updateSpecRow = (id: string, patch: Partial<SpecRow>) =>
    setSpecRows(prev => prev.map(r => r.id === id ? { ...r, ...patch } : r))

  // Expands the spec pool to exactly `count` per-question specs.
  const buildExpandedSpecs = () => {
    const pool = specRows
    const out: { bloom_level: number; co: string; marks: number }[] = []
    for (let i = 0; i < count; i++) {
      const row = assignment === 'sequential'
        ? pool[i % pool.length]
        : pool[Math.floor(Math.random() * pool.length)]
      out.push({ bloom_level: row.bloomLevel, co: row.co, marks: row.marks })
    }
    return out
  }

  const handleGenerate = async () => {
    setLoading(true)
    setQuestions([])
    setWarning(null)
    setAgentStatuses(Object.fromEntries(PIPELINE_STEPS.map(s => [s, 'idle'])))

    // Lightweight visual progress through the agent chain while the single
    // batched /api/pipeline/generate request is in flight - this isn't an
    // SSE stream of real per-agent events (mixed-spec batches run as one
    // request), just a paced animation so the wait doesn't feel inert.
    let stepIndex = 0
    const stepInterval = setInterval(() => {
      if (stepIndex < PIPELINE_STEPS.length) {
        const name = PIPELINE_STEPS[stepIndex]
        setAgentStatuses(prev => ({ ...prev, [name]: 'running' }))
        setTimeout(() => setAgentStatuses(prev => ({ ...prev, [name]: 'done' })), 350)
        stepIndex += 1
      }
    }, 450)

    try {
      const res = await fetch('/api/pipeline/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          subject, chapter: unit, question_type: questionType,
          questions: buildExpandedSpecs(),
        }),
      })
      if (!res.ok) throw new Error('Server error')
      const data = await res.json()
      setQuestions(data.questions || [])
      setSelected(new Set((data.questions || []).map((q: any) => q.id)))
      if (data.warning) setWarning(data.warning)
    } catch {
      alert('Generation failed — is the backend running?')
    } finally {
      clearInterval(stepInterval)
      setAgentStatuses(Object.fromEntries(PIPELINE_STEPS.map(s => [s, 'done'])))
      setLoading(false)
    }
  }

  const toggleExpand = (id: string) => {
    const next = new Set(expanded)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setExpanded(next)
  }

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
              <div>
                <label className="label">Question Type</label>
                <select className="select" value={questionType} onChange={e => setQuestionType(e.target.value)}>
                  {QUESTION_TYPES.map(t => <option key={t} className="capitalize">{t}</option>)}
                </select>
              </div>

              <div>
                <label className="label">CO / Bloom Levels</label>
                <div className="space-y-2">
                  {specRows.map((row, idx) => (
                    <div key={row.id} className="flex items-center gap-2 bg-gray-50 rounded-lg p-2">
                      <span className="text-[10px] text-gray-400 w-4">{idx + 1}</span>
                      <select className="select text-xs py-1.5" value={row.bloomLevel} onChange={e => updateSpecRow(row.id, { bloomLevel: +e.target.value })}>
                        {BLOOM_LEVELS.map(b => <option key={b.level} value={b.level}>L{b.level}</option>)}
                      </select>
                      <select className="select text-xs py-1.5" value={row.co} onChange={e => updateSpecRow(row.id, { co: e.target.value })}>
                        {COs.map(c => <option key={c}>{c}</option>)}
                      </select>
                      <input type="number" className="input text-xs py-1.5 w-16" value={row.marks} min={1} max={20} onChange={e => updateSpecRow(row.id, { marks: +e.target.value })} />
                      <button onClick={() => removeSpecRow(row.id)} disabled={specRows.length <= 1} className="text-gray-300 hover:text-red-500 disabled:opacity-30 disabled:hover:text-gray-300 shrink-0">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                  <button onClick={addSpecRow} className="text-xs text-indigo-600 hover:underline flex items-center gap-1">
                    <Plus className="w-3 h-3" /> Add CO / Bloom level
                  </button>

                  {specRows.length > 1 && (
                    <div className="pt-2">
                      <label className="label">Assign across questions</label>
                      <div className="flex gap-2">
                        <button
                          onClick={() => setAssignment('sequential')}
                          className={`flex-1 text-xs py-1.5 rounded-md border ${assignment === 'sequential' ? 'bg-indigo-600 text-white border-indigo-600' : 'border-gray-200 text-gray-600'}`}
                        >Sequential</button>
                        <button
                          onClick={() => setAssignment('random')}
                          className={`flex-1 text-xs py-1.5 rounded-md border ${assignment === 'random' ? 'bg-indigo-600 text-white border-indigo-600' : 'border-gray-200 text-gray-600'}`}
                        >Random</button>
                      </div>
                      <p className="text-[10px] text-gray-400 mt-1">
                        {assignment === 'sequential'
                          ? 'Cycles through the levels above, in order, across the questions generated.'
                          : 'Picks one of the levels above at random for each question generated.'}
                      </p>
                    </div>
                  )}
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
                  PedagogyTagger: 'Pedagogy Tagger', SyllabusGuardian: 'Syllabus Guardian',
                  ProvenanceExplainer: 'Provenance Explainer', AnswerKey: 'Answer Key', Archivist: 'Archivist',
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
          {warning && (
            <div className="card p-3 mb-3 bg-amber-50 border-amber-200 text-xs text-amber-700">{warning}</div>
          )}
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
              {questions.map(q => {
                const isExpanded = expanded.has(q.id)
                const validation = q.generationExplanation
                return (
                <div
                  key={q.id}
                  className={`card p-4 transition-all ${selected.has(q.id) ? 'ring-2 ring-indigo-400 border-indigo-200' : ''}`}
                >
                  <div className="flex items-start gap-3">
                    <div
                      className={`w-4 h-4 rounded border-2 mt-0.5 shrink-0 flex items-center justify-center transition-colors cursor-pointer ${selected.has(q.id) ? 'bg-indigo-600 border-indigo-600' : 'border-gray-300'}`}
                      onClick={() => toggleSelect(q.id)}
                    >
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
                      <p className="text-sm text-gray-700 leading-relaxed cursor-pointer" onClick={() => toggleSelect(q.id)}>{q.text}</p>
                      <div className="flex items-center justify-between mt-2">
                        <p className="text-xs text-gray-400">{q.unit}{q.answerId ? ` · Answer ID: ${q.answerId}` : ''}</p>
                        {validation && (
                          <button onClick={() => toggleExpand(q.id)} className="text-[11px] text-indigo-600 hover:underline flex items-center gap-0.5 shrink-0">
                            Validation {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                          </button>
                        )}
                      </div>
                      {isExpanded && validation && (
                        <div className="mt-2 bg-indigo-50/60 border border-indigo-100 rounded-lg p-3">
                          <p className="text-[10px] font-semibold text-indigo-700 uppercase tracking-wide mb-1">Why / where this question was generated from</p>
                          <p className="text-xs text-indigo-800 leading-relaxed">{validation}</p>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
