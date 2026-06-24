const BASE = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) throw new Error(`API error ${res.status}`)
  return res.json()
}

export const api = {
  // Dashboard
  getDashboardStats: () => request<any>('/stats'),
  getActivity: (limit = 10) => request<any>(`/activity?limit=${limit}`),

  // Question generation
  generateQuestions: (payload: any) =>
    request<any>('/questions/generate', { method: 'POST', body: JSON.stringify(payload) }),
  pipelineGenerate: (payload: any) =>
    request<any>('/pipeline/generate', { method: 'POST', body: JSON.stringify(payload) }),
  pipelineAssess: (payload: any) =>
    request<any>('/pipeline/assess', { method: 'POST', body: JSON.stringify(payload) }),

  // Question bank
  getQuestions: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return request<any>(`/questions${qs}`)
  },
  getQuestion: (id: string) => request<any>(`/questions/${id}`),
  deleteQuestion: (id: string) => request<any>(`/questions/${id}`, { method: 'DELETE' }),

  // Answer schemes
  getAnswerSchemes: (params?: { question_id?: string; subject?: string }) => {
    const qs = params ? '?' + new URLSearchParams(params as any).toString() : ''
    return request<any>(`/answer-schemes${qs}`)
  },
  getAnswerScheme: (answerId: string) => request<any>(`/answer-schemes/${answerId}`),

  // Evaluation
  evalTheory: (payload: any) =>
    request<any>('/eval/theory', { method: 'POST', body: JSON.stringify(payload) }),
  evalNumerical: (payload: any) =>
    request<any>('/eval/numerical', { method: 'POST', body: JSON.stringify(payload) }),

  // Students & submissions
  getStudents: () => request<any>('/students'),
  getSubmissions: (params?: { status?: string }) => {
    const qs = params ? '?' + new URLSearchParams(params as any).toString() : ''
    return request<any>(`/submissions${qs}`)
  },
  gradeSubmission: (id: string) => request<any>(`/submissions/${id}/grade`, { method: 'POST' }),
  overrideGrade: (id: string, score: number, reason: string) =>
    request<any>(`/submissions/${id}/override`, {
      method: 'POST',
      body: JSON.stringify({ score, reason }),
    }),

  // Analytics
  getCOAnalytics: () => request<any>('/analytics/co'),
  getCOTrend: () => request<any>('/analytics/co-trend'),
  getCOPOCorrelation: () => request<any>('/analytics/co-po-correlation'),

  // Exams
  getExamPapers: () => request<any>('/exams'),
  createExamPaper: (payload: any) =>
    request<any>('/exams', { method: 'POST', body: JSON.stringify(payload) }),

  // Data sources
  getDataSources: () => request<any>('/data-sources'),
  getDataSourceFiles: (subject: string) => request<any>(`/data-sources/${encodeURIComponent(subject)}/files`),

  // Health
  getHealth: () => request<any>('/health'),

  // Validation metrics
  getValidationMetrics: () => request<any>('/eval/validate/kappa'),

  // Answer-script pipeline (multipart — use FormData, bypasses JSON wrapper)
  evalScript: (formData: FormData) =>
    fetch(`${BASE}/eval/script`, { method: 'POST', body: formData }).then(r => {
      if (!r.ok) return r.json().then((e: any) => Promise.reject(new Error(e.detail || r.statusText)))
      return r.json()
    }),
}
