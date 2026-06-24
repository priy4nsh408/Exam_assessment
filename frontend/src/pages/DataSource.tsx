import { useState, useEffect, useRef } from 'react'
import { Database, FileText, Download, ChevronDown, ChevronUp, CheckCircle2, AlertCircle, Upload, FolderUp, RefreshCw, Loader2 } from 'lucide-react'
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

  const [uploading, setUploading] = useState(false)
  const [uploadResult, setUploadResult] = useState<any>(null)
  const [reingesting, setReingesting] = useState<string | null>(null)
  const folderInputRef = useRef<HTMLInputElement>(null)
  const [subjectName, setSubjectName] = useState('')

  const fetchSubjects = () => {
    setLoading(true)
    fetch('/api/data-sources')
      .then(r => r.json())
      .then(data => {
        setSubjects(data.subjects || [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }

  useEffect(() => { fetchSubjects() }, [])

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
        // leave unset
      }
      setLoadingFiles(null)
    }
  }

  const fileUrl = (subject: string, relativePath: string, source: 'raw' | 'pyqs') =>
    `/api/data-sources/${encodeURIComponent(subject)}/download?path=${encodeURIComponent(relativePath)}&source=${source}`

  const handleFolderUpload = async () => {
    const input = folderInputRef.current
    if (!input?.files?.length) return

    const name = subjectName.trim()
    if (!name) { alert('Please enter a subject name'); return }

    setUploading(true)
    setUploadResult(null)

    const formData = new FormData()
    formData.append('subject', name)

    for (let i = 0; i < input.files.length; i++) {
      const file = input.files[i]
      const ext = file.name.split('.').pop()?.toLowerCase()
      if (!['pdf', 'docx', 'doc', 'txt', 'pptx'].includes(ext || '')) continue

      const relativePath = (file as any).webkitRelativePath || file.name
      const parts = relativePath.split('/')
      // Strip the top-level folder name (the one user selected)
      // Keep unit subfolder + filename, e.g. "Unit-1/file.pdf"
      const trimmedPath = parts.length > 1 ? parts.slice(1).join('/') : file.name
      formData.append('files', file, trimmedPath)
    }

    try {
      const res = await fetch('/api/data-sources/upload', { method: 'POST', body: formData })
      const data = await res.json()
      if (!res.ok) {
        setUploadResult({ error: data.detail || 'Upload failed' })
      } else {
        setUploadResult(data)
        setSubjectName('')
        if (input) input.value = ''
        // Refresh subject list and clear cached file listings
        setFilesBySubject({})
        fetchSubjects()
      }
    } catch (e: any) {
      setUploadResult({ error: e.message || 'Network error' })
    }
    setUploading(false)
  }

  const handleReingest = async (subject: string) => {
    setReingesting(subject)
    try {
      const res = await fetch(`/api/data-sources/${encodeURIComponent(subject)}/reingest`, { method: 'POST' })
      const data = await res.json()
      if (res.ok) {
        setFilesBySubject({})
        fetchSubjects()
      } else {
        alert(data.detail || 'Re-ingestion failed')
      }
    } catch {
      alert('Network error during re-ingestion')
    }
    setReingesting(null)
  }

  const totalIngested = subjects.filter(s => s.ingested).length

  return (
    <div>
      <Header
        title="Data Source"
        subtitle="Raw chapter material the generation pipeline retrieves context from"
      />

      <div className="p-6 space-y-4">
        {/* Upload Section */}
        <div className="card p-5 space-y-4">
          <div className="flex items-center gap-2 mb-1">
            <FolderUp className="w-5 h-5 text-indigo-500" />
            <h3 className="text-sm font-semibold text-gray-900">Upload Subject Material</h3>
          </div>
          <p className="text-xs text-gray-500">
            Select a folder organized by unit. Expected structure: <code className="bg-gray-100 px-1 rounded">SubjectFolder/Unit-1/file.pdf</code>, <code className="bg-gray-100 px-1 rounded">SubjectFolder/Unit-2/file.pdf</code>, etc.
            Files placed directly in the folder (without a unit subfolder) will have their unit extracted from the filename.
          </p>

          <div className="flex items-end gap-3 flex-wrap">
            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs font-medium text-gray-600 mb-1">Subject Name</label>
              <input
                type="text"
                value={subjectName}
                onChange={e => setSubjectName(e.target.value)}
                placeholder="e.g. Big Data Technologies"
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400"
              />
            </div>

            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs font-medium text-gray-600 mb-1">Select Folder</label>
              <input
                ref={folderInputRef}
                type="file"
                {...({ webkitdirectory: "", directory: "" } as any)}
                multiple
                className="w-full text-sm text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-indigo-50 file:text-indigo-600 hover:file:bg-indigo-100"
              />
            </div>

            <button
              onClick={handleFolderUpload}
              disabled={uploading}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shrink-0"
            >
              {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
              {uploading ? 'Uploading & Ingesting...' : 'Upload & Ingest'}
            </button>
          </div>

          {uploadResult && (
            <div className={`text-xs p-3 rounded-lg ${uploadResult.error ? 'bg-red-50 text-red-700' : 'bg-emerald-50 text-emerald-700'}`}>
              {uploadResult.error ? (
                <p>{uploadResult.error}</p>
              ) : (
                <p>
                  Uploaded {uploadResult.filesUploaded} file(s) for <strong>{uploadResult.subject}</strong>.
                  {uploadResult.chunksIngested > 0
                    ? ` Ingested ${uploadResult.chunksIngested} chunks into the vector store.`
                    : ' Warning: No chunks were ingested.'}
                  {uploadResult.ingestWarning && <span className="block mt-1 text-amber-600">{uploadResult.ingestWarning}</span>}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Stats */}
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
            <p className="text-sm text-gray-400">No data/raw/ folders found on the backend. Upload a subject folder above to get started.</p>
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
                <button
                  onClick={(e) => { e.stopPropagation(); handleReingest(s.subject) }}
                  disabled={reingesting === s.subject}
                  className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 disabled:opacity-50 transition-colors shrink-0"
                  title="Re-ingest this subject's raw data"
                >
                  {reingesting === s.subject ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                  Re-ingest
                </button>
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
