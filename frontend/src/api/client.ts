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
  getDashboardStats: () => request<any>('/stats'),
  generateQuestions: (payload: any) =>
    request<any>('/questions/generate', { method: 'POST', body: JSON.stringify(payload) }),
  getQuestions: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return request<any>(`/questions${qs}`)
  },
  deleteQuestion: (id: string) => request<any>(`/questions/${id}`, { method: 'DELETE' }),
  getStudents: () => request<any>('/students'),
  getSubmissions: () => request<any>('/submissions'),
  gradeSubmission: (id: string) => request<any>(`/submissions/${id}/grade`, { method: 'POST' }),
  overrideGrade: (id: string, score: number, reason: string) =>
    request<any>(`/submissions/${id}/override`, {
      method: 'POST',
      body: JSON.stringify({ score, reason }),
    }),
  getCOAnalytics: () => request<any>('/analytics/co'),
  getExamPapers: () => request<any>('/exams'),
  createExamPaper: (payload: any) =>
    request<any>('/exams', { method: 'POST', body: JSON.stringify(payload) }),
}
