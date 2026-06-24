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

// No mock fixture - displayData is null until a real grading result comes
// back from /api/eval/numerical. Previously fell back to a hand-written
// fake Kavitha Rao / Q-053 result that displayed even before any real
// grading happened.

export default function NumericalGrader() {
  const [showResult, setShowResult] = useState(false)
  const [grading, setGrading] = useState(false)
  const [overrideScore, setOverrideScore] = useState('')
  const [numericalResult, setNumericalResult] = useState<any>(null)
  const [answerId, setAnswerId] = useState('')
  const [usn, setUsn] = useState('')
  const [solutionText, setSolutionText] = useState('Step 1: η = 1 - 300/900 = 0.667\nStep 2: Q_H = 200 × 0.667 = 133.4 kW\nStep 3: Q_L = 133.4 - 200 = -66.6 kW')

  const handleGrade = async () => {
    setGrading(true)
    try {
      const body: any = answerId.trim()
        ? { answer_id: answerId.trim(), student_solution: solutionText }
        : {
            question: 'A Carnot engine operates between 900 K and 300 K producing 200 kW. Find efficiency, heat supplied, heat rejected.',
            student_solution: solutionText,
            subject: 'Thermodynamics',
            max_marks: 10
          }
      const res = await fetch('/api/eval/numerical', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Grading failed')
      // Normalize API response fields to match display expectations
      const normalized = {
        student: usn.trim() || 'No USN entered',
        question: data.questionId || '—',
        questionText: 'A Carnot engine operates between 900 K and 300 K producing 200 kW.',
        aiScore: data.ai_score ?? data.total_earned ?? 0,
        maxScore: data.max_score ?? data.total_marks ?? 10,
        confidence: data.confidence ?? 0.8,
        baseScore: data.base_score,
        deductions: data.deductions,
        formulaMentioned: data.formula_mentioned,
        finalAnswerCorrect: data.final_answer_correct,
        explanation: data.explanation,
        answerId: data.answerId,
        totalSteps: (data.steps || []).length,
        steps: (data.steps || []).map((s: any) => ({
          step: s.step,
          description: s.description,
          expected: s.expected,
          student: s.student_work ?? s.student ?? '',
          correct: s.correct,
          marks: s.marks,
          earned: s.earned,
          errorType: s.error_type === 'correct' ? null : s.error_type ?? null,
          deduction: s.marks - s.earned,
        }))
      }
      setNumericalResult(normalized)
      setShowResult(true)
    } catch (e: any) {
      alert(e.message || 'Grading failed — is the backend running?')
    }
    setGrading(false)
  }

  const displayData = numericalResult

  return (
    <div>
      <Header title="Numerical Step-Level Grader" subtitle="DeepSeek-R1 · Tree-of-thought prompting · 5-category error classification" />
      <div className="p-6 grid grid-cols-3 gap-6">
        <div className="col-span-1 space-y-4">
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-3">Submit Solution</h2>
            <div className="space-y-3">
              <div>
                <label className="label">Student USN (optional, for display only)</label>
                <input className="input" value={usn} onChange={e => setUsn(e.target.value)} placeholder="e.g. 1RV23ME004" />
              </div>
              <div>
                <label className="label">Answer ID (optional — grades against a real answer scheme)</label>
                <input className="input font-mono text-xs" value={answerId} onChange={e => setAnswerId(e.target.value)} placeholder="e.g. AK-20260624-A1B2C3" />
              </div>
              <div>
                <label className="label">Question (used only if Answer ID is empty)</label>
                <input className="input text-xs" defaultValue="A Carnot engine operates between 900 K and 300 K producing 200 kW. Find efficiency, heat supplied, heat rejected." readOnly />
              </div>
              <div>
                <label className="label">Student Solution (type or paste each step)</label>
                <textarea
                  className="input resize-none font-mono text-xs"
                  rows={6}
                  value={solutionText}
                  onChange={e => setSolutionText(e.target.value)}
                  placeholder="Step 1: formula&#10;Step 2: substitution&#10;Step 3: result"
                />
              </div>
              <button className="btn-primary w-full justify-center" onClick={handleGrade} disabled={grading}>
                {grading ? <><div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />Running DeepSeek-R1...</> : 'Grade Step-by-Step'}
              </button>
            </div>
          </div>

          {showResult && displayData && (
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
          {showResult && !grading && displayData && (
            <div className="space-y-4">
              <div className="card p-5">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h2 className="text-sm font-semibold text-gray-900">{displayData.student}{displayData.answerId ? ` · ${displayData.answerId}` : ''}</h2>
                    <p className="text-xs text-gray-500">{displayData.questionText}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold text-gray-900">{displayData.aiScore}<span className="text-sm font-normal text-gray-400">/{displayData.maxScore}</span></p>
                    <p className="text-xs text-gray-400">Step accuracy: {displayData.steps.filter((s: any) => s.correct).length}/{displayData.totalSteps}</p>
                  </div>
                </div>
                {(displayData.formulaMentioned !== undefined || displayData.finalAnswerCorrect !== undefined) && (
                  <div className="flex gap-2 mb-3">
                    {displayData.formulaMentioned !== undefined && (
                      <span className={`badge ${displayData.formulaMentioned ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-600'}`}>
                        {displayData.formulaMentioned ? 'Formula mentioned' : 'Formula missing (-1)'}
                      </span>
                    )}
                    {displayData.finalAnswerCorrect !== undefined && (
                      <span className={`badge ${displayData.finalAnswerCorrect ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-600'}`}>
                        {displayData.finalAnswerCorrect ? 'Final answer correct' : 'Final answer wrong (-1)'}
                      </span>
                    )}
                  </div>
                )}
                {displayData.explanation && (
                  <div className="bg-indigo-50 border border-indigo-100 rounded-lg p-3">
                    <p className="text-xs font-medium text-indigo-800 mb-1">Why this score — marks awarded / deducted</p>
                    <p className="text-xs text-indigo-700">{displayData.explanation}</p>
                  </div>
                )}
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
