export type BloomLevel = 1 | 2 | 3 | 4 | 5 | 6;
export type QuestionType = 'theory' | 'numerical' | 'drawing';
export type Subject = 'Thermodynamics' | 'Strength of Materials' | 'Fluid Mechanics' | 'Engineering Drawing';

export interface Question {
  id: string;
  text: string;
  type: QuestionType;
  subject: Subject;
  unit: string;
  bloomLevel: BloomLevel;
  bloomLabel: string;
  co: string;
  po: string;
  marks: number;
  difficulty: 'easy' | 'medium' | 'hard';
  answerKey?: string;
  sourceChunk?: string;
  createdAt: string;
}

export interface Student {
  id: string;
  usn: string;
  name: string;
  section: string;
}

export interface Submission {
  id: string;
  studentId: string;
  questionId: string;
  type: QuestionType;
  content: string;
  imageUrl?: string;
  submittedAt: string;
  status: 'pending' | 'graded' | 'overridden';
}

export interface GradeResult {
  submissionId: string;
  aiScore: number;
  maxScore: number;
  confidence: number;
  feedback: string;
  errorCategories?: ErrorCategory[];
  isOverridden: boolean;
  overriddenScore?: number;
  overriddenBy?: string;
  co: string;
  po: string;
}

export interface ErrorCategory {
  type: 'formula_error' | 'substitution_error' | 'unit_error' | 'arithmetic_error' | 'boundary_condition_error';
  step: number;
  description: string;
  deduction: number;
}

export interface COAnalytics {
  co: string;
  description: string;
  averageAttainment: number;
  studentsAchieved: number;
  totalStudents: number;
  target: number;
}

export interface ExamPaper {
  id: string;
  title: string;
  subject: Subject;
  totalMarks: number;
  duration: number;
  questions: Question[];
  createdAt: string;
  status: 'draft' | 'published';
}

export interface DashboardStats {
  totalQuestions: number;
  activeExams: number;
  submissionsPending: number;
  avgCOAttainment: number;
  timeSavedHours: number;
  questionsThisMonth: number;
}
