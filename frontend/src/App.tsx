import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './components/layout/Layout'
import Dashboard from './pages/Dashboard'
import QuestionGenerator from './pages/QuestionGenerator'
import QuestionBank from './pages/QuestionBank'
import ExamPapers from './pages/ExamPapers'
import DataSource from './pages/DataSource'
import COPOAnalytics from './pages/COPOAnalytics'
import Students from './pages/Students'
import FacultyOverride from './pages/FacultyOverride'
import ValidationMetrics from './pages/ValidationMetrics'
import AnswerScriptEvaluator from './pages/AnswerScriptEvaluator'
import TrainingEngine from './pages/TrainingEngine'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="generate" element={<QuestionGenerator />} />
          <Route path="questions" element={<QuestionBank />} />
          <Route path="exams" element={<ExamPapers />} />
          <Route path="data-sources" element={<DataSource />} />
          {/* Main evaluation hub */}
          <Route path="eval/script" element={<AnswerScriptEvaluator />} />
          <Route path="eval/train" element={<TrainingEngine />} />
          <Route path="eval/validate" element={<ValidationMetrics />} />
          <Route path="analytics" element={<COPOAnalytics />} />
          <Route path="students" element={<Students />} />
          <Route path="override" element={<FacultyOverride />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
