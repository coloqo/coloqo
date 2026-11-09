import { useTranslation } from 'react-i18next'

import claude from '../assets/agents/claude.png'
import codex from '../assets/agents/codex.png'
import qwen from '../assets/agents/qwen.png'
import { AGENT_NAMES, type Agent } from '../lib/agents'

const ICONS: Record<Agent, string> = { claude, codex, qwen }

/**
 * The icon of the agent a session runs in — Claude Code, Codex or Qwen Code — with its name on
 * hover (decision 0035). ``decorative`` hides it from assistive technology where the agent's name
 * is written beside it.
 */
export function AgentIcon({
  agent,
  className = 'size-4',
  decorative = false,
}: {
  agent: Agent
  className?: string
  decorative?: boolean
}) {
  const { t } = useTranslation()
  const label = t('sessions.agent', { name: AGENT_NAMES[agent] })
  return (
    <img
      src={ICONS[agent]}
      width={16}
      height={16}
      alt={decorative ? '' : label}
      title={decorative ? undefined : label}
      aria-hidden={decorative || undefined}
      draggable={false}
      className={`${className} shrink-0 object-contain`}
    />
  )
}
