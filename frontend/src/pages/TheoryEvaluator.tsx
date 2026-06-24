import { useState, useRef } from 'react'
import { Upload, CheckCircle } from 'lucide-react'
import { Header } from '../components/layout/Header'

const MOCK_RESULTS = [
  {
    student: '1RV23ME001', name: 'Arjun Sharma', question: 'Q-052',
    answer: 'The first law of thermodynamics states that energy cannot be created or destroyed...',
    aiScore: 7.5, maxScore: 10, confidence: 0.87,
    keywordScore: 3.5, semanticScore: 4.0,
    feedback: 'Core principle correctly stated. Missing derivation for open system steady-state SFEE. Nozzle application partially addressed — exit velocity expression derivation incomplete.',
    explanation: 'Awarded 3.5/4.0 marks for keyword coverage (8/12 key terms matched). Awarded 4.0/6.0 marks for semantic similarity (78% similarity). Total: 7.5/10.',
    keywords: { found: ['conservation of energy', 'enthalpy', 'work done', 'heat transfer'], missing: ['SFEE', 'isentropic', 'velocity head'] },
    co: 'CO1', status: 'graded'
  },
  {
    student: '1RV23ME002', name: 'Priya Nair', question: 'Q-052',
    answer: 'First law: dU = delta Q - delta W. For open systems, we consider enthalpy and kinetic energy...',
    aiScore: 9.0, maxScore: 10, confidence: 0.92,
    keywordScore: 4.5, semanticScore: 4.5,
    feedback: 'Excellent derivation of SFEE for open system. Nozzle application correctly applied with proper assumptions stated. Minor: did not mention steady-flow assumption explicitly.',
    explanation: 'Awarded 4.5/4.0 marks for keyword coverage (11/12 key terms matched). Awarded 4.5/6.0 marks for semantic similarity (91% similarity). Total: 9.0/10.',
    keywords: { found: ['SFEE', 'enthalpy', 'kinetic energy', 'steady state', 'isentropic'], missing: ['continuity equation'] },
    co: 'CO1', status: 'graded'
  },
  {
    student: '1RV23ME003', name: 'Rohan Das', question: 'Q-052',
    answer: 'Energy is conserved. In thermodynamics, Q = W + dU is the first law.',
    aiScore: 3.0, maxScore: 10, confidence: 0.78,
    keywordScore: 1.0, semanticScore: 2.0,
    feedback: 'Only basic statement provided. Open system analysis absent. No derivation of SFEE or application to nozzle. Significant gaps in understanding of flow work and enthalpy.',
    explanation: 'Awarded 1.0/4.0 marks for keyword coverage (2/12 key terms matched). Awarded 2.0/6.0 marks for semantic similarity (38% similarity). Total: 3.0/10.',
    keywords: { found: ['Q = W', 'energy'], missing: ['SFEE', 'enthalpy', 'open system', 'isentropic', 'nozzle', 'exit velocity'] },
    co: 'CO1', status: 'graded'
  },
]

export default function TheoryEvaluator() {
  const [results, setResults] = useState<any[]>(MOCK_RESULTS)
  const [selected, setSelected] = useState<any | null>(null)
  const [overrideScore, setOverrideScore] = useState('')
  const [overrideReason, setOverrideReason] = useState('')
  const [grading, setGrading] = useState(false)
  const [answerText, setAnswerText] = useState('')
  const [answerId, setAnswerId] = useState('')
  const [question, setQuestion] = useState('State and derive the first law of thermodynamics for an open system.')
  const [subject, setSubject] = useState('Thermodynamics')
  const fileRef = useRef<HTMLInputElement>(null)

  const handleGrade = async () => {
    if (!answerText.trim()) { alert('Paste or type the student answer first.'); return }
    setGrading(true)
    try {
      const body: any = answerId.trim()
        ? { answer_id: answerId.trim(), student_answer: answerText }
        : { question, student_answer: answerText, subject, model_answer: '', max_marks: 10 }
      const res = await fetch('/api/eval/theory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Grading failed')
      const newResult = {
        student: `S-${Date.now()}`, name: 'Student', question: data.questionId || 'Custom',
        answer: answerText,
        aiScore: data.aiScore ?? 0, maxScore: data.maxScore ?? 10,
        confidence: data.confidence ?? 0,
        keywordScore: data.keywordScore ?? 0, semanticScore: data.semanticScore ?? 0,
        feedback: data.feedback ?? '',
        explanation: data.explanation ?? '',
        keywords: { found: data.matchedKeywords ?? [], missing: data.missingKeywords ?? [] },
        answerId: data.answerId,
        hadReferenceData: data.hadReferenceData,
        co: 'CO1', status: 'graded'
      }
      setResults(prev => [newResult, ...prev])
      setSelected(newResult)
    } catch (e: any) { alert(e.message || 'Grading failed — is the backend running?') }
    setGrading(false)
  }

  return (
    <div>
      <Header title="Theory Answer Evaluator" subtitle="LLaMA 3 / DeepSeek-R1 · Semantic similarity + ME keyword coverage" />
      <div className="p-6 grid grid-cols-3 gap-6">
        {/* Upload + list */}
        <div className="col-span-1 space-y-4">
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-3">Upload Submissions</h2>
            <div>
              <label className="label">Answer ID (optional — grades against a real answer scheme)</label>
              <input className="input mb-2 font-mono text-xs" value={answerId} onChange={e => setAnswerId(e.target.value)} placeholder="e.g. AK-20260624-A1B2C3" />
              <p className="text-[10px] text-gray-400 mb-3">If set, Question/Subject below are ignored — grading uses the answer scheme's own reference answer.</p>
              <label className="label">Question</label>
              <input className="input mb-2" value={question} onChange={e => setQuestion(e.target.value)} placeholder="Enter question text" disabled={!!answerId.trim()} />
              <label className="label">Subject</label>
              <select className="select mb-2" value={subject} onChange={e => setSubject(e.target.value)} disabled={!!answerId.trim()}>
                <option>Thermodynamics</option>
                <option>Strength of Materials</option>
                <option>Fluid Mechanics</option>
                <option>Engineering Drawing</option>
              </select>
              <label className="label">Student Answer</label>
              <textarea
                className="input resize-none"
                rows={5}
                value={answerText}
                onChange={e => setAnswerText(e.target.value)}
                placeholder="Paste or type the student's answer here..."
              />
            </div>
            <button className="btn-primary w-full justify-center mt-3" onClick={handleGrade} disabled={grading}>
              {grading ? <><div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> Grading...</> : 'Grade All Submissions'}
            </button>
          </div>

          <div className="card p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-3">Results ({results.length})</h2>
            <div className="space-y-2">
              {results.map(r => (
                <button
                  key={r.student}
                  onClick={() => setSelected(r)}
                  className={`w-full text-left p-3 rounded-lg border transition-colors ${selected?.student === r.student ? 'border-indigo-200 bg-indigo-50' : 'border-gray-100 bg-gray-50 hover:bg-gray-100'}`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-semibold text-gray-700">{r.name}</span>
                    <span className={`text-xs font-bold ${r.aiScore / r.maxScore >= 0.7 ? 'text-emerald-600' : r.aiScore / r.maxScore >= 0.4 ? 'text-amber-600' : 'text-red-600'}`}>
                      {r.aiScore}/{r.maxScore}
                    </span>
                  </div>
                  <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full ${r.aiScore / r.maxScore >= 0.7 ? 'bg-emerald-500' : r.aiScore / r.maxScore >= 0.4 ? 'bg-amber-400' : 'bg-red-500'}`} style={{ width: `${(r.aiScore / r.maxScore) * 100}%` }} />
                  </div>
                  <p className="text-[10px] text-gray-400 mt-1">Confidence: {(r.confidence * 100).toFixed(0)}% · {r.co}</p>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Detail view */}
        <div className="col-span-2">
          {!selected ? (
            <div className="card h-full flex items-center justify-center p-12">
              <div className="text-center">
                <CheckCircle className="w-12 h-12 text-gray-200 mx-auto mb-3" />
                <p className="text-sm text-gray-400">Select a submission to view evaluation details</p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="card p-5">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h2 className="text-sm font-semibold text-gray-900">{selected.name} · {selected.student}</h2>
                    <p className="text-xs text-gray-500">Question {selected.question} · {selected.co}{selected.answerId ? ` · ${selected.answerId}` : ''}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold text-gray-900">{selected.aiScore}<span className="text-sm font-normal text-gray-400">/{selected.maxScore}</span></p>
                    <p className="text-xs text-gray-500">AI Score · Confidence {(selected.confidence * 100).toFixed(0)}%</p>
                  </div>
                </div>
                {/* Score breakdown */}
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-xs text-gray-500 mb-1">Keyword Score</p>
                    <p className="text-lg font-bold text-gray-800">{selected.keywordScore}<span className="text-xs text-gray-400">/{selected.maxScore}</span></p>
                    <p className="text-xs text-gray-400">Terms matched from source material</p>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-xs text-gray-500 mb-1">Semantic Score</p>
                    <p className="text-lg font-bold text-gray-800">{selected.semanticScore}<span className="text-xs text-gray-400">/{selected.maxScore}</span></p>
                    <p className="text-xs text-gray-400">Similarity to reference answer</p>
                  </div>
                </div>
                {selected.explanation && (
                  <div className="bg-indigo-50 border border-indigo-100 rounded-lg p-3 mb-3">
                    <p className="text-xs font-medium text-indigo-800 mb-1">Why this score — marks awarded / deducted</p>
                    <p className="text-xs text-indigo-700">{selected.explanation}</p>
                  </div>
                )}
                {selected.hadReferenceData === false && (
                  <div className="bg-amber-50 border border-amber-100 rounded-lg p-2.5 mb-3">
                    <p className="text-[11px] text-amber-700">No grounded reference answer was available — this score is ungrounded (manual mode).</p>
                  </div>
                )}
                <div className="bg-amber-50 border border-amber-100 rounded-lg p-3">
                  <p className="text-xs font-medium text-amber-800 mb-1">AI Feedback</p>
                  <p className="text-xs text-amber-700">{selected.feedback}</p>
                </div>
              </div>

              <div className="card p-5">
                <h3 className="text-sm font-semibold text-gray-900 mb-3">Keyword Analysis</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs font-medium text-emerald-700 mb-2">Found ({selected.keywords.found.length})</p>
                    <div className="flex flex-wrap gap-1.5">
                      {selected.keywords.found.map((k: string) => <span key={k} className="badge bg-emerald-50 text-emerald-700">{k}</span>)}
                    </div>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-red-600 mb-2">Missing ({selected.keywords.missing.length})</p>
                    <div className="flex flex-wrap gap-1.5">
                      {selected.keywords.missing.map((k: string) => <span key={k} className="badge bg-red-50 text-red-600">{k}</span>)}
                    </div>
                  </div>
                </div>
              </div>

              <div className="card p-5">
                <h3 className="text-sm font-semibold text-gray-900 mb-3">Faculty Override</h3>
                <div className="grid grid-cols-2 gap-3 mb-3">
                  <div>
                    <label className="label">Override Score (/ {selected.maxScore})</label>
                    <input type="number" className="input" placeholder={String(selected.aiScore)} value={overrideScore} onChange={e => setOverrideScore(e.target.value)} min={0} max={selected.maxScore} step={0.5} />
                  </div>
                  <div>
                    <label className="label">Reason for Override</label>
                    <input type="text" className="input" placeholder="e.g. Partial credit for diagram" value={overrideReason} onChange={e => setOverrideReason(e.target.value)} />
                  </div>
                </div>
                <button className="btn-primary" disabled={!overrideScore}>Apply Override</button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
