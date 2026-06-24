import { useState } from 'react'
import { AlertCircle } from 'lucide-react'
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

const DEFAULT_QUESTION = 'A Carnot engine operates between 900 K and 300 K producing 200 kW. Find the thermal efficiency, heat supplied, and heat rejected.'

export default function NumericalGrader() {
  const [grading, setGrading] = useState(false)
  const [numericalResult, setNumericalResult] = useState<any>(null)
  const [answerId, setAnswerId] = useState('')
  const [usn, setUsn] = useState('')
  const [question, setQuestion] = useState(DEFAULT_QUESTION)
  const [subject, setSubject] = useState('Thermodynamics')
  const [maxMarks, setMaxMarks] = useState(10)
  const [expectedFormula, setExpectedFormula] = useState('')
  const [expectedFinalAnswer, setExpectedFinalAnswer] = useState('')
  const [solutionText, setSolutionText] = useState(
    'Step 1: η = 1 - T_L/T_H = 1 - 300/900 = 0.667\nStep 2: Q_H = W_net / η = 200 / 0.667 = 299.9 kW\nStep 3: Q_L = Q_H - W_net = 299.9 - 200 = 99.9 kW'
  )
  const [overrideScore, setOverrideScore] = useState('')
  const [overrideApplied, setOverrideApplied] = useState(false)

  const useGrounded = !!answerId.trim()

  const handleGrade = async () => {
    if (!solutionText.trim()) { alert('Enter the student solution first.'); return }
    setGrading(true)
    setOverrideApplied(false)
    setOverrideScore('')
    try {
      const body: any = useGrounded
        ? { answer_id: answerId.trim(), student_solution: solutionText }
        : {
            question,
            student_solution: solutionText,
            subject,
            max_marks: maxMarks,
            expected_formula: expectedFormula.trim() || undefined,
            expected_final_answer: expectedFinalAnswer.trim() || undefined,
          }
      const res = await fetch('/api/eval/numerical', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Grading failed')
      setNumericalResult({
        student: usn.trim() || 'Anonymous',
        questionId: data.questionId || '—',
        questionText: useGrounded ? question : question,
        aiScore: data.ai_score ?? data.total_earned ?? 0,
        maxScore: data.max_score ?? data.total_marks ?? maxMarks,
        confidence: data.confidence ?? 0.8,
        baseScore: data.base_score,
        deductions: data.deductions,
        formulaMentioned: data.formula_mentioned,
        finalAnswerCorrect: data.final_answer_correct,
        explanation: data.explanation,
        answerId: data.answerId,
        co: data.co,
        steps: (data.steps || []).map((s: any) => ({
          step: s.step,
          description: s.description,
          expected: s.expected,
          student: s.student_work ?? s.student ?? '',
          correct: s.correct,
          marks: s.marks,
          earned: s.earned,
          errorType: s.error_type === 'correct' ? null : (s.error_type ?? null),
          deduction: (s.marks ?? 0) - (s.earned ?? 0),
        })),
      })
    } catch (e: any) {
      alert(e.message || 'Grading failed — is the backend running?')
    }
    setGrading(false)
  }

  const applyOverride = () => {
    const s = parseFloat(overrideScore)
    if (isNaN(s)) return
    setNumericalResult((prev: any) => prev ? { ...prev, aiScore: s, overridden: true } : prev)
    setOverrideApplied(true)
  }

  const d = numericalResult

  return (
    <div>
      <Header title="Numerical Step-Level Grader" subtitle="DeepSeek-R1 · Tree-of-thought prompting · 5-category error classification" />
      <div className="p-6 grid grid-cols-3 gap-6">
        {/* Left panel */}
        <div className="col-span-1 space-y-4">
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-3">Submit Solution</h2>
            <div className="space-y-3">
              <div>
                <label className="label">Student USN <span className="text-gray-400 font-normal">(display only)</span></label>
                <input className="input" value={usn} onChange={e => setUsn(e.target.value)} placeholder="e.g. 1RV23ME004" />
              </div>
              <div>
                <label className="label">Answer Scheme ID <span className="text-gray-400 font-normal">(optional)</span></label>
                <input
                  className="input font-mono text-xs"
                  value={answerId}
                  onChange={e => setAnswerId(e.target.value)}
                  placeholder="e.g. AK-20260624-A1B2C3"
                />
                <p className="text-[10px] text-gray-400 mt-0.5">
                  {useGrounded ? 'Grounded mode — grading against real answer scheme.' : 'Manual mode — fill in fields below.'}
                </p>
              </div>

              {!useGrounded && (
                <>
                  <div>
                    <label className="label">Question</label>
                    <textarea
                      className="input resize-none text-xs"
                      rows={3}
                      value={question}
                      onChange={e => setQuestion(e.target.value)}
                      placeholder="Enter the numerical problem statement"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="label">Subject</label>
                      <select className="select" value={subject} onChange={e => setSubject(e.target.value)}>
                        <option>Thermodynamics</option>
                        <option>Strength of Materials</option>
                        <option>Fluid Mechanics</option>
                        <option>Basic Design of Turbomachinery</option>
                        <option>Propulsion</option>
                        <option>Structural Mechanics</option>
                      </select>
                    </div>
                    <div>
                      <label className="label">Max Marks</label>
                      <input
                        type="number" className="input" min={1} max={50} step={1}
                        value={maxMarks} onChange={e => setMaxMarks(Number(e.target.value))}
                      />
                    </div>
                  </div>
                  <div>
                    <label className="label">Expected Formula <span className="text-gray-400 font-normal">(optional)</span></label>
                    <input
                      className="input text-xs font-mono"
                      value={expectedFormula}
                      onChange={e => setExpectedFormula(e.target.value)}
                      placeholder="e.g. eta = 1 - T_L/T_H"
                    />
                  </div>
                  <div>
                    <label className="label">Expected Final Answer <span className="text-gray-400 font-normal">(optional)</span></label>
                    <input
                      className="input text-xs font-mono"
                      value={expectedFinalAnswer}
                      onChange={e => setExpectedFinalAnswer(e.target.value)}
                      placeholder="e.g. 150 kW"
                    />
                  </div>
                </>
              )}

              <div>
                <label className="label">Student Solution</label>
                <textarea
                  className="input resize-none font-mono text-xs"
                  rows={6}
                  value={solutionText}
                  onChange={e => setSolutionText(e.target.value)}
                  placeholder="Step 1: formula&#10;Step 2: substitution&#10;Step 3: result"
                />
              </div>
              <button className="btn-primary w-full justify-center" onClick={handleGrade} disabled={grading}>
                {grading
                  ? <><div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> Running step grader…</>
                  : 'Grade Step-by-Step'}
              </button>
            </div>
          </div>

          {d && (
            <div className="card p-5">
              <h2 className="text-sm font-semibold text-gray-900 mb-3">Error Summary</h2>
              <div className="space-y-2">
                {Object.entries(ERROR_LABELS).map(([k, v]) => {
                  const count = d.steps.filter((s: any) => s.errorType === k).length
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

        {/* Right panel */}
        <div className="col-span-2">
          {!d && !grading && (
            <div className="card h-full flex items-center justify-center p-12">
              <div className="text-center">
                <AlertCircle className="w-12 h-12 text-gray-200 mx-auto mb-3" />
                <p className="text-sm text-gray-400">Enter a solution and click Grade</p>
                <p className="text-xs text-gray-300 mt-1">Supports theory, Carnot, SOM, and fluid mechanics problems</p>
              </div>
            </div>
          )}
          {grading && (
            <div className="card h-64 flex items-center justify-center">
              <div className="text-center">
                <div className="w-10 h-10 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mx-auto mb-4" style={{ borderWidth: 3, borderStyle: 'solid' }} />
                <p className="text-sm text-gray-700">Evaluating step-by-step with tree-of-thought…</p>
              </div>
            </div>
          )}
          {d && !grading && (
            <div className="space-y-4">
              {/* Summary card */}
              <div className="card p-5">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h2 className="text-sm font-semibold text-gray-900">
                      {d.student}{d.answerId ? ` · ${d.answerId}` : ''}
                    </h2>
                    <p className="text-xs text-gray-500 max-w-md truncate">{question}</p>
                    {d.co && <p className="text-xs text-indigo-600 mt-0.5">{d.co}</p>}
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold text-gray-900">
                      {d.aiScore}<span className="text-sm font-normal text-gray-400">/{d.maxScore}</span>
                    </p>
                    <p className="text-xs text-gray-400">
                      Step accuracy: {d.steps.filter((s: any) => s.correct).length}/{d.steps.length}
                    </p>
                  </div>
                </div>

                {(d.formulaMentioned !== undefined || d.finalAnswerCorrect !== undefined) && (
                  <div className="flex gap-2 mb-3">
                    {d.formulaMentioned !== undefined && (
                      <span className={`badge ${d.formulaMentioned ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-600'}`}>
                        {d.formulaMentioned ? 'Formula mentioned' : 'Formula missing (-1)'}
                      </span>
                    )}
                    {d.finalAnswerCorrect !== undefined && (
                      <span className={`badge ${d.finalAnswerCorrect ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-600'}`}>
                        {d.finalAnswerCorrect ? 'Final answer correct' : 'Final answer wrong (-1)'}
                      </span>
                    )}
                    {d.overridden && (
                      <span className="badge bg-indigo-50 text-indigo-700">Faculty overridden</span>
                    )}
                  </div>
                )}

                {d.explanation && (
                  <div className="bg-indigo-50 border border-indigo-100 rounded-lg p-3">
                    <p className="text-xs font-medium text-indigo-800 mb-1">Why this score — marks awarded / deducted</p>
                    <p className="text-xs text-indigo-700">{d.explanation}</p>
                  </div>
                )}
              </div>

              {/* Step cards */}
              {d.steps.map((step: any) => (
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
                      <p className="text-xs font-mono text-gray-700">{step.expected || '—'}</p>
                    </div>
                    <div className={`rounded p-2 ${step.correct ? 'bg-emerald-50' : 'bg-red-50'}`}>
                      <p className={`text-[10px] font-semibold uppercase tracking-wide mb-0.5 ${step.correct ? 'text-emerald-700' : 'text-red-700'}`}>Student Answer</p>
                      <p className="text-xs font-mono text-gray-700">{step.student || '—'}</p>
                    </div>
                    {!step.correct && step.errorType && (
                      <span className={`badge border ${ERROR_COLORS[step.errorType]}`}>
                        {ERROR_LABELS[step.errorType]} · -{step.deduction.toFixed(1)} pts
                      </span>
                    )}
                  </div>
                </div>
              ))}

              {/* Faculty override */}
              <div className="card p-5">
                <h3 className="text-sm font-semibold text-gray-900 mb-3">Faculty Override</h3>
                {overrideApplied ? (
                  <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3">
                    <p className="text-xs text-emerald-700">Override applied — score updated to {overrideScore}/{d.maxScore}.</p>
                  </div>
                ) : (
                  <div className="flex items-end gap-3">
                    <div className="flex-1">
                      <label className="label">Override Score (/{d.maxScore})</label>
                      <input
                        type="number" className="input"
                        placeholder={String(d.aiScore)}
                        value={overrideScore}
                        onChange={e => setOverrideScore(e.target.value)}
                        min={0} max={d.maxScore} step={0.5}
                      />
                    </div>
                    <button className="btn-primary" disabled={!overrideScore} onClick={applyOverride}>Apply</button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
