import { useState, useEffect } from 'react'
import { FileText, ClipboardCheck, Download, ListChecks } from 'lucide-react'
import { Header } from '../components/layout/Header'
import { BloomBadge } from '../components/ui/BloomBadge'

type Tab = 'paper' | 'scheme'

const CO_CODES = ['CO1', 'CO2', 'CO3', 'CO4', 'CO5']

async function downloadPdf(url: string, filename: string) {
  const res = await fetch(url)
  if (!res.ok) {
    const detail = await res.json().catch(() => null)
    throw new Error(detail?.detail || 'Export failed')
  }
  const blob = await res.blob()
  const objectUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = objectUrl
  a.download = filename
  a.click()
  URL.revokeObjectURL(objectUrl)
}

export default function ExamPapers() {
  const [exams, setExams] = useState<any[]>([])
  const [questionsById, setQuestionsById] = useState<Record<string, any>>({})
  const [schemesByQuestionId, setSchemesByQuestionId] = useState<Record<string, any>>({})
  const [selectedExamId, setSelectedExamId] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>('paper')
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [showCOEditor, setShowCOEditor] = useState(false)
  const [coDescriptions, setCoDescriptions] = useState<Record<string, string>>({})
  const [coLoading, setCoLoading] = useState(false)
  const [coSaving, setCoSaving] = useState(false)

  useEffect(() => {
    Promise.all([
      fetch('/api/exams').then(r => r.json()).catch(() => ({ exams: [] })),
      fetch('/api/questions').then(r => r.json()).catch(() => ({ questions: [] })),
      fetch('/api/answer-schemes').then(r => r.json()).catch(() => ({ answerSchemes: [] })),
    ]).then(([examsData, questionsData, schemesData]) => {
      const examList = examsData.exams || []
      setExams(examList)
      if (examList.length > 0) setSelectedExamId(examList[0].id)

      const qMap: Record<string, any> = {}
      for (const q of questionsData.questions || []) qMap[q.id] = q
      setQuestionsById(qMap)

      const sMap: Record<string, any> = {}
      for (const s of schemesData.answerSchemes || []) {
        // keep the most recent scheme per question (list is already created_at DESC)
        if (!sMap[s.questionId]) sMap[s.questionId] = s
      }
      setSchemesByQuestionId(sMap)
      setLoading(false)
    })
  }, [])

  const selectedExam = exams.find(e => e.id === selectedExamId)
  const examQuestions: any[] = selectedExam
    ? selectedExam.questions.map((qid: string) => questionsById[qid]).filter(Boolean)
    : []

  const handleExportPaper = async () => {
    if (!selectedExam) return
    setExporting(true)
    try {
      await downloadPdf(`/api/exams/${selectedExam.id}/export/paper`, `${selectedExam.id}_question_paper.pdf`)
    } catch (e: any) {
      alert(e.message || 'Export failed — is the backend running?')
    }
    setExporting(false)
  }

  const handleExportScheme = async () => {
    if (!selectedExam) return
    setExporting(true)
    try {
      await downloadPdf(`/api/exams/${selectedExam.id}/export/scheme`, `${selectedExam.id}_answer_scheme.pdf`)
    } catch (e: any) {
      alert(e.message || 'Export failed — is the backend running?')
    }
    setExporting(false)
  }

  const openCOEditor = async () => {
    if (!selectedExam) return
    setShowCOEditor(true)
    setCoLoading(true)
    try {
      const res = await fetch(`/api/co-descriptions/${encodeURIComponent(selectedExam.subject)}`)
      const data = await res.json()
      const merged: Record<string, string> = {}
      for (const co of CO_CODES) merged[co] = data.descriptions?.[co] || ''
      setCoDescriptions(merged)
    } catch {
      setCoDescriptions(Object.fromEntries(CO_CODES.map(co => [co, ''])))
    }
    setCoLoading(false)
  }

  const saveCoDescriptions = async () => {
    if (!selectedExam) return
    setCoSaving(true)
    try {
      const nonEmpty = Object.fromEntries(Object.entries(coDescriptions).filter(([, v]) => v.trim()))
      const res = await fetch(`/api/co-descriptions/${encodeURIComponent(selectedExam.subject)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ descriptions: nonEmpty }),
      })
      if (!res.ok) throw new Error('Save failed')
      setShowCOEditor(false)
    } catch {
      alert('Could not save CO descriptions — is the backend running?')
    }
    setCoSaving(false)
  }

  return (
    <div>
      <Header
        title="Exam Papers"
        subtitle="Question paper assembly + answer scheme with validation"
        actions={
          selectedExam ? (
            <div className="flex items-center gap-2">
              <button className="btn-secondary" onClick={openCOEditor}>
                <ListChecks className="w-4 h-4" /> CO Descriptions
              </button>
              <button
                className="btn-secondary"
                onClick={tab === 'paper' ? handleExportPaper : handleExportScheme}
                disabled={exporting}
              >
                <Download className="w-4 h-4" />
                {exporting ? 'Exporting…' : `Export ${tab === 'paper' ? 'Paper' : 'Scheme'} (PDF)`}
              </button>
            </div>
          ) : null
        }
      />

      <div className="p-6 grid grid-cols-3 gap-6">
        {/* Exam list */}
        <div className="col-span-1 space-y-2">
          <h2 className="text-sm font-semibold text-gray-900 mb-2">Exams ({exams.length})</h2>
          {loading && <p className="text-xs text-gray-400">Loading...</p>}
          {!loading && exams.length === 0 && (
            <div className="card p-5 text-center">
              <p className="text-xs text-gray-400">No exam papers yet — publish one from Question Generator.</p>
            </div>
          )}
          {exams.map(exam => (
            <button
              key={exam.id}
              onClick={() => setSelectedExamId(exam.id)}
              className={`w-full text-left card p-4 transition-colors ${selectedExamId === exam.id ? 'ring-2 ring-indigo-400 border-indigo-200' : 'hover:bg-gray-50'}`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-mono text-gray-400">{exam.id}</span>
                <span className={`badge ${exam.status === 'published' ? 'bg-emerald-50 text-emerald-600' : 'bg-gray-100 text-gray-500'}`}>{exam.status}</span>
              </div>
              <p className="text-sm font-medium text-gray-800">{exam.title}</p>
              <p className="text-xs text-gray-400 mt-1">{exam.questions.length} questions · {exam.totalMarks} marks</p>
            </button>
          ))}
        </div>

        {/* Detail with tabs */}
        <div className="col-span-2">
          {!selectedExam ? (
            <div className="card h-full flex items-center justify-center p-12">
              <p className="text-sm text-gray-400">Select an exam paper to view its questions and answer scheme</p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Tabs */}
              <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit">
                <button
                  onClick={() => setTab('paper')}
                  className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-md transition-colors ${tab === 'paper' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500'}`}
                >
                  <FileText className="w-3.5 h-3.5" /> Question Paper
                </button>
                <button
                  onClick={() => setTab('scheme')}
                  className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-md transition-colors ${tab === 'scheme' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500'}`}
                >
                  <ClipboardCheck className="w-3.5 h-3.5" /> Answer Scheme
                </button>
              </div>

              <div className="card p-4 flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-semibold text-gray-900">{selectedExam.title}</h2>
                  <p className="text-xs text-gray-500">{selectedExam.subject} · {selectedExam.duration} min</p>
                  {(selectedExam.courseCode || selectedExam.cieLabel) && (
                    <p className="text-[11px] text-gray-400 mt-0.5">
                      {[selectedExam.cieLabel, selectedExam.courseCode, selectedExam.semester ? `Sem ${selectedExam.semester}` : null]
                        .filter(Boolean).join(' · ')}
                    </p>
                  )}
                </div>
                <p className="text-lg font-bold text-gray-900">{selectedExam.totalMarks} <span className="text-xs font-normal text-gray-400">marks</span></p>
              </div>

              {examQuestions.length === 0 && (
                <div className="card p-6 text-center">
                  <p className="text-xs text-gray-400">
                    This exam references questions not found in the current Question Bank
                    (e.g. mock seed data) — generate matching questions to populate this view.
                  </p>
                </div>
              )}

              {tab === 'paper' && examQuestions.map((q, i) => (
                <div key={q.id} className="card p-4">
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <span className="text-xs font-semibold text-gray-700">Q{i + 1}</span>
                    <span className="text-xs font-mono text-gray-400">{q.id}</span>
                    <BloomBadge level={q.bloomLevel} />
                    <span className="badge bg-indigo-50 text-indigo-600">{q.co}</span>
                    <span className="ml-auto text-xs font-semibold text-gray-700">{q.marks} marks</span>
                  </div>
                  <p className="text-sm text-gray-700 leading-relaxed">{q.text}</p>
                </div>
              ))}

              {tab === 'scheme' && examQuestions.map((q, i) => {
                const scheme = schemesByQuestionId[q.id]
                const answerKey = scheme?.answerKey || q.answerKey
                const explanation = scheme?.explanation || q.answerKeyExplanation
                return (
                  <div key={q.id} className="card p-4">
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <span className="text-xs font-semibold text-gray-700">Q{i + 1}</span>
                      <span className="text-xs font-mono text-gray-400">{q.id}</span>
                      {scheme && <span className="badge bg-violet-50 text-violet-700 font-mono">{scheme.id}</span>}
                      <span className="ml-auto text-xs font-semibold text-gray-700">{q.marks} marks</span>
                    </div>
                    <p className="text-xs text-gray-500 mb-3">{q.text}</p>
                    <div className="bg-emerald-50 border border-emerald-100 rounded-lg p-3 mb-2">
                      <p className="text-[10px] font-semibold text-emerald-700 uppercase tracking-wide mb-1">Model Answer</p>
                      <p className="text-xs text-emerald-900 leading-relaxed whitespace-pre-wrap">
                        {answerKey || 'No answer key generated for this question yet.'}
                      </p>
                    </div>
                    {explanation && (
                      <div className="bg-indigo-50 border border-indigo-100 rounded-lg p-3">
                        <p className="text-[10px] font-semibold text-indigo-700 uppercase tracking-wide mb-1">Validation</p>
                        <p className="text-xs text-indigo-800 leading-relaxed">{explanation}</p>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {showCOEditor && selectedExam && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 space-y-4">
            <div>
              <h2 className="text-sm font-semibold text-gray-900">Course Outcome descriptions</h2>
              <p className="text-xs text-gray-500 mt-0.5">
                For <span className="font-medium">{selectedExam.subject}</span> — shown in the footer table of every exported PDF for this subject.
              </p>
            </div>
            {coLoading ? (
              <p className="text-xs text-gray-400">Loading…</p>
            ) : (
              <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
                {CO_CODES.map(co => (
                  <label key={co} className="block text-xs text-gray-600">
                    {co}
                    <textarea
                      className="input mt-1 w-full"
                      rows={2}
                      placeholder={`Description for ${co} (leave blank to omit from the PDF)`}
                      value={coDescriptions[co] || ''}
                      onChange={e => setCoDescriptions(prev => ({ ...prev, [co]: e.target.value }))}
                    />
                  </label>
                ))}
              </div>
            )}
            <div className="flex justify-end gap-2 pt-2">
              <button className="btn-secondary" onClick={() => setShowCOEditor(false)} disabled={coSaving}>
                Cancel
              </button>
              <button className="btn-primary" onClick={saveCoDescriptions} disabled={coSaving || coLoading}>
                {coSaving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
