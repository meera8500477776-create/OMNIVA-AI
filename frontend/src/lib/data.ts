import { api, appMode } from './api'

export type Course = {
  id: string
  backendId?: string
  title: string
  category: string
  level: string
  lessons: number
  duration: string
  progress: number
  color: string
  instructor: string
  description: string
  lessonIds?: string[]
}
export type LessonProgress = { lesson_id: string; status: 'not_started' | 'in_progress' | 'completed'; position_seconds: number }
export type BackendLesson = { id: string; title: string; content: string; duration_seconds: number; position: number }
type BackendCourse = {
  id: string
  slug: string
  title: string
  description: string
  modules: Array<{ lessons: BackendLesson[] }>
}

export const courses: Course[] = [
  { id: 'product-design', title: 'Product Design Foundations', category: 'Design', level: 'Beginner', lessons: 18, duration: '6h 20m', progress: 68, color: 'lilac', instructor: 'Nina Patel', description: 'Learn to turn real user needs into thoughtful, intuitive product experiences.' },
  { id: 'ai-literacy', title: 'AI for Everyday Work', category: 'Artificial intelligence', level: 'Beginner', lessons: 12, duration: '4h 10m', progress: 32, color: 'mint', instructor: 'Marcus Lee', description: 'Build practical AI fluency, from good prompts to responsible everyday workflows.' },
  { id: 'data-storytelling', title: 'Data Storytelling', category: 'Business', level: 'Intermediate', lessons: 15, duration: '5h 45m', progress: 0, color: 'peach', instructor: 'Elena Cruz', description: 'Make complex information clear and compelling with visual narratives.' },
  { id: 'frontend-accessibility', title: 'Accessible Frontend Essentials', category: 'Development', level: 'Intermediate', lessons: 20, duration: '8h', progress: 0, color: 'blue', instructor: 'Sam Rivera', description: 'Create inclusive, keyboard-friendly interfaces that work for everyone.' },
  { id: 'career-story', title: 'Build Your Career Story', category: 'Career', level: 'All levels', lessons: 9, duration: '2h 30m', progress: 0, color: 'rose', instructor: 'Jordan Kim', description: 'Connect your skills, experience and goals into a clear next-step plan.' },
  { id: 'creative-thinking', title: 'Creative Thinking at Work', category: 'Business', level: 'Beginner', lessons: 11, duration: '3h 15m', progress: 0, color: 'gold', instructor: 'Priya Shah', description: 'Practice flexible thinking and turn new ideas into useful experiments.' },
]

function categoryFromSlug(slug: string) {
  if (slug.includes('python')) return 'Development'
  if (slug.includes('design')) return 'Design'
  if (slug.includes('career')) return 'Career'
  return 'Learning'
}

function mapCourse(item: BackendCourse): Course {
  const lessons = item.modules.flatMap((module) => module.lessons)
  const seconds = lessons.reduce((total, lesson) => total + lesson.duration_seconds, 0)
  return {
    id: item.slug,
    backendId: item.id,
    title: item.title,
    category: categoryFromSlug(item.slug),
    level: 'All levels',
    lessons: lessons.length,
    duration: `${Math.floor(seconds / 3600)}h ${Math.round((seconds % 3600) / 60)}m`,
    progress: 0,
    color: 'lilac',
    instructor: 'Omniva learning team',
    description: item.description,
    lessonIds: lessons.map((lesson) => lesson.id),
  }
}

export async function getCourses(): Promise<Course[]> {
  if (appMode === 'demo') return courses
  const page = await api<{ items: BackendCourse[] }>('/courses')
  return page.items.map(mapCourse)
}

export async function getCourse(id: string): Promise<Course | undefined> {
  if (appMode === 'demo') return courses.find((course) => course.id === id)
  const page = await api<{ items: BackendCourse[] }>('/courses')
  const match = page.items.find((item) => item.slug === id || item.id === id)
  return match ? mapCourse(match) : undefined
}

export async function enrollCourse(courseId: string) {
  return api<{ id: string; course_id: string; status: string }>(`/courses/${encodeURIComponent(courseId)}/enroll`, { method: 'POST' })
}

export async function getLesson(lessonId: string): Promise<BackendLesson> {
  return api<BackendLesson>(`/lessons/${encodeURIComponent(lessonId)}`)
}

export async function saveProgress(lessonId: string, status: LessonProgress['status'], position_seconds = 0) {
  if (appMode === 'demo') {
    sessionStorage.setItem(`omniva.progress.${lessonId}`, JSON.stringify({ lesson_id: lessonId, status, position_seconds }))
    return
  }
  await api(`/me/progress/${encodeURIComponent(lessonId)}`, { method: 'PUT', body: JSON.stringify({ status, position_seconds }) })
}

export async function recordQuiz(lessonId: string, answer: string, correct: boolean) {
  if (appMode === 'demo') return
  await api('/quizzes/attempts', {
    method: 'POST',
    body: JSON.stringify({ lesson_id: lessonId, score: correct ? 1 : 0, answers: { q1: answer } }),
  })
}

export async function getProgress() {
  if (appMode === 'demo') return { completed: 8, minutes: 1260, streak: 6, weekly: [{ day: 'Mon', minutes: 32 }, { day: 'Tue', minutes: 48 }, { day: 'Wed', minutes: 25 }, { day: 'Thu', minutes: 62 }, { day: 'Fri', minutes: 44 }, { day: 'Sat', minutes: 70 }, { day: 'Sun', minutes: 38 }] }
  const [dashboard, progress] = await Promise.all([
    api<{ summary: { completed_lessons: number }; recent_progress: Array<{ position_seconds: number; updated_at: string }> }>('/dashboard'),
    api<{ items: Array<{ status: string; position_seconds: number; updated_at: string }> }>('/me/progress'),
  ])
  const weekly = Array.from({ length: 7 }, (_, offset) => {
    const date = new Date()
    date.setDate(date.getDate() - (6 - offset))
    const key = date.toLocaleDateString('en', { weekday: 'short' })
    const minutes = progress.items
      .filter((item) => new Date(item.updated_at).toDateString() === date.toDateString())
      .reduce((sum, item) => sum + Math.round(item.position_seconds / 60), 0)
    return { day: key, minutes }
  })
  return {
    completed: dashboard.summary.completed_lessons,
    minutes: progress.items.reduce((sum, item) => sum + Math.round(item.position_seconds / 60), 0),
    streak: 0,
    weekly,
  }
}
