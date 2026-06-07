import { useState } from 'react'
import { Upload, CheckCircle } from 'lucide-react'
import { Header } from '../components/layout/Header'

const MOCK_RESULTS = [
  {
    student: '1RV23ME001', name: 'Arjun Sharma', question: 'Q-052',
    answer: 'The first law of thermodynamics states that energy cannot be created or destroyed...',
    aiScore: 7.5, maxScore: 10, confidence: 0.87,
    conceptScore: 3.5, detailScore: 4.0,
    feedback: 'Core principle correctly stated. Missing derivation for open system steady-state SFEE. Nozzle application partially addressed — exit velocity expression derivation incomplete.',
    keywords: { found: ['conservation of energy', 'enthalpy', 'work done', 'heat transfer'], missing: ['SFEE', 'isentropic', 'velocity head'] },
    co: 'CO1', status: 'graded'
  },
  {
    student: '1RV23ME002', name: 'Priya Nair', question: 'Q-052',
    answer: 'First law: dU = delta Q - delta W. For open systems, we consider enthalpy and kinetic energy...',
    aiScore: 9.0, maxScore: 10, confidence: 0.92,
    conceptScore: 4.5, detailScore: 4.5,
    feedback: 'Excellent derivation of SFEE for open system. Nozzle application correctly applied with proper assumptions stated. Minor: did not mention steady-flow assumption explicitly.',
    keywords: { found: ['SFEE', 'enthalpy', 'kinetic energy', 'steady state', 'isentropic'], missing: ['continuity equation'] },
    co: 'CO1', status: 'graded'
  },
  {
    student: '1RV23ME003', name: 'Rohan Das', question: 'Q-052',
    answer: 'Energy is conserved. In thermodynamics, Q = W + dU is the first law.',
    aiScore: 3.0, maxScore: 10, confidence: 0.78,
    conceptScore: 2.0, detailScore: 1.0,
    feedback: 'Only basic statement provided. Open system analysis absent. No derivation of SFEE or application to nozzle. Significant gaps in understanding of flow work and enthalpy.',
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

  const handleGrade = async () => {
    setGrading(true)
    const res = await fetch('/api/eval/theory', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: "State and derive the first law of thermodynamics for an open system.",
        student_answer: "The first law states energy is conserved. Q = W + ΔU for closed systems.",
        subject: "Thermodynamics",
        model_answer: "",
        max_marks: 10
      })
    })
    const data = await res.json()
    setResults([{
      student: '1RV23ME001', name: 'Demo Student', question: 'Q-052',
      answer: 'Student answer submitted',
      aiScore: data.ai_score, maxScore: data.max_score,
      confidence: data.confidence,
      conceptScore: data.concept_score, detailScore: data.detail_score,
      feedback: data.feedback,
      keywords: data.keywords || { found: [], missing: [], coverage_ratio: 0 },
      co: 'CO1', status: 'graded'
    }])
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
            <div className="border-2 border-dashed border-gray-200 rounded-lg p-6 text-center hover:border-indigo-300 transition-colors cursor-pointer">
              <Upload className="w-8 h-8 text-gray-300 mx-auto mb-2" />
              <p className="text-xs font-medium text-gray-600">Drop PDF or images here</p>
              <p className="text-xs text-gray-400">or click to browse</p>
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
                    <p className="text-xs text-gray-500">Question {selected.question} · {selected.co}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold text-gray-900">{selected.aiScore}<span className="text-sm font-normal text-gray-400">/{selected.maxScore}</span></p>
                    <p className="text-xs text-gray-500">AI Score · Confidence {(selected.confidence * 100).toFixed(0)}%</p>
                  </div>
                </div>
                {/* Score breakdown */}
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-xs text-gray-500 mb-1">Concept Score</p>
                    <p className="text-lg font-bold text-gray-800">{selected.conceptScore}<span className="text-xs text-gray-400">/5</span></p>
                    <p className="text-xs text-gray-400">Core principle presence</p>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-xs text-gray-500 mb-1">Detail Score</p>
                    <p className="text-lg font-bold text-gray-800">{selected.detailScore}<span className="text-xs text-gray-400">/5</span></p>
                    <p className="text-xs text-gray-400">Reasoning + terminology</p>
                  </div>
                </div>
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
