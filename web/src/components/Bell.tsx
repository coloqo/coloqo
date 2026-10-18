export function Bell({ className = 'size-14' }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className={`${className} fill-amber-600 dark:fill-amber-400`}>
      <path d="M16 3a2 2 0 0 1 2 2v1.2c4.6.9 8 4.9 8 9.8v5.5l2.3 3.1A.9.9 0 0 1 27.6 26H4.4a.9.9 0 0 1-.7-1.4L6 21.5V16c0-4.9 3.4-8.9 8-9.8V5a2 2 0 0 1 2-2Z" />
      <path d="M12.5 27.5h7a3.5 3.5 0 0 1-7 0Z" />
    </svg>
  )
}
