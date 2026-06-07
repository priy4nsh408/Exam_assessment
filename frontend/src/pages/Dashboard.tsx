import { useState, useEffect } from 'react'
import { Brain, Clock, TrendingUp, AlertCircle, Activity } from 'lucide-react'
import { Header } from '../components/layout/Header'
import { StatCard } from '../components/ui/StatCard'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, LineChart, Line, Legend
} from 'recharts'
import { BloomBadge } from '../components/ui/BloomBadge'

const bloomDist = [
  { level: 'L1 Remember', count: 12 },
  { level: 'L2 Understand', count: 18 },
  { level: 'L3 Apply', count: 24 },
  { level: 'L4 Analyze', count: 20 },
  { level: 'L5 Evaluate', count: 14 },
  { level: 'L6 Create', count: 8 },
]

const coData = [
  { co: 'CO1', attainment: 78, target: 70 },
  { co: 'CO2', attainment: 65, target: 70 },
  { co: 'CO3', attainment: 82, target: 70 },
  { co: 'CO4', attainment: 71, target: 70 },
  { co: 'CO5', attainment: 88, target: 70 },
]

const recentActivity = [
  { action: 'Generated 12 questions', subject: 'Thermodynamics', time: '2 min ago', type: 'generate' },
  { action: 'Graded 34 theory submissions', subject: 'Fluid Mechanics', time: '18 min ago', type: 'grade' },
  { action: 'Faculty override on Q-047', subject: 'SOM', time: '1 hr ago', type: 'override' },
  { action: 'Exam paper published', subject: 'Thermodynamics Mid-Sem', time: '3 hrs ago', type: 'publish' },
  { action: '8 drawings evaluated', subject: 'Engineering Drawing', time: '5 hrs ago', type: 'grade' },
]

const activityColor: Record<string, string> = {
  generate: 'bg-indigo-50 text-indigo-600',
  grade: 'bg-emerald-50 text-emerald-600',
  override: 'bg-amber-50 text-amber-600',
  publish: 'bg-violet-50 text-violet-600',
}

const recentQuestions = [
  { id: 'Q-049', text: 'Derive the expression for thermal efficiency of a Carnot cycle operating between temperatures T1 and T2.', bloom: 4, type: 'Theory', co: 'CO2' },
  { id: 'Q-050', text: 'A beam of length 4m carries a UDL of 10 kN/m. Calculate the maximum bending moment and shear force.', bloom: 3, type: 'Numerical', co: 'CO3' },
  { id: 'Q-051', text: 'Draw the orthographic projections of a hexagonal prism resting on its base.', bloom: 3, type: 'Drawing', co: 'CO5' },
]

export default function Dashboard() {
  const [stats, setStats] = useState<any>(null)
  useEffect(() => {
    fetch('/api/stats').then(r => r.json()).then(setStats).catch(() => {})
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
            value={stats?.total_questions != null ? String(stats.total_questions) : '1,248'}
            sub="across 4 subjects"
            icon={Brain}
            color="indigo"
            trend={{ value: 12, label: 'this week' }}
          />
          <StatCard
            label="Time Saved"
            value={stats?.time_saved != null ? `${stats.time_saved} hrs` : '186 hrs'}
            sub="vs. manual preparation"
            icon={Clock}
            color="emerald"
            trend={{ value: 73, label: 'reduction' }}
          />
          <StatCard
            label="Pending Grades"
            value={stats?.pending_grades != null ? String(stats.pending_grades) : '47'}
            sub="submissions awaiting AI"
            icon={AlertCircle}
            color="amber"
          />
          <StatCard
            label="Avg CO Attainment"
            value={stats?.avg_co_attainment != null ? `${stats.avg_co_attainment}%` : '76.8%'}
            sub="target: 70%"
            icon={TrendingUp}
            color="violet"
            trend={{ value: 6.8, label: 'above target' }}
          />
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-3 gap-4">
          {/* Bloom Distribution */}
          <div className="card p-5 col-span-2">
            <div className="mb-4">
              <h2 className="text-sm font-semibold text-gray-900">Bloom's Taxonomy Distribution</h2>
              <p className="text-xs text-gray-500">Questions generated across cognitive levels</p>
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={bloomDist} barSize={32}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="level" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }} />
                <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* CO Attainment */}
          <div className="card p-5">
            <div className="mb-4">
              <h2 className="text-sm font-semibold text-gray-900">CO Attainment</h2>
              <p className="text-xs text-gray-500">vs. 70% target threshold</p>
            </div>
            <div className="space-y-3">
              {coData.map(row => (
                <div key={row.co}>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="font-medium text-gray-700">{row.co}</span>
                    <span className={row.attainment >= row.target ? 'text-emerald-600 font-semibold' : 'text-amber-600 font-semibold'}>
                      {row.attainment}%
                    </span>
                  </div>
                  <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${row.attainment >= row.target ? 'bg-emerald-500' : 'bg-amber-400'}`}
                      style={{ width: `${row.attainment}%` }}
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
              {recentActivity.map((item, i) => (
                <div key={i} className="flex items-start gap-3">
                  <div className={`w-7 h-7 rounded-md flex items-center justify-center shrink-0 ${activityColor[item.type]}`}>
                    <Activity className="w-3.5 h-3.5" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-gray-800 truncate">{item.action}</p>
                    <p className="text-xs text-gray-400">{item.subject} · {item.time}</p>
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
              {recentQuestions.map(q => (
                <div key={q.id} className="p-3 rounded-lg bg-gray-50 border border-gray-100">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className="text-xs font-mono text-gray-400">{q.id}</span>
                        <BloomBadge level={q.bloom} />
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
