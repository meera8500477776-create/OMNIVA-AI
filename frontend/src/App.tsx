import { lazy, Suspense, type ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell, NotFound, ProtectedRoute, PublicLayout } from './components/Shell'
import { useAuth } from './lib/auth'
const LandingPage=lazy(()=>import('./pages-public').then(m=>({default:m.LandingPage})))
const FeaturesPage=lazy(()=>import('./pages-public').then(m=>({default:m.FeaturesPage})))
const LoginPage=lazy(()=>import('./pages-public').then(m=>({default:m.LoginPage})))
const RegisterPage=lazy(()=>import('./pages-public').then(m=>({default:m.RegisterPage})))
const ForgotPage=lazy(()=>import('./pages-public').then(m=>({default:m.ForgotPage})))
const DashboardPage=lazy(()=>import('./pages-learning').then(m=>({default:m.DashboardPage})))
const CoursesPage=lazy(()=>import('./pages-learning').then(m=>({default:m.CoursesPage})))
const CourseDetailPage=lazy(()=>import('./pages-learning').then(m=>({default:m.CourseDetailPage})))
const LessonPage=lazy(()=>import('./pages-lesson-progress').then(m=>({default:m.LessonPage})))
const ProgressPage=lazy(()=>import('./pages-lesson-progress').then(m=>({default:m.ProgressPage})))
const DesktopAgentPage=lazy(()=>import('./pages-tools').then(m=>({default:m.DesktopAgentPage})))
const VoicePage=lazy(()=>import('./pages-tools').then(m=>({default:m.VoicePage})))
const CareerPage=lazy(()=>import('./pages-tools').then(m=>({default:m.CareerPage})))
const TutorPage=lazy(()=>import('./pages-tutor-avatar').then(m=>({default:m.TutorPage})))
const AvatarPage=lazy(()=>import('./pages-tutor-avatar').then(m=>({default:m.AvatarPage})))
const ProfilePage=lazy(()=>import('./pages-account').then(m=>({default:m.ProfilePage})))
const SettingsPage=lazy(()=>import('./pages-account').then(m=>({default:m.SettingsPage})))
const CareCompanionPage=lazy(()=>import('./pages-phase4').then(m=>({default:m.CareCompanionPage})))
const EmailAgentPage=lazy(()=>import('./pages-phase4').then(m=>({default:m.EmailAgentPage})))
const AutopilotPage=lazy(()=>import('./pages-phase4').then(m=>({default:m.AutopilotPage})))
function Guest({children}:{children:ReactNode}) { const {user}=useAuth();return user?<Navigate to="/dashboard" replace/>:<>{children}</> }
function PageLoading(){return <div className="route-loading" role="status">Opening your learning space…</div>}
export default function App(){return <Suspense fallback={<PageLoading/>}><Routes>
 <Route element={<PublicLayout/>}>
  <Route path="/" element={<LandingPage/>}/><Route path="/features" element={<FeaturesPage/>}/>
  <Route path="/login" element={<Guest><LoginPage/></Guest>}/><Route path="/register" element={<Guest><RegisterPage/></Guest>}/><Route path="/forgot-password" element={<Guest><ForgotPage/></Guest>}/>
 </Route>
 <Route element={<ProtectedRoute/>}><Route element={<AppShell/>}>
  <Route path="/dashboard" element={<DashboardPage/>}/><Route path="/courses" element={<CoursesPage/>}/><Route path="/courses/:id" element={<CourseDetailPage/>}/><Route path="/learn/:id" element={<LessonPage/>}/><Route path="/progress" element={<ProgressPage/>}/>
  <Route path="/desktop-agent" element={<DesktopAgentPage/>}/><Route path="/voice-assistant" element={<VoicePage/>}/><Route path="/career" element={<CareerPage/>}/><Route path="/ai-tutor" element={<TutorPage/>}/><Route path="/avatar" element={<AvatarPage/>}/><Route path="/profile" element={<ProfilePage/>}/><Route path="/settings" element={<SettingsPage/>}/>
  <Route path="/email-agent" element={<EmailAgentPage/>}/><Route path="/care-companion" element={<CareCompanionPage/>}/><Route path="/autopilot" element={<AutopilotPage/>}/>
 </Route></Route><Route path="*" element={<NotFound/>}/>
 </Routes></Suspense>}
