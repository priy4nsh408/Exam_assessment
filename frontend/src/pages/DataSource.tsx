import { useState, useEffect } from 'react'
import { Database, FileText, Download, ChevronDown, ChevronUp, CheckCircle2, AlertCircle } from 'lucide-react'
import { Header } from '../components/layout/Header'

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(epochSeconds: number): string {
  return new Date(epochSeconds * 1000).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

export default function DataSource() {
  const [subjects, setSubjects] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [filesBySubject, setFilesBySubject] = useState<Record<string, any>>({})
  const [loadingFiles, setLoadingFiles] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/data-sources')
      .then(r => r.json())
      .then(data => {
        setSubjects(data.subjects || [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  const toggleExpand = async (subject: string) => {
    if (expanded === subject) { setExpanded(null); return }
    setExpanded(subject)
    if (!filesBySubject[subject]) {
      setLoadingFiles(subject)
      try {
        const res = await fetch(`/api/data-sources/${encodeURIComponent(subject)}/files`)
        const data = await res.json()
        setFilesBySubject(prev => ({ ...prev, [subject]: data }))
      } catch {
        // leave unset - the expanded panel will show an empty/error state
      }
      setLoadingFiles(null)
    }
  }

  const fileUrl = (subject: string, relativePath: string, source: 'raw' | 'pyqs') =>
    `/api/data-sources/${encodeURIComponent(subject)}/download?path=${encodeURIComponent(relativePath)}&source=${source}`

  const totalIngested = subjects.filter(s => s.ingested).length

  return (
    <div>
      <Header
        title="Data Source"
        subtitle="Raw chapter material the generation pipeline retrieves context from"
      />

      <div className="p-6 space-y-4">
        <div className="card p-4 flex items-center gap-6">
          <div>
            <p className="text-2xl font-bold text-gray-900">{subjects.length}</p>
            <p className="text-xs text-gray-500">subjects with raw material</p>
          </div>
          <div className="w-px h-10 bg-gray-100" />
          <div>
            <p className="text-2xl font-bold text-emerald-600">{totalIngested}</p>
            <p className="text-xs text-gray-500">actually ingested into ChromaDB</p>
          </div>
          {subjects.length > totalIngested && (
            <p className="text-xs text-amber-600 ml-auto max-w-xs">
              Subjects without a green "Ingested" badge will generate questions from the LLM's
              general knowledge only — no grounded answer key until their material is ingested.
            </p>
          )}
        </div>

        {loading && <p className="text-xs text-gray-400">Loading...</p>}

        {!loading && subjects.length === 0 && (
          <div className="card p-8 text-center">
            <Database className="w-10 h-10 text-gray-200 mx-auto mb-3" />
            <p className="text-sm text-gray-400">No data/raw/ folders found on the backend.</p>
          </div>
        )}

        {subjects.map(s => {
          const isExpanded = expanded === s.subject
          const detail = filesBySubject[s.subject]
          return (
            <div key={s.subject} className="card overflow-hidden">
              <button
                onClick={() => toggleExpand(s.subject)}
                className="w-full flex items-center gap-3 p-4 text-left hover:bg-gray-50 transition-colors"
              >
                <div className="w-9 h-9 rounded-lg bg-indigo-50 flex items-center justify-center shrink-0">
                  <Database className="w-4 h-4 text-indigo-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-gray-900">{s.subject}</span>
                    {s.ingested ? (
                      <span className="badge bg-emerald-50 text-emerald-700 flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" /> Ingested · {s.chunkCount} chunks
                      </span>
                    ) : (
                      <span className="badge bg-amber-50 text-amber-700 flex items-center gap-1">
                        <AlertCircle className="w-3 h-3" /> Not ingested
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {s.rawFileCount} source file{s.rawFileCount === 1 ? '' : 's'} ({formatBytes(s.rawSizeBytes)})
                    {s.pyqFileCount > 0 && ` · ${s.pyqFileCount} past paper${s.pyqFileCount === 1 ? '' : 's'}`}
                    {s.units.length > 0 && ` · ${s.units.join(', ')}`}
                  </p>
                </div>
                {isExpanded ? <ChevronUp className="w-4 h-4 text-gray-400 shrink-0" /> : <ChevronDown className="w-4 h-4 text-gray-400 shrink-0" />}
              </button>

              {isExpanded && (
                <div className="border-t border-gray-100 px-4 py-3 bg-gray-50/50">
                  {loadingFiles === s.subject && <p className="text-xs text-gray-400">Loading files...</p>}
                  {detail && (
                    <div className="space-y-3">
                      <div>
                        <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-2">
                          Source chapters ({detail.rawFiles.length})
                        </p>
                        <div className="space-y-1">
                          {detail.rawFiles.map((f: any) => (
                            <a
                              key={f.relativePath}
                              href={fileUrl(s.subject, f.relativePath, 'raw')}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-2 px-2.5 py-1.5 rounded-md hover:bg-white transition-colors group"
                            >
                              <FileText className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                              <span className="text-xs text-gray-700 flex-1 truncate">{f.name}</span>
                              <span className="badge bg-gray-100 text-gray-500 shrink-0">{f.unit}</span>
                              <span className="text-[10px] text-gray-400 shrink-0">{formatBytes(f.sizeBytes)}</span>
                              <span className="text-[10px] text-gray-400 shrink-0">{formatDate(f.modifiedAt)}</span>
                              <Download className="w-3 h-3 text-gray-300 group-hover:text-indigo-500 shrink-0" />
                            </a>
                          ))}
                          {detail.rawFiles.length === 0 && (
                            <p className="text-xs text-gray-400 px-2.5">No source chapter files found.</p>
                          )}
                        </div>
                      </div>

                      {detail.pyqFiles.length > 0 && (
                        <div>
                          <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-2">
                            Previous year question papers ({detail.pyqFiles.length})
                          </p>
                          <div className="space-y-1">
                            {detail.pyqFiles.map((f: any) => (
                              <a
                                key={f.relativePath}
                                href={fileUrl(s.subject, f.relativePath, 'pyqs')}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-2 px-2.5 py-1.5 rounded-md hover:bg-white transition-colors group"
                              >
                                <FileText className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                                <span className="text-xs text-gray-700 flex-1 truncate">{f.relativePath}</span>
                                <span className="text-[10px] text-gray-400 shrink-0">{formatBytes(f.sizeBytes)}</span>
                                <Download className="w-3 h-3 text-gray-300 group-hover:text-indigo-500 shrink-0" />
                              </a>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
