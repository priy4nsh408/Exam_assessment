import { useState, useEffect, useRef } from 'react'
import { ClipboardCheck, Upload, Loader2, AlertTriangle, CheckCircle2, XCircle, Camera, FileText, Calculator, PenTool, Plus, Trash2 } from 'lucide-react'
import { Header } from '../components/layout/Header'

const TYPE_OPTIONS = [
  { value: 'auto', label: 'Auto-Detect', icon: ClipboardCheck, desc: 'System detects question type from content' },
  { value: 'theory', label: 'Theory', icon: FileText, desc: 'Keyword + semantic similarity grading' },
  { value: 'numerical', label: 'Numerical', icon: Calculator, desc: 'Step-level grading with formula check' },
  { value: 'drawing', label: 'Drawing', icon: PenTool, desc: 'VLM interpretation + IS/BIS compliance' },
]

interface StudentScript {
  id: string
  file: File
  preview: string
  studentName: string
}

export default function Evaluator() {
  const [subjects, setSubjects] = useState<string[]>([])
  const [subject, setSubject] = useState('')
  const [question, setQuestion] = useState('')
  const [studentAnswer, setStudentAnswer] = useState('')
  const [referenceAnswer, setReferenceAnswer] = useState('')
  const [maxMarks, setMaxMarks] = useState(10)
  const [questionType, setQuestionType] = useState('auto')
  const [expectedFormula, setExpectedFormula] = useState('')
  const [expectedFinalAnswer, setExpectedFinalAnswer] = useState('')

  // Answer scheme PDF
  const [schemePdf, setSchemePdf] = useState<File | null>(null)
  const schemePdfRef = useRef<HTMLInputElement>(null)

  // Multiple student answer scripts
  const [studentScripts, setStudentScripts] = useState<StudentScript[]>([])
  const scriptInputRef = useRef<HTMLInputElement>(null)

  // Single image mode (backward compat)
  const [answerImage, setAnswerImage] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [batchResults, setBatchResults] = useState<any[]>([])
  const [error, setError] = useState('')
  const [mode, setMode] = useState<'single' | 'batch'>('single')

  useEffect(() => {
    fetch('/api/data-sources')
      .then(r => r.json())
      .then(data => {
        const names = (data.subjects || []).map((s: any) => s.subject)
        setSubjects(names)
        if (names.length > 0) setSubject(names[0])
      })
      .catch(() => {})
  }, [])

  const handleSchemeUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) setSchemePdf(file)
  }

  const handleAddScripts = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files) return
    const newScripts: StudentScript[] = []
    Array.from(files).forEach(file => {
      const id = `script-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
      const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
      if (isPdf) {
        setStudentScripts(prev => [...prev, {
          id, file, preview: '', studentName: file.name.replace(/\.[^/.]+$/, ''),
        }])
      } else {
        const reader = new FileReader()
        reader.onloadend = () => {
          setStudentScripts(prev => [...prev, {
            id, file, preview: reader.result as string,
            studentName: file.name.replace(/\.[^/.]+$/, ''),
          }])
        }
        reader.readAsDataURL(file)
      }
    })
    if (scriptInputRef.current) scriptInputRef.current.value = ''
  }

  const removeScript = (id: string) => {
    setStudentScripts(prev => prev.filter(s => s.id !== id))
  }

  const updateScriptName = (id: string, name: string) => {
    setStudentScripts(prev => prev.map(s => s.id === id ? { ...s, studentName: name } : s))
  }

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setAnswerImage(file)
      const reader = new FileReader()
      reader.onloadend = () => setImagePreview(reader.result as string)
      reader.readAsDataURL(file)
    }
  }

  const clearImage = () => {
    setAnswerImage(null)
    setImagePreview(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleEvaluate = async () => {
    if (!question.trim() && !schemePdf) { setError('Please enter the question text or upload an answer scheme PDF'); return }
    if (mode === 'single' && !studentAnswer.trim() && !answerImage) { setError('Please enter student answer or upload an answer paper image'); return }
    if (mode === 'batch' && studentScripts.length === 0) { setError('Please add at least one student answer script'); return }

    setLoading(true)
    setError('')
    setResult(null)
    setBatchResults([])

    if (mode === 'batch') {
      const results: any[] = []
      for (const script of studentScripts) {
        const formData = new FormData()
        formData.append('file', script.file)
        if (schemePdf) formData.append('scheme_pdf', schemePdf)
        formData.append('student_answer', '')
        formData.append('student_name', script.studentName)
        formData.append('question', question)
        formData.append('subject', subject)
        formData.append('reference_answer', referenceAnswer)
        formData.append('max_marks', String(maxMarks))
        formData.append('question_type', questionType)
        formData.append('expected_formula', expectedFormula)
        formData.append('expected_final_answer', expectedFinalAnswer)
        formData.append('save_history', 'true')

        try {
          const res = await fetch('/api/eval/unified', { method: 'POST', body: formData })
          const data = await res.json()
          results.push({ ...data, studentName: script.studentName, scriptFile: script.file.name })
        } catch (e: any) {
          results.push({ error: e.message, studentName: script.studentName, scriptFile: script.file.name, ai_score: 0, max_score: maxMarks })
        }
      }
      setBatchResults(results)
    } else {
      const formData = new FormData()
      if (answerImage) formData.append('file', answerImage)
      if (schemePdf) formData.append('scheme_pdf', schemePdf)
      formData.append('student_answer', studentAnswer)
      formData.append('question', question)
      formData.append('subject', subject)
      formData.append('reference_answer', referenceAnswer)
      formData.append('max_marks', String(maxMarks))
      formData.append('question_type', questionType)
      formData.append('expected_formula', expectedFormula)
      formData.append('expected_final_answer', expectedFinalAnswer)
      formData.append('save_history', 'true')

      try {
        const res = await fetch('/api/eval/unified', { method: 'POST', body: formData })
        const data = await res.json()
        if (!res.ok) {
          setError(data.detail || 'Evaluation failed')
        } else {
          setResult(data)
        }
      } catch (e: any) {
        setError(e.message || 'Network error')
      }
    }
    setLoading(false)
  }

  const scoreColor = (score: number, max: number) => {
    const pct = (score / max) * 100
    if (pct >= 80) return 'text-emerald-600'
    if (pct >= 50) return 'text-amber-600'
    return 'text-red-600'
  }

  const scoreBg = (score: number, max: number) => {
    const pct = (score / max) * 100
    if (pct >= 80) return 'bg-emerald-50 border-emerald-200'
    if (pct >= 50) return 'bg-amber-50 border-amber-200'
    return 'bg-red-50 border-red-200'
  }

  return (
    <div>
      <Header title="Answer Evaluator" subtitle="Upload answer scheme PDF + student scripts for batch evaluation with OCR" />

      <div className="p-6 space-y-4">
        {/* Mode Toggle */}
        <div className="flex gap-2">
          <button
            onClick={() => setMode('single')}
            className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
              mode === 'single' ? 'bg-indigo-50 border-indigo-300 text-indigo-700' : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
            }`}
          >
            Single Evaluation
          </button>
          <button
            onClick={() => setMode('batch')}
            className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
              mode === 'batch' ? 'bg-indigo-50 border-indigo-300 text-indigo-700' : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
            }`}
          >
            Batch Evaluation (Multiple Scripts)
          </button>
        </div>

        <div className="card p-5 space-y-4">
          <div className="flex items-center gap-2 mb-1">
            <ClipboardCheck className="w-5 h-5 text-indigo-500" />
            <h3 className="text-sm font-semibold text-gray-900">Evaluate Student Answer{mode === 'batch' ? 's' : ''}</h3>
          </div>

          {/* Answer Scheme PDF Upload */}
          <div className="bg-blue-50 border-2 border-dashed border-blue-200 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <FileText className="w-4 h-4 text-blue-600" />
              <span className="text-xs font-semibold text-gray-700">Answer Scheme (PDF)</span>
              <span className="text-[10px] text-gray-400 ml-auto">Extracts questions & reference answers from PDF</span>
            </div>
            <div className="flex items-center gap-3">
              <input
                ref={schemePdfRef}
                type="file"
                accept=".pdf"
                onChange={handleSchemeUpload}
                className="flex-1 text-sm text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-blue-100 file:text-blue-700 hover:file:bg-blue-200"
              />
              {schemePdf && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-blue-700 font-medium">{schemePdf.name}</span>
                  <button onClick={() => { setSchemePdf(null); if (schemePdfRef.current) schemePdfRef.current.value = '' }} className="text-xs text-red-500 hover:text-red-700">Clear</button>
                </div>
              )}
            </div>
          </div>

          {/* Question Type Selection */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-2">Question Type</label>
            <div className="flex gap-2 flex-wrap">
              {TYPE_OPTIONS.map(opt => {
                const Icon = opt.icon
                const active = questionType === opt.value
                return (
                  <button
                    key={opt.value}
                    onClick={() => setQuestionType(opt.value)}
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium border transition-colors ${
                      active
                        ? 'bg-indigo-50 border-indigo-300 text-indigo-700'
                        : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    {opt.label}
                  </button>
                )
              })}
            </div>
            <p className="text-[10px] text-gray-400 mt-1">
              {TYPE_OPTIONS.find(o => o.value === questionType)?.desc}
            </p>
          </div>

          {/* Subject + Max Marks */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Subject</label>
              <select
                value={subject}
                onChange={e => setSubject(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-200"
              >
                {subjects.map(s => <option key={s} value={s}>{s}</option>)}
                <option value="">Other</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Max Marks</label>
              <input
                type="number"
                value={maxMarks}
                onChange={e => setMaxMarks(Number(e.target.value))}
                min={1} max={100}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-200"
              />
            </div>
          </div>

          {/* Question */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Question <span className="text-gray-400 font-normal">(or leave blank if answer scheme PDF has it)</span>
            </label>
            <textarea
              value={question}
              onChange={e => setQuestion(e.target.value)}
              rows={3}
              placeholder="Enter the question text, or upload an answer scheme PDF above..."
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-200 resize-none"
            />
          </div>

          {/* Reference Answer */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Reference / Model Answer <span className="text-gray-400 font-normal">(auto-filled from PDF if uploaded)</span>
            </label>
            <textarea
              value={referenceAnswer}
              onChange={e => setReferenceAnswer(e.target.value)}
              rows={3}
              placeholder="Enter the expected answer, or leave blank to use the answer scheme PDF..."
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-200 resize-none"
            />
          </div>

          {/* Expected Formula / Final Answer (for numerical) */}
          {(questionType === 'numerical' || questionType === 'auto') && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Expected Formula <span className="text-gray-400 font-normal">(optional)</span>
                </label>
                <input
                  type="text"
                  value={expectedFormula}
                  onChange={e => setExpectedFormula(e.target.value)}
                  placeholder="e.g. F = ma, η = 1 - T2/T1"
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-200"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Expected Final Answer <span className="text-gray-400 font-normal">(optional)</span>
                </label>
                <input
                  type="text"
                  value={expectedFinalAnswer}
                  onChange={e => setExpectedFinalAnswer(e.target.value)}
                  placeholder="e.g. 6500 N"
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-200"
                />
              </div>
            </div>
          )}

          {/* Divider */}
          <div className="flex items-center gap-3 py-1">
            <div className="flex-1 h-px bg-gray-200" />
            <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-400">
              {mode === 'batch' ? 'Student Answer Scripts' : 'Student Answer'}
            </span>
            <div className="flex-1 h-px bg-gray-200" />
          </div>

          {mode === 'batch' ? (
            <>
              {/* Batch: Multiple student scripts */}
              <div className="bg-purple-50 border-2 border-dashed border-purple-200 rounded-xl p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Upload className="w-4 h-4 text-purple-600" />
                  <span className="text-xs font-semibold text-gray-700">Upload Student Answer Scripts</span>
                  <span className="text-[10px] text-gray-400 ml-auto">Select multiple images or PDFs — each is OCR'd and scored</span>
                </div>
                <div className="flex items-center gap-3">
                  <input
                    ref={scriptInputRef}
                    type="file"
                    accept="image/*,.pdf"
                    multiple
                    onChange={handleAddScripts}
                    className="flex-1 text-sm text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-purple-100 file:text-purple-700 hover:file:bg-purple-200"
                  />
                </div>
              </div>

              {studentScripts.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-medium text-gray-600">{studentScripts.length} script(s) added:</p>
                  {studentScripts.map(s => (
                    <div key={s.id} className="flex items-center gap-3 p-2 bg-gray-50 rounded-lg">
                      {s.preview ? (
                        <img src={s.preview} alt="" className="w-12 h-12 rounded border border-gray-200 object-cover" />
                      ) : (
                        <div className="w-12 h-12 rounded border border-blue-200 bg-blue-50 flex items-center justify-center">
                          <FileText className="w-5 h-5 text-blue-500" />
                        </div>
                      )}
                      <input
                        type="text"
                        value={s.studentName}
                        onChange={e => updateScriptName(s.id, e.target.value)}
                        placeholder="Student name / USN"
                        className="flex-1 px-2 py-1 text-sm border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-indigo-200"
                      />
                      <button onClick={() => removeScript(s.id)} className="p-1 text-red-400 hover:text-red-600">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </>
          ) : (
            <>
              {/* Single: Answer Paper Image Upload */}
              <div className="bg-gray-50 border-2 border-dashed border-gray-200 rounded-xl p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Camera className="w-4 h-4 text-indigo-500" />
                  <span className="text-xs font-semibold text-gray-700">Upload Answer Paper (Image or PDF)</span>
                  <span className="text-[10px] text-gray-400 ml-auto">OCR for images (LLaVA), text extraction for PDFs</span>
                </div>
                <div className="flex items-center gap-3">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*,.pdf"
                    onChange={handleImageChange}
                    className="flex-1 text-sm text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-indigo-50 file:text-indigo-600 hover:file:bg-indigo-100"
                  />
                  {answerImage && (
                    <button onClick={clearImage} className="text-xs text-red-500 hover:text-red-700">Clear</button>
                  )}
                </div>
                {answerImage && (
                  <div className="mt-3">
                    {answerImage.type === 'application/pdf' ? (
                      <div className="flex items-center gap-2 p-3 bg-blue-50 rounded-lg border border-blue-200">
                        <FileText className="w-5 h-5 text-blue-600" />
                        <span className="text-sm text-blue-800 font-medium">{answerImage.name}</span>
                      </div>
                    ) : imagePreview ? (
                      <img src={imagePreview} alt="Answer paper preview" className="max-h-48 rounded-lg border border-gray-200" />
                    ) : null}
                  </div>
                )}
              </div>

              {/* OR divider */}
              <div className="flex items-center gap-3">
                <div className="flex-1 h-px bg-gray-200" />
                <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-400">or type answer</span>
                <div className="flex-1 h-px bg-gray-200" />
              </div>

              {/* Typed Student Answer */}
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Student Answer (typed)</label>
                <textarea
                  value={studentAnswer}
                  onChange={e => setStudentAnswer(e.target.value)}
                  rows={5}
                  placeholder="Type or paste the student's answer here..."
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-200 resize-none font-mono"
                />
              </div>
            </>
          )}

          {/* Evaluate Button */}
          <button
            onClick={handleEvaluate}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-indigo-600 text-white text-sm font-semibold rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ClipboardCheck className="w-4 h-4" />}
            {loading ? (mode === 'batch' ? `Evaluating ${studentScripts.length} scripts...` : 'Evaluating...') : (mode === 'batch' ? `Evaluate ${studentScripts.length} Script${studentScripts.length !== 1 ? 's' : ''}` : 'Evaluate Answer')}
          </button>

          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-50 text-red-700 text-xs rounded-lg">
              <XCircle className="w-4 h-4 shrink-0" />
              {error}
            </div>
          )}
        </div>

        {/* Batch Results */}
        {batchResults.length > 0 && (
          <div className="card p-5">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Batch Evaluation Results</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-2 px-3 text-xs font-semibold text-gray-500">#</th>
                    <th className="text-left py-2 px-3 text-xs font-semibold text-gray-500">Student</th>
                    <th className="text-left py-2 px-3 text-xs font-semibold text-gray-500">File</th>
                    <th className="text-left py-2 px-3 text-xs font-semibold text-gray-500">Score</th>
                    <th className="text-left py-2 px-3 text-xs font-semibold text-gray-500">Type</th>
                    <th className="text-left py-2 px-3 text-xs font-semibold text-gray-500">OCR Confidence</th>
                    <th className="text-left py-2 px-3 text-xs font-semibold text-gray-500">Feedback</th>
                  </tr>
                </thead>
                <tbody>
                  {batchResults.map((r, i) => (
                    <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="py-2 px-3 text-xs text-gray-500">{i + 1}</td>
                      <td className="py-2 px-3 text-xs font-medium text-gray-800">{r.studentName}</td>
                      <td className="py-2 px-3 text-xs text-gray-500">{r.scriptFile}</td>
                      <td className="py-2 px-3">
                        <span className={`text-sm font-bold ${scoreColor(r.ai_score || 0, r.max_score || maxMarks)}`}>
                          {r.ai_score ?? '?'}/{r.max_score || maxMarks}
                        </span>
                      </td>
                      <td className="py-2 px-3">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-indigo-50 text-indigo-700">
                          {r.question_type || '—'}
                        </span>
                      </td>
                      <td className="py-2 px-3">
                        {r.ocr_used ? (
                          <span className={`text-xs font-medium ${(r.confidence || 0) >= 0.7 ? 'text-emerald-600' : (r.confidence || 0) >= 0.4 ? 'text-amber-600' : 'text-red-600'}`}>
                            {((r.confidence || 0) * 100).toFixed(0)}%
                            {(r.confidence || 0) < 0.5 && (
                              <AlertTriangle className="w-3 h-3 inline ml-1 text-amber-500" />
                            )}
                          </span>
                        ) : <span className="text-xs text-gray-400">N/A</span>}
                      </td>
                      <td className="py-2 px-3 text-xs text-gray-600 max-w-xs truncate">{r.feedback || r.error || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-4 pt-3 border-t border-gray-200 flex items-center justify-between">
              <p className="text-xs text-gray-500">
                Results saved to evaluation history — view in <a href="/evaluated-scripts" className="text-indigo-600 hover:underline">Evaluated Answer Scripts</a>
              </p>
              <div className="text-sm font-semibold text-gray-700">
                Avg: {(batchResults.reduce((sum, r) => sum + (r.ai_score || 0), 0) / batchResults.length).toFixed(1)}/{maxMarks}
              </div>
            </div>
          </div>
        )}

        {/* Single Result */}
        {result && (
          <div className="space-y-4">
            {/* Score Card */}
            <div className="card p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className={`text-3xl font-bold ${scoreColor(result.ai_score, result.max_score)}`}>
                    {result.ai_score}/{result.max_score}
                  </div>
                  <div>
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-indigo-50 text-indigo-700">
                      {result.question_type === 'theory' && <FileText className="w-3 h-3" />}
                      {result.question_type === 'numerical' && <Calculator className="w-3 h-3" />}
                      {result.question_type === 'drawing' && <PenTool className="w-3 h-3" />}
                      {result.question_type?.charAt(0).toUpperCase() + result.question_type?.slice(1)}
                    </span>
                    <p className="text-[10px] text-gray-400 mt-0.5">
                      Confidence: {((result.confidence || 0) * 100).toFixed(0)}%
                      {(result.confidence || 0) < 0.5 && (
                        <span className="ml-1 text-amber-500 font-medium">(Low — consider manual review)</span>
                      )}
                    </p>
                  </div>
                </div>

                {result.ocr_used && (
                  <span className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs bg-purple-50 text-purple-700">
                    <Camera className="w-3 h-3" />
                    OCR: {result.ocr_method}
                  </span>
                )}
              </div>

              {/* Equation Check */}
              <div className="flex items-center gap-4 text-xs mb-3">
                <span className={`flex items-center gap-1 ${result.equation_required ? (result.equation_present ? 'text-emerald-600' : 'text-red-600') : 'text-gray-400'}`}>
                  {result.equation_required ? (
                    result.equation_present ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />
                  ) : (
                    <span className="w-3.5 h-3.5 rounded-full bg-gray-200 inline-block" />
                  )}
                  {result.equation_required
                    ? (result.equation_present ? 'Equation present' : 'Equation missing (-1)')
                    : 'No equation required'}
                </span>

                {result.question_type === 'numerical' && (
                  <>
                    <span className={`flex items-center gap-1 ${result.formula_mentioned ? 'text-emerald-600' : 'text-red-600'}`}>
                      {result.formula_mentioned ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                      {result.formula_mentioned ? 'Formula mentioned' : 'Formula missing (-1)'}
                    </span>
                    <span className={`flex items-center gap-1 ${result.final_answer_correct ? 'text-emerald-600' : 'text-red-600'}`}>
                      {result.final_answer_correct ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                      {result.final_answer_correct ? 'Final answer correct' : 'Final answer wrong (-2)'}
                    </span>
                  </>
                )}
              </div>

              {/* Feedback */}
              <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-700 space-y-2">
                <p><strong>Feedback:</strong> {result.feedback}</p>
                <p className="text-gray-500"><strong>Explanation:</strong> {result.explanation}</p>
              </div>
            </div>

            {/* OCR Extracted Text */}
            {result.ocr_used && result.ocr_text && (
              <div className="card p-5">
                <h4 className="text-xs font-semibold text-gray-700 mb-2 flex items-center gap-1.5">
                  <Camera className="w-3.5 h-3.5 text-purple-500" />
                  OCR Extracted Text
                </h4>
                <pre className="text-xs text-gray-600 bg-gray-50 p-3 rounded-lg whitespace-pre-wrap font-mono max-h-48 overflow-y-auto">
                  {result.ocr_text}
                </pre>
              </div>
            )}

            {/* Keywords (Theory) */}
            {result.keywords && (
              <div className="card p-5">
                <h4 className="text-xs font-semibold text-gray-700 mb-3">Keyword Analysis</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-[10px] font-semibold text-emerald-600 uppercase tracking-wide mb-1">
                      Matched ({result.keywords.matched_count})
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {(result.keywords.found || []).map((k: string) => (
                        <span key={k} className="px-2 py-0.5 bg-emerald-50 text-emerald-700 text-[10px] rounded-full">{k}</span>
                      ))}
                      {(result.keywords.found || []).length === 0 && (
                        <span className="text-[10px] text-gray-400">None</span>
                      )}
                    </div>
                  </div>
                  <div>
                    <p className="text-[10px] font-semibold text-red-600 uppercase tracking-wide mb-1">
                      Missing ({result.keywords.missing?.length || 0})
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {(result.keywords.missing || []).map((k: string) => (
                        <span key={k} className="px-2 py-0.5 bg-red-50 text-red-700 text-[10px] rounded-full">{k}</span>
                      ))}
                      {(result.keywords.missing || []).length === 0 && (
                        <span className="text-[10px] text-gray-400">None</span>
                      )}
                    </div>
                  </div>
                </div>
                {result.keyword_score !== undefined && result.semantic_score !== undefined && (
                  <div className="mt-3 flex gap-4 text-xs text-gray-500">
                    <span>Keyword score: {result.keyword_score}/{result.max_score}</span>
                    <span>Semantic score: {result.semantic_score}/{result.max_score}</span>
                  </div>
                )}
              </div>
            )}

            {/* Steps (Numerical) */}
            {result.steps && result.steps.length > 0 && (
              <div className="card p-5">
                <h4 className="text-xs font-semibold text-gray-700 mb-3">Step-by-Step Breakdown</h4>
                <div className="space-y-2">
                  {result.steps.map((step: any, i: number) => (
                    <div key={i} className={`flex items-start gap-3 p-2.5 rounded-lg text-xs ${step.correct ? 'bg-emerald-50' : 'bg-red-50'}`}>
                      <span className={`w-5 h-5 rounded-full flex items-center justify-center text-white text-[10px] font-bold shrink-0 ${step.correct ? 'bg-emerald-500' : 'bg-red-500'}`}>
                        {step.step}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-gray-800">{step.description}</p>
                        <p className="text-gray-500 mt-0.5">{step.student_work}</p>
                        {!step.correct && (
                          <p className="text-red-600 mt-0.5">
                            <span className="font-medium">{step.error_type?.replace('_', ' ')}:</span> {step.explanation}
                          </p>
                        )}
                      </div>
                      <span className={`text-xs font-semibold shrink-0 ${step.correct ? 'text-emerald-600' : 'text-red-600'}`}>
                        {step.earned}/{step.marks}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Drawing Details */}
            {result.question_type === 'drawing' && result.vlm_output && (
              <div className="card p-5">
                <h4 className="text-xs font-semibold text-gray-700 mb-3">Drawing Analysis</h4>
                <div className="grid grid-cols-2 gap-4 text-xs">
                  <div>
                    <p className="text-gray-500 mb-1">Views Detected</p>
                    <div className="flex gap-1">
                      {(result.vlm_output.views_detected || []).map((v: string) => (
                        <span key={v} className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full">{v}</span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="text-gray-500 mb-1">Projection</p>
                    <p className="font-medium text-gray-800">{result.vlm_output.projection_angle || 'unknown'}</p>
                  </div>
                </div>

                {result.violations && result.violations.length > 0 && (
                  <div className="mt-3">
                    <p className="text-[10px] font-semibold text-red-600 uppercase tracking-wide mb-1">IS/BIS Violations</p>
                    {result.violations.map((v: any, i: number) => (
                      <div key={i} className="flex items-center gap-2 p-2 bg-red-50 rounded-lg mb-1 text-xs">
                        <AlertTriangle className="w-3.5 h-3.5 text-red-500 shrink-0" />
                        <span className="font-medium text-red-700">{v.clause}</span>
                        <span className="text-red-600 flex-1">{v.issue}</span>
                        <span className="text-red-700 font-semibold">-{v.deduction}</span>
                      </div>
                    ))}
                  </div>
                )}

                {result.missing_parts && result.missing_parts.length > 0 && (
                  <div className="mt-2 text-xs">
                    <span className="text-red-600 font-medium">Missing parts: </span>
                    {result.missing_parts.join(', ')}
                  </div>
                )}
                {result.missing_dimensions && result.missing_dimensions.length > 0 && (
                  <div className="mt-1 text-xs">
                    <span className="text-red-600 font-medium">Missing dimensions: </span>
                    {result.missing_dimensions.join(', ')}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
