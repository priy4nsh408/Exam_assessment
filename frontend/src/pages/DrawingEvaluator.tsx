import { useState } from 'react'
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

  return (
    <div>
      <Header title="Engineering Drawing Evaluator" subtitle="YOLOv8 element detection · LLaVA VLM · IS 696 / SP:46 / IS 919 / IS 3073 compliance" />
      <div className="p-6 grid grid-cols-3 gap-6">
        <div className="col-span-1 space-y-4">
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-3">Upload Drawing</h2>
            <div className="border-2 border-dashed border-gray-200 rounded-lg p-8 text-center cursor-pointer hover:border-indigo-300 transition-colors">
              <ImageIcon className="w-10 h-10 text-gray-200 mx-auto mb-2" />
              <p className="text-xs font-medium text-gray-600">Photograph or scan</p>
              <p className="text-xs text-gray-400">JPEG / PNG · max 10 MB</p>
            </div>
            <div className="mt-3 space-y-2">
              <div><label className="label">Student USN</label><input className="input" defaultValue="1RV23AS060" /></div>
              <div><label className="label">Assignment</label><select className="select"><option>Drawing Sheet 3 — Orthographic Projection</option></select></div>
            </div>
            <button className="btn-primary w-full justify-center mt-3" onClick={async () => { setProcessing(true); await new Promise(r => setTimeout(r, 2500)); setProcessing(false); setResult(true) }}>
              {processing ? <><div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />Processing with YOLOv8...</> : 'Evaluate Drawing'}
            </button>
          </div>

          {result && (
            <div className="card p-5">
              <h2 className="text-sm font-semibold text-gray-900 mb-3">IS/BIS Violations</h2>
              <div className="space-y-2">
                {VIOLATIONS.map((v, i) => (
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
                    <h2 className="text-sm font-semibold text-gray-900">Taran Nithin Rao · 1RV23AS060</h2>
                    <p className="text-xs text-gray-500">Drawing Sheet 3 — Orthographic Projection</p>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold text-amber-600">16<span className="text-sm font-normal text-gray-400">/20</span></p>
                    <p className="text-xs text-gray-400">3 IS violations found · -6 pts total</p>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  {DETECTED.map(d => (
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

              <div className="card p-5">
                <h3 className="text-sm font-semibold text-gray-900 mb-3">VLM Interpretation (LLaVA output)</h3>
                <pre className="text-xs bg-gray-50 rounded-lg p-4 border border-gray-100 overflow-auto text-gray-700 font-mono leading-relaxed">{JSON.stringify(vlmOutput, null, 2)}</pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
