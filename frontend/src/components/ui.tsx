import type { ButtonHTMLAttributes, HTMLAttributes, PropsWithChildren, ReactNode, InputHTMLAttributes } from 'react'
import { ArrowRight, LoaderCircle, Sparkles } from 'lucide-react'

export function Button({ children, className = '', variant = 'primary', ...props }: PropsWithChildren<ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' | 'danger' }>) {
  return <button className={`button button-${variant} ${className}`} {...props}>{children}</button>
}
export function Card({ children, className = '', ...props }: PropsWithChildren<HTMLAttributes<HTMLDivElement>>) { return <div className={`card ${className}`} {...props}>{children}</div> }
export function Badge({ children, tone = 'neutral' }: PropsWithChildren<{ tone?: 'neutral' | 'purple' | 'green' | 'amber' | 'blue' }>) { return <span className={`badge badge-${tone}`}>{children}</span> }
export function ProgressBar({ value, color = 'violet' }: { value: number; color?: string }) { const safe = Math.max(0, Math.min(100, value)); return <div className="progress-track" role="progressbar" aria-valuenow={safe} aria-valuemin={0} aria-valuemax={100} aria-label="Course progress"><span className={`progress-fill ${color}`} style={{ width: `${safe}%` }} /></div> }
export function PageTitle({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description?: string; action?: ReactNode }) { return <div className="page-title-row"><div>{eyebrow && <div className="eyebrow">{eyebrow}</div>}<h1>{title}</h1>{description && <p className="page-description">{description}</p>}</div>{action && <div className="page-title-action">{action}</div>}</div> }
export function EmptyState({ title, text, action }: { title: string; text: string; action?: ReactNode }) { return <div className="empty-state"><div className="empty-icon"><Sparkles size={20} /></div><h3>{title}</h3><p>{text}</p>{action}</div> }
export function ErrorState({ message, retry }: { message: string; retry?: () => void }) { return <div className="error-state" role="alert"><strong>We couldn’t load this just now.</strong><p>{message}</p>{retry && <Button variant="secondary" onClick={retry}>Try again <ArrowRight size={15} /></Button>}</div> }
export function Skeleton({ className = '' }: { className?: string }) { return <div aria-label="Loading" className={`skeleton ${className}`} /> }
export function Spinner() { return <LoaderCircle className="spin" size={17} aria-hidden="true" /> }
export function Field({ label, error, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string }) { const id = props.id ?? props.name; return <label className="field" htmlFor={id}><span>{label}</span><input {...props} id={id} aria-invalid={Boolean(error)} aria-describedby={error ? `${id}-error` : undefined} />{error && <small className="field-error" id={`${id}-error`}>{error}</small>}</label> }
export function SectionHeading({ title, action }: { title: string; action?: ReactNode }) { return <div className="section-heading"><h2>{title}</h2>{action}</div> }
