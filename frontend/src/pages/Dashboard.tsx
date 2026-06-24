import { useState, useEffect } from 'react'
import { Brain, CheckCircle2, AlertCircle, TrendingUp, Activity } from 'lucide-react'
import { Header } from '../components/layout/Header'
import { StatCard } from '../components/ui/StatCard'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { BloomBadge } from '../components/ui/BloomBadge'

const activityColor: Record<string, string> = {
  generate: 'bg-indigo-50 text-indigo-600',
  grade: 'bg-emerald-50 text-emerald-600',
  override: 'bg-amber-50 text-amber-600',
  publish: 'bg-violet-50 text-violet-600',
}

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diffMs / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} min ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs} hr${hrs > 1 ? 's' : ''} ago`
  const days = Math.floor(hrs / 24)
  return `${days} day${days > 1 ? 's' : ''} ago`
}

export default function Dashboard() {
  const [stats, setStats] = useState<any>(null)
  const [activity, setActivity] = useState<any[]>([])
  const [coAnalytics, setCoAnalytics] = useState<any[]>([])
  const [loadingActivity, setLoadingActivity] = useState(true)

  useEffect(() => {
    fetch('/api/stats').then(r => r.json()).then(setStats).catch(() => {})
    fetch('/api/activity').then(r => r.json()).then(d => setActivity(d.activity || [])).catch(() => {}).finally(() => setLoadingActivity(false))
    fetch('/api/analytics/co').then(r => r.json()).then(d => setCoAnalytics(d.co_analytics || [])).catch(() => {})
  }, [])

  return (
    <div>
      <Header
        title="Dashboard"
        subtitle="MechAssess — AI Assessment Platform · RVCE Mechanical Engineering"
        actions={
          <span className="flex items-center gap-1.5 text-xs text-emerald-600 font-medium bg-emerald-50 px-2.5 py-1 rounded-full">
            <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse" />
            System Online
          </span>
        }
      />

      <div className="p-6 space-y-6">
        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Questions Generated"
            value={stats?.totalQuestions != null ? String(stats.totalQuestions) : '—'}
            sub="in the question bank"
            icon={Brain}
            color="indigo"
          />
          <StatCard
            label="Graded Today"
            value={stats?.gradedToday != null ? String(stats.gradedToday) : '—'}
            sub="theory + numerical submissions"
            icon={CheckCircle2}
            color="emerald"
          />
          <StatCard
            label="Pending Grades"
            value={stats?.submissionsPending != null ? String(stats.submissionsPending) : '—'}
            sub="submissions awaiting AI"
            icon={AlertCircle}
            color="amber"
          />
          <StatCard
            label="Avg CO Attainment"
            value={stats?.avgCOAttainment != null ? `${stats.avgCOAttainment}%` : '—'}
            sub="target: 70%"
            icon={TrendingUp}
            color="violet"
          />
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-3 gap-4">
          {/* Bloom Distribution */}
          <div className="card p-5 col-span-2">
            <div className="mb-4">
              <h2 className="text-sm font-semibold text-gray-900">Bloom's Taxonomy Distribution</h2>
              <p className="text-xs text-gray-500">Questions in the bank, across cognitive levels</p>
            </div>
            {stats?.bloomDistribution && stats.bloomDistribution.some((b: any) => b.count > 0) ? (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={stats.bloomDistribution} barSize={32}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="level" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }} />
                  <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[200px] flex items-center justify-center">
                <p className="text-xs text-gray-400">No questions generated yet.</p>
              </div>
            )}
          </div>

          {/* CO Attainment */}
          <div className="card p-5">
            <div className="mb-4">
              <h2 className="text-sm font-semibold text-gray-900">CO Attainment</h2>
              <p className="text-xs text-gray-500">vs. 70% target threshold</p>
            </div>
            <div className="space-y-3">
              {coAnalytics.length === 0 && (
                <p className="text-xs text-gray-400">No graded submissions yet.</p>
              )}
              {coAnalytics.filter(row => row.averageAttainment != null).map(row => (
                <div key={row.co}>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="font-medium text-gray-700">{row.co}</span>
                    <span className={row.averageAttainment >= row.target ? 'text-emerald-600 font-semibold' : 'text-amber-600 font-semibold'}>
                      {row.averageAttainment}%
                    </span>
                  </div>
                  <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${row.averageAttainment >= row.target ? 'bg-emerald-500' : 'bg-amber-400'}`}
                      style={{ width: `${row.averageAttainment}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Bottom Row */}
        <div className="grid grid-cols-3 gap-4">
          {/* Recent Activity */}
          <div className="card p-5 col-span-1">
            <h2 className="text-sm font-semibold text-gray-900 mb-4">Recent Activity</h2>
            <div className="space-y-3">
              {loadingActivity && <p className="text-xs text-gray-400">Loading…</p>}
              {!loadingActivity && activity.length === 0 && (
                <p className="text-xs text-gray-400">No activity yet — generate or grade something to see it here.</p>
              )}
              {activity.map((item, i) => (
                <div key={i} className="flex items-start gap-3">
                  <div className={`w-7 h-7 rounded-md flex items-center justify-center shrink-0 ${activityColor[item.type] || 'bg-gray-50 text-gray-500'}`}>
                    <Activity className="w-3.5 h-3.5" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-gray-800 truncate">{item.action}</p>
                    <p className="text-xs text-gray-400 truncate">{item.subject}{item.detail ? ` · ${item.detail}` : ''} · {timeAgo(item.createdAt)}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Recently Generated Questions */}
          <div className="card p-5 col-span-2">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-gray-900">Recently Generated Questions</h2>
              <a href="/questions" className="text-xs text-indigo-600 hover:underline">View all</a>
            </div>
            <div className="space-y-3">
              {(!stats?.recentQuestions || stats.recentQuestions.length === 0) && (
                <p className="text-xs text-gray-400">No questions generated yet.</p>
              )}
              {(stats?.recentQuestions || []).map((q: any) => (
                <div key={q.id} className="p-3 rounded-lg bg-gray-50 border border-gray-100">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className="text-xs font-mono text-gray-400">{q.id}</span>
                        <BloomBadge level={q.bloomLevel} />
                        <span className="badge bg-gray-100 text-gray-600">{q.type}</span>
                        <span className="badge bg-indigo-50 text-indigo-600">{q.co}</span>
                      </div>
                      <p className="text-xs text-gray-700 line-clamp-2">{q.text}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
