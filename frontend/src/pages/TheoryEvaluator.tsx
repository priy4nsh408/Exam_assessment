import { useState } from 'react'
import { CheckCircle } from 'lucide-react'
import { Header } from '../components/layout/Header'

export default function TheoryEvaluator() {
  const [results, setResults] = useState<any[]>([])
  const [selected, setSelected] = useState<any | null>(null)
  const [grading, setGrading] = useState(false)
  const [answerText, setAnswerText] = useState('')
  const [answerId, setAnswerId] = useState('')
  const [question, setQuestion] = useState('State and derive the first law of thermodynamics for an open system.')
  const [subject, setSubject] = useState('Thermodynamics')
  const [referenceAnswer, setReferenceAnswer] = useState('')
  const [maxMarks, setMaxMarks] = useState(10)
  // override state per result
  const [overrides, setOverrides] = useState<Record<number, { score: string; reason: string; applied: boolean }>>({})

  const useGrounded = !!answerId.trim()

  const handleGrade = async () => {
    if (!answerText.trim()) { alert('Paste or type the student answer first.'); return }
    setGrading(true)
    try {
      const body: any = useGrounded
        ? { answer_id: answerId.trim(), student_answer: answerText }
        : {
            question,
            student_answer: answerText,
            subject,
            reference_answer: referenceAnswer.trim(),
            max_marks: maxMarks,
          }
      const res = await fetch('/api/eval/theory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Grading failed')
      const ts = Date.now()
      const newResult = {
        ts,
        student: 'Manual submission',
        question: data.questionId || (useGrounded ? answerId : question.slice(0, 40) + '…'),
        answer: answerText,
        aiScore: data.aiScore ?? 0,
        maxScore: data.maxScore ?? maxMarks,
        confidence: data.confidence ?? 0,
        keywordScore: data.keywordScore ?? 0,
        semanticScore: data.semanticScore ?? 0,
        feedback: data.feedback ?? '',
        explanation: data.explanation ?? '',
        keywords: { found: data.matchedKeywords ?? [], missing: data.missingKeywords ?? [] },
        answerId: data.answerId,
        hadReferenceData: data.hadReferenceData,
        co: data.co ?? null,
      }
      setResults(prev => [newResult, ...prev])
      setSelected(newResult)
    } catch (e: any) { alert(e.message || 'Grading failed — is the backend running?') }
    setGrading(false)
  }

  const applyOverride = async (ts: number, result: any) => {
    const ov = overrides[ts]
    if (!ov?.score) return
    const score = parseFloat(ov.score)
    if (isNaN(score)) return
    // If result has a submissionId, call the API; otherwise just update locally
    setOverrides(prev => ({ ...prev, [ts]: { ...prev[ts], applied: true } }))
    setResults(prev => prev.map(r => r.ts === ts ? { ...r, aiScore: score, overridden: true, overrideReason: ov.reason } : r))
    if (selected?.ts === ts) setSelected((s: any) => s ? { ...s, aiScore: score, overridden: true, overrideReason: ov.reason } : s)
  }

  return (
    <div>
      <Header title="Theory Answer Evaluator" subtitle="LLaMA 3 / DeepSeek-R1 · Semantic similarity + ME keyword coverage" />
      <div className="p-6 grid grid-cols-3 gap-6">
        {/* Left panel */}
        <div className="col-span-1 space-y-4">
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-3">Grade a Submission</h2>

            {/* Mode selector */}
            <div className="mb-4">
              <label className="label">Answer Scheme ID <span className="text-gray-400 font-normal">(optional — use for grounded grading)</span></label>
              <input
                className="input mb-1 font-mono text-xs"
                value={answerId}
                onChange={e => setAnswerId(e.target.value)}
                placeholder="e.g. AK-20260624-A1B2C3"
              />
              <p className="text-[10px] text-gray-400">
                {useGrounded
                  ? 'Grounded mode: grading against the real answer scheme reference.'
                  : 'Manual mode: fill in Question + Reference Answer below.'}
              </p>
            </div>

            {!useGrounded && (
              <>
                <label className="label">Question</label>
                <textarea
                  className="input resize-none mb-2"
                  rows={2}
                  value={question}
                  onChange={e => setQuestion(e.target.value)}
                  placeholder="Enter the question text"
                />
                <label className="label">Subject</label>
                <select className="select mb-2" value={subject} onChange={e => setSubject(e.target.value)}>
                  <option>Thermodynamics</option>
                  <option>Strength of Materials</option>
                  <option>Fluid Mechanics</option>
                  <option>Engineering Drawing</option>
                  <option>Basic Design of Turbomachinery</option>
                  <option>Propulsion</option>
                  <option>Structural Mechanics</option>
                </select>
                <label className="label">Max Marks</label>
                <input
                  type="number" className="input mb-2" min={1} max={50} step={1}
                  value={maxMarks} onChange={e => setMaxMarks(Number(e.target.value))}
                />
                <label className="label">
                  Reference / Model Answer <span className="text-gray-400 font-normal">(used for keyword + semantic scoring)</span>
                </label>
                <textarea
                  className="input resize-none mb-2 text-xs"
                  rows={4}
                  value={referenceAnswer}
                  onChange={e => setReferenceAnswer(e.target.value)}
                  placeholder="Paste the ideal answer / source material here. Without this, only semantic heuristics are used."
                />
              </>
            )}

            <label className="label">Student Answer</label>
            <textarea
              className="input resize-none"
              rows={5}
              value={answerText}
              onChange={e => setAnswerText(e.target.value)}
              placeholder="Paste or type the student's answer here…"
            />
            <button className="btn-primary w-full justify-center mt-3" onClick={handleGrade} disabled={grading}>
              {grading
                ? <><div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> Grading…</>
                : 'Grade Submission'}
            </button>
          </div>

          <div className="card p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-3">Results ({results.length})</h2>
            <div className="space-y-2">
              {results.length === 0 && (
                <p className="text-xs text-gray-400">No submissions graded yet — paste an answer and click Grade.</p>
              )}
              {results.map(r => (
                <button
                  key={r.ts}
                  onClick={() => setSelected(r)}
                  className={`w-full text-left p-3 rounded-lg border transition-colors ${selected?.ts === r.ts ? 'border-indigo-200 bg-indigo-50' : 'border-gray-100 bg-gray-50 hover:bg-gray-100'}`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-semibold text-gray-700 truncate max-w-[120px]">{r.question}</span>
                    <span className={`text-xs font-bold ${r.aiScore / r.maxScore >= 0.7 ? 'text-emerald-600' : r.aiScore / r.maxScore >= 0.4 ? 'text-amber-600' : 'text-red-600'}`}>
                      {r.aiScore}/{r.maxScore}
                    </span>
                  </div>
                  <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${r.aiScore / r.maxScore >= 0.7 ? 'bg-emerald-500' : r.aiScore / r.maxScore >= 0.4 ? 'bg-amber-400' : 'bg-red-500'}`}
                      style={{ width: `${(r.aiScore / r.maxScore) * 100}%` }}
                    />
                  </div>
                  <p className="text-[10px] text-gray-400 mt-1">
                    Confidence: {(r.confidence * 100).toFixed(0)}%{r.co ? ` · ${r.co}` : ''}{r.overridden ? ' · Overridden' : ''}
                  </p>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Right panel — detail */}
        <div className="col-span-2">
          {!selected ? (
            <div className="card h-full flex items-center justify-center p-12">
              <div className="text-center">
                <CheckCircle className="w-12 h-12 text-gray-200 mx-auto mb-3" />
                <p className="text-sm text-gray-400">Grade a submission to view the evaluation details</p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Score card */}
              <div className="card p-5">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h2 className="text-sm font-semibold text-gray-900">
                      {selected.question}{selected.answerId ? ` · ${selected.answerId}` : ''}
                    </h2>
                    <p className="text-xs text-gray-500">
                      {selected.co ? `${selected.co} · ` : ''}
                      {selected.hadReferenceData ? 'Grounded grading (answer scheme)' : 'Manual / ungrounded grading'}
                      {selected.overridden ? ' · Faculty override applied' : ''}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold text-gray-900">
                      {selected.aiScore}<span className="text-sm font-normal text-gray-400">/{selected.maxScore}</span>
                    </p>
                    <p className="text-xs text-gray-500">Score · Confidence {(selected.confidence * 100).toFixed(0)}%</p>
                  </div>
                </div>

                {/* Score breakdown */}
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-xs text-gray-500 mb-1">Keyword Score</p>
                    <p className="text-lg font-bold text-gray-800">{selected.keywordScore}<span className="text-xs text-gray-400">/{selected.maxScore}</span></p>
                    <p className="text-xs text-gray-400">Terms matched from reference material</p>
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

                {selected.hadReferenceData === false && !selected.overridden && (
                  <div className="bg-amber-50 border border-amber-100 rounded-lg p-2.5 mb-3">
                    <p className="text-[11px] text-amber-700">
                      {referenceAnswer ? 'Graded against the reference answer you provided above.' : 'No reference answer provided — only semantic heuristics were applied. Paste a reference answer for more accurate scoring.'}
                    </p>
                  </div>
                )}

                <div className="bg-amber-50 border border-amber-100 rounded-lg p-3">
                  <p className="text-xs font-medium text-amber-800 mb-1">AI Feedback</p>
                  <p className="text-xs text-amber-700">{selected.feedback}</p>
                </div>
              </div>

              {/* Keyword analysis */}
              <div className="card p-5">
                <h3 className="text-sm font-semibold text-gray-900 mb-3">Keyword Analysis</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs font-medium text-emerald-700 mb-2">Found ({selected.keywords.found.length})</p>
                    <div className="flex flex-wrap gap-1.5">
                      {selected.keywords.found.map((k: string) => (
                        <span key={k} className="badge bg-emerald-50 text-emerald-700">{k}</span>
                      ))}
                      {selected.keywords.found.length === 0 && <span className="text-xs text-gray-400">None matched</span>}
                    </div>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-red-600 mb-2">Missing ({selected.keywords.missing.length})</p>
                    <div className="flex flex-wrap gap-1.5">
                      {selected.keywords.missing.map((k: string) => (
                        <span key={k} className="badge bg-red-50 text-red-600">{k}</span>
                      ))}
                      {selected.keywords.missing.length === 0 && <span className="text-xs text-gray-400">All key terms covered</span>}
                    </div>
                  </div>
                </div>
              </div>

              {/* Faculty override */}
              <div className="card p-5">
                <h3 className="text-sm font-semibold text-gray-900 mb-3">Faculty Override</h3>
                {overrides[selected.ts]?.applied ? (
                  <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3">
                    <p className="text-xs text-emerald-700">Override applied — score updated to {overrides[selected.ts].score}/{selected.maxScore}.</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <div>
                      <label className="label">Override Score (/{selected.maxScore})</label>
                      <input
                        type="number" className="input"
                        placeholder={String(selected.aiScore)}
                        value={overrides[selected.ts]?.score ?? ''}
                        onChange={e => setOverrides(prev => ({ ...prev, [selected.ts]: { ...(prev[selected.ts] ?? { score: '', reason: '', applied: false }), score: e.target.value } }))}
                        min={0} max={selected.maxScore} step={0.5}
                      />
                    </div>
                    <div>
                      <label className="label">Reason for Override</label>
                      <input
                        type="text" className="input"
                        placeholder="e.g. Partial credit for diagram"
                        value={overrides[selected.ts]?.reason ?? ''}
                        onChange={e => setOverrides(prev => ({ ...prev, [selected.ts]: { ...(prev[selected.ts] ?? { score: '', reason: '', applied: false }), reason: e.target.value } }))}
                      />
                    </div>
                    <button
                      className="btn-primary col-span-2"
                      disabled={!overrides[selected.ts]?.score}
                      onClick={() => applyOverride(selected.ts, selected)}
                    >
                      Apply Override
                    </button>
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
