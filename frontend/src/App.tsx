import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './components/layout/Layout'
import Dashboard from './pages/Dashboard'
import QuestionGenerator from './pages/QuestionGenerator'
import QuestionBank from './pages/QuestionBank'
import TheoryEvaluator from './pages/TheoryEvaluator'
import NumericalGrader from './pages/NumericalGrader'
import DrawingEvaluator from './pages/DrawingEvaluator'
import COPOAnalytics from './pages/COPOAnalytics'
import Students from './pages/Students'
import FacultyOverride from './pages/FacultyOverride'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="generate" element={<QuestionGenerator />} />
          <Route path="questions" element={<QuestionBank />} />
          <Route path="exams" element={<Dashboard />} />
          <Route path="eval/theory" element={<TheoryEvaluator />} />
          <Route path="eval/numerical" element={<NumericalGrader />} />
          <Route path="eval/drawing" element={<DrawingEvaluator />} />
          <Route path="analytics" element={<COPOAnalytics />} />
          <Route path="students" element={<Students />} />
          <Route path="override" element={<FacultyOverride />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
