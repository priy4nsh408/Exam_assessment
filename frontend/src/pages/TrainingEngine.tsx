import { useState, useEffect, useRef } from 'react'
import { Header } from '../components/layout/Header'
import {
  Upload, Trash2, Brain, Calculator, PenTool,
  CheckCircle, AlertCircle, FileText, Loader2,
  ChevronDown, ChevronRight, AlertTriangle, BookOpen,
} from 'lucide-react'

interface ParsedQuestion {
  q_number: number
  question: string
  reference_answer: string
  max_marks: number
}

interface RefEntry {
  id: string
  subject: string
  q_type: string
  filename: string
  description: string
  marks_per_q: number
  questions_json: string   // JSON string
  parse_warnings: string  // JSON string
  created_at: string
}

interface UploadResult {
  id: string
  subject: string
  filename: string
  questions_parsed: number
  marks_per_q: number
  parse_warnings: string[]
  questions: ParsedQuestion[]
  raw_ocr_text: string
  message: string
}

export default function TrainingEngine() {
  const [refs, setRefs] = useState<RefEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null)
  const [expandedRef, setExpandedRef] = useState<string | null>(null)

  const [file, setFile] = useState<File | null>(null)
  const [description, setDescription] = useState('')
  const [defaultMarks, setDefaultMarks] = useState(10)

  const fileRef = useRef<HTMLInputElement>(null)

  const loadRefs = () => {
    setLoading(true)
    fetch('/api/training/references')
      .then(r => r.json())
      .then(d => setRefs(d.references || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadRefs() }, [])

  const upload = async () => {
    if (!file) return
    setUploading(true); setError(''); setUploadResult(null)
    const fd = new FormData()
    fd.append('file', file)
    fd.append('description', description)
    fd.append('default_marks', String(defaultMarks))
    try {
      const res = await fetch('/api/training/upload', { method: 'POST', body: fd })
      if (!res.ok) { const e = await res.json().catch(() => ({ detail: res.statusText })); throw new Error(e.detail) }
      const result: UploadResult = await res.json()
      setUploadResult(result)
      setFile(null); setDescription('')
      loadRefs()
    } catch (e: any) {
      setError(e.message || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const deleteRef = async (id: string) => {
    if (!confirm('Delete this answer scheme?')) return
    await fetch(`/api/training/references/${id}`, { method: 'DELETE' }).catch(() => {})
    loadRefs()
  }

  const parseQuestions = (ref: RefEntry): ParsedQuestion[] => {
    try { return JSON.parse(ref.questions_json || '[]') } catch { return [] }
  }
  const parseWarnings = (ref: RefEntry): string[] => {
    try { return JSON.parse(ref.parse_warnings || '[]') } catch { return [] }
  }

  return (
    <div>
      <Header
        title="Answer Schemes"
        subtitle="Upload answer scheme PDFs — the system extracts questions, expected answers, and marks automatically"
      />
      <div className="p-6 space-y-6 max-w-4xl">

        {/* How it works */}
        <div className="card p-4 bg-indigo-50 border-indigo-100 space-y-2">
          <div className="flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-indigo-600" />
            <p className="text-sm font-semibold text-indigo-800">How it works</p>
          </div>
          <ol className="text-xs text-indigo-700 space-y-1 list-decimal list-inside">
            <li>Upload your answer scheme PDF (with questions, expected answers, and marks)</li>
            <li>The system OCRs it and extracts each question, its expected answer, and marks automatically</li>
            <li>When you evaluate student scripts, select this scheme — evaluation uses your expected answers for scoring</li>
          </ol>
          <p className="text-xs text-indigo-600 mt-1">
            <b>Tip:</b> Mark questions clearly as "Q1.", "1.", "Question 1" etc. and include marks like "(5M)" or "[10 marks]" for best extraction.
          </p>
        </div>

        {/* Upload form */}
        <div className="card p-5 space-y-4">
          <p className="text-sm font-semibold text-gray-800">Upload Answer Scheme</p>

          <div
            onClick={() => fileRef.current?.click()}
            className="border-2 border-dashed rounded-xl flex flex-col items-center justify-center py-8 cursor-pointer hover:border-indigo-300 hover:bg-gray-50 transition-colors"
          >
            <input ref={fileRef} type="file" accept=".pdf,.png,.jpg,.jpeg"
              className="hidden"
              onChange={e => { const f = e.target.files?.[0]; if (f) { setFile(f); setUploadResult(null); setError('') } }} />
            <Upload className="w-6 h-6 text-gray-300 mb-2" />
            {file
              ? <p className="text-sm text-indigo-700 flex items-center gap-2"><FileText className="w-4 h-4" />{file.name}</p>
              : <div className="text-center">
                  <p className="text-sm text-gray-500">Click to select answer scheme PDF or image</p>
                  <p className="text-xs text-gray-400 mt-1">PDF, PNG, JPG — scanned or typed</p>
                </div>}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-gray-600 mb-1 block">Default marks per question</label>
              <input
                type="number" min={1} max={100} className="input-field w-full text-sm"
                value={defaultMarks} onChange={e => setDefaultMarks(Number(e.target.value))}
              />
              <p className="text-[10px] text-gray-400 mt-1">Used if the scheme doesn't specify marks explicitly</p>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 mb-1 block">Description (optional)</label>
              <input
                type="text" className="input-field w-full text-sm"
                placeholder="e.g. Thermodynamics Unit 2 — VTU Dec 2023"
                value={description} onChange={e => setDescription(e.target.value)}
              />
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 text-xs text-red-600 bg-red-50 rounded p-2">
              <AlertCircle className="w-4 h-4 shrink-0" />{error}
            </div>
          )}

          {uploadResult && (
            <div className="space-y-3">
              <div className={`flex items-start gap-2 text-xs rounded p-3 ${uploadResult.questions_parsed > 0 ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
                {uploadResult.questions_parsed > 0
                  ? <CheckCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  : <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />}
                <div>
                  <p className="font-semibold">{uploadResult.message}</p>
                  {uploadResult.subject && <p className="mt-0.5">Subject detected: <b>{uploadResult.subject}</b></p>}
                  {uploadResult.marks_per_q > 0 && <p>Marks per question: <b>{uploadResult.marks_per_q}</b></p>}
                  {uploadResult.parse_warnings.map((w, i) => (
                    <p key={i} className="mt-1 text-amber-600">⚠ {w}</p>
                  ))}
                </div>
              </div>

              {/* Show raw OCR when nothing was parsed so user can see what was read */}
              {uploadResult.questions.length === 0 && uploadResult.raw_ocr_text && (
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-gray-700">Raw OCR text (what the system read from your PDF):</p>
                  <pre className="text-[10px] text-gray-600 bg-gray-50 rounded p-3 whitespace-pre-wrap max-h-48 overflow-y-auto font-mono leading-relaxed border border-gray-200">
                    {uploadResult.raw_ocr_text}
                  </pre>
                  <p className="text-xs text-amber-700 bg-amber-50 rounded p-2">
                    The text above was extracted from your PDF. If it looks correct but questions weren't detected,
                    make sure questions are numbered like <b>1.</b> or <b>Q1.</b> or <b>Question 1</b> at the start of a line.
                  </p>
                </div>
              )}

              {uploadResult.questions.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-gray-700">Extracted questions:</p>
                  {uploadResult.questions.map(q => (
                    <div key={q.q_number} className="bg-gray-50 rounded-lg px-3 py-2 text-xs space-y-0.5">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-gray-700">Q{q.q_number}</span>
                        <span className="badge bg-indigo-50 text-indigo-600">{q.max_marks}M</span>
                      </div>
                      <p className="text-gray-600 line-clamp-2">{q.question || '(question text not detected)'}</p>
                      {q.reference_answer && (
                        <p className="text-gray-400 italic line-clamp-1">Answer: {q.reference_answer}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          <button
            onClick={upload}
            disabled={!file || uploading}
            className="btn-primary flex items-center gap-2 disabled:opacity-50"
          >
            {uploading
              ? <><Loader2 className="w-4 h-4 animate-spin" />Parsing scheme…</>
              : <><Upload className="w-4 h-4" />Upload &amp; Parse Scheme</>}
          </button>
        </div>

        {/* Scheme library */}
        <div className="card p-5 space-y-4">
          <p className="text-sm font-semibold text-gray-800">Uploaded Schemes</p>

          {loading && <p className="text-sm text-gray-400 py-4 text-center">Loading…</p>}
          {!loading && refs.length === 0 && (
            <div className="text-center py-8">
              <BookOpen className="w-8 h-8 text-gray-200 mx-auto mb-2" />
              <p className="text-sm text-gray-400">No answer schemes uploaded yet.</p>
            </div>
          )}

          <div className="space-y-2">
            {refs.map(ref => {
              const questions = parseQuestions(ref)
              const warnings  = parseWarnings(ref)
              const isOpen    = expandedRef === ref.id
              return (
                <div key={ref.id} className="border border-gray-100 rounded-lg overflow-hidden">
                  <div className="flex items-center justify-between gap-3 p-3 hover:bg-gray-50">
                    <button
                      className="flex items-center gap-3 min-w-0 flex-1 text-left"
                      onClick={() => setExpandedRef(isOpen ? null : ref.id)}
                    >
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 bg-indigo-50">
                        <Brain className="w-4 h-4 text-indigo-600" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-gray-800 truncate">{ref.filename}</p>
                        <p className="text-xs text-gray-400">
                          {ref.subject} · {questions.length} question{questions.length !== 1 ? 's' : ''} · {ref.marks_per_q ?? 10}M each
                          {ref.description ? ` · ${ref.description}` : ''}
                        </p>
                        <p className="text-[10px] text-gray-300">{new Date(ref.created_at).toLocaleString()}</p>
                      </div>
                      {isOpen ? <ChevronDown className="w-4 h-4 text-gray-400 shrink-0" /> : <ChevronRight className="w-4 h-4 text-gray-400 shrink-0" />}
                    </button>
                    <button
                      onClick={() => deleteRef(ref.id)}
                      className="p-1.5 hover:bg-red-50 rounded-lg transition-colors shrink-0"
                    >
                      <Trash2 className="w-4 h-4 text-gray-300 hover:text-red-500" />
                    </button>
                  </div>

                  {isOpen && (
                    <div className="border-t border-gray-100 px-4 py-3 space-y-2 bg-gray-50">
                      {warnings.length > 0 && warnings.map((w, i) => (
                        <div key={i} className="flex items-start gap-2 text-xs text-amber-700 bg-amber-50 rounded p-2">
                          <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />{w}
                        </div>
                      ))}
                      {questions.length === 0 && (
                        <p className="text-xs text-gray-400 italic">No questions extracted — scheme may need clearer formatting.</p>
                      )}
                      {questions.map(q => (
                        <div key={q.q_number} className="bg-white rounded-lg border border-gray-100 px-3 py-2 text-xs space-y-1">
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-gray-700">Q{q.q_number}</span>
                            <span className="badge bg-indigo-50 text-indigo-600">{q.max_marks}M</span>
                          </div>
                          {q.question && <p className="text-gray-600">{q.question}</p>}
                          {q.reference_answer && (
                            <p className="text-gray-400 italic border-t border-gray-100 pt-1">
                              <span className="font-medium text-gray-500">Expected: </span>{q.reference_answer}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
