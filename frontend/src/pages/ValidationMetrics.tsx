import { useState, useEffect } from 'react'
import { Header } from '../components/layout/Header'
import { CheckCircle, AlertCircle, BarChart3 } from 'lucide-react'

export default function ValidationMetrics() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch('/api/eval/validate/kappa')
      .then(r => r.json())
      .then(setData)
      .catch(() => setError('Could not load validation metrics — is the backend running?'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div>
      <Header
        title="Validation Metrics"
        subtitle="Cohen's Kappa inter-rater agreement · AI vs Faculty scores · Target κ ≥ 0.75"
      />
      <div className="p-6 space-y-6">
        {loading && (
          <div className="card p-8 flex items-center justify-center gap-3">
            <div className="w-5 h-5 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
            <p className="text-sm text-gray-500">Computing validation metrics…</p>
          </div>
        )}
        {error && (
          <div className="card p-6 bg-red-50 border-red-200">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}
        {data && (
          <>
            {/* Kappa summary */}
            <div className="grid grid-cols-4 gap-4">
              <div className={`card p-5 col-span-1 ${data.target_met ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'}`}>
                <p className="text-xs font-medium text-gray-600 mb-1">Cohen's κ</p>
                <p className={`text-4xl font-bold ${data.target_met ? 'text-emerald-600' : 'text-amber-600'}`}>
                  {data.kappa ?? '—'}
                </p>
                <p className="text-xs text-gray-500 mt-1">{data.target} · {data.target_met ? 'Target met ✓' : 'Below target'}</p>
              </div>
              <div className="card p-5">
                <p className="text-xs font-medium text-gray-600 mb-1">Observed Agreement</p>
                <p className="text-2xl font-bold text-gray-800">{data.p_observed != null ? `${(data.p_observed * 100).toFixed(1)}%` : '—'}</p>
                <p className="text-xs text-gray-400">{data.n_agreement}/{data.n_pairs} pairs agreed</p>
              </div>
              <div className="card p-5">
                <p className="text-xs font-medium text-gray-600 mb-1">Theory Accuracy</p>
                <p className="text-2xl font-bold text-indigo-600">
                  {data.theory_accuracy != null ? `${(data.theory_accuracy * 100).toFixed(0)}%` : '—'}
                </p>
                <p className="text-xs text-gray-400">bucket-level agreement</p>
              </div>
              <div className="card p-5">
                <p className="text-xs font-medium text-gray-600 mb-1">Numerical Accuracy</p>
                <p className="text-2xl font-bold text-indigo-600">
                  {data.numerical_accuracy != null ? `${(data.numerical_accuracy * 100).toFixed(0)}%` : '—'}
                </p>
                <p className="text-xs text-gray-400">bucket-level agreement</p>
              </div>
            </div>

            {/* Interpretation */}
            <div className={`card p-4 flex items-start gap-3 ${data.target_met ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'}`}>
              {data.target_met
                ? <CheckCircle className="w-5 h-5 text-emerald-600 mt-0.5 flex-shrink-0" />
                : <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />}
              <div>
                <p className={`text-sm font-semibold ${data.target_met ? 'text-emerald-800' : 'text-amber-800'}`}>
                  {data.interpretation}
                </p>
                <p className="text-xs text-gray-500 mt-0.5">{data.note}</p>
              </div>
            </div>

            {/* Per-pair table */}
            <div className="card p-5">
              <h3 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-indigo-500" />
                Per-Submission Comparison (AI vs Faculty)
              </h3>
              <div className="overflow-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-gray-100">
                      <th className="text-left py-2 pr-4 font-medium text-gray-500">Submission</th>
                      <th className="text-left py-2 pr-4 font-medium text-gray-500">Type</th>
                      <th className="text-right py-2 pr-4 font-medium text-gray-500">AI Score</th>
                      <th className="text-right py-2 pr-4 font-medium text-gray-500">Faculty Score</th>
                      <th className="text-left py-2 pr-4 font-medium text-gray-500">AI Bucket</th>
                      <th className="text-left py-2 pr-4 font-medium text-gray-500">Faculty Bucket</th>
                      <th className="text-center py-2 font-medium text-gray-500">Agree</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.pairs || []).map((p: any) => (
                      <tr key={p.submission_id} className="border-b border-gray-50">
                        <td className="py-2 pr-4 font-mono text-gray-600">{p.submission_id}</td>
                        <td className="py-2 pr-4 capitalize text-gray-600">{p.type}</td>
                        <td className="py-2 pr-4 text-right font-medium text-gray-800">{p.ai_score}/{p.max_score}</td>
                        <td className="py-2 pr-4 text-right font-medium text-gray-800">{p.faculty_score}/10</td>
                        <td className="py-2 pr-4">
                          <span className={`badge ${p.ai_bucket.startsWith('High') ? 'bg-emerald-50 text-emerald-700' : p.ai_bucket.startsWith('Low') ? 'bg-red-50 text-red-600' : 'bg-amber-50 text-amber-700'}`}>
                            {p.ai_bucket}
                          </span>
                        </td>
                        <td className="py-2 pr-4">
                          <span className={`badge ${p.faculty_bucket.startsWith('High') ? 'bg-emerald-50 text-emerald-700' : p.faculty_bucket.startsWith('Low') ? 'bg-red-50 text-red-600' : 'bg-amber-50 text-amber-700'}`}>
                            {p.faculty_bucket}
                          </span>
                        </td>
                        <td className="py-2 text-center">
                          {p.agreement
                            ? <span className="text-emerald-600 font-bold">✓</span>
                            : <span className="text-red-500 font-bold">✗</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Method note */}
            <div className="card p-4 bg-gray-50">
              <p className="text-xs text-gray-500 font-medium mb-1">Methodology</p>
              <p className="text-xs text-gray-500">
                Scores are bucketed into three ordinal levels (Low 0–3, Mid 4–6, High 7–10 out of 10) before Kappa computation,
                following standard practice for continuous grading scales. Cohen's κ = (P_o − P_e) / (1 − P_e) where P_o is the
                fraction of pairs where AI and faculty agree on the bucket, and P_e is expected agreement by chance (from marginal
                frequencies). Landis & Koch (1977) scale: κ ≥ 0.80 = almost perfect, κ ≥ 0.75 = substantial (project target),
                κ ≥ 0.60 = moderate, κ ≥ 0.40 = fair.
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
