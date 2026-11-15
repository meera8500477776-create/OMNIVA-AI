import { describe, expect, it } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import App from '../App'
import { AuthProvider } from '../lib/auth'

function renderAt(path: string, authenticated = false) {
  if (authenticated) sessionStorage.setItem('omniva.session.v1', JSON.stringify({id:'test',name:'Avery Morgan',email:'demo@omniva.ai'}))
  return render(<MemoryRouter initialEntries={[path]}><AuthProvider><App/></AuthProvider></MemoryRouter>)
}

describe('approved route map', () => {
  it.each([
    ['/', 'Big goals.'], ['/features', 'More than a course catalog.'], ['/login', 'Good to see you.'],
    ['/register', 'Make room to grow.'], ['/forgot-password', 'Forgot your password?'],
  ])('renders public route %s', async (path, heading) => { renderAt(path); await waitFor(()=>expect(screen.getByRole('heading', {name:new RegExp(heading,'i')})).toBeInTheDocument()) })
  it.each([
    ['/dashboard','Good morning'], ['/courses','Find your next spark.'], ['/courses/product-design','Product Design Foundations'],
    ['/learn/design-lesson-6','Discover the real problem'], ['/progress','Look how far you’ve come.'],
    ['/desktop-agent','A calmer way to get things done.'], ['/voice-assistant','Think out loud.'],
    ['/career','Find a direction that feels like you.'], ['/ai-tutor','Let’s figure it out together.'],
    ['/avatar','Give your words a little life.'], ['/profile','A little about you.'], ['/settings','Make this space yours.'],
  ])('renders protected route %s', async (path, heading) => {
    renderAt(path,true)
    await waitFor(()=>expect(screen.getByRole('heading',{name:new RegExp(heading,'i')})).toBeInTheDocument())
  })
  it('signs into the seeded demo account and reaches the workspace', async()=>{const user=userEvent.setup();renderAt('/login');await user.click(screen.getByRole('button',{name:/sign in/i}));await waitFor(()=>expect(screen.getByRole('heading',{name:/good morning/i})).toBeInTheDocument())})
  it('rejects an incorrect demo password without authenticating', async()=>{const user=userEvent.setup();renderAt('/login');const field=screen.getByLabelText(/password/i);await user.clear(field);await user.type(field,'wrong');await user.click(screen.getByRole('button',{name:/sign in/i}));expect(await screen.findByRole('alert')).toHaveTextContent(/demo@omniva.ai/);expect(sessionStorage.getItem('omniva.session.v1')).toBeNull()})
  it('validates registration consent before recording a demo account', async()=>{const user=userEvent.setup();renderAt('/register');await user.type(screen.getByLabelText(/your name/i),'Taylor Learner');await user.type(screen.getByLabelText(/email address/i),'taylor@example.com');await user.type(screen.getByLabelText('Password'),'learnpass123');await user.type(screen.getByLabelText(/confirm password/i),'learnpass123');await user.click(screen.getByRole('button',{name:/create account/i}));expect(await screen.findByRole('alert')).toHaveTextContent(/agree to continue/i);expect(sessionStorage.getItem('omniva.session.v1')).toBeNull()})
  it('records demo recovery locally and states that no email was sent', async()=>{const user=userEvent.setup();renderAt('/forgot-password');await user.type(screen.getByLabelText(/email address/i),'learner@example.com');await user.click(screen.getByRole('button',{name:/send recovery link/i}));expect(await screen.findByRole('status')).toHaveTextContent(/no email was sent/i)})
  it('filters the course catalog by search', async()=>{const user=userEvent.setup();renderAt('/courses',true);await waitFor(()=>expect(screen.getByRole('heading',{name:/find your next spark/i})).toBeInTheDocument());await user.type(screen.getByRole('textbox',{name:/search courses/i}),'Accessible Frontend');expect(await screen.findByRole('heading',{name:/accessible frontend essentials/i})).toBeInTheDocument();expect(screen.queryByRole('heading',{name:/product design foundations/i})).not.toBeInTheDocument()})
  it('shows quiz feedback and marks a lesson complete', async()=>{const user=userEvent.setup();renderAt('/learn/design-lesson-6',true);await waitFor(()=>expect(screen.getByRole('heading',{name:/discover the real problem/i})).toBeInTheDocument());await user.click(screen.getByRole('button',{name:/start by noticing/i}));expect(screen.getByRole('status')).toHaveTextContent(/exactly/i);await user.click(screen.getByRole('button',{name:/mark as complete/i}));expect(await screen.findByRole('button',{name:/lesson complete/i})).toBeDisabled()})
  it('redirects protected pages to login without a demo session', async()=>{renderAt('/dashboard');await waitFor(()=>expect(screen.getByRole('heading',{name:/good to see you/i})).toBeInTheDocument())})
  it('validates sign-in and labels the seeded demo credentials', async()=>{renderAt('/login');expect(screen.getByText(/demo account/i)).toBeInTheDocument();expect(screen.getByRole('textbox',{name:/email address/i})).toHaveValue('demo@omniva.ai')})
})
