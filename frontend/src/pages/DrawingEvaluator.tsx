import { useState, useRef } from 'react'
import { Upload, ImageIcon } from 'lucide-react'
import { Header } from '../components/layout/Header'

const VIOLATIONS = [
  { clause: 'IS 696:1972 Clause 6.3', issue: 'Third angle projection used instead of first angle', severity: 'major', deduction: 4 },
  { clause: 'IS 919:1993 Clause 4.1', issue: 'Dimensional tolerance notation non-standard', severity: 'minor', deduction: 1 },
  { clause: 'SP:46:2003 Section 8', issue: 'Title block incomplete — material specification missing', severity: 'minor', deduction: 1 },
]
const DETECTED = [
  { element: 'Front View', status: 'detected', score: '4/5' },
  { element: 'Top View', status: 'detected', score: '4/5' },
  { element: 'Side View', status: 'detected', score: '3/5' },
  { element: 'Dimension Lines', status: 'detected', score: '3/4' },
  { element: 'Title Block', status: 'detected', score: '2/3' },
  { element: 'GD&T Frame', status: 'not_detected', score: '0/3' },
]

const vlmOutput = {
  view_type: "orthographic",
  projection_angle: "third_angle",
  views_detected: ["front", "top", "side"],
  dimensions: ["45mm", "30mm", "60mm", "R15"],
  tolerances: ["0.5+/-", "H7/f6"],
  GDT_symbols: [],
  surface_finish: ["Ra 3.2"],
  title_block: { drawing_no: "ME-003", scale: "1:1", material: null, date: "2026-05-10" }
}

export default function DrawingEvaluator() {
  const [result, setResult] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [drawingResult, setDrawingResult] = useState<any>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [usnValue, setUsnValue] = useState('1RV23AS060')
  const [answerId, setAnswerId] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] ?? null
    setSelectedFile(f)
  }

  const handleEvaluate = async () => {
    setProcessing(true)
    const formData = new FormData()
    formData.append('max_marks', '20')
    formData.append('student_usn', usnValue)
    formData.append('assignment', 'Drawing Sheet 3')
    if (answerId.trim()) formData.append('answer_id', answerId.trim())
    if (selectedFile) formData.append('file', selectedFile)

    try {
      const res = await fetch('/api/eval/drawing', { method: 'POST', body: formData })
      const data = await res.json()
      setDrawingResult(data)
    } catch {
      setDrawingResult(null)
    }
    setProcessing(false)
    setResult(true)
  }

  return (
    <div>
      <Header title="Engineering Drawing Evaluator" subtitle="YOLOv8 element detection · LLaVA VLM · IS 696 / SP:46 / IS 919 / IS 3073 compliance" />
      <div className="p-6 grid grid-cols-3 gap-6">
        <div className="col-span-1 space-y-4">
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-3">Upload Drawing</h2>
            <input ref={fileRef} type="file" accept="image/*,.pdf" className="hidden" onChange={handleFileChange} />
            <div
              className="border-2 border-dashed border-gray-200 rounded-lg p-8 text-center cursor-pointer hover:border-indigo-300 transition-colors"
              onClick={() => fileRef.current?.click()}
            >
              <ImageIcon className="w-10 h-10 text-gray-200 mx-auto mb-2" />
              {selectedFile
                ? <p className="text-xs font-medium text-indigo-600">{selectedFile.name}</p>
                : <><p className="text-xs font-medium text-gray-600">Click to select drawing</p><p className="text-xs text-gray-400">JPEG / PNG · max 10 MB</p></>
              }
            </div>
            <div className="mt-3 space-y-2">
              <div><label className="label">Student USN</label><input className="input" value={usnValue} onChange={e => setUsnValue(e.target.value)} /></div>
              <div><label className="label">Answer ID (optional — grades against a real answer scheme)</label><input className="input font-mono text-xs" value={answerId} onChange={e => setAnswerId(e.target.value)} placeholder="e.g. AK-20260624-A1B2C3" /></div>
              <div><label className="label">Assignment</label><select className="select"><option>Drawing Sheet 3 — Orthographic Projection</option></select></div>
            </div>
            <button className="btn-primary w-full justify-center mt-3" onClick={handleEvaluate}>
              {processing ? <><div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />Processing with YOLOv8...</> : 'Evaluate Drawing'}
            </button>
          </div>

          {result && (
            <div className="card p-5">
              <h2 className="text-sm font-semibold text-gray-900 mb-3">IS/BIS Violations</h2>
              <div className="space-y-2">
                {(drawingResult?.violations ?? VIOLATIONS).map((v: any, i: number) => (
                  <div key={i} className={`p-2.5 rounded-lg border text-xs ${v.severity === 'major' ? 'bg-red-50 border-red-200' : 'bg-amber-50 border-amber-200'}`}>
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="font-mono text-[10px] text-gray-500">{v.clause}</span>
                      <span className={`font-bold ${v.severity === 'major' ? 'text-red-600' : 'text-amber-600'}`}>-{v.deduction} pts</span>
                    </div>
                    <p className={v.severity === 'major' ? 'text-red-700' : 'text-amber-700'}>{v.issue}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="col-span-2">
          {!result && !processing && (
            <div className="card h-full flex items-center justify-center p-12">
              <div className="text-center">
                <ImageIcon className="w-14 h-14 text-gray-200 mx-auto mb-3" />
                <p className="text-sm text-gray-400">Upload a drawing to begin evaluation</p>
                <p className="text-xs text-gray-300 mt-1">OpenCV preprocessing — YOLOv8 detection — LLaVA interpretation — IS clause validation</p>
              </div>
            </div>
          )}
          {processing && (
            <div className="card h-64 flex items-center justify-center">
              <div className="text-center space-y-2">
                <div className="w-10 h-10 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mx-auto" style={{ borderWidth: 3, borderStyle: 'solid' }} />
                <p className="text-sm text-gray-700">Processing pipeline...</p>
                <p className="text-xs text-gray-400">OpenCV preprocessing — YOLOv8 detection — LLaVA VLM — IS validation</p>
              </div>
            </div>
          )}
          {result && !processing && (
            <div className="space-y-4">
              <div className="card p-5">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h2 className="text-sm font-semibold text-gray-900">Taran Nithin Rao · 1RV23AS060{drawingResult?.answerId ? ` · ${drawingResult.answerId}` : ''}</h2>
                    <p className="text-xs text-gray-500">Drawing Sheet 3 — Orthographic Projection</p>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold text-amber-600">{drawingResult?.ai_score ?? 16}<span className="text-sm font-normal text-gray-400">/{drawingResult?.max_score ?? 20}</span></p>
                    <p className="text-xs text-gray-400">{drawingResult?.violations?.length ?? 3} IS violations found · -6 pts total</p>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  {(drawingResult?.detected_elements ?? DETECTED).map((d: any) => (
                    <div key={d.element} className={`rounded-lg p-3 border text-center ${d.status === 'detected' ? 'bg-gray-50 border-gray-200' : 'bg-red-50 border-red-200'}`}>
                      <p className="text-xs font-medium text-gray-700 mb-1">{d.element}</p>
                      <p className={`text-lg font-bold ${d.status === 'detected' ? 'text-gray-800' : 'text-red-600'}`}>{d.score}</p>
                      <p className={`text-[10px] ${d.status === 'detected' ? 'text-emerald-600' : 'text-red-500'}`}>
                        {d.status === 'detected' ? 'Detected' : 'Not found'}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              {drawingResult?.explanation && (
                <div className="card p-5">
                  <h3 className="text-sm font-semibold text-gray-900 mb-2">Why this score — marks awarded / deducted</h3>
                  <div className="bg-indigo-50 border border-indigo-100 rounded-lg p-3">
                    <p className="text-xs text-indigo-700">{drawingResult.explanation}</p>
                  </div>
                </div>
              )}

              {drawingResult?.rubric && (
                <div className="card p-5">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">Parts & Dimensions Rubric</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-xs font-medium text-emerald-700 mb-2">Matched parts ({drawingResult.rubric.matched_parts?.length ?? 0})</p>
                      <div className="flex flex-wrap gap-1.5 mb-3">
                        {(drawingResult.rubric.matched_parts ?? []).map((p: string) => <span key={p} className="badge bg-emerald-50 text-emerald-700">{p}</span>)}
                      </div>
                      <p className="text-xs font-medium text-red-600 mb-2">Missing parts ({drawingResult.rubric.missing_parts?.length ?? 0}) · -1 each</p>
                      <div className="flex flex-wrap gap-1.5">
                        {(drawingResult.rubric.missing_parts ?? []).map((p: string) => <span key={p} className="badge bg-red-50 text-red-600">{p}</span>)}
                      </div>
                    </div>
                    <div>
                      <p className="text-xs font-medium text-emerald-700 mb-2">Matched dimensions ({drawingResult.rubric.matched_dimensions?.length ?? 0})</p>
                      <div className="flex flex-wrap gap-1.5 mb-3">
                        {(drawingResult.rubric.matched_dimensions ?? []).map((d: string) => <span key={d} className="badge bg-emerald-50 text-emerald-700">{d}</span>)}
                      </div>
                      <p className="text-xs font-medium text-amber-700 mb-2">Missing ({drawingResult.rubric.missing_dimensions?.length ?? 0}) · -0.5 each</p>
                      <div className="flex flex-wrap gap-1.5 mb-3">
                        {(drawingResult.rubric.missing_dimensions ?? []).map((d: string) => <span key={d} className="badge bg-amber-50 text-amber-700">{d}</span>)}
                      </div>
                      {(drawingResult.rubric.wrong_dimensions ?? []).length > 0 && (
                        <>
                          <p className="text-xs font-medium text-red-600 mb-2">Wrong values ({drawingResult.rubric.wrong_dimensions.length}) · -1 each</p>
                          <div className="flex flex-wrap gap-1.5">
                            {drawingResult.rubric.wrong_dimensions.map((w: any, i: number) => (
                              <span key={i} className="badge bg-red-50 text-red-600">expected {w.expected}, found {w.found}</span>
                            ))}
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              )}

              <div className="card p-5">
                <h3 className="text-sm font-semibold text-gray-900 mb-3">VLM Interpretation (LLaVA output)</h3>
                <pre className="text-xs bg-gray-50 rounded-lg p-4 border border-gray-100 overflow-auto text-gray-700 font-mono leading-relaxed">{JSON.stringify(drawingResult?.vlm_output ?? vlmOutput, null, 2)}</pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
