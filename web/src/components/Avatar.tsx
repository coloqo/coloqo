import type { ReactNode } from 'react'

// The faces of a Topic's feed (decision 0019): a person by their initials, an Assistant and a
// Worker by one icon each, with the person they act for in the corner.

const PALETTE = ['#7c5cbf', '#2f8f6b', '#c0573a', '#3b6fb6', '#a3489a', '#5f7d2a', '#b07a12', '#2b8a9a']

/** A color of the palette, the same for the same name everywhere. */
function colorOf(name: string): string {
  let hash = 0
  for (const char of name) hash = (hash * 31 + char.codePointAt(0)!) | 0
  return PALETTE[Math.abs(hash) % PALETTE.length]
}

function initials(name: string): string {
  const words = name.trim().split(/[\s._-]+/).filter(Boolean)
  const letters = words.length > 1 ? words[0][0] + words[1][0] : (words[0] ?? '?')[0]
  return letters.toUpperCase()
}

/** A person: initials on a color of their name. */
export function PersonAvatar({ name, size }: { name: string; size: number }) {
  return (
    <span
      aria-hidden="true"
      className="inline-grid shrink-0 place-items-center rounded-full font-semibold text-white select-none"
      style={{ width: size, height: size, background: colorOf(name), fontSize: Math.round(size * 0.4) }}
    >
      {initials(name)}
    </span>
  )
}

/** An Assistant: an amber robot with a screen for a face. */
export function AssistantIcon({ size }: { size: number }) {
  return (
    <svg viewBox="0 0 48 48" width={size} height={size} aria-hidden="true" className="block shrink-0">
      <circle cx="24" cy="24" r="24" fill="#FBEBD0" />
      <rect x="9" y="21" width="3" height="7" rx="1.5" fill="#A8661A" />
      <rect x="36" y="21" width="3" height="7" rx="1.5" fill="#A8661A" />
      <rect x="20" y="35" width="8" height="4" rx="1.5" fill="#A8661A" />
      <rect x="11" y="12" width="26" height="24" rx="8" fill="#E39B2F" />
      <rect x="14.5" y="16" width="19" height="15" rx="5" fill="#2B2622" />
      <rect x="18" y="19.5" width="3.2" height="6" rx="1.6" fill="#FFD27A" />
      <rect x="26.8" y="19.5" width="3.2" height="6" rx="1.6" fill="#FFD27A" />
      <path d="M21 28 q3 1.8 6 0" stroke="#FFD27A" strokeWidth="1.8" fill="none" strokeLinecap="round" />
    </svg>
  )
}

/** A Worker: a teal robot with a screen, in a hard hat. */
export function WorkerIcon({ size }: { size: number }) {
  return (
    <svg viewBox="0 0 48 48" width={size} height={size} aria-hidden="true" className="block shrink-0">
      <circle cx="24" cy="24" r="24" fill="#D6E9EC" />
      <rect x="9" y="23" width="3" height="7" rx="1" fill="#1D5560" />
      <rect x="36" y="23" width="3" height="7" rx="1" fill="#1D5560" />
      <rect x="20" y="36" width="8" height="3.5" rx="1" fill="#1D5560" />
      <rect x="11" y="16" width="26" height="21" rx="3" fill="#2E7D8A" />
      <rect x="14.5" y="19.5" width="19" height="13.5" rx="2" fill="#17323A" />
      <rect x="17.5" y="24" width="5" height="2.6" rx="1.3" fill="#9FE3F0" />
      <rect x="25.5" y="24" width="5" height="2.6" rx="1.3" fill="#9FE3F0" />
      <path d="M13.5 16.5 a10.5 8.5 0 0 1 21 0 z" fill="#F2B233" />
      <rect x="10" y="15" width="28" height="3" rx="1.5" fill="#F2B233" />
      <rect x="22.6" y="7.5" width="2.8" height="7" rx="1.4" fill="#D9971A" />
    </svg>
  )
}

/** The face of a Message's author: the person alone, or an Assistant with its person in the corner. */
export function AuthorAvatar({ person, assistant, size }: { person: string | null; assistant: boolean; size: number }) {
  const badge = Math.round(size * 0.45)
  let face: ReactNode
  if (assistant) face = <AssistantIcon size={size} />
  else face = <PersonAvatar name={person ?? '?'} size={size} />
  return (
    <span className="relative inline-block shrink-0" style={{ width: size, height: size }}>
      {face}
      {assistant && person && (
        <span className="absolute -right-1 -bottom-1 flex rounded-full ring-2 ring-[var(--feed-ring)]">
          <PersonAvatar name={person} size={badge} />
        </span>
      )}
    </span>
  )
}
