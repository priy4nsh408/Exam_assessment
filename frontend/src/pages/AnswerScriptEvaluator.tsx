import { useState, useRef, useCallback } from 'react'
import { Header } from '../components/layout/Header'
import {
  Upload, FileText, ChevronDown, ChevronRight,
  CheckCircle, AlertCircle, Brain, Calculator, PenTool,
  Loader2, BarChart3, Eye,
} from 'lucide-react'

const SUBJECTS = [
  'Thermodynamics', 'Strength of Materials', 'Fluid Mechanics',
  'Engineering Drawing', 'Basic Design & Theory', 'Propulsion',
  'Structural Mechanics', 'Machine Design', 'Manufacturing Technology',
  'Mechanical Engineering',
]

interface AnswerResult {
  q_number: number
  q_type: 'theory' | 'numerical' | 'drawing'
  question: string
  ocr_text: string
  ai_score: number
  max_score: number
  confidence: number
  feedback: string
  page_start: number
  detail: Record<string, any>
}

interface ScriptReport {
  total_score: number
  max_total: number
  percentage: number
  subject: string
  questions_evaluated: number
  ocr_pages: number
  answers: AnswerResult[]
}

const TYPE_ICON: Record<string, React.ReactNode> = {
  theory: <Brain className="w-3.5 h-3.5" />,
  numerical: <Calculator className="w-3.5 h-3.5" />,
  drawing: <PenTool className="w-3.5 h-3.5" />,
}
const TYPE_COLOR: Record<string, string> = {
  theory: 'bg-indigo-50 text-indigo-700',
  numerical: 'bg-amber-50 text-amber-700',
  drawing: 'bg-emerald-50 text-emerald-700',
}

function ScorePill({ score, max }: { score: number; max: number }) {
  const pct = max > 0 ? (score / max) * 100 : 0
  const color = pct >= 70 ? 'text-emerald-600' : pct >= 40 ? 'text-amber-600' : 'text-red-500'
  return (
    <span className={`font-bold text-base ${color}`}>
      {score}<span className="text-xs text-gray-400">/{max}</span>
    </span>
  )
}

function AnswerCard({ ans }: { ans: AnswerResult }) {
  const [open, setOpen] = useState(false)
  const [tab, setTab] = useState<'feedback' | 'ocr' | 'detail'>('feedback')

  const keywords = ans.detail?.matched_keywords ?? []
  const missing   = ans.detail?.missing_keywords ?? []
  const steps     = ans.detail?.steps ?? []
  const errors    = ans.detail?.error_summary ?? {}
  const violations = ans.detail?.violations ?? []

  return (
    <div className="card overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-50 transition-colors"
        onClick={() => setOpen(o => !o)}
      >
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-gray-700 w-6">Q{ans.q_number}</span>
          <span className={`flex items-center gap-1 badge text-xs ${TYPE_COLOR[ans.q_type]}`}>
            {TYPE_ICON[ans.q_type]}
            {ans.q_type}
          </span>
          <span className="text-xs text-gray-400">p.{ans.page_start}</span>
          <span className="text-xs text-gray-500 max-w-xs truncate hidden sm:block">{ans.question}</span>
        </div>
        <div className="flex items-center gap-4 shrink-0">
          <div className="text-right">
            <ScorePill score={ans.ai_score} max={ans.max_score} />
            <p className="text-[10px] text-gray-400">{Math.round(ans.confidence * 100)}% conf.</p>
          </div>
          {open ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
        </div>
      </button>

      {open && (
        <div className="border-t border-gray-100 px-5 py-4 space-y-4">
          {/* Question text */}
          <p className="text-sm text-gray-700 font-medium">{ans.question}</p>

          {/* Tabs */}
          <div className="flex gap-1 text-xs border-b border-gray-100 pb-1">
            {(['feedback', 'ocr', 'detail'] as const).map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-3 py-1 rounded-t capitalize transition-colors ${tab === t ? 'bg-indigo-600 text-white' : 'text-gray-500 hover:text-gray-700'}`}
              >
                {t === 'ocr' ? 'OCR Text' : t === 'detail' ? 'Detail' : 'Feedback'}
              </button>
            ))}
          </div>

          {tab === 'feedback' && (
            <div className="space-y-2">
              <p className="text-sm text-gray-600">{ans.feedback}</p>
              {ans.detail?.explanation && (
                <p className="text-xs text-gray-400 italic">{ans.detail.explanation}</p>
              )}
              {/* Theory keyword chips */}
              {keywords.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {keywords.map((k: string) => (
                    <span key={k} className="badge bg-emerald-50 text-emerald-700 text-[10px]">✓ {k}</span>
                  ))}
                  {missing.map((k: string) => (
                    <span key={k} className="badge bg-red-50 text-red-600 text-[10px]">✗ {k}</span>
                  ))}
                </div>
              )}
              {/* Numerical step summary */}
              {steps.length > 0 && (
                <div className="space-y-1 mt-2">
                  {steps.map((s: any, i: number) => (
                    <div key={i} className="flex items-center justify-between text-xs bg-gray-50 rounded px-3 py-1.5">
                      <span className="text-gray-600">{s.step_name || `Step ${i+1}`}</span>
                      <span className={`font-medium ${s.earned > 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                        {s.earned ?? 0}/{s.max ?? 0}
                      </span>
                    </div>
                  ))}
                </div>
              )}
              {/* Drawing violations */}
              {violations.length > 0 && (
                <div className="space-y-1 mt-2">
                  {violations.map((v: any, i: number) => (
                    <div key={i} className="flex items-center gap-2 text-xs text-red-600 bg-red-50 rounded px-3 py-1">
                      <AlertCircle className="w-3 h-3 shrink-0" />
                      {v.rule}: {v.description} ({v.deduction} marks)
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {tab === 'ocr' && (
            <div>
              <p className="text-[10px] text-gray-400 mb-1 flex items-center gap-1">
                <Eye className="w-3 h-3" /> Extracted by OCR — may contain recognition errors
              </p>
              <pre className="text-xs text-gray-700 bg-gray-50 rounded p-3 whitespace-pre-wrap max-h-60 overflow-y-auto font-mono leading-relaxed">
                {ans.ocr_text || '(no text detected)'}
              </pre>
            </div>
          )}

          {tab === 'detail' && (
            <div className="text-xs space-y-2">
              {ans.q_type === 'theory' && (
                <>
                  <div className="flex gap-4">
                    <span>Keyword score: <b>{((ans.detail?.keyword_score ?? 0)*100).toFixed(0)}%</b></span>
                    <span>Semantic score: <b>{((ans.detail?.semantic_score ?? 0)*100).toFixed(0)}%</b></span>
                  </div>
                </>
              )}
              {ans.q_type === 'numerical' && Object.keys(errors).length > 0 && (
                <div className="bg-amber-50 rounded p-2">
                  <p className="font-medium text-amber-700 mb-1">Error types detected:</p>
                  {Object.entries(errors).map(([k, v]: [string, any]) => (
                    <div key={k} className="flex justify-between text-amber-600">
                      <span>{k.replace(/_/g, ' ')}</span><span>{v} error(s)</span>
                    </div>
                  ))}
                </div>
              )}
              {ans.q_type === 'drawing' && (
                <div>
                  <p className="font-medium text-gray-600 mb-1">Detected elements:</p>
                  <div className="flex flex-wrap gap-1">
                    {(ans.detail?.detected_elements ?? []).map((el: string, i: number) => (
                      <span key={i} className="badge bg-gray-100 text-gray-600">{el}</span>
                    ))}
                    {(ans.detail?.detected_elements ?? []).length === 0 && (
                      <span className="text-gray-400">None detected</span>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function AnswerScriptEvaluator() {
  const [file, setFile] = useState<File | null>(null)
  const [subject, setSubject] = useState('Mechanical Engineering')
  const [maxMarks, setMaxMarks] = useState(10)
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState('')
  const [error, setError] = useState('')
  const [report, setReport] = useState<ScriptReport | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const acceptFile = useCallback((f: File) => {
    setFile(f)
    setReport(null)
    setError('')
  }, [])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) acceptFile(f)
  }, [acceptFile])

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) acceptFile(f)
  }

  const evaluate = async () => {
    if (!file) return
    setLoading(true)
    setError('')
    setReport(null)

    const steps = ['Uploading PDF…', 'Running OCR on handwriting…', 'Classifying answers…', 'Evaluating with AI…']
    let si = 0
    const timer = setInterval(() => {
      si = (si + 1) % steps.length
      setProgress(steps[si])
    }, 2500)
    setProgress(steps[0])

    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('subject', subject)
      fd.append('max_marks_per_q', String(maxMarks))

      const res = await fetch('/api/eval/script', { method: 'POST', body: fd })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || 'Server error')
      }
      const data = await res.json()
      setReport(data)
    } catch (e: any) {
      setError(e.message || 'Evaluation failed')
    } finally {
      clearInterval(timer)
      setLoading(false)
      setProgress('')
    }
  }

  const pct = report ? report.percentage : 0
  const grade =
    pct >= 90 ? 'O' : pct >= 80 ? 'A+' : pct >= 70 ? 'A' :
    pct >= 60 ? 'B+' : pct >= 50 ? 'B' : pct >= 40 ? 'C' : 'F'

  return (
    <div>
      <Header
        title="Answer Script Evaluator"
        subtitle="Upload a handwritten answer PDF — OCR + AI grades all questions automatically"
      />
      <div className="p-6 space-y-6 max-w-4xl">

        {/* Upload zone */}
        <div className="card p-6 space-y-5">
          <div
            onDrop={onDrop}
            onDragOver={e => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onClick={() => fileRef.current?.click()}
            className={`border-2 border-dashed rounded-xl flex flex-col items-center justify-center py-12 cursor-pointer transition-colors ${
              dragging ? 'border-indigo-500 bg-indigo-50' : 'border-gray-200 hover:border-indigo-300 hover:bg-gray-50'
            }`}
          >
            <input ref={fileRef} type="file" accept=".pdf,.png,.jpg,.jpeg" className="hidden" onChange={onFileChange} />
            <Upload className={`w-8 h-8 mb-3 ${dragging ? 'text-indigo-500' : 'text-gray-300'}`} />
            {file ? (
              <div className="text-center">
                <p className="text-sm font-medium text-indigo-700 flex items-center gap-2">
                  <FileText className="w-4 h-4" /> {file.name}
                </p>
                <p className="text-xs text-gray-400 mt-1">{(file.size / 1024).toFixed(0)} KB · click to change</p>
              </div>
            ) : (
              <div className="text-center">
                <p className="text-sm text-gray-500">Drop handwritten answer PDF here</p>
                <p className="text-xs text-gray-400 mt-1">or click to browse · PDF, PNG, JPG</p>
              </div>
            )}
          </div>

          {/* Config row */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-gray-600 mb-1 block">Subject</label>
              <select
                className="input-field w-full text-sm"
                value={subject}
                onChange={e => setSubject(e.target.value)}
              >
                {SUBJECTS.map(s => <option key={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 mb-1 block">Marks per question</label>
              <input
                type="number" min={1} max={100}
                className="input-field w-full text-sm"
                value={maxMarks}
                onChange={e => setMaxMarks(Number(e.target.value))}
              />
            </div>
          </div>

          <button
            onClick={evaluate}
            disabled={!file || loading}
            className="btn-primary w-full flex items-center justify-center gap-2 py-3 disabled:opacity-50"
          >
            {loading ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> {progress}</>
            ) : (
              <><Brain className="w-4 h-4" /> Evaluate Answer Script</>
            )}
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="card p-4 bg-red-50 border-red-200 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-500 mt-0.5 shrink-0" />
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {/* Report */}
        {report && (
          <>
            {/* Summary banner */}
            <div className={`card p-6 grid grid-cols-2 sm:grid-cols-4 gap-6 ${pct >= 70 ? 'bg-emerald-50 border-emerald-200' : pct >= 40 ? 'bg-amber-50 border-amber-200' : 'bg-red-50 border-red-200'}`}>
              <div>
                <p className="text-xs font-medium text-gray-500 mb-1">Total Score</p>
                <p className={`text-4xl font-bold ${pct >= 70 ? 'text-emerald-700' : pct >= 40 ? 'text-amber-700' : 'text-red-600'}`}>
                  {report.total_score}<span className="text-lg text-gray-400">/{report.max_total}</span>
                </p>
              </div>
              <div>
                <p className="text-xs font-medium text-gray-500 mb-1">Percentage</p>
                <p className="text-3xl font-bold text-gray-800">{report.percentage}%</p>
              </div>
              <div>
                <p className="text-xs font-medium text-gray-500 mb-1">Grade</p>
                <p className="text-3xl font-bold text-indigo-600">{grade}</p>
              </div>
              <div className="space-y-1">
                <p className="text-xs font-medium text-gray-500">Stats</p>
                <p className="text-xs text-gray-600">📄 {report.ocr_pages} page(s) scanned</p>
                <p className="text-xs text-gray-600">❓ {report.questions_evaluated} question(s) found</p>
                <p className="text-xs text-gray-600">📚 {report.subject}</p>
              </div>
            </div>

            {/* Type breakdown */}
            <div className="flex items-center gap-4 text-xs text-gray-500">
              <BarChart3 className="w-4 h-4 text-indigo-400" />
              {(['theory', 'numerical', 'drawing'] as const).map(t => {
                const count = report.answers.filter(a => a.q_type === t).length
                return count > 0 ? (
                  <span key={t} className={`flex items-center gap-1 badge ${TYPE_COLOR[t]}`}>
                    {TYPE_ICON[t]} {count} {t}
                  </span>
                ) : null
              })}
            </div>

            {/* Per-question cards */}
            <div className="space-y-3">
              {report.answers.map(ans => (
                <AnswerCard key={ans.q_number} ans={ans} />
              ))}
            </div>

            {/* Result icon */}
            <div className={`card p-4 flex items-center gap-3 ${pct >= 50 ? 'bg-emerald-50 border-emerald-200' : 'bg-red-50 border-red-200'}`}>
              {pct >= 50
                ? <CheckCircle className="w-5 h-5 text-emerald-600 shrink-0" />
                : <AlertCircle className="w-5 h-5 text-red-500 shrink-0" />}
              <p className={`text-sm font-medium ${pct >= 50 ? 'text-emerald-800' : 'text-red-700'}`}>
                {pct >= 50 ? 'Pass' : 'Fail'} — {report.percentage}% ({grade})
                {' · '}Overall {report.total_score} out of {report.max_total} marks.
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
