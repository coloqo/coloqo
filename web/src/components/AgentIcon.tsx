import { useTranslation } from 'react-i18next'

import { AGENT_NAMES, type Agent } from '../lib/agents'

/**
 * A small mark of the agent a session runs in, with its name on hover: a spark for Claude Code, a
 * terminal prompt for Codex, a hexagon for Qwen Code. Own drawings, not the vendors' logos.
 */
export function AgentIcon({ agent, className = 'size-3.5' }: { agent: Agent; className?: string }) {
  const { t } = useTranslation()
  const label = t('sessions.agent', { name: AGENT_NAMES[agent] })
  return (
    <svg viewBox="0 0 16 16" role="img" aria-label={label} className={`${className} shrink-0`}>
      <title>{label}</title>
      {agent === 'claude' && (
        <path
          d="M8 1.75v12.5M1.75 8h12.5M3.6 3.6l8.8 8.8M12.4 3.6l-8.8 8.8"
          className="stroke-orange-600 dark:stroke-orange-400"
          strokeWidth="1.9"
          strokeLinecap="round"
          fill="none"
        />
      )}
      {agent === 'codex' && (
        <g className="stroke-stone-700 dark:stroke-stone-200" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="none">
          <rect x="1.5" y="2.5" width="13" height="11" rx="2.5" />
          <path d="M4.75 6.25 7 8l-2.25 1.75M8.75 10h2.75" />
        </g>
      )}
      {agent === 'qwen' && (
        <g className="stroke-violet-600 dark:stroke-violet-400" strokeWidth="1.5" strokeLinejoin="round" fill="none">
          <path d="M8 1.6 13.55 4.8v6.4L8 14.4 2.45 11.2V4.8Z" />
          <circle cx="8" cy="8" r="1.9" className="fill-violet-600 dark:fill-violet-400" stroke="none" />
        </g>
      )}
    </svg>
  )
}
