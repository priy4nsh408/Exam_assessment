import { useState, useRef, useCallback, useEffect } from 'react'
import { Header } from '../components/layout/Header'
import {
  Upload, FileText, ChevronDown, ChevronRight,
  CheckCircle, AlertCircle, Brain, Calculator, PenTool,
  Loader2, BarChart3, Eye, AlertTriangle, Download,
  Users, X,
} from 'lucide-react'

interface RefEntry {
  id: string
  subject: string
  q_type: string
  filename: string
  description: string
  marks_per_q: number
}

interface AnswerResult {
  q_number: number
  q_type: 'theory' | 'numerical' | 'drawing'
  question: string
  ocr_text: string
  ai_score: number
  max_score: number
  confidence: number
  ocr_confidence: number
  low_confidence: boolean
  feedback: string
  page_start: number
  requires_faculty_review?: boolean
  detail: Record<string, any>
}

interface ScriptReport {
  student_name: string
  student_usn: string
  total_score: number
  max_total: number
  percentage: number
  subject: string
  questions_evaluated: number
  ocr_pages: number
  avg_ocr_confidence: number
  low_confidence_pages: number[]
  ocr_warning: boolean
  answers: AnswerResult[]
  deps?: Record<string, any>
  error?: string | null
}

interface BatchResult {
  reports: ScriptReport[]
  total_students: number
  class_avg: number
  pass_count: number
  fail_count: number
  subject: string
}

interface DepStatus {
  pdf2image: { available: boolean; error: string }
  easyocr:  { available: boolean; error: string }
  pillow:   { available: boolean; error: string }
  ready:    boolean
}

const TYPE_ICON: Record<string, React.ReactNode> = {
  theory:   <Brain className="w-3.5 h-3.5" />,
  numerical:<Calculator className="w-3.5 h-3.5" />,
  drawing:  <PenTool className="w-3.5 h-3.5" />,
}
const TYPE_COLOR: Record<string, string> = {
  theory:   'bg-indigo-50 text-indigo-700',
  numerical:'bg-amber-50 text-amber-700',
  drawing:  'bg-emerald-50 text-emerald-700',
}

function ScorePill({ score, max }: { score: number; max: number }) {
  const pct = max > 0 ? (score / max) * 100 : 0
  const color = pct >= 70 ? 'text-emerald-600' : pct >= 40 ? 'text-amber-600' : 'text-red-500'
  return <span className={`font-bold text-base ${color}`}>{score}<span className="text-xs text-gray-400">/{max}</span></span>
}

function DepBanner({ deps }: { deps: DepStatus }) {
  if (deps.ready) return null
  const missing = [
    !deps.pdf2image?.available && 'pdf2image',
    !deps.easyocr?.available && 'easyocr',
  ].filter(Boolean)
  return (
    <div className="card p-4 bg-amber-50 border-amber-300 flex items-start gap-3">
      <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
      <div>
        <p className="text-sm font-semibold text-amber-800">OCR dependencies not installed</p>
        <p className="text-xs text-amber-700 mt-0.5">
          Missing: <code className="bg-amber-100 px-1 rounded">{missing.join(', ')}</code>
        </p>
        <p className="text-xs text-amber-600 mt-1 font-mono bg-amber-100 px-2 py-1 rounded mt-2">
          pip install easyocr pdf2image Pillow &amp;&amp; apt-get install -y poppler-utils
        </p>
        <p className="text-xs text-amber-600 mt-1">
          Without these, uploaded PDFs cannot be read. Install on the server then restart.
        </p>
      </div>
    </div>
  )
}

function AnswerCard({ ans }: { ans: AnswerResult }) {
  const [open, setOpen] = useState(false)
  const [tab, setTab]   = useState<'feedback' | 'ocr' | 'detail'>('feedback')

  const keywords  = ans.detail?.matched_keywords ?? []
  const missing   = ans.detail?.missing_keywords ?? []
  const steps     = ans.detail?.steps ?? []
  const errors    = ans.detail?.error_summary ?? {}
  const violations = ans.detail?.violations ?? []

  return (
    <div className="card overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-gray-50 transition-colors"
        onClick={() => setOpen(o => !o)}
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-sm font-semibold text-gray-700 w-6 shrink-0">Q{ans.q_number}</span>
          <span className={`flex items-center gap-1 badge text-xs shrink-0 ${TYPE_COLOR[ans.q_type]}`}>
            {TYPE_ICON[ans.q_type]} {ans.q_type}
          </span>
          {ans.low_confidence && (
            <span className="badge bg-amber-50 text-amber-600 text-[10px] shrink-0">
              ⚠ Low OCR ({Math.round(ans.ocr_confidence * 100)}%)
            </span>
          )}
          {ans.requires_faculty_review && (
            <span className="badge bg-violet-50 text-violet-600 text-[10px] shrink-0">
              Faculty review needed
            </span>
          )}
          <span className="text-xs text-gray-400 truncate hidden sm:block">{ans.question}</span>
        </div>
        <div className="flex items-center gap-4 shrink-0 ml-2">
          <div className="text-right">
            <ScorePill score={ans.ai_score} max={ans.max_score} />
            <p className="text-[10px] text-gray-400">{Math.round(ans.confidence * 100)}% conf</p>
          </div>
          {open ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
        </div>
      </button>

      {open && (
        <div className="border-t border-gray-100 px-5 py-4 space-y-3">
          {ans.low_confidence && (
            <div className="flex items-start gap-2 text-xs bg-amber-50 border border-amber-200 rounded p-2">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-500 mt-0.5 shrink-0" />
              <span className="text-amber-700">
                OCR confidence is low ({Math.round(ans.ocr_confidence * 100)}%) — handwriting may be unclear.
                Review the OCR text tab and consider manual correction.
              </span>
            </div>
          )}
          {ans.requires_faculty_review && (
            <div className="flex items-start gap-2 text-xs bg-violet-50 border border-violet-200 rounded p-2">
              <AlertCircle className="w-3.5 h-3.5 text-violet-500 mt-0.5 shrink-0" />
              <span className="text-violet-700">
                Drawing score is based on text labels/annotations found via OCR. Faculty should verify
                actual line work, proportions, and drawing quality.
              </span>
            </div>
          )}

          <p className="text-sm text-gray-700 font-medium">{ans.question}</p>

          <div className="flex gap-1 border-b border-gray-100 pb-1">
            {(['feedback', 'ocr', 'detail'] as const).map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-3 py-1 rounded text-xs capitalize transition-colors ${tab === t ? 'bg-indigo-600 text-white' : 'text-gray-500 hover:text-gray-700'}`}
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
              {steps.length > 0 && (
                <div className="space-y-1 mt-2">
                  {steps.map((s: any, i: number) => (
                    <div key={i} className="flex items-center justify-between text-xs bg-gray-50 rounded px-3 py-1.5">
                      <span className="text-gray-600">{s.step_name || `Step ${i + 1}`}</span>
                      <span className={`font-medium ${(s.earned ?? 0) > 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                        {s.earned ?? 0}/{s.max ?? 0}
                      </span>
                    </div>
                  ))}
                </div>
              )}
              {violations.length > 0 && (
                <div className="space-y-1 mt-2">
                  {violations.map((v: any, i: number) => (
                    <div key={i} className="flex items-center gap-2 text-xs text-red-600 bg-red-50 rounded px-3 py-1">
                      <AlertCircle className="w-3 h-3 shrink-0" />
                      {v.rule}: {v.description} (−{v.deduction} marks)
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {tab === 'ocr' && (
            <div>
              <p className="text-[10px] text-gray-400 mb-1 flex items-center gap-1">
                <Eye className="w-3 h-3" />
                OCR-extracted text · confidence {Math.round(ans.ocr_confidence * 100)}%
              </p>
              <pre className="text-xs text-gray-700 bg-gray-50 rounded p-3 whitespace-pre-wrap max-h-60 overflow-y-auto font-mono leading-relaxed">
                {ans.ocr_text || '(no text detected on this page)'}
              </pre>
            </div>
          )}

          {tab === 'detail' && (
            <div className="text-xs space-y-2">
              {ans.q_type === 'theory' && (
                <div className="flex gap-6">
                  <span>Keyword score: <b>{((ans.detail?.keyword_score ?? 0) * 100).toFixed(0)}%</b></span>
                  <span>Semantic score: <b>{((ans.detail?.semantic_score ?? 0) * 100).toFixed(0)}%</b></span>
                </div>
              )}
              {ans.q_type === 'numerical' && Object.keys(errors).length > 0 && (
                <div className="bg-amber-50 rounded p-2">
                  <p className="font-medium text-amber-700 mb-1">Error types:</p>
                  {Object.entries(errors).map(([k, v]: any) => (
                    <div key={k} className="flex justify-between text-amber-600">
                      <span>{k.replace(/_/g, ' ')}</span><span>{v} error(s)</span>
                    </div>
                  ))}
                </div>
              )}
              {ans.q_type === 'drawing' && (
                <div className="space-y-2">
                  <div>
                    <p className="font-medium text-gray-600 mb-1">Labels found in drawing (OCR):</p>
                    <div className="flex flex-wrap gap-1">
                      {(ans.detail?.matched_parts ?? []).length === 0 && (ans.detail?.matched_dimensions ?? []).length === 0
                        ? <span className="text-gray-400">No expected labels detected via OCR</span>
                        : <>
                          {(ans.detail?.matched_parts ?? []).map((el: string, i: number) => (
                            <span key={i} className="badge bg-emerald-50 text-emerald-700">✓ {el}</span>
                          ))}
                          {(ans.detail?.matched_dimensions ?? []).map((el: string, i: number) => (
                            <span key={`d${i}`} className="badge bg-blue-50 text-blue-700">✓ {el}</span>
                          ))}
                        </>
                      }
                    </div>
                  </div>
                  {((ans.detail?.missing_parts ?? []).length > 0 || (ans.detail?.missing_dimensions ?? []).length > 0) && (
                    <div>
                      <p className="font-medium text-red-600 mb-1">Missing labels/dimensions:</p>
                      <div className="flex flex-wrap gap-1">
                        {(ans.detail?.missing_parts ?? []).map((el: string, i: number) => (
                          <span key={i} className="badge bg-red-50 text-red-600">✗ {el}</span>
                        ))}
                        {(ans.detail?.missing_dimensions ?? []).map((el: string, i: number) => (
                          <span key={`d${i}`} className="badge bg-red-50 text-red-600">✗ {el}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  <p className="text-gray-400 italic">
                    Line quality, proportions, and drawing correctness require faculty visual review.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function SingleReport({ report }: { report: ScriptReport }) {
  const pct = report.percentage
  const grade = pct >= 90 ? 'O' : pct >= 80 ? 'A+' : pct >= 70 ? 'A' : pct >= 60 ? 'B+' : pct >= 50 ? 'B' : pct >= 40 ? 'C' : 'F'
  const bannerColor = pct >= 70 ? 'bg-emerald-50 border-emerald-200' : pct >= 40 ? 'bg-amber-50 border-amber-200' : 'bg-red-50 border-red-200'

  return (
    <div className="space-y-4">
      {report.ocr_warning && (
        <div className="card p-3 bg-amber-50 border-amber-200 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-500 mt-0.5 shrink-0" />
          <p className="text-xs text-amber-700">
            Pages with low OCR confidence: {report.low_confidence_pages.join(', ')}.
            Handwriting may be unclear — review OCR text per question and override if needed.
          </p>
        </div>
      )}

      <div className={`card p-5 grid grid-cols-2 sm:grid-cols-4 gap-4 ${bannerColor}`}>
        <div>
          <p className="text-xs text-gray-500 mb-1">Total Score</p>
          <p className={`text-3xl font-bold ${pct >= 70 ? 'text-emerald-700' : pct >= 40 ? 'text-amber-700' : 'text-red-600'}`}>
            {report.total_score}<span className="text-base text-gray-400">/{report.max_total}</span>
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-1">Percentage</p>
          <p className="text-2xl font-bold text-gray-800">{report.percentage}%</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-1">Grade</p>
          <p className="text-2xl font-bold text-indigo-600">{grade}</p>
        </div>
        <div className="space-y-0.5">
          <p className="text-xs text-gray-500">Info</p>
          <p className="text-xs text-gray-600">📄 {report.ocr_pages} page(s)</p>
          <p className="text-xs text-gray-600">❓ {report.questions_evaluated} question(s)</p>
          <p className="text-xs text-gray-600">🔍 OCR conf: {Math.round(report.avg_ocr_confidence * 100)}%</p>
        </div>
      </div>

      <div className="flex gap-3 flex-wrap text-xs text-gray-500 items-center">
        <BarChart3 className="w-4 h-4 text-indigo-400" />
        {(['theory', 'numerical', 'drawing'] as const).map(t => {
          const count = report.answers.filter(a => a.q_type === t).length
          return count > 0 ? (
            <span key={t} className={`flex items-center gap-1 badge ${TYPE_COLOR[t]}`}>
              {TYPE_ICON[t]} {count} {t}
            </span>
          ) : null
        })}
        {report.answers.some(a => a.q_type === 'drawing') && (
          <span className="badge bg-violet-50 text-violet-600">Drawing: faculty review needed</span>
        )}
      </div>

      <div className="space-y-2">
        {report.answers.map(ans => <AnswerCard key={ans.q_number} ans={ans} />)}
      </div>

      <div className={`card p-4 flex items-center gap-3 ${pct >= 40 ? 'bg-emerald-50 border-emerald-200' : 'bg-red-50 border-red-200'}`}>
        {pct >= 40
          ? <CheckCircle className="w-5 h-5 text-emerald-600 shrink-0" />
          : <AlertCircle className="w-5 h-5 text-red-500 shrink-0" />}
        <p className={`text-sm font-medium ${pct >= 40 ? 'text-emerald-800' : 'text-red-700'}`}>
          {pct >= 40 ? 'Pass' : 'Fail'} — {grade} ({report.percentage}%) · {report.total_score}/{report.max_total} marks
        </p>
      </div>
    </div>
  )
}

function BatchSummary({ batch, onSelect }: { batch: BatchResult; onSelect: (r: ScriptReport) => void }) {
  const exportCSV = () => {
    const lines = ['Name,USN,Score,Max,Percentage,Grade,OCR_Confidence,Questions']
    batch.reports.forEach(r => {
      const pct = r.percentage
      const g = pct >= 90 ? 'O' : pct >= 80 ? 'A+' : pct >= 70 ? 'A' : pct >= 60 ? 'B+' : pct >= 50 ? 'B' : pct >= 40 ? 'C' : 'F'
      lines.push(
        `"${r.student_name}","${r.student_usn}",${r.total_score},${r.max_total},${r.percentage},${g},${Math.round((r.avg_ocr_confidence ?? 1) * 100)}%,${r.questions_evaluated}`
      )
    })
    const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob)
    a.download = `batch_grades_${batch.subject.replace(/\s+/g, '_')}.csv`; a.click()
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Class Average', value: `${batch.class_avg}%`, color: 'text-indigo-600' },
          { label: 'Total Students', value: String(batch.total_students), color: 'text-gray-800' },
          { label: 'Pass', value: String(batch.pass_count), color: 'text-emerald-600' },
          { label: 'Fail', value: String(batch.fail_count), color: 'text-red-500' },
        ].map(s => (
          <div key={s.label} className="card p-4">
            <p className="text-xs text-gray-500 mb-1">{s.label}</p>
            <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      <div className="flex justify-end">
        <button onClick={exportCSV} className="btn-secondary flex items-center gap-2 text-sm">
          <Download className="w-4 h-4" /> Export CSV
        </button>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-xs">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              <th className="text-left px-4 py-2.5 font-medium text-gray-500">Student</th>
              <th className="text-right px-4 py-2.5 font-medium text-gray-500">Score</th>
              <th className="text-right px-4 py-2.5 font-medium text-gray-500">%</th>
              <th className="text-center px-4 py-2.5 font-medium text-gray-500">Grade</th>
              <th className="text-center px-4 py-2.5 font-medium text-gray-500">OCR Conf</th>
              <th className="text-center px-4 py-2.5 font-medium text-gray-500">Result</th>
              <th className="px-4 py-2.5"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {batch.reports.map((r, i) => {
              const pct = r.percentage
              const g = pct >= 90 ? 'O' : pct >= 80 ? 'A+' : pct >= 70 ? 'A' : pct >= 60 ? 'B+' : pct >= 50 ? 'B' : pct >= 40 ? 'C' : 'F'
              return (
                <tr key={i} className="hover:bg-gray-50">
                  <td className="px-4 py-2.5">
                    <p className="font-medium text-gray-800">{r.student_name || `Student ${i + 1}`}</p>
                    {r.student_usn && <p className="text-gray-400">{r.student_usn}</p>}
                    {r.error && <p className="text-red-500 text-[10px]">{r.error}</p>}
                  </td>
                  <td className="px-4 py-2.5 text-right font-medium text-gray-700">{r.total_score}/{r.max_total}</td>
                  <td className={`px-4 py-2.5 text-right font-bold ${pct >= 70 ? 'text-emerald-600' : pct >= 40 ? 'text-amber-600' : 'text-red-500'}`}>{pct}%</td>
                  <td className="px-4 py-2.5 text-center font-bold text-indigo-600">{g}</td>
                  <td className="px-4 py-2.5 text-center">
                    <span className={`badge text-[10px] ${(r.avg_ocr_confidence ?? 1) >= 0.7 ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-600'}`}>
                      {Math.round((r.avg_ocr_confidence ?? 1) * 100)}%
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-center">
                    {r.error ? <span className="badge bg-red-50 text-red-600">Error</span>
                      : pct >= 40 ? <span className="badge bg-emerald-50 text-emerald-700">Pass</span>
                        : <span className="badge bg-red-50 text-red-600">Fail</span>}
                  </td>
                  <td className="px-4 py-2.5">
                    {!r.error && (
                      <button onClick={() => onSelect(r)} className="text-indigo-600 hover:underline text-[10px]">
                        Detail →
                      </button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

type Mode = 'single' | 'batch'

export default function AnswerScriptEvaluator() {
  const [mode, setMode] = useState<Mode>('single')
  const [referenceId, setReferenceId] = useState('')
  const [refs, setRefs] = useState<RefEntry[]>([])

  // Single mode
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [report, setReport] = useState<ScriptReport | null>(null)

  // Batch mode
  const [batchFiles, setBatchFiles] = useState<File[]>([])
  const [batchResult, setBatchResult] = useState<BatchResult | null>(null)
  const [selectedReport, setSelectedReport] = useState<ScriptReport | null>(null)

  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState('')
  const [error, setError] = useState('')

  const [deps, setDeps] = useState<DepStatus | null>(null)
  const fileRef    = useRef<HTMLInputElement>(null)
  const batchRef   = useRef<HTMLInputElement>(null)

  useEffect(() => {
    fetch('/api/health/deps')
      .then(r => r.json())
      .then(d => setDeps(d.ocr_pipeline))
      .catch(() => {})
    fetch('/api/training/references')
      .then(r => r.json())
      .then(d => setRefs(d.references || []))
      .catch(() => {})
  }, [])

  const acceptFile = useCallback((f: File) => {
    setFile(f); setReport(null); setError('')
  }, [])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) acceptFile(f)
  }, [acceptFile])

  const progressSteps = [
    'Uploading PDF…',
    'Converting pages to images…',
    'Running OCR on handwriting…',
    'Detecting question boundaries…',
    'Classifying answer types…',
    'Running AI evaluation engines…',
    'Computing scores…',
  ]

  const startProgress = () => {
    let si = 0
    setProgress(progressSteps[0])
    const t = setInterval(() => {
      si = (si + 1) % progressSteps.length
      setProgress(progressSteps[si])
    }, 2200)
    return t
  }

  const evaluate = async () => {
    if (!file) return
    setLoading(true); setError(''); setReport(null)
    const t = startProgress()
    try {
      const fd = new FormData()
      fd.append('file', file)
      if (referenceId) fd.append('reference_id', referenceId)
      const res = await fetch('/api/eval/script', { method: 'POST', body: fd })
      if (!res.ok) { const e = await res.json().catch(() => ({ detail: res.statusText })); throw new Error(e.detail) }
      setReport(await res.json())
    } catch (e: any) { setError(e.message || 'Evaluation failed') }
    finally { clearInterval(t); setLoading(false); setProgress('') }
  }

  const evaluateBatch = async () => {
    if (!batchFiles.length) return
    setLoading(true); setError(''); setBatchResult(null); setSelectedReport(null)
    const t = startProgress()
    try {
      const fd = new FormData()
      batchFiles.forEach(f => fd.append('files', f))
      if (referenceId) fd.append('reference_id', referenceId)
      const res = await fetch('/api/eval/script/batch', { method: 'POST', body: fd })
      if (!res.ok) { const e = await res.json().catch(() => ({ detail: res.statusText })); throw new Error(e.detail) }
      setBatchResult(await res.json())
    } catch (e: any) { setError(e.message || 'Batch evaluation failed') }
    finally { clearInterval(t); setLoading(false); setProgress('') }
  }

  return (
    <div>
      <Header
        title="Evaluate Answer Scripts"
        subtitle="Upload handwritten answer PDFs — OCR + Theory + Numerical + Drawing engines evaluate automatically"
      />
      <div className="p-6 space-y-5 max-w-4xl">

        {deps && !deps.ready && <DepBanner deps={deps} />}

        {/* Mode toggle */}
        <div className="flex gap-2">
          {(['single', 'batch'] as const).map(m => (
            <button
              key={m}
              onClick={() => { setMode(m); setError(''); setReport(null); setBatchResult(null) }}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${mode === m ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            >
              {m === 'single' ? <FileText className="w-4 h-4" /> : <Users className="w-4 h-4" />}
              {m === 'single' ? 'Single Script' : 'Batch (Class)'}
            </button>
          ))}
        </div>

        {/* Upload card */}
        <div className="card p-5 space-y-4">
          {mode === 'single' ? (
            <div
              onDrop={onDrop}
              onDragOver={e => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onClick={() => fileRef.current?.click()}
              className={`border-2 border-dashed rounded-xl flex flex-col items-center justify-center py-10 cursor-pointer transition-colors ${dragging ? 'border-indigo-500 bg-indigo-50' : 'border-gray-200 hover:border-indigo-300 hover:bg-gray-50'}`}
            >
              <input ref={fileRef} type="file" accept=".pdf,.png,.jpg,.jpeg" className="hidden" onChange={e => { const f = e.target.files?.[0]; if (f) acceptFile(f) }} />
              <Upload className={`w-7 h-7 mb-2 ${dragging ? 'text-indigo-500' : 'text-gray-300'}`} />
              {file ? (
                <div className="text-center">
                  <p className="text-sm font-medium text-indigo-700 flex items-center gap-2"><FileText className="w-4 h-4" />{file.name}</p>
                  <p className="text-xs text-gray-400 mt-1">{(file.size / 1024).toFixed(0)} KB · click to change</p>
                </div>
              ) : (
                <div className="text-center">
                  <p className="text-sm text-gray-500">Drop handwritten answer PDF here</p>
                  <p className="text-xs text-gray-400 mt-1">or click to browse · PDF, PNG, JPG</p>
                </div>
              )}
            </div>
          ) : (
            <div>
              <div
                onClick={() => batchRef.current?.click()}
                className="border-2 border-dashed rounded-xl flex flex-col items-center justify-center py-8 cursor-pointer hover:border-indigo-300 hover:bg-gray-50 transition-colors"
              >
                <input
                  ref={batchRef} type="file" multiple
                  accept=".pdf,.png,.jpg,.jpeg,.zip" className="hidden"
                  onChange={e => {
                    if (e.target.files) {
                      setBatchFiles(Array.from(e.target.files))
                      setBatchResult(null); setError('')
                    }
                  }}
                />
                <Upload className="w-7 h-7 mb-2 text-gray-300" />
                <p className="text-sm text-gray-500">Select multiple PDFs or a ZIP file</p>
                <p className="text-xs text-gray-400 mt-1">One file per student · up to 60 scripts at once</p>
              </div>
              {batchFiles.length > 0 && (
                <div className="mt-3 space-y-1 max-h-40 overflow-y-auto">
                  {batchFiles.map((f, i) => (
                    <div key={i} className="flex items-center justify-between text-xs bg-gray-50 rounded px-3 py-1.5">
                      <span className="text-gray-700 truncate">{f.name}</span>
                      <button onClick={() => setBatchFiles(prev => prev.filter((_, j) => j !== i))}>
                        <X className="w-3.5 h-3.5 text-gray-400 hover:text-red-500" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          <div>
            <label className="text-xs font-medium text-gray-600 mb-1 block">Reference Answer Scheme</label>
            {refs.length === 0 ? (
              <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2.5">
                <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />
                <p className="text-xs text-amber-700">
                  No reference schemes uploaded yet.{' '}
                  <a href="/eval/train" className="underline font-medium">Upload one in Train Engine</a>{' '}
                  to provide subject and marks automatically.
                </p>
              </div>
            ) : (
              <select
                className="input-field w-full text-sm"
                value={referenceId}
                onChange={e => setReferenceId(e.target.value)}
              >
                <option value="">— Select reference scheme (optional) —</option>
                {refs.map(r => (
                  <option key={r.id} value={r.id}>
                    {r.subject} · {r.marks_per_q ?? 10} marks/q{r.description ? ` · ${r.description}` : ''}
                  </option>
                ))}
              </select>
            )}
            {referenceId && (() => {
              const ref = refs.find(r => r.id === referenceId)
              return ref ? (
                <p className="text-[10px] text-gray-400 mt-1">
                  Subject: <b>{ref.subject}</b> · Marks per question: <b>{ref.marks_per_q ?? 10}</b>
                </p>
              ) : null
            })()}
            {!referenceId && refs.length > 0 && (
              <p className="text-[10px] text-gray-400 mt-1">Without a reference, subject defaults to "General" and marks default to 10 per question.</p>
            )}
          </div>

          <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-500 space-y-1">
            <p className="font-medium text-gray-600">How evaluation works:</p>
            <div className="flex flex-wrap gap-x-6 gap-y-1">
              <span className="flex items-center gap-1"><Brain className="w-3 h-3 text-indigo-500" /> Theory — keyword + semantic similarity scoring</span>
              <span className="flex items-center gap-1"><Calculator className="w-3 h-3 text-amber-500" /> Numerical — step-level grading + error detection</span>
              <span className="flex items-center gap-1"><PenTool className="w-3 h-3 text-emerald-500" /> Drawing — OCR label matching + faculty review flag</span>
            </div>
            <p className="text-gray-400 mt-1">Question type is auto-detected from the OCR text. Add "Q1." / "1." markers in the script for best segmentation.</p>
          </div>

          <button
            onClick={mode === 'single' ? evaluate : evaluateBatch}
            disabled={loading || (mode === 'single' ? !file : batchFiles.length === 0)}
            className="btn-primary w-full flex items-center justify-center gap-2 py-3 disabled:opacity-50"
          >
            {loading
              ? <><Loader2 className="w-4 h-4 animate-spin" />{progress}</>
              : mode === 'single'
                ? <><Brain className="w-4 h-4" />Evaluate Script</>
                : <><Users className="w-4 h-4" />Evaluate {batchFiles.length} Script{batchFiles.length !== 1 ? 's' : ''}</>}
          </button>
        </div>

        {error && (
          <div className="card p-4 bg-red-50 border-red-200 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-500 mt-0.5 shrink-0" />
            <div>
              <p className="text-sm font-semibold text-red-700">Evaluation failed</p>
              <p className="text-xs text-red-600 mt-1">{error}</p>
              {error.toLowerCase().includes('easyocr') || error.toLowerCase().includes('pdf2image') ? (
                <p className="text-xs text-red-500 font-mono mt-2 bg-red-100 rounded px-2 py-1">
                  pip install easyocr pdf2image Pillow &amp;&amp; apt-get install -y poppler-utils
                </p>
              ) : null}
            </div>
          </div>
        )}

        {/* Single result */}
        {report && mode === 'single' && <SingleReport report={report} />}

        {/* Batch result */}
        {batchResult && mode === 'batch' && !selectedReport && (
          <BatchSummary batch={batchResult} onSelect={setSelectedReport} />
        )}
        {selectedReport && (
          <div className="space-y-3">
            <button
              onClick={() => setSelectedReport(null)}
              className="flex items-center gap-2 text-sm text-indigo-600 hover:underline"
            >
              ← Back to class summary
            </button>
            <p className="text-sm font-semibold text-gray-800">
              {selectedReport.student_name} {selectedReport.student_usn && `· ${selectedReport.student_usn}`}
            </p>
            <SingleReport report={selectedReport} />
          </div>
        )}
      </div>
    </div>
  )
}
