/** The agent a session runs in (decision 0035). */
export type Agent = 'claude' | 'codex' | 'qwen'

/** The agent's name as people know it. */
export const AGENT_NAMES: Record<Agent, string> = { claude: 'Claude Code', codex: 'Codex', qwen: 'Qwen Code' }

/** The hint with a session's id and, where the agent has one, the command that resumes it. */
export function sessionHint(t: (key: string, options?: Record<string, string>) => string, agent: Agent, id: string) {
  if (agent === 'claude') return t('sessions.id', { id })
  if (agent === 'codex') return t('sessions.idCodex', { id })
  return t('sessions.idOnly', { id })
}
