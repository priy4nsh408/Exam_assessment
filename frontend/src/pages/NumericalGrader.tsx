import { useState } from 'react'
import { Upload, AlertCircle } from 'lucide-react'
import { Header } from '../components/layout/Header'

const ERROR_COLORS: Record<string, string> = {
  formula_error: 'bg-red-50 text-red-700 border-red-200',
  substitution_error: 'bg-orange-50 text-orange-700 border-orange-200',
  unit_error: 'bg-yellow-50 text-yellow-700 border-yellow-200',
  arithmetic_error: 'bg-amber-50 text-amber-700 border-amber-200',
  boundary_condition_error: 'bg-rose-50 text-rose-700 border-rose-200',
}
const ERROR_LABELS: Record<string, string> = {
  formula_error: 'Wrong Formula',
  substitution_error: 'Substitution Error',
  unit_error: 'Unit Error',
  arithmetic_error: 'Arithmetic Error',
  boundary_condition_error: 'Boundary Condition Error',
}

const MOCK = {
  student: '1RV23ME004', name: 'Kavitha Rao', question: 'Q-053',
  questionText: 'A Carnot engine operates between 900 K and 300 K producing 200 kW. Find efficiency, heat supplied, heat rejected.',
  totalSteps: 4,
  steps: [
    { step: 1, description: 'Calculate thermal efficiency', expected: 'eta = 1 - T_L/T_H = 1 - 300/900 = 0.667 (66.7%)', student: 'eta = 1 - 300/900 = 0.667', correct: true, marks: 2, earned: 2, errorType: null, deduction: 0 },
    { step: 2, description: 'Calculate heat supplied from source', expected: 'Q_H = W_net / eta = 200/0.667 = 299.9 kW approx 300 kW', student: 'Q_H = 200 x 0.667 = 133.4 kW', correct: false, marks: 3, earned: 0, errorType: 'formula_error', deduction: 3 },
    { step: 3, description: 'Calculate heat rejected to sink', expected: 'Q_L = Q_H - W_net = 300 - 200 = 100 kW', student: 'Q_L = 133.4 - 200 = -66.6 kW', correct: false, marks: 3, earned: 1, errorType: 'arithmetic_error', deduction: 2 },
    { step: 4, description: 'State final answers with correct units', expected: 'eta = 66.7%, Q_H = 300 kW, Q_L = 100 kW', student: 'eta = 66.7%, Q_H = 133.4 kW, Q_L = -66.6 kW', correct: false, marks: 2, earned: 1, errorType: 'substitution_error', deduction: 1 },
  ],
  aiScore: 4, maxScore: 10, confidence: 0.91,
}

export default function NumericalGrader() {
  const [showResult, setShowResult] = useState(false)
  const [grading, setGrading] = useState(false)
  const [overrideScore, setOverrideScore] = useState('')
  const [numericalResult, setNumericalResult] = useState<any>(null)

  const handleGrade = async () => {
    setGrading(true)
    const res = await fetch('/api/eval/numerical', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: 'A Carnot engine operates between 900 K and 300 K producing 200 kW. Find efficiency, heat supplied, heat rejected.',
        student_solution: 'Step 1: η = 1 - 300/900 = 0.667\nStep 2: Q_H = 200 × 0.667 = 133.4 kW\nStep 3: Q_L = 133.4 - 200 = -66.6 kW',
        subject: 'Thermodynamics',
        max_marks: 10
      })
    })
    const data = await res.json()
    setNumericalResult(data)
    setGrading(false)
    setShowResult(true)
  }

  const displayData = numericalResult ?? MOCK

  return (
    <div>
      <Header title="Numerical Step-Level Grader" subtitle="DeepSeek-R1 · Tree-of-thought prompting · 5-category error classification" />
      <div className="p-6 grid grid-cols-3 gap-6">
        <div className="col-span-1 space-y-4">
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-3">Submit Solution</h2>
            <div className="space-y-3">
              <div>
                <label className="label">Student USN</label>
                <input className="input" defaultValue="1RV23ME004" readOnly />
              </div>
              <div>
                <label className="label">Question</label>
                <select className="select"><option>Q-053 — Carnot Cycle (10 marks)</option></select>
              </div>
              <div>
                <label className="label">Upload Solution (image/PDF)</label>
                <div className="border-2 border-dashed border-gray-200 rounded-lg p-4 text-center cursor-pointer hover:border-indigo-300 transition-colors">
                  <Upload className="w-6 h-6 text-gray-300 mx-auto mb-1" />
                  <p className="text-xs text-gray-400">Drop file or click</p>
                </div>
              </div>
              <button className="btn-primary w-full justify-center" onClick={handleGrade} disabled={grading}>
                {grading ? <><div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />Running DeepSeek-R1...</> : 'Grade Step-by-Step'}
              </button>
            </div>
          </div>

          {showResult && (
            <div className="card p-5">
              <h2 className="text-sm font-semibold text-gray-900 mb-3">Error Summary</h2>
              <div className="space-y-2">
                {Object.entries(ERROR_LABELS).map(([k, v]) => {
                  const count = displayData.steps.filter((s: any) => s.errorType === k).length
                  return (
                    <div key={k} className={`flex items-center justify-between px-2.5 py-1.5 rounded border text-xs ${count > 0 ? ERROR_COLORS[k] : 'bg-gray-50 text-gray-400 border-gray-100'}`}>
                      <span>{v}</span>
                      <span className="font-bold">{count}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        <div className="col-span-2">
          {!showResult && !grading && (
            <div className="card h-full flex items-center justify-center p-12">
              <div className="text-center">
                <AlertCircle className="w-12 h-12 text-gray-200 mx-auto mb-3" />
                <p className="text-sm text-gray-400">Upload a solution and click Grade</p>
              </div>
            </div>
          )}
          {grading && (
            <div className="card h-64 flex items-center justify-center">
              <div className="text-center">
                <div className="w-10 h-10 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mx-auto mb-4" style={{ borderWidth: 3, borderStyle: 'solid' }} />
                <p className="text-sm text-gray-700">Evaluating step-by-step with tree-of-thought...</p>
              </div>
            </div>
          )}
          {showResult && !grading && (
            <div className="space-y-4">
              <div className="card p-5">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h2 className="text-sm font-semibold text-gray-900">{displayData.name} · {displayData.student}</h2>
                    <p className="text-xs text-gray-500">{displayData.questionText}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold text-gray-900">{displayData.aiScore}<span className="text-sm font-normal text-gray-400">/{displayData.maxScore}</span></p>
                    <p className="text-xs text-gray-400">Step accuracy: {displayData.steps.filter((s: any) => s.correct).length}/{displayData.totalSteps}</p>
                  </div>
                </div>
              </div>

              {displayData.steps.map((step: any) => (
                <div key={step.step} className={`card p-4 border-l-4 ${step.correct ? 'border-l-emerald-400' : 'border-l-red-400'}`}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${step.correct ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-600'}`}>
                        {step.step}
                      </span>
                      <span className="text-sm font-medium text-gray-800">{step.description}</span>
                    </div>
                    <span className={`text-sm font-bold ${step.correct ? 'text-emerald-600' : 'text-red-600'}`}>
                      {step.earned}/{step.marks} pts
                    </span>
                  </div>
                  <div className="ml-8 space-y-2">
                    <div className="bg-emerald-50 rounded p-2">
                      <p className="text-[10px] font-semibold text-emerald-700 uppercase tracking-wide mb-0.5">Expected</p>
                      <p className="text-xs font-mono text-gray-700">{step.expected}</p>
                    </div>
                    <div className={`rounded p-2 ${step.correct ? 'bg-emerald-50' : 'bg-red-50'}`}>
                      <p className={`text-[10px] font-semibold uppercase tracking-wide mb-0.5 ${step.correct ? 'text-emerald-700' : 'text-red-700'}`}>Student Answer</p>
                      <p className="text-xs font-mono text-gray-700">{step.student}</p>
                    </div>
                    {!step.correct && step.errorType && (
                      <span className={`badge border ${ERROR_COLORS[step.errorType]}`}>{ERROR_LABELS[step.errorType]} · -{step.deduction} pts</span>
                    )}
                  </div>
                </div>
              ))}

              <div className="card p-5">
                <h3 className="text-sm font-semibold text-gray-900 mb-3">Faculty Override</h3>
                <div className="flex items-end gap-3">
                  <div className="flex-1">
                    <label className="label">Override Score (/{displayData.maxScore})</label>
                    <input type="number" className="input" placeholder={String(displayData.aiScore)} value={overrideScore} onChange={e => setOverrideScore(e.target.value)} />
                  </div>
                  <button className="btn-primary" disabled={!overrideScore}>Apply</button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
