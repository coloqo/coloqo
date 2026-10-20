import { useState, type ComponentProps, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

const cx = (...parts: (string | false | null | undefined)[]) => parts.filter(Boolean).join(' ')

type ButtonProps = ComponentProps<'button'> & { variant?: 'primary' | 'secondary' | 'ghost' | 'danger'; size?: 'sm' | 'md' }

export function Button({ variant = 'secondary', size = 'md', className, type = 'button', ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={cx(
        'inline-flex items-center justify-center gap-1.5 rounded-md font-medium whitespace-nowrap transition-colors',
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-500',
        'disabled:cursor-not-allowed disabled:opacity-50',
        size === 'sm' ? 'px-2.5 py-1 text-sm' : 'px-3.5 py-2 text-sm',
        variant === 'primary' &&
          'bg-stone-900 text-stone-50 hover:bg-stone-700 dark:bg-stone-100 dark:text-stone-900 dark:hover:bg-stone-300',
        variant === 'secondary' &&
          'border border-stone-300 bg-white text-stone-800 hover:bg-stone-100 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-200 dark:hover:bg-stone-800',
        variant === 'ghost' &&
          'text-stone-600 hover:bg-stone-200 dark:text-stone-400 dark:hover:bg-stone-800',
        variant === 'danger' &&
          'border border-red-300 text-red-700 hover:bg-red-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950',
        className,
      )}
      {...props}
    />
  )
}

const control =
  'w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-base text-stone-900 placeholder:text-stone-400 ' +
  'focus:border-amber-500 focus:ring-2 focus:ring-amber-500/30 focus:outline-none sm:text-sm ' +
  'dark:border-stone-700 dark:bg-stone-900 dark:text-stone-100 dark:placeholder:text-stone-500'

export function Input({ className, ...props }: ComponentProps<'input'>) {
  return <input className={cx(control, className)} {...props} />
}

export function Textarea({ className, ...props }: ComponentProps<'textarea'>) {
  return <textarea className={cx(control, 'leading-relaxed', className)} {...props} />
}

export function Select({ className, ...props }: ComponentProps<'select'>) {
  return <select className={cx(control, 'pr-8', className)} {...props} />
}

export function Field({ label, hint, children }: { label: ReactNode; hint?: ReactNode; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-sm font-medium text-stone-700 dark:text-stone-300">{label}</span>
      {children}
      {hint && <span className="text-xs text-stone-500 dark:text-stone-400">{hint}</span>}
    </label>
  )
}

export function Card({ className, ...props }: ComponentProps<'section'>) {
  return (
    <section
      className={cx(
        'rounded-lg border border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900/60',
        className,
      )}
      {...props}
    />
  )
}

export function CardHeader({ title, children }: { title: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-stone-200 px-4 py-3 dark:border-stone-800">
      <h2 className="text-sm font-semibold tracking-wide text-stone-500 uppercase dark:text-stone-400">{title}</h2>
      {children}
    </div>
  )
}

type BadgeTone = 'stone' | 'amber' | 'green' | 'blue' | 'red'

export function Badge({ tone = 'stone', className, ...props }: ComponentProps<'span'> & { tone?: BadgeTone }) {
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium whitespace-nowrap',
        tone === 'stone' && 'bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-300',
        tone === 'amber' && 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300',
        tone === 'green' && 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300',
        tone === 'blue' && 'bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300',
        tone === 'red' && 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300',
        className,
      )}
      {...props}
    />
  )
}

export function ErrorNote({ children }: { children: ReactNode }) {
  if (!children) return null
  return (
    <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800 dark:bg-red-950/60 dark:text-red-300">
      {children}
    </p>
  )
}

export function Notice({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:bg-amber-950/50 dark:text-amber-200">
      {children}
    </p>
  )
}

export function Loading() {
  const { t } = useTranslation()
  return <p className="px-1 py-6 text-sm text-stone-500 dark:text-stone-400">{t('common.loading')}</p>
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="px-4 py-6 text-sm text-stone-500 dark:text-stone-400">{children}</p>
}

/** A copy-to-clipboard button that says when it worked. */
export function CopyButton({ text, size = 'sm', label }: { text: string; size?: 'sm' | 'md'; label?: string }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)
  return (
    <Button
      size={size}
      onClick={() => {
        void navigator.clipboard.writeText(text).then(() => {
          setCopied(true)
          window.setTimeout(() => setCopied(false), 1500)
        })
      }}
    >
      {copied ? t('common.copied') : (label ?? t('common.copy'))}
    </Button>
  )
}

/** A command line with a copy button. */
export function CommandLine({ command }: { command: string }) {
  return (
    <div className="flex items-start gap-2 rounded-md bg-stone-100 p-2 pl-3 dark:bg-stone-800/70">
      <code className="min-w-0 flex-1 overflow-x-auto py-1 font-mono text-sm break-all whitespace-pre-wrap">{command}</code>
      <CopyButton text={command} />
    </div>
  )
}
