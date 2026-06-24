import { useState, useEffect, useRef } from 'react'
import { Header } from '../components/layout/Header'
import {
  Upload, Trash2, Brain, Calculator, PenTool,
  CheckCircle, AlertCircle, TestTube2, FileText, Loader2,
} from 'lucide-react'

const SUBJECTS = [
  'Thermodynamics', 'Strength of Materials', 'Fluid Mechanics',
  'Engineering Drawing', 'Basic Design & Theory', 'Propulsion',
  'Structural Mechanics', 'Machine Design', 'Manufacturing Technology',
  'Mechanical Engineering',
]

const Q_TYPES = [
  { value: 'theory',   label: 'Theory',   icon: Brain,       color: 'text-indigo-600', bg: 'bg-indigo-50' },
  { value: 'numerical',label: 'Numerical', icon: Calculator,  color: 'text-amber-600',  bg: 'bg-amber-50'  },
  { value: 'drawing',  label: 'Drawing',  icon: PenTool,     color: 'text-emerald-600',bg: 'bg-emerald-50'},
]

interface RefEntry {
  id: string
  subject: string
  q_type: string
  filename: string
  description: string
  file_path: string
  marks_per_q: number
  created_at: string
}

export default function TrainingEngine() {
  const [refs, setRefs] = useState<RefEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  // Upload form state
  const [file, setFile] = useState<File | null>(null)
  const [subject, setSubject] = useState('Mechanical Engineering')
  const [qType, setQType] = useState('theory')
  const [description, setDescription] = useState('')
  const [marksPerQ, setMarksPerQ] = useState(10)
  const [filterSubject, setFilterSubject] = useState('')
  const [filterType, setFilterType] = useState('')

  const fileRef = useRef<HTMLInputElement>(null)

  const loadRefs = () => {
    setLoading(true)
    const qs = new URLSearchParams()
    if (filterSubject) qs.set('subject', filterSubject)
    if (filterType) qs.set('q_type', filterType)
    fetch(`/api/training/references?${qs}`)
      .then(r => r.json())
      .then(d => setRefs(d.references || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadRefs() }, [filterSubject, filterType])

  const upload = async () => {
    if (!file) return
    setUploading(true); setError(''); setSuccess('')
    const fd = new FormData()
    fd.append('file', file)
    fd.append('subject', subject)
    fd.append('q_type', qType)
    fd.append('description', description)
    fd.append('marks_per_q', String(marksPerQ))
    try {
      const res = await fetch('/api/training/upload', { method: 'POST', body: fd })
      if (!res.ok) { const e = await res.json().catch(() => ({ detail: res.statusText })); throw new Error(e.detail) }
      setSuccess('Reference uploaded successfully. The evaluator will use it for keyword and rubric extraction.')
      setFile(null); setDescription('')
      loadRefs()
    } catch (e: any) {
      setError(e.message || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const deleteRef = async (id: string) => {
    if (!confirm('Delete this training reference?')) return
    await fetch(`/api/training/references/${id}`, { method: 'DELETE' }).catch(() => {})
    loadRefs()
  }

  const typeMap: Record<string, typeof Q_TYPES[0]> = Object.fromEntries(Q_TYPES.map(t => [t.value, t]))

  return (
    <div>
      <Header
        title="Train Evaluation Engine"
        subtitle="Upload reference answer PDFs to improve AI grading accuracy per subject and question type"
      />
      <div className="p-6 space-y-6 max-w-4xl">

        {/* What this does */}
        <div className="card p-5 bg-indigo-50 border-indigo-100 space-y-2">
          <div className="flex items-center gap-2">
            <TestTube2 className="w-5 h-5 text-indigo-600" />
            <p className="text-sm font-semibold text-indigo-800">How training works</p>
          </div>
          <div className="grid grid-cols-3 gap-4 text-xs text-indigo-700">
            <div>
              <p className="font-medium flex items-center gap-1"><Brain className="w-3 h-3" /> Theory engine</p>
              <p className="mt-0.5 text-indigo-600">Upload ideal answers — the engine extracts keywords and builds a subject-specific vocabulary for better scoring.</p>
            </div>
            <div>
              <p className="font-medium flex items-center gap-1"><Calculator className="w-3 h-3" /> Numerical engine</p>
              <p className="mt-0.5 text-indigo-600">Upload worked solutions — the engine learns expected formula patterns and step structures for your subject.</p>
            </div>
            <div>
              <p className="font-medium flex items-center gap-1"><PenTool className="w-3 h-3" /> Drawing engine</p>
              <p className="mt-0.5 text-indigo-600">Upload ideal drawings — used as visual reference for IS/BIS compliance checking and element detection.</p>
            </div>
          </div>
        </div>

        {/* Upload form */}
        <div className="card p-5 space-y-4">
          <p className="text-sm font-semibold text-gray-800">Upload Reference Answer</p>

          <div
            onClick={() => fileRef.current?.click()}
            className="border-2 border-dashed rounded-xl flex flex-col items-center justify-center py-8 cursor-pointer hover:border-indigo-300 hover:bg-gray-50 transition-colors"
          >
            <input ref={fileRef} type="file" accept=".pdf,.png,.jpg,.jpeg,.txt" className="hidden"
              onChange={e => { const f = e.target.files?.[0]; if (f) { setFile(f); setSuccess('') } }} />
            <Upload className="w-6 h-6 text-gray-300 mb-2" />
            {file
              ? <p className="text-sm text-indigo-700 flex items-center gap-2"><FileText className="w-4 h-4" />{file.name}</p>
              : <p className="text-sm text-gray-500">Click to select reference answer PDF / image / text</p>}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-gray-600 mb-1 block">Subject</label>
              <select className="input-field w-full text-sm" value={subject} onChange={e => setSubject(e.target.value)}>
                {SUBJECTS.map(s => <option key={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 mb-1 block">Question Type</label>
              <div className="flex gap-2">
                {Q_TYPES.map(t => {
                  const Icon = t.icon
                  return (
                    <button
                      key={t.value}
                      onClick={() => setQType(t.value)}
                      className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-medium border transition-colors ${qType === t.value ? `${t.bg} ${t.color} border-current` : 'border-gray-200 text-gray-500 hover:border-gray-300'}`}
                    >
                      <Icon className="w-3.5 h-3.5" />{t.label}
                    </button>
                  )
                })}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-gray-600 mb-1 block">Marks per question</label>
              <input
                type="number" min={1} max={100} className="input-field w-full text-sm"
                value={marksPerQ} onChange={e => setMarksPerQ(Number(e.target.value))}
              />
              <p className="text-[10px] text-gray-400 mt-1">Used automatically when this scheme is selected during evaluation</p>
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
          {success && (
            <div className="flex items-center gap-2 text-xs text-emerald-700 bg-emerald-50 rounded p-2">
              <CheckCircle className="w-4 h-4 shrink-0" />{success}
            </div>
          )}

          <button
            onClick={upload}
            disabled={!file || uploading}
            className="btn-primary flex items-center gap-2 disabled:opacity-50"
          >
            {uploading ? <><Loader2 className="w-4 h-4 animate-spin" />Uploading…</> : <><Upload className="w-4 h-4" />Upload Reference</>}
          </button>
        </div>

        {/* Reference library */}
        <div className="card p-5 space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <p className="text-sm font-semibold text-gray-800">Reference Library</p>
            <div className="flex gap-2">
              <select className="input-field text-xs py-1.5" value={filterSubject} onChange={e => setFilterSubject(e.target.value)}>
                <option value="">All subjects</option>
                {SUBJECTS.map(s => <option key={s}>{s}</option>)}
              </select>
              <select className="input-field text-xs py-1.5" value={filterType} onChange={e => setFilterType(e.target.value)}>
                <option value="">All types</option>
                {Q_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
          </div>

          {loading && <p className="text-sm text-gray-400 py-4 text-center">Loading…</p>}
          {!loading && refs.length === 0 && (
            <div className="text-center py-8">
              <TestTube2 className="w-8 h-8 text-gray-200 mx-auto mb-2" />
              <p className="text-sm text-gray-400">No training references uploaded yet.</p>
              <p className="text-xs text-gray-300 mt-1">Upload reference answers above to improve evaluation accuracy.</p>
            </div>
          )}

          <div className="space-y-2">
            {refs.map(ref => {
              const t = typeMap[ref.q_type]
              const Icon = t?.icon ?? Brain
              return (
                <div key={ref.id} className="flex items-center justify-between gap-3 rounded-lg border border-gray-100 p-3 hover:bg-gray-50">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${t?.bg ?? 'bg-gray-100'}`}>
                      <Icon className={`w-4 h-4 ${t?.color ?? 'text-gray-500'}`} />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-800 truncate">{ref.filename}</p>
                      <p className="text-xs text-gray-400">{ref.subject} · {ref.q_type} · {ref.marks_per_q ?? 10} marks/q{ref.description ? ` · ${ref.description}` : ''}</p>
                      <p className="text-[10px] text-gray-300">{new Date(ref.created_at).toLocaleString()}</p>
                    </div>
                  </div>
                  <button
                    onClick={() => deleteRef(ref.id)}
                    className="p-1.5 hover:bg-red-50 rounded-lg transition-colors shrink-0"
                  >
                    <Trash2 className="w-4 h-4 text-gray-300 hover:text-red-500" />
                  </button>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
