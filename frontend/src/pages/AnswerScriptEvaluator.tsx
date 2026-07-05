import { useState, useRef, useCallback, useEffect } from 'react'
import { Header } from '../components/layout/Header'
import {
  Upload, FileText, ChevronDown, ChevronRight,
  CheckCircle, AlertCircle, Brain, Calculator, PenTool,
  Loader2, BarChart3, Eye, AlertTriangle, Download,
  Users, X, Sigma, GitBranch, LineChart, Layers, Check, Pencil,
} from 'lucide-react'

interface RefEntry {
  id: string
  subject: string
  q_type: string
  filename: string
  description: string
  marks_per_q: number
  questions_json?: string
}

interface SchemeQ { q_number: number; question?: string; max_marks?: number; type?: string }

interface RubricRow { criterion: string; max: number; awarded: number; reason: string }

interface AnswerResult {
  q_number: number
  q_type: string
  question: string
  ocr_text: string
  ai_score: number
  max_score: number
  confidence: number
  ocr_confidence: number
  low_confidence: boolean
  illegible?: boolean
  feedback: string
  page_start: number
  requires_faculty_review?: boolean
  grading_method?: string
  matched_by?: string
  match_similarity?: number | null
  rubric_mapping?: RubricRow[]
  covered?: string[]
  missing?: string[]
  strengths?: string[]
  weaknesses?: string[]
  suggestions?: string[]
  expected_answer?: string
  confidence_breakdown?: Record<string, number>
  overridden?: boolean
  faculty_approved?: boolean
  detail?: Record<string, any>
}

interface UnansweredQ { q_number: number; question: string; max_marks: number }

interface ScriptReport {
  result_id?: string
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
  blank_pages?: number[]
  needs_review_questions?: number[]
  unanswered_questions?: UnansweredQ[]
  ocr_methods?: string[]
  grading_path?: string
  grading_note?: string
  vision_key_detected?: boolean
  ocr_warning: boolean
  answers: AnswerResult[]
  deps?: Record<string, any>
  error?: string | null
}

interface EvalSummary {
  id: string
  student_name: string
  student_usn: string
  subject: string
  total_score: number
  max_total: number
  questions_evaluated: number
  evaluated_at: string
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
  pymupdf:   { available: boolean; error: string }
  tesseract: { available: boolean; error: string }
  cloud_vlm?:{ available: boolean; error: string }
  pillow:    { available: boolean; error: string }
  ready:     boolean
}

const TYPE_ICON: Record<string, React.ReactNode> = {
  theory:     <Brain className="w-3.5 h-3.5" />,
  numerical:  <Calculator className="w-3.5 h-3.5" />,
  diagram:    <PenTool className="w-3.5 h-3.5" />,
  drawing:    <PenTool className="w-3.5 h-3.5" />,
  derivation: <Sigma className="w-3.5 h-3.5" />,
  flowchart:  <GitBranch className="w-3.5 h-3.5" />,
  graph:      <LineChart className="w-3.5 h-3.5" />,
  mixed:      <Layers className="w-3.5 h-3.5" />,
}
const TYPE_COLOR: Record<string, string> = {
  theory:     'bg-indigo-50 text-indigo-700',
  numerical:  'bg-amber-50 text-amber-700',
  diagram:    'bg-emerald-50 text-emerald-700',
  drawing:    'bg-emerald-50 text-emerald-700',
  derivation: 'bg-sky-50 text-sky-700',
  flowchart:  'bg-fuchsia-50 text-fuchsia-700',
  graph:      'bg-rose-50 text-rose-700',
  mixed:      'bg-violet-50 text-violet-700',
}
const typeColor = (t: string) => TYPE_COLOR[t] || 'bg-gray-100 text-gray-600'
const typeIcon  = (t: string) => TYPE_ICON[t] || <FileText className="w-3.5 h-3.5" />
const ALL_TYPES = ['theory', 'numerical', 'diagram', 'derivation', 'flowchart', 'graph', 'mixed']

function ScorePill({ score, max }: { score: number; max: number }) {
  const pct = max > 0 ? (score / max) * 100 : 0
  const color = pct >= 70 ? 'text-emerald-600' : pct >= 40 ? 'text-amber-600' : 'text-red-500'
  return <span className={`font-bold text-base ${color}`}>{score}<span className="text-xs text-gray-400 ml-0.5">/ {max}</span></span>
}

function DepBanner({ deps }: { deps: DepStatus }) {
  if (deps.ready) return null
  const missing = [
    !deps.pymupdf?.available && 'pymupdf',
    !deps.tesseract?.available && 'tesseract',
  ].filter(Boolean)
  if (missing.length === 0) return null
  return (
    <div className="card p-4 bg-amber-50 border-amber-300 flex items-start gap-3">
      <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
      <div>
        <p className="text-sm font-semibold text-amber-800">OCR dependencies not installed</p>
        <p className="text-xs text-amber-700 mt-0.5">
          Missing: <code className="bg-amber-100 px-1 rounded">{missing.join(', ')}</code>
        </p>
        <p className="text-xs text-amber-600 mt-2 font-mono bg-amber-100 px-2 py-1 rounded">
          pip install pymupdf pytesseract Pillow
        </p>
      </div>
    </div>
  )
}

/* Small note when no cloud vision key is set — explains why handwriting may be weak */
function OcrModeNote({ deps }: { deps: DepStatus }) {
  if (deps.cloud_vlm?.available) {
    return (
      <div className="card p-3 bg-emerald-50 border-emerald-200 flex items-center gap-2">
        <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
        <p className="text-xs text-emerald-700">
          Cloud vision OCR is active — handwriting, equations and diagrams are read by a vision model.
        </p>
      </div>
    )
  }
  return (
    <div className="card p-3 bg-sky-50 border-sky-200 flex items-start gap-2">
      <AlertCircle className="w-4 h-4 text-sky-600 mt-0.5 shrink-0" />
      <p className="text-xs text-sky-700">
        No vision API key set — handwriting is read by Tesseract (weaker) and grading uses the
        semantic fallback. Add <code className="bg-sky-100 px-1 rounded">GEMINI_API_KEY</code> to a{' '}
        <code className="bg-sky-100 px-1 rounded">.env</code> file at the project root and restart the
        backend for accurate results.
      </p>
    </div>
  )
}

/** Read a fetch Response as JSON without ever throwing a cryptic browser
 * parse error — an empty/non-JSON body almost always means the backend was
 * mid-restart (uvicorn --reload) or crashed, so say that plainly instead. */
async function safeJson(res: Response): Promise<any> {
  const raw = await res.text()
  if (!raw) {
    throw new Error(
      `Backend gave an empty response (HTTP ${res.status}). It was likely still restarting after a `
      + `git pull / .env change — wait for "Application startup complete" in the backend terminal and try again.`
    )
  }
  try {
    return JSON.parse(raw)
  } catch {
    throw new Error(`Backend returned non-JSON (HTTP ${res.status}): ${raw.slice(0, 300)}`)
  }
}

function chip(label: string, cls: string, key: string | number) {
  return <span key={key} className={`badge text-[10px] ${cls}`}>{label}</span>
}

function AnswerCard({ ans, resultId, onUpdate }: {
  ans: AnswerResult
  resultId?: string
  onUpdate?: () => void
}) {
  const [open, setOpen]   = useState(false)
  const [tab, setTab]     = useState<'reasoning' | 'ocr' | 'expected'>('reasoning')
  const [editMarks, setEditMarks] = useState(false)
  const [markVal, setMarkVal]     = useState(String(ans.ai_score))
  const [fbEdit, setFbEdit]       = useState(false)
  const [fbVal, setFbVal]         = useState(ans.feedback || '')
  const [saving, setSaving]       = useState(false)

  const rubric   = ans.rubric_mapping ?? []
  const covered  = ans.covered ?? ans.detail?.matched_keywords ?? []
  const missing  = ans.missing ?? ans.detail?.missing_keywords ?? []
  const strengths   = ans.strengths ?? []
  const weaknesses  = ans.weaknesses ?? []
  const suggestions = ans.suggestions ?? []
  const cb = ans.confidence_breakdown ?? {}

  const override = async (action: string, extra: Record<string, any> = {}) => {
    if (!resultId) return
    setSaving(true)
    try {
      await fetch(`/api/eval/results/${resultId}/override`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ q_number: ans.q_number, action, faculty: 'faculty', ...extra }),
      })
      onUpdate?.()
    } catch { /* ignore */ }
    finally { setSaving(false); setEditMarks(false); setFbEdit(false) }
  }

  return (
    <div className="card overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-gray-50 transition-colors"
        onClick={() => setOpen(o => !o)}
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-sm font-semibold text-gray-700 w-6 shrink-0">Q{ans.q_number}</span>
          <span className={`flex items-center gap-1 badge text-xs shrink-0 ${typeColor(ans.q_type)}`}>
            {typeIcon(ans.q_type)} {ans.q_type}
          </span>
          {ans.overridden && chip('✎ overridden', 'bg-blue-50 text-blue-600', 'ov')}
          {ans.faculty_approved && chip('✓ approved', 'bg-emerald-50 text-emerald-700', 'ap')}
          {ans.illegible && chip('illegible', 'bg-red-50 text-red-600', 'il')}
          {ans.low_confidence && !ans.illegible &&
            chip(`⚠ Low OCR ${Math.round(ans.ocr_confidence * 100)}%`, 'bg-amber-50 text-amber-600', 'lc')}
          {ans.requires_faculty_review && !ans.faculty_approved &&
            chip('review needed', 'bg-violet-50 text-violet-600', 'rv')}
          <span className="text-xs text-gray-400 truncate hidden sm:block">{ans.question}</span>
        </div>
        <div className="flex items-center gap-4 shrink-0 ml-2">
          <div className="text-right">
            <ScorePill score={ans.ai_score} max={ans.max_score} />
            <p className="text-[10px] text-gray-400">{Math.round(ans.confidence * 100)}% confidence</p>
          </div>
          {open ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
        </div>
      </button>

      {open && (
        <div className="border-t border-gray-100 px-5 py-4 space-y-3">
          {ans.illegible && (
            <div className="flex items-start gap-2 text-xs bg-amber-50 border border-amber-200 rounded p-2">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-500 mt-0.5 shrink-0" />
              <span className="text-amber-700">
                Handwriting was hard to read (low OCR confidence). Marks are still awarded from what was
                read against the scheme — check the OCR Text tab and adjust below if needed.
              </span>
            </div>
          )}

          <p className="text-sm text-gray-700 font-medium">{ans.question}</p>

          {/* how this answer was matched to the scheme */}
          {ans.matched_by && (
            <p className="text-[10px] text-gray-400">
              Matched to Q{ans.q_number} by{' '}
              {ans.matched_by === 'detected_number' ? 'detected question number'
                : ans.matched_by === 'semantic' ? `semantic similarity${ans.match_similarity != null ? ` (${Math.round(ans.match_similarity * 100)}%)` : ''}`
                : ans.matched_by}
              {ans.grading_method && <> · graded via {ans.grading_method.replace(/_/g, ' ')}</>}
            </p>
          )}

          {/* Rubric breakdown */}
          {rubric.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-semibold text-gray-600">Rubric</p>
              {rubric.map((r, i) => (
                <div key={i} className="text-xs bg-gray-50 rounded px-3 py-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600">{r.criterion}</span>
                    <span className={`font-semibold ${r.awarded >= r.max ? 'text-emerald-600' : r.awarded > 0 ? 'text-amber-600' : 'text-red-500'}`}>
                      {r.awarded} / {r.max}
                    </span>
                  </div>
                  {r.reason && <p className="text-[11px] text-gray-400 mt-0.5">{r.reason}</p>}
                </div>
              ))}
            </div>
          )}

          <div className="flex gap-1 border-b border-gray-100 pb-1">
            {(['reasoning', 'ocr', 'expected'] as const).map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-3 py-1 rounded text-xs capitalize transition-colors ${tab === t ? 'bg-indigo-600 text-white' : 'text-gray-500 hover:text-gray-700'}`}
              >
                {t === 'ocr' ? 'OCR Text' : t === 'expected' ? 'Expected Answer' : 'AI Reasoning'}
              </button>
            ))}
          </div>

          {tab === 'reasoning' && (
            <div className="space-y-2">
              <p className="text-sm text-gray-600">{ans.feedback}</p>
              {(covered.length > 0 || missing.length > 0) && (
                <div className="flex flex-wrap gap-1">
                  {covered.map((k: string, i: number) => chip(`✓ ${k}`, 'bg-emerald-50 text-emerald-700', `c${i}`))}
                  {missing.map((k: string, i: number) => chip(`✗ ${k}`, 'bg-red-50 text-red-600', `m${i}`))}
                </div>
              )}
              {strengths.length > 0 && (
                <div>
                  <p className="text-[11px] font-semibold text-emerald-700 mt-1">Strengths</p>
                  <ul className="list-disc list-inside text-xs text-gray-500">{strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>
                </div>
              )}
              {weaknesses.length > 0 && (
                <div>
                  <p className="text-[11px] font-semibold text-red-600 mt-1">Weaknesses</p>
                  <ul className="list-disc list-inside text-xs text-gray-500">{weaknesses.map((s, i) => <li key={i}>{s}</li>)}</ul>
                </div>
              )}
              {suggestions.length > 0 && (
                <div>
                  <p className="text-[11px] font-semibold text-indigo-600 mt-1">Suggestions</p>
                  <ul className="list-disc list-inside text-xs text-gray-500">{suggestions.map((s, i) => <li key={i}>{s}</li>)}</ul>
                </div>
              )}
              {Object.keys(cb).length > 0 && (
                <div className="flex flex-wrap gap-2 pt-1">
                  {Object.entries(cb).map(([k, v]) => (
                    <span key={k} className="text-[10px] text-gray-400">
                      {k.replace(/_/g, ' ')}: <b className="text-gray-500">{Math.round((v as number) * 100)}%</b>
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {tab === 'ocr' && (
            <div>
              <p className="text-[10px] text-gray-400 mb-1 flex items-center gap-1">
                <Eye className="w-3 h-3" /> OCR-extracted text · confidence {Math.round(ans.ocr_confidence * 100)}%
              </p>
              <pre className="text-xs text-gray-700 bg-gray-50 rounded p-3 whitespace-pre-wrap max-h-60 overflow-y-auto font-mono leading-relaxed">
                {ans.ocr_text || '(no text detected on this page)'}
              </pre>
            </div>
          )}

          {tab === 'expected' && (
            <pre className="text-xs text-gray-600 bg-gray-50 rounded p-3 whitespace-pre-wrap max-h-60 overflow-y-auto leading-relaxed">
              {ans.expected_answer || '(no reference answer provided in the scheme)'}
            </pre>
          )}

          {/* Faculty override controls */}
          {resultId && (
            <div className="border-t border-gray-100 pt-3 flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-semibold text-gray-500">Faculty:</span>
              {editMarks ? (
                <span className="flex items-center gap-1">
                  <input
                    type="number" step="0.5" min="0" max={ans.max_score}
                    value={markVal} onChange={e => setMarkVal(e.target.value)}
                    className="input-field w-20 text-xs py-1"
                  />
                  <button disabled={saving} onClick={() => override('adjust_marks', { new_marks: parseFloat(markVal) })}
                    className="btn-primary text-[11px] px-2 py-1 flex items-center gap-1">
                    {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />} Save
                  </button>
                  <button onClick={() => setEditMarks(false)} className="text-[11px] text-gray-400">Cancel</button>
                </span>
              ) : (
                <button onClick={() => { setMarkVal(String(ans.ai_score)); setEditMarks(true) }}
                  className="btn-secondary text-[11px] px-2 py-1 flex items-center gap-1">
                  <Pencil className="w-3 h-3" /> Adjust marks
                </button>
              )}
              <button disabled={saving} onClick={() => override('approve')}
                className="btn-secondary text-[11px] px-2 py-1 flex items-center gap-1 text-emerald-700">
                <Check className="w-3 h-3" /> Approve
              </button>
              {fbEdit ? (
                <span className="flex items-center gap-1 w-full mt-1">
                  <input value={fbVal} onChange={e => setFbVal(e.target.value)}
                    className="input-field flex-1 text-xs py-1" placeholder="Rewrite feedback…" />
                  <button disabled={saving} onClick={() => override('rewrite_feedback', { new_feedback: fbVal })}
                    className="btn-primary text-[11px] px-2 py-1">Save</button>
                  <button onClick={() => setFbEdit(false)} className="text-[11px] text-gray-400">Cancel</button>
                </span>
              ) : (
                <button onClick={() => { setFbVal(ans.feedback || ''); setFbEdit(true) }}
                  className="btn-secondary text-[11px] px-2 py-1 flex items-center gap-1">
                  <Pencil className="w-3 h-3" /> Rewrite feedback
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function SingleReport({ report, resultId, onUpdate }: {
  report: ScriptReport
  resultId?: string
  onUpdate?: () => void
}) {
  const rid = resultId ?? report.result_id
  const reviewCount = report.needs_review_questions?.length ?? report.answers.filter(a => a.requires_faculty_review).length
  return (
    <div className="space-y-4">
      {report.grading_note && (
        <div className="card p-4 bg-red-50 border-red-300 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-red-500 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-red-700">Why this scored low / 0</p>
            <p className="text-xs text-red-600 mt-1">{report.grading_note}</p>
          </div>
        </div>
      )}
      {report.ocr_warning && !report.grading_note && report.low_confidence_pages?.length > 0 && (
        <div className="card p-3 bg-amber-50 border-amber-200 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-500 mt-0.5 shrink-0" />
          <p className="text-xs text-amber-700">
            Low OCR confidence on page(s): {report.low_confidence_pages.join(', ')} — handwriting may be unclear.
          </p>
        </div>
      )}

      {/* Score summary — marks only */}
      <div className="card p-5 bg-indigo-50 border-indigo-200">
        <p className="text-xs text-gray-500 mb-1">Marks Obtained</p>
        <p className="text-5xl font-bold text-indigo-700">
          {report.total_score}
          <span className="text-2xl text-gray-400 font-normal"> / {report.max_total}</span>
        </p>
        <div className="flex gap-4 mt-3 text-xs text-gray-500 flex-wrap">
          <span>{report.questions_evaluated} question(s) evaluated</span>
          <span>·</span>
          <span>OCR confidence: {Math.round(report.avg_ocr_confidence * 100)}%</span>
          {report.subject && <><span>·</span><span>{report.subject}</span></>}
          {report.grading_path === 'vision'
            ? <><span>·</span><span className="text-emerald-600 font-medium">Graded by vision AI</span></>
            : report.ocr_methods && report.ocr_methods.length > 0 &&
              <><span>·</span><span>via {report.ocr_methods.join(', ')}</span></>}
        </div>
      </div>

      {/* Status strip: review / blank / unanswered */}
      <div className="flex gap-3 flex-wrap text-xs items-center">
        <BarChart3 className="w-4 h-4 text-indigo-400" />
        {ALL_TYPES.map(t => {
          const count = report.answers.filter(a => a.q_type === t).length
          return count > 0 ? (
            <span key={t} className={`flex items-center gap-1 badge ${typeColor(t)}`}>
              {typeIcon(t)} {count} {t}
            </span>
          ) : null
        })}
        {reviewCount > 0 && chip(`${reviewCount} need faculty review`, 'bg-violet-50 text-violet-600', 'rc')}
        {report.blank_pages && report.blank_pages.length > 0 &&
          chip(`${report.blank_pages.length} blank page(s) skipped`, 'bg-gray-100 text-gray-500', 'bp')}
      </div>

      {report.unanswered_questions && report.unanswered_questions.length > 0 && (
        <div className="card p-3 bg-gray-50 border-gray-200">
          <p className="text-xs font-semibold text-gray-600 mb-1">Not attempted (0 marks)</p>
          <div className="flex flex-wrap gap-1">
            {report.unanswered_questions.map(u =>
              chip(`Q${u.q_number} · ${u.max_marks}m`, 'bg-red-50 text-red-500', u.q_number))}
          </div>
        </div>
      )}

      <div className="space-y-2">
        {report.answers.map(ans => (
          <AnswerCard key={ans.q_number} ans={ans} resultId={rid} onUpdate={onUpdate} />
        ))}
      </div>
    </div>
  )
}

function BatchSummary({ batch, onSelect }: { batch: BatchResult; onSelect: (r: ScriptReport) => void }) {
  const exportCSV = () => {
    const lines = ['Name,USN,Marks,MaxMarks,OCR_Confidence,Questions,NeedsReview']
    batch.reports.forEach(r => {
      const review = (r.needs_review_questions?.length ?? 0)
      lines.push(
        `"${r.student_name}","${r.student_usn}",${r.total_score},${r.max_total},${Math.round((r.avg_ocr_confidence ?? 1) * 100)}%,${r.questions_evaluated},${review}`
      )
    })
    const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob)
    a.download = `batch_marks_${batch.subject.replace(/\s+/g, '_')}.csv`; a.click()
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Class Average', value: `${batch.class_avg}%`, color: 'text-indigo-600' },
          { label: 'Total Scripts', value: String(batch.total_students), color: 'text-gray-800' },
          { label: 'Need Review', value: String(batch.reports.reduce((n, r) => n + (r.needs_review_questions?.length ?? 0), 0)), color: 'text-violet-600' },
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
              <th className="text-left px-4 py-2.5 font-medium text-gray-500">Student / File</th>
              <th className="text-right px-4 py-2.5 font-medium text-gray-500">Marks</th>
              <th className="text-center px-4 py-2.5 font-medium text-gray-500">OCR Conf</th>
              <th className="text-center px-4 py-2.5 font-medium text-gray-500">Review</th>
              <th className="px-4 py-2.5"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {batch.reports.map((r, i) => {
              const review = r.needs_review_questions?.length ?? 0
              return (
                <tr key={i} className="hover:bg-gray-50">
                  <td className="px-4 py-2.5">
                    <p className="font-medium text-gray-800">{r.student_name || `Script ${i + 1}`}</p>
                    {r.student_usn && <p className="text-gray-400">{r.student_usn}</p>}
                    {r.error && <p className="text-red-500 text-[10px]">{r.error}</p>}
                  </td>
                  <td className="px-4 py-2.5 text-right font-semibold text-gray-700">{r.total_score} / {r.max_total}</td>
                  <td className="px-4 py-2.5 text-center">
                    <span className={`badge text-[10px] ${(r.avg_ocr_confidence ?? 1) >= 0.7 ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-600'}`}>
                      {Math.round((r.avg_ocr_confidence ?? 1) * 100)}%
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-center">
                    {review > 0
                      ? <span className="badge bg-violet-50 text-violet-600 text-[10px]">{review}</span>
                      : <span className="text-gray-300">—</span>}
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

type Mode = 'single' | 'batch' | 'paste'

export default function AnswerScriptEvaluator() {
  const [mode, setMode] = useState<Mode>('single')
  const [referenceId, setReferenceId] = useState('')
  const [refs, setRefs] = useState<RefEntry[]>([])

  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [report, setReport] = useState<ScriptReport | null>(null)

  const [batchFiles, setBatchFiles] = useState<File[]>([])
  const [batchResult, setBatchResult] = useState<BatchResult | null>(null)
  const [selectedReport, setSelectedReport] = useState<ScriptReport | null>(null)

  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState('')
  const [error, setError] = useState('')

  // Paste mode
  const [pasteTexts, setPasteTexts] = useState<Record<number, string>>({})
  const [studentName, setStudentName] = useState('')

  // API self-test
  const [selftest, setSelftest] = useState<any>(null)
  const [testing, setTesting] = useState(false)

  const [deps, setDeps] = useState<DepStatus | null>(null)
  const [history, setHistory] = useState<EvalSummary[]>([])
  const [historyReport, setHistoryReport] = useState<ScriptReport | null>(null)
  const [historyId, setHistoryId] = useState('')
  const fileRef    = useRef<HTMLInputElement>(null)
  const batchRef   = useRef<HTMLInputElement>(null)

  const loadHistory = () => {
    fetch('/api/eval/results')
      .then(r => r.json())
      .then(d => setHistory(d.results || []))
      .catch(() => {})
  }

  useEffect(() => {
    fetch('/api/health/deps')
      .then(r => r.json())
      .then(d => setDeps(d.ocr_pipeline))
      .catch(() => {})
    fetch('/api/training/references')
      .then(r => r.json())
      .then(d => setRefs(d.references || []))
      .catch(() => {})
    loadHistory()
  }, [])

  const reload = (id: string, setter: (r: ScriptReport) => void) =>
    fetch(`/api/eval/results/${id}`).then(r => r.json()).then(setter).catch(() => {})

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
    'Detecting blank pages…',
    'Running OCR on handwriting…',
    'Detecting question numbers…',
    'Matching answers to the scheme…',
    'Grading against the rubric…',
    'Scoring confidence…',
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
      const data = await safeJson(res)
      if (!res.ok) throw new Error(data.detail || 'Evaluation failed')
      setReport(data)
      loadHistory()
    } catch (e: any) { setError(e.message || 'Evaluation failed') }
    finally { clearInterval(t); setLoading(false); setProgress('') }
  }

  const selectedRef = refs.find(r => r.id === referenceId)
  const schemeQs: SchemeQ[] = (() => {
    if (!selectedRef?.questions_json) return []
    try { return JSON.parse(selectedRef.questions_json) } catch { return [] }
  })()

  const runSelftest = async () => {
    setTesting(true); setSelftest(null)
    try {
      const r = await fetch('/api/eval/selftest')
      setSelftest(await safeJson(r))
    } catch (e: any) {
      setSelftest({ error: e.message || 'Could not reach the backend — is uvicorn running on port 8000?' })
    }
    finally { setTesting(false) }
  }

  const gradePaste = async () => {
    const answers = Object.entries(pasteTexts)
      .filter(([, t]) => (t as string).trim())
      .map(([q, t]) => ({ q_number: Number(q), text: t }))
    if (!answers.length) { setError('Type at least one answer to grade.'); return }
    setLoading(true); setError(''); setReport(null)
    try {
      const res = await fetch('/api/eval/script/text', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reference_id: referenceId, student_name: studentName, answers }),
      })
      const data = await safeJson(res)
      if (!res.ok) throw new Error(data.detail || 'Grading failed')
      setReport(data)
      loadHistory()
    } catch (e: any) { setError(e.message || 'Grading failed') }
    finally { setLoading(false) }
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
      const data = await safeJson(res)
      if (!res.ok) throw new Error(data.detail || 'Batch evaluation failed')
      setBatchResult(data)
    } catch (e: any) { setError(e.message || 'Batch evaluation failed') }
    finally { clearInterval(t); setLoading(false); setProgress('') }
  }

  return (
    <div>
      <Header
        title="Evaluate Answer Scripts"
        subtitle="Upload handwritten answer PDFs — OCR → detect → match → rubric grading → confidence, with faculty override"
      />
      <div className="p-6 space-y-5 max-w-4xl">

        {deps && !deps.ready && <DepBanner deps={deps} />}
        {deps && deps.ready && <OcrModeNote deps={deps} />}

        {/* Mode toggle */}
        <div className="flex gap-2 flex-wrap items-center">
          {(['single', 'batch', 'paste'] as const).map(m => (
            <button
              key={m}
              onClick={() => { setMode(m); setError(''); setReport(null); setBatchResult(null) }}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${mode === m ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            >
              {m === 'single' ? <FileText className="w-4 h-4" /> : m === 'batch' ? <Users className="w-4 h-4" /> : <Pencil className="w-4 h-4" />}
              {m === 'single' ? 'Single Script' : m === 'batch' ? 'Batch (Class)' : 'Paste Answers'}
            </button>
          ))}
          <button onClick={runSelftest} disabled={testing}
            className="ml-auto btn-secondary text-xs px-3 py-2 flex items-center gap-1">
            {testing ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle className="w-3 h-3" />} Test API key
          </button>
        </div>

        {/* Self-test result */}
        {selftest && (
          <div className={`card p-3 text-xs ${selftest.any_working ? 'bg-emerald-50 border-emerald-200' : 'bg-red-50 border-red-200'}`}>
            {selftest.any_working
              ? <p className="text-emerald-700 font-medium">✓ API key works — vision grading is available.</p>
              : <p className="text-red-700 font-medium">✗ No working API key — will use offline grading. Details:</p>}
            {selftest.providers && Object.entries(selftest.providers).map(([name, p]: any) => (
              <p key={name} className={`mt-1 ${p.ok ? 'text-emerald-600' : 'text-red-500'}`}>
                <b>{name}</b>{p.model ? ` (${p.model})` : ''}: {p.ok ? 'OK' : (p.error || `HTTP ${p.status}`)}
              </p>
            ))}
            {selftest.error && <p className="text-red-500 mt-1">{selftest.error}</p>}
          </div>
        )}

        {/* Upload card */}
        <div className="card p-5 space-y-4">
          {mode === 'paste' ? (
            <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-3 text-xs text-indigo-700">
              <b>Guaranteed grading — no OCR, no API key needed.</b> Pick your answer scheme below,
              type or paste what the student wrote for each question, and grade. Marks are computed
              against the scheme every time.
            </div>
          ) : mode === 'single' ? (
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
                  <p className="text-xs text-gray-400 mt-1">or click to browse · PDF, PNG, JPG · multi-page, shuffled order OK</p>
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
                  to provide questions, expected answers and marks automatically.
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
            {!referenceId && refs.length > 0 && mode !== 'paste' && (
              <p className="text-[10px] text-gray-400 mt-1">Without a scheme, answers are graded on general correctness and everything is flagged for faculty review.</p>
            )}
          </div>

          {/* Paste-per-question inputs */}
          {mode === 'paste' && (
            <div className="space-y-3">
              <input
                type="text" placeholder="Student name / roll no (optional)"
                value={studentName} onChange={e => setStudentName(e.target.value)}
                className="input-field w-full text-sm"
              />
              {schemeQs.length === 0 ? (
                <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded p-2">
                  Select an answer scheme above to load its questions here.
                </p>
              ) : (
                schemeQs.map(q => (
                  <div key={q.q_number}>
                    <label className="text-xs font-medium text-gray-600 mb-1 flex items-center gap-2">
                      <span className="badge bg-indigo-50 text-indigo-700 text-[10px]">Q{q.q_number}</span>
                      <span className="truncate">{q.question || `Question ${q.q_number}`}</span>
                      <span className="text-gray-400 ml-auto shrink-0">{q.max_marks ?? 10} marks</span>
                    </label>
                    <textarea
                      rows={3}
                      placeholder={`Type or paste the student's answer for Q${q.q_number}…`}
                      value={pasteTexts[q.q_number] || ''}
                      onChange={e => setPasteTexts(prev => ({ ...prev, [q.q_number]: e.target.value }))}
                      className="input-field w-full text-sm font-mono"
                    />
                  </div>
                ))
              )}
            </div>
          )}

          {mode !== 'paste' && (
            <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-500 space-y-1">
              <p className="font-medium text-gray-600">The engine automatically:</p>
              <div className="flex flex-wrap gap-x-6 gap-y-1">
                <span className="flex items-center gap-1"><Eye className="w-3 h-3 text-sky-500" /> Skips blank pages, reads handwriting</span>
                <span className="flex items-center gap-1"><GitBranch className="w-3 h-3 text-fuchsia-500" /> Matches shuffled answers to questions</span>
                <span className="flex items-center gap-1"><Brain className="w-3 h-3 text-indigo-500" /> Grades each type against its rubric</span>
                <span className="flex items-center gap-1"><AlertCircle className="w-3 h-3 text-violet-500" /> Flags low-confidence answers for review</span>
              </div>
            </div>
          )}

          <button
            onClick={mode === 'single' ? evaluate : mode === 'batch' ? evaluateBatch : gradePaste}
            disabled={loading || (mode === 'single' ? !file : mode === 'batch' ? batchFiles.length === 0 : Object.values(pasteTexts).every(t => !t.trim()))}
            className="btn-primary w-full flex items-center justify-center gap-2 py-3 disabled:opacity-50"
          >
            {loading
              ? <><Loader2 className="w-4 h-4 animate-spin" />{progress || 'Grading…'}</>
              : mode === 'single'
                ? <><Brain className="w-4 h-4" />Evaluate Script</>
                : mode === 'batch'
                  ? <><Users className="w-4 h-4" />Evaluate {batchFiles.length} Script{batchFiles.length !== 1 ? 's' : ''}</>
                  : <><Pencil className="w-4 h-4" />Grade Answers</>}
          </button>
        </div>

        {error && (
          <div className="card p-4 bg-red-50 border-red-200 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-500 mt-0.5 shrink-0" />
            <div>
              <p className="text-sm font-semibold text-red-700">Evaluation failed</p>
              <p className="text-xs text-red-600 mt-1">{error}</p>
            </div>
          </div>
        )}

        {/* Single result */}
        {report && mode === 'single' && (
          <SingleReport
            report={report}
            resultId={report.result_id}
            onUpdate={() => report.result_id && reload(report.result_id, setReport)}
          />
        )}

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
            <SingleReport
              report={selectedReport}
              resultId={selectedReport.result_id}
              onUpdate={() => selectedReport.result_id && reload(selectedReport.result_id, setSelectedReport)}
            />
          </div>
        )}

        {/* History of all evaluated scripts */}
        {history.length > 0 && !historyReport && (
          <div className="card p-5 space-y-3">
            <p className="text-sm font-semibold text-gray-800">Past Evaluations</p>
            <div className="overflow-hidden rounded-lg border border-gray-100">
              <table className="w-full text-xs">
                <thead className="bg-gray-50 border-b border-gray-100">
                  <tr>
                    <th className="text-left px-4 py-2.5 font-medium text-gray-500">Student / File</th>
                    <th className="text-left px-4 py-2.5 font-medium text-gray-500">Subject</th>
                    <th className="text-right px-4 py-2.5 font-medium text-gray-500">Marks</th>
                    <th className="text-center px-4 py-2.5 font-medium text-gray-500">Questions</th>
                    <th className="text-right px-4 py-2.5 font-medium text-gray-500">Date</th>
                    <th className="px-4 py-2.5"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {history.map(h => (
                    <tr key={h.id} className="hover:bg-gray-50">
                      <td className="px-4 py-2.5 font-medium text-gray-800">{h.student_name || '(unnamed)'}</td>
                      <td className="px-4 py-2.5 text-gray-500">{h.subject}</td>
                      <td className="px-4 py-2.5 text-right font-semibold text-gray-700">{h.total_score} / {h.max_total}</td>
                      <td className="px-4 py-2.5 text-center text-gray-500">{h.questions_evaluated}</td>
                      <td className="px-4 py-2.5 text-right text-gray-400">{new Date(h.evaluated_at).toLocaleDateString()}</td>
                      <td className="px-4 py-2.5">
                        <button
                          className="text-indigo-600 hover:underline"
                          onClick={() => { setHistoryId(h.id); reload(h.id, setHistoryReport) }}
                        >
                          View →
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* History drill-down */}
        {historyReport && (
          <div className="space-y-3">
            <button
              onClick={() => { setHistoryReport(null); setHistoryId('') }}
              className="flex items-center gap-2 text-sm text-indigo-600 hover:underline"
            >
              ← Back to history
            </button>
            <p className="text-sm font-semibold text-gray-800">{historyReport.student_name}</p>
            <SingleReport
              report={historyReport}
              resultId={historyId}
              onUpdate={() => { reload(historyId, setHistoryReport); loadHistory() }}
            />
          </div>
        )}
      </div>
    </div>
  )
}
