import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, FileText, Brain, Calculator, PenTool,
  BarChart3, Users, CheckSquare, BookOpen, Cpu, Database
} from 'lucide-react'
import clsx from 'clsx'

const navItems = [
  { label: 'Overview', icon: LayoutDashboard, path: '/' },
  { label: 'Question Generator', icon: Brain, path: '/generate' },
  { label: 'Question Bank', icon: BookOpen, path: '/questions' },
  { label: 'Exam Papers', icon: FileText, path: '/exams' },
  { label: 'Data Source', icon: Database, path: '/data-sources' },
  { divider: true, label: 'Evaluation' },
  { label: 'Answer Evaluator', icon: CheckSquare, path: '/evaluate' },
  { divider: true, label: 'Analytics' },
  { label: 'CO/PO Analytics', icon: BarChart3, path: '/analytics' },
  { label: 'Students', icon: Users, path: '/students' },
  { label: 'Faculty Override', icon: CheckSquare, path: '/override' },
]

export function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 w-60 bg-navy-900 flex flex-col z-50">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-navy-700">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-indigo-500 rounded-lg flex items-center justify-center">
            <Cpu className="w-4 h-4 text-white" />
          </div>
          <div>
            <span className="text-white font-semibold text-sm">MechAssess</span>
            <p className="text-navy-700 text-xs text-slate-400">RVCE &middot; Team QE29</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-4 px-3">
        {navItems.map((item, idx) => {
          if (item.divider) {
            return (
              <div key={idx} className="px-3 pt-5 pb-2">
                <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                  {item.label}
                </span>
              </div>
            )
          }
          const Icon = item.icon!
          return (
            <NavLink
              key={item.path}
              to={item.path!}
              end={item.path === '/'}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium mb-0.5 transition-colors',
                  isActive
                    ? 'bg-indigo-600 text-white'
                    : 'text-slate-400 hover:text-white hover:bg-navy-800'
                )
              }
            >
              <Icon className="w-4 h-4 shrink-0" />
              {item.label}
            </NavLink>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="px-3 py-4 border-t border-navy-700">
        <div className="flex items-center gap-3 px-3 py-2">
          <div className="w-7 h-7 rounded-full bg-indigo-500 flex items-center justify-center">
            <span className="text-white text-xs font-semibold">FA</span>
          </div>
          <div className="min-w-0">
            <p className="text-white text-xs font-medium truncate">Faculty</p>
            <p className="text-slate-500 text-xs">ME Department</p>
          </div>
        </div>
      </div>
    </aside>
  )
}
