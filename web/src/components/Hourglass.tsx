/** An hourglass: waiting for someone outside the Team (decision 0033). */
export function Hourglass({ className = 'size-4' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" className={`${className} shrink-0 fill-none stroke-current`} strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 1.5h8M4 14.5h8M4.5 1.5c0 3 3.5 4.5 3.5 6.5S4.5 11.5 4.5 14.5M11.5 1.5c0 3-3.5 4.5-3.5 6.5s3.5 3.5 3.5 6.5" />
    </svg>
  )
}
