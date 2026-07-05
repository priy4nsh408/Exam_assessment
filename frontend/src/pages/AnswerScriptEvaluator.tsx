import { useState, useRef, useCallback, useEffect } from 'react'
import { Header } from '../components/layout/Header'
import {
  Upload, FileText, ChevronDown, ChevronRight,
  AlertCircle, Brain, Calculator, PenTool,
  Loader2, Sparkles, Users, X, Sigma, GitBranch, LineChart, Layers,
  Check, Pencil, Circle, ClipboardList, ScanEye, ArrowRight,
  History as HistoryIcon,
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
  ocr_warning: boolean
  answers: AnswerResult[]
  deps?: Record<string, any>
  error?: string | null
  grading_path?: string
  grading_note?: string
  vision_key_detected?: boolean
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
  cloud_vlm?:{ available: boolean; error: string; via?: string }
  pillow:    { available: boolean; error: string }
  ready:     boolean
}

/* ── shared visual language ─────────────────────────────────────────────── */

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
  theory:     'bg-indigo-50 text-indigo-700 ring-indigo-200',
  numerical:  'bg-amber-50 text-amber-700 ring-amber-200',
  diagram:    'bg-emerald-50 text-emerald-700 ring-emerald-200',
  drawing:    'bg-emerald-50 text-emerald-700 ring-emerald-200',
  derivation: 'bg-sky-50 text-sky-700 ring-sky-200',
  flowchart:  'bg-fuchsia-50 text-fuchsia-700 ring-fuchsia-200',
  graph:      'bg-rose-50 text-rose-700 ring-rose-200',
  mixed:      'bg-violet-50 text-violet-700 ring-violet-200',
}
const TYPE_BAR: Record<string, string> = {
  theory: 'bg-indigo-500', numerical: 'bg-amber-500', diagram: 'bg-emerald-500',
  drawing: 'bg-emerald-500', derivation: 'bg-sky-500', flowchart: 'bg-fuchsia-500',
  graph: 'bg-rose-500', mixed: 'bg-violet-500',
}
const typeColor = (t: string) => TYPE_COLOR[t] || 'bg-gray-100 text-gray-600 ring-gray-200'
const typeIcon  = (t: string) => TYPE_ICON[t] || <FileText className="w-3.5 h-3.5" />
const typeBar   = (t: string) => TYPE_BAR[t] || 'bg-gray-400'
const ALL_TYPES = ['theory', 'numerical', 'diagram', 'derivation', 'flowchart', 'graph', 'mixed']

function chip(label: string, cls: string, key: string | number) {
  return <span key={key} className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ring-1 ring-inset ${cls}`}>{label}</span>
}

/** Read a fetch Response as JSON without ever throwing a cryptic browser
 * parse error — an empty/non-JSON body almost always means the backend was
 * mid-restart or crashed, so say that plainly instead. */
async function safeJson(res: Response): Promise<any> {
  const raw = await res.text()
  if (!raw) {
    throw new Error(
      `The server didn't respond (HTTP ${res.status}). It may still be starting up — `
      + `wait a few seconds and try again.`
    )
  }
  try {
    return JSON.parse(raw)
  } catch {
    throw new Error(`Server returned an unexpected response (HTTP ${res.status}).`)
  }
}

/* ── AI status indicator (replaces the old always-on OCR/API banners) ───── */

function AiStatusChip({ deps, onOpen }: { deps: DepStatus | null; onOpen: () => void }) {
  if (!deps) return null
  const ready = deps.cloud_vlm?.available
  const via = deps.cloud_vlm?.via
  return (
    <button
      onClick={onOpen}
      className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
        ready ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100' : 'bg-amber-50 text-amber-700 hover:bg-amber-100'
      }`}
      title="Click to see AI reading status"
    >
      <Circle className={`w-2 h-2 fill-current ${ready ? 'text-emerald-500' : 'text-amber-500'}`} />
      {ready
        ? (via === 'ollama' ? 'AI reading: Local' : 'AI reading: Ready')
        : 'AI reading: Limited'}
    </button>
  )
}

function AiStatusPanel({ deps, onClose }: { deps: DepStatus | null; onClose: () => void }) {
  const [selftest, setSelftest] = useState<any>(null)
  const [testing, setTesting] = useState(false)

  const runSelftest = async () => {
    setTesting(true); setSelftest(null)
    try {
      const r = await fetch('/api/eval/selftest')
      setSelftest(await safeJson(r))
    } catch (e: any) {
      setSelftest({ error: e.message || 'Could not reach the backend.' })
    } finally { setTesting(false) }
  }

  const ready = deps?.cloud_vlm?.available

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <ScanEye className="w-5 h-5 text-indigo-500" />
            <p className="text-sm font-semibold text-gray-900">Handwriting AI Status</p>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded-lg"><X className="w-4 h-4 text-gray-400" /></button>
        </div>

        <div className="p-6 space-y-4">
          <div className={`rounded-xl p-4 ${ready ? 'bg-emerald-50' : 'bg-amber-50'}`}>
            <p className={`text-sm font-medium ${ready ? 'text-emerald-800' : 'text-amber-800'}`}>
              {ready ? '✓ Handwriting AI is active' : '⚠ Handwriting reading is limited right now'}
            </p>
            <p className={`text-xs mt-1 ${ready ? 'text-emerald-700' : 'text-amber-700'}`}>
              {ready
                ? 'Uploaded scripts will be read and graded by an AI vision model.'
                : 'No vision AI was detected, so basic text scanning is used instead — weaker on handwriting.'}
            </p>
          </div>

          {!ready && (
            <div className="space-y-3 text-sm">
              <p className="font-medium text-gray-700">Two ways to enable proper handwriting reading:</p>
              <div className="rounded-lg border border-gray-100 p-3">
                <p className="font-medium text-gray-800 text-xs mb-1">Option A — Free cloud key</p>
                <p className="text-xs text-gray-500">Get a free key at aistudio.google.com/apikey, add
                  <code className="bg-gray-100 px-1 rounded mx-1">GEMINI_API_KEY=...</code>
                  to a <code className="bg-gray-100 px-1 rounded">.env</code> file in the project root, restart the backend.</p>
              </div>
              <div className="rounded-lg border border-gray-100 p-3">
                <p className="font-medium text-gray-800 text-xs mb-1">Option B — Fully offline (no key)</p>
                <p className="text-xs text-gray-500">Install <a href="https://ollama.ai" target="_blank" rel="noreferrer" className="underline">Ollama</a>, run
                  <code className="bg-gray-100 px-1 rounded mx-1">ollama pull llava</code>
                  in any terminal, restart the backend.</p>
              </div>
            </div>
          )}

          <button onClick={runSelftest} disabled={testing} className="btn-secondary w-full text-sm flex items-center justify-center gap-2">
            {testing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            Run a live connection test
          </button>

          {selftest && (
            <div className="text-xs space-y-1.5 bg-gray-50 rounded-lg p-3">
              {selftest.error && <p className="text-red-600">{selftest.error}</p>}
              {selftest.providers && Object.entries(selftest.providers).map(([name, p]: any) => (
                <p key={name} className={p.ok ? 'text-emerald-600' : 'text-gray-500'}>
                  <b className="text-gray-700">{name}</b>{p.model ? ` (${p.model})` : ''}: {p.ok ? 'working' : (p.error || `HTTP ${p.status}`)}
                </p>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/* ── Answer card ──────────────────────────────────────────────────────────── */

function RubricBar({ r }: { r: RubricRow }) {
  const pct = r.max > 0 ? (r.awarded / r.max) * 100 : 0
  const color = pct >= 90 ? 'bg-emerald-500' : pct > 0 ? 'bg-amber-500' : 'bg-red-400'
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-gray-600">{r.criterion}</span>
        <span className="font-semibold text-gray-700">{r.awarded} / {r.max}</span>
      </div>
      <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      {r.reason && <p className="text-[11px] text-gray-400">{r.reason}</p>}
    </div>
  )
}

function AnswerCard({ ans, resultId, onUpdate }: {
  ans: AnswerResult
  resultId?: string
  onUpdate?: () => void
}) {
  const [open, setOpen]   = useState(false)
  const [tab, setTab]     = useState<'feedback' | 'written' | 'expected'>('feedback')
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
  const pct = ans.max_score > 0 ? (ans.ai_score / ans.max_score) * 100 : 0
  const scoreColor = pct >= 70 ? 'text-emerald-600' : pct >= 40 ? 'text-amber-600' : 'text-red-500'

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
    <div className="rounded-2xl bg-white ring-1 ring-gray-100 shadow-sm hover:shadow-md transition-shadow overflow-hidden">
      <button
        className="w-full flex items-center gap-3 px-5 py-4 text-left"
        onClick={() => setOpen(o => !o)}
      >
        <div className={`w-1 self-stretch rounded-full ${typeBar(ans.q_type)} shrink-0`} />
        <div className="flex items-center gap-2.5 min-w-0 flex-1">
          <span className="text-sm font-bold text-gray-800 shrink-0">Q{ans.q_number}</span>
          <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset shrink-0 ${typeColor(ans.q_type)}`}>
            {typeIcon(ans.q_type)} {ans.q_type}
          </span>
          {ans.overridden && chip('✎ overridden', 'bg-blue-50 text-blue-600 ring-blue-200', 'ov')}
          {ans.faculty_approved && chip('✓ approved', 'bg-emerald-50 text-emerald-700 ring-emerald-200', 'ap')}
          {ans.requires_faculty_review && !ans.faculty_approved &&
            chip('worth a look', 'bg-violet-50 text-violet-600 ring-violet-200', 'rv')}
          <span className="text-xs text-gray-400 truncate hidden md:block">{ans.question}</span>
        </div>
        <div className="flex items-center gap-4 shrink-0">
          <p className={`font-bold text-lg tabular-nums ${scoreColor}`}>{ans.ai_score}<span className="text-xs text-gray-400 font-normal">/{ans.max_score}</span></p>
          {open ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
        </div>
      </button>

      {open && (
        <div className="border-t border-gray-100 px-5 py-4 space-y-4 bg-gray-50/50">
          <p className="text-sm text-gray-700 font-medium">{ans.question}</p>

          {rubric.length > 0 && (
            <div className="bg-white rounded-xl p-3 space-y-3 ring-1 ring-gray-100">
              {rubric.map((r, i) => <RubricBar key={i} r={r} />)}
            </div>
          )}

          <div className="flex gap-1">
            {(['feedback', 'written', 'expected'] as const).map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${tab === t ? 'bg-indigo-600 text-white' : 'text-gray-500 hover:bg-gray-100'}`}
              >
                {t === 'written' ? "Student's Answer" : t === 'expected' ? 'Expected Answer' : 'AI Feedback'}
              </button>
            ))}
          </div>

          {tab === 'feedback' && (
            <div className="space-y-2.5">
              <p className="text-sm text-gray-600">{ans.feedback}</p>
              {(covered.length > 0 || missing.length > 0) && (
                <div className="flex flex-wrap gap-1">
                  {covered.map((k: string, i: number) => chip(`✓ ${k}`, 'bg-emerald-50 text-emerald-700 ring-emerald-200', `c${i}`))}
                  {missing.map((k: string, i: number) => chip(`✗ ${k}`, 'bg-red-50 text-red-600 ring-red-200', `m${i}`))}
                </div>
              )}
              {strengths.length > 0 && (
                <div>
                  <p className="text-[11px] font-semibold text-emerald-700">Strengths</p>
                  <ul className="list-disc list-inside text-xs text-gray-500">{strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>
                </div>
              )}
              {weaknesses.length > 0 && (
                <div>
                  <p className="text-[11px] font-semibold text-red-600">Weaknesses</p>
                  <ul className="list-disc list-inside text-xs text-gray-500">{weaknesses.map((s, i) => <li key={i}>{s}</li>)}</ul>
                </div>
              )}
              {suggestions.length > 0 && (
                <div>
                  <p className="text-[11px] font-semibold text-indigo-600">Suggestions</p>
                  <ul className="list-disc list-inside text-xs text-gray-500">{suggestions.map((s, i) => <li key={i}>{s}</li>)}</ul>
                </div>
              )}
            </div>
          )}

          {tab === 'written' && (
            <pre className="text-xs text-gray-700 bg-white rounded-lg p-3 whitespace-pre-wrap max-h-60 overflow-y-auto font-mono leading-relaxed ring-1 ring-gray-100">
              {ans.ocr_text || '(nothing was read for this question)'}
            </pre>
          )}

          {tab === 'expected' && (
            <pre className="text-xs text-gray-600 bg-white rounded-lg p-3 whitespace-pre-wrap max-h-60 overflow-y-auto leading-relaxed ring-1 ring-gray-100">
              {ans.expected_answer || '(no reference answer provided in the scheme)'}
            </pre>
          )}

          {resultId && (
            <div className="border-t border-gray-200 pt-3 flex flex-wrap items-center gap-2">
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

/* ── Report views ─────────────────────────────────────────────────────────── */

function SingleReport({ report, resultId, onUpdate }: {
  report: ScriptReport
  resultId?: string
  onUpdate?: () => void
}) {
  const rid = resultId ?? report.result_id
  const reviewCount = report.needs_review_questions?.length ?? report.answers.filter(a => a.requires_faculty_review).length
  const pct = report.max_total > 0 ? (report.total_score / report.max_total) * 100 : 0

  return (
    <div className="space-y-4">
      {report.grading_note && (
        <div className="rounded-2xl p-4 bg-amber-50 ring-1 ring-amber-200 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-amber-500 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-amber-800">Heads up</p>
            <p className="text-xs text-amber-700 mt-0.5">{report.grading_note}</p>
          </div>
        </div>
      )}

      {/* Hero score card */}
      <div className="rounded-2xl bg-gradient-to-br from-indigo-600 to-violet-600 p-6 text-white shadow-lg">
        <p className="text-xs text-indigo-100 uppercase tracking-wide font-medium">Marks Obtained</p>
        <p className="text-5xl font-bold mt-1">
          {report.total_score}
          <span className="text-2xl text-indigo-200 font-normal"> / {report.max_total}</span>
        </p>
        <div className="h-2 rounded-full bg-white/20 mt-4 overflow-hidden">
          <div className="h-full rounded-full bg-white transition-all" style={{ width: `${Math.min(100, pct)}%` }} />
        </div>
        <div className="flex gap-4 mt-4 text-xs text-indigo-100 flex-wrap">
          <span>{report.questions_evaluated} question(s) graded</span>
          {report.subject && <span>· {report.subject}</span>}
          {report.grading_path === 'vision' && <span className="inline-flex items-center gap-1">· <Sparkles className="w-3 h-3" /> Read by AI</span>}
        </div>
      </div>

      <div className="flex gap-2 flex-wrap items-center">
        {ALL_TYPES.map(t => {
          const count = report.answers.filter(a => a.q_type === t).length
          return count > 0 ? (
            <span key={t} className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${typeColor(t)}`}>
              {typeIcon(t)} {count} {t}
            </span>
          ) : null
        })}
        {reviewCount > 0 && chip(`${reviewCount} worth a second look`, 'bg-violet-50 text-violet-600 ring-violet-200', 'rc')}
      </div>

      {report.unanswered_questions && report.unanswered_questions.length > 0 && (
        <div className="rounded-2xl p-4 bg-white ring-1 ring-gray-100">
          <p className="text-xs font-semibold text-gray-600 mb-2">Not attempted</p>
          <div className="flex flex-wrap gap-1.5">
            {report.unanswered_questions.map(u =>
              chip(`Q${u.q_number} · ${u.max_marks} marks`, 'bg-red-50 text-red-500 ring-red-200', u.q_number))}
          </div>
        </div>
      )}

      <div className="space-y-2.5">
        {report.answers.map(ans => (
          <AnswerCard key={ans.q_number} ans={ans} resultId={rid} onUpdate={onUpdate} />
        ))}
      </div>
    </div>
  )
}

function BatchSummary({ batch, onSelect }: { batch: BatchResult; onSelect: (r: ScriptReport) => void }) {
  const exportCSV = () => {
    const lines = ['Name,USN,Marks,MaxMarks,Questions,NeedsReview']
    batch.reports.forEach(r => {
      const review = (r.needs_review_questions?.length ?? 0)
      lines.push(`"${r.student_name}","${r.student_usn}",${r.total_score},${r.max_total},${r.questions_evaluated},${review}`)
    })
    const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob)
    a.download = `batch_marks_${batch.subject.replace(/\s+/g, '_')}.csv`; a.click()
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'Class Average', value: `${batch.class_avg}%`, color: 'text-indigo-600' },
          { label: 'Total Scripts', value: String(batch.total_students), color: 'text-gray-800' },
          { label: 'Need Review', value: String(batch.reports.reduce((n, r) => n + (r.needs_review_questions?.length ?? 0), 0)), color: 'text-violet-600' },
        ].map(s => (
          <div key={s.label} className="rounded-2xl bg-white ring-1 ring-gray-100 p-4">
            <p className="text-xs text-gray-500 mb-1">{s.label}</p>
            <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      <div className="flex justify-end">
        <button onClick={exportCSV} className="btn-secondary flex items-center gap-2 text-sm">
          <ClipboardList className="w-4 h-4" /> Export CSV
        </button>
      </div>

      <div className="rounded-2xl bg-white ring-1 ring-gray-100 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              <th className="text-left px-4 py-2.5 font-medium text-gray-500 text-xs">Student / File</th>
              <th className="text-right px-4 py-2.5 font-medium text-gray-500 text-xs">Marks</th>
              <th className="text-center px-4 py-2.5 font-medium text-gray-500 text-xs">Review</th>
              <th className="px-4 py-2.5"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {batch.reports.map((r, i) => {
              const review = r.needs_review_questions?.length ?? 0
              return (
                <tr key={i} className="hover:bg-gray-50">
                  <td className="px-4 py-2.5">
                    <p className="font-medium text-gray-800 text-sm">{r.student_name || `Script ${i + 1}`}</p>
                    {r.student_usn && <p className="text-gray-400 text-xs">{r.student_usn}</p>}
                    {r.error && <p className="text-red-500 text-[10px]">{r.error}</p>}
                  </td>
                  <td className="px-4 py-2.5 text-right font-semibold text-gray-700">{r.total_score} / {r.max_total}</td>
                  <td className="px-4 py-2.5 text-center">
                    {review > 0 ? chip(String(review), 'bg-violet-50 text-violet-600 ring-violet-200', i) : <span className="text-gray-300">—</span>}
                  </td>
                  <td className="px-4 py-2.5">
                    {!r.error && (
                      <button onClick={() => onSelect(r)} className="text-indigo-600 hover:underline text-xs font-medium flex items-center gap-1">
                        Detail <ArrowRight className="w-3 h-3" />
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

/* ── Main page ────────────────────────────────────────────────────────────── */

type Mode = 'upload' | 'paste' | 'batch'

export default function AnswerScriptEvaluator() {
  const [mode, setMode] = useState<Mode>('upload')
  const [referenceId, setReferenceId] = useState('')
  const [refs, setRefs] = useState<RefEntry[]>([])

  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [report, setReport] = useState<ScriptReport | null>(null)

  const [batchFiles, setBatchFiles] = useState<File[]>([])
  const [batchResult, setBatchResult] = useState<BatchResult | null>(null)
  const [selectedReport, setSelectedReport] = useState<ScriptReport | null>(null)

  const [pasteTexts, setPasteTexts] = useState<Record<number, string>>({})
  const [studentName, setStudentName] = useState('')

  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState('')
  const [error, setError] = useState('')

  const [deps, setDeps] = useState<DepStatus | null>(null)
  const [showAiPanel, setShowAiPanel] = useState(false)
  const [history, setHistory] = useState<EvalSummary[]>([])
  const [historyReport, setHistoryReport] = useState<ScriptReport | null>(null)
  const [historyId, setHistoryId] = useState('')
  const [showHistory, setShowHistory] = useState(false)
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
    'Reading the pages…',
    'Finding each answer…',
    'Matching answers to the scheme…',
    'Grading against the rubric…',
    'Almost done…',
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

  const selectedRef = refs.find(r => r.id === referenceId)
  const schemeQs: SchemeQ[] = (() => {
    if (!selectedRef?.questions_json) return []
    try { return JSON.parse(selectedRef.questions_json) } catch { return [] }
  })()

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

  const modeConfig: { key: Mode; label: string; icon: React.ReactNode }[] = [
    { key: 'upload', label: 'Upload Script', icon: <Upload className="w-4 h-4" /> },
    { key: 'batch', label: 'Whole Class', icon: <Users className="w-4 h-4" /> },
    { key: 'paste', label: 'Type Answers', icon: <Pencil className="w-4 h-4" /> },
  ]

  const canSubmit = mode === 'upload' ? !!file : mode === 'batch' ? batchFiles.length > 0 : Object.values(pasteTexts).some(t => t.trim())

  return (
    <div>
      <Header
        title="Evaluate Answer Scripts"
        subtitle="Upload a script, and let AI grade it against your answer scheme"
        actions={<AiStatusChip deps={deps} onOpen={() => setShowAiPanel(true)} />}
      />
      {showAiPanel && <AiStatusPanel deps={deps} onClose={() => setShowAiPanel(false)} />}

      <div className="p-6 space-y-5 max-w-4xl">

        {/* Mode selector — segmented pill control */}
        <div className="inline-flex p-1 rounded-xl bg-gray-100">
          {modeConfig.map(m => (
            <button
              key={m.key}
              onClick={() => { setMode(m.key); setError(''); setReport(null); setBatchResult(null) }}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                mode === m.key ? 'bg-white text-indigo-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {m.icon} {m.label}
            </button>
          ))}
        </div>

        {/* Main input card */}
        <div className="rounded-2xl bg-white ring-1 ring-gray-100 p-6 space-y-5">

          {/* Scheme picker */}
          <div>
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 block">Answer Scheme</label>
            {refs.length === 0 ? (
              <div className="flex items-center gap-3 bg-amber-50 rounded-xl px-4 py-3 ring-1 ring-amber-200">
                <AlertCircle className="w-5 h-5 text-amber-500 shrink-0" />
                <p className="text-sm text-amber-700">
                  No answer schemes yet — <a href="/eval/train" className="underline font-medium">upload one</a> to grade against it.
                </p>
              </div>
            ) : (
              <select
                className="input-field w-full text-sm"
                value={referenceId}
                onChange={e => setReferenceId(e.target.value)}
              >
                <option value="">— Select scheme —</option>
                {refs.map(r => (
                  <option key={r.id} value={r.id}>
                    {r.subject} · {r.marks_per_q ?? 10} marks/q{r.description ? ` · ${r.description}` : ''}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Upload script */}
          {mode === 'upload' && (
            <div
              onDrop={onDrop}
              onDragOver={e => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onClick={() => fileRef.current?.click()}
              className={`rounded-2xl border-2 border-dashed flex flex-col items-center justify-center py-12 cursor-pointer transition-all ${
                dragging ? 'border-indigo-400 bg-indigo-50 scale-[1.01]' : 'border-gray-200 hover:border-indigo-300 hover:bg-gray-50'
              }`}
            >
              <input ref={fileRef} type="file" accept=".pdf,.png,.jpg,.jpeg" className="hidden" onChange={e => { const f = e.target.files?.[0]; if (f) acceptFile(f) }} />
              <div className={`w-12 h-12 rounded-full flex items-center justify-center mb-3 ${dragging ? 'bg-indigo-100' : 'bg-gray-50'}`}>
                <Upload className={`w-5 h-5 ${dragging ? 'text-indigo-500' : 'text-gray-400'}`} />
              </div>
              {file ? (
                <div className="text-center">
                  <p className="text-sm font-semibold text-indigo-700 flex items-center gap-2"><FileText className="w-4 h-4" />{file.name}</p>
                  <p className="text-xs text-gray-400 mt-1">{(file.size / 1024).toFixed(0)} KB · click to change</p>
                </div>
              ) : (
                <div className="text-center">
                  <p className="text-sm font-medium text-gray-600">Drop the answer script here</p>
                  <p className="text-xs text-gray-400 mt-1">PDF, PNG or JPG · pages can be in any order</p>
                </div>
              )}
            </div>
          )}

          {/* Batch upload */}
          {mode === 'batch' && (
            <div>
              <div
                onClick={() => batchRef.current?.click()}
                className="rounded-2xl border-2 border-dashed border-gray-200 flex flex-col items-center justify-center py-10 cursor-pointer hover:border-indigo-300 hover:bg-gray-50 transition-all"
              >
                <input
                  ref={batchRef} type="file" multiple
                  accept=".pdf,.png,.jpg,.jpeg,.zip" className="hidden"
                  onChange={e => { if (e.target.files) { setBatchFiles(Array.from(e.target.files)); setBatchResult(null); setError('') } }}
                />
                <div className="w-12 h-12 rounded-full bg-gray-50 flex items-center justify-center mb-3">
                  <Users className="w-5 h-5 text-gray-400" />
                </div>
                <p className="text-sm font-medium text-gray-600">Select every student's script, or a ZIP</p>
                <p className="text-xs text-gray-400 mt-1">One file per student</p>
              </div>
              {batchFiles.length > 0 && (
                <div className="mt-3 space-y-1 max-h-40 overflow-y-auto">
                  {batchFiles.map((f, i) => (
                    <div key={i} className="flex items-center justify-between text-xs bg-gray-50 rounded-lg px-3 py-2">
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

          {/* Paste answers */}
          {mode === 'paste' && (
            <div className="space-y-3">
              <div className="rounded-xl bg-indigo-50 px-4 py-3">
                <p className="text-xs text-indigo-700">Type or paste what the student wrote. This always works — no scanning involved.</p>
              </div>
              <input
                type="text" placeholder="Student name / roll no (optional)"
                value={studentName} onChange={e => setStudentName(e.target.value)}
                className="input-field w-full text-sm"
              />
              {schemeQs.length === 0 ? (
                <p className="text-xs text-amber-600 bg-amber-50 rounded-lg px-3 py-2 ring-1 ring-amber-200">
                  Select an answer scheme above to load its questions here.
                </p>
              ) : (
                <div className="space-y-3">
                  {schemeQs.map(q => (
                    <div key={q.q_number}>
                      <label className="text-xs font-medium text-gray-600 mb-1 flex items-center gap-2">
                        <span className="rounded-full bg-indigo-50 text-indigo-700 px-2 py-0.5 text-[10px] font-semibold">Q{q.q_number}</span>
                        <span className="truncate">{q.question || `Question ${q.q_number}`}</span>
                        <span className="text-gray-400 ml-auto shrink-0">{q.max_marks ?? 10} marks</span>
                      </label>
                      <textarea
                        rows={3}
                        placeholder={`Student's answer for Q${q.q_number}…`}
                        value={pasteTexts[q.q_number] || ''}
                        onChange={e => setPasteTexts(prev => ({ ...prev, [q.q_number]: e.target.value }))}
                        className="input-field w-full text-sm"
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          <button
            onClick={mode === 'upload' ? evaluate : mode === 'batch' ? evaluateBatch : gradePaste}
            disabled={loading || !canSubmit}
            className="btn-primary w-full flex items-center justify-center gap-2 py-3.5 text-sm font-semibold disabled:opacity-40 rounded-xl"
          >
            {loading
              ? <><Loader2 className="w-4 h-4 animate-spin" />{progress || 'Grading…'}</>
              : mode === 'upload'
                ? <><Sparkles className="w-4 h-4" />Grade This Script</>
                : mode === 'batch'
                  ? <><Users className="w-4 h-4" />Grade {batchFiles.length || ''} Script{batchFiles.length !== 1 ? 's' : ''}</>
                  : <><Sparkles className="w-4 h-4" />Grade These Answers</>}
          </button>
        </div>

        {error && (
          <div className="rounded-2xl p-4 bg-red-50 ring-1 ring-red-200 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-500 mt-0.5 shrink-0" />
            <div>
              <p className="text-sm font-semibold text-red-700">Something went wrong</p>
              <p className="text-xs text-red-600 mt-1">{error}</p>
            </div>
          </div>
        )}

        {/* Results */}
        {report && mode !== 'batch' && (
          <SingleReport report={report} resultId={report.result_id} onUpdate={() => report.result_id && reload(report.result_id, setReport)} />
        )}

        {batchResult && mode === 'batch' && !selectedReport && (
          <BatchSummary batch={batchResult} onSelect={setSelectedReport} />
        )}
        {selectedReport && (
          <div className="space-y-3">
            <button onClick={() => setSelectedReport(null)} className="flex items-center gap-2 text-sm text-indigo-600 hover:underline font-medium">
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

        {/* History — tucked behind a toggle so the page stays focused */}
        {history.length > 0 && !historyReport && (
          <div className="rounded-2xl bg-white ring-1 ring-gray-100">
            <button
              onClick={() => setShowHistory(s => !s)}
              className="w-full flex items-center justify-between px-6 py-4"
            >
              <span className="flex items-center gap-2 text-sm font-semibold text-gray-800">
                <HistoryIcon className="w-4 h-4 text-gray-400" /> Past Evaluations ({history.length})
              </span>
              {showHistory ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
            </button>
            {showHistory && (
              <div className="overflow-hidden border-t border-gray-100">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-100">
                    <tr>
                      <th className="text-left px-4 py-2.5 font-medium text-gray-500 text-xs">Student / File</th>
                      <th className="text-left px-4 py-2.5 font-medium text-gray-500 text-xs">Subject</th>
                      <th className="text-right px-4 py-2.5 font-medium text-gray-500 text-xs">Marks</th>
                      <th className="text-right px-4 py-2.5 font-medium text-gray-500 text-xs">Date</th>
                      <th className="px-4 py-2.5"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {history.map(h => (
                      <tr key={h.id} className="hover:bg-gray-50">
                        <td className="px-4 py-2.5 font-medium text-gray-800">{h.student_name || '(unnamed)'}</td>
                        <td className="px-4 py-2.5 text-gray-500 text-xs">{h.subject}</td>
                        <td className="px-4 py-2.5 text-right font-semibold text-gray-700">{h.total_score} / {h.max_total}</td>
                        <td className="px-4 py-2.5 text-right text-gray-400 text-xs">{new Date(h.evaluated_at).toLocaleDateString()}</td>
                        <td className="px-4 py-2.5">
                          <button className="text-indigo-600 hover:underline text-xs font-medium" onClick={() => { setHistoryId(h.id); reload(h.id, setHistoryReport) }}>
                            View →
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {historyReport && (
          <div className="space-y-3">
            <button onClick={() => { setHistoryReport(null); setHistoryId('') }} className="flex items-center gap-2 text-sm text-indigo-600 hover:underline font-medium">
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
