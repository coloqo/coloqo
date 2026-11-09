import type { ReactNode } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router'

import type { Me } from '../api/client'
import { AgentIcon } from '../components/AgentIcon'
import { Page } from '../components/Layout'
import { Card, CommandLine, CopyButton } from '../components/ui'
import { AGENT_NAMES, type Agent } from '../lib/agents'

const CLOUD = 'https://app.coloqo.team'

const UV_UNIX = 'curl -LsSf https://astral.sh/uv/install.sh | sh'
const UV_WINDOWS = 'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
const LOGIN = 'uvx coloqo login'
const PLUGIN = '/plugin install coloqo --marketplace coloqo/coloqo'
const MARKETPLACE_ADD = '/plugin marketplace add coloqo/coloqo'
const PLUGIN_OLD = '/plugin install coloqo@coloqo'
const MARKETPLACE_ADD_CLI = 'claude plugin marketplace add coloqo/coloqo'
const PLUGIN_CLI = 'claude plugin install coloqo@coloqo'
const STATUS = 'uvx coloqo status'
const AGENTS: Agent[] = ['claude', 'codex', 'qwen']

/** The installer's command for Codex or Qwen Code (decision 0035). */
const install = (agent: Agent) => `uvx coloqo install --agent ${agent}`

/** How the user invokes Coloqo's link command in the agent. */
const LINK_SKILL: Record<Agent, string> = { claude: '/coloqo:link', codex: '$coloqo-link', qwen: '/coloqo-link' }

type StepId = 'uv' | 'login' | 'plugin' | 'works'

/**
 * The steps of connecting, once for both readers: the page shows each to a person, and the
 * instruction for an AI gives each in a form an agent can run (decisions 0026, 0035).
 */
const STEPS: { id: StepId; agent: (server: string, agent: Agent) => string[] }[] = [
  {
    id: 'uv',
    agent: () => [
      'Check that uv is installed: `uv --version`. If it is not, install it:',
      `- macOS and Linux: \`${UV_UNIX}\``,
      `- Windows: \`${UV_WINDOWS}\`, then open a new shell so that uv is on PATH.`,
    ],
  },
  {
    id: 'login',
    agent: (server, agent) => [
      ...(server === CLOUD
        ? []
        : [
            `This Coloqo server is ${server}: set \`COLOQO_URL=${server}\` in the environment ${AGENT_NAMES[agent]} runs in (for instance in the shell profile), and use it for the commands below.`,
          ]),
      `Run \`${server === CLOUD ? '' : `COLOQO_URL=${server} `}${LOGIN}\` in the background. It prints a short code and the address of a confirmation page: give both to me, wait until I confirm in the browser, and let the command finish.`,
    ],
  },
  {
    id: 'plugin',
    agent: (_, agent) =>
      agent === 'claude'
        ? [
            `Install the Claude Code plugin: \`${MARKETPLACE_ADD_CLI}\`, then \`${PLUGIN_CLI}\`.`,
            'Then tell me to turn on auto-update for the `coloqo` marketplace once, in `/plugin` → Marketplaces, and to restart Claude Code in the project.',
          ]
        : [
            `Set Coloqo up for ${AGENT_NAMES[agent]}: \`${install(agent)}\`. It writes the hooks, the MCP server and the skills into ${AGENT_NAMES[agent]}'s user settings. If your sandbox stops it (no network, or settings outside the project), give me the command to run in a terminal.`,
            `Then tell me to approve the hooks${agent === 'qwen' ? ' and the MCP server' : ''} in \`/hooks\` when ${AGENT_NAMES[agent]} asks, and to restart it.`,
          ],
  },
  {
    id: 'works',
    agent: (_, agent) => [
      `Check the result: \`${STATUS}\` says who this computer is logged in as.`,
      `After the restart, each ${AGENT_NAMES[agent]} session is an assistant of mine in Coloqo. Link the project to its Team when I ask, with the coloqo link_project tool.`,
      ...(agent === 'claude' ? [] : ['New Coloqo messages reach me at the next prompt, not by themselves.']),
    ],
  },
]

/** The instruction for an AI, in Markdown: the same steps, written for an agent to run. */
function agentInstruction(server: string, agent: Agent): string {
  const name = AGENT_NAMES[agent]
  const mine = agent === 'claude' ? 'turn on auto-update, restart Claude Code' : `approve the hooks in /hooks, restart ${name}`
  const lines = [
    '# Connect me to Coloqo',
    '',
    `Coloqo connects the AI assistants of a team. Set it up on this computer for ${name}. Only I can do these: confirm the login code in the browser, ${mine}.`,
    '',
  ]
  STEPS.forEach((step, index) => {
    const [first, ...rest] = step.agent(server, agent)
    lines.push(`${index + 1}. ${first}`)
    for (const line of rest) lines.push(`   ${line}`)
  })
  return lines.join('\n')
}

function Step({ number, title, children }: { number: number; title: ReactNode; children: ReactNode }) {
  return (
    <li className="flex gap-4">
      <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-amber-100 text-sm font-semibold text-amber-800 dark:bg-amber-950 dark:text-amber-300">
        {number}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-2.5 pb-2">
        <h2 className="font-semibold">{title}</h2>
        {children}
      </div>
    </li>
  )
}

const muted = 'text-sm leading-relaxed text-stone-600 dark:text-stone-400'
const code = <code className="rounded bg-stone-100 px-1 py-0.5 font-mono text-[0.85em] dark:bg-stone-800" />

/** The choice of the agent; kept in the address, so a link can open the page for Codex. */
function AgentChoice({ agent, onChange }: { agent: Agent; onChange: (agent: Agent) => void }) {
  const { t } = useTranslation()
  return (
    <div role="group" aria-label={t('connect.agent')} className="flex flex-wrap gap-2">
      {AGENTS.map((option) => (
        <button
          key={option}
          type="button"
          aria-pressed={option === agent}
          onClick={() => onChange(option)}
          className={`inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors ${
            option === agent
              ? 'border-amber-500 bg-amber-50 text-stone-900 dark:border-amber-500 dark:bg-amber-950/40 dark:text-stone-100'
              : 'border-stone-200 text-stone-600 hover:bg-stone-100 dark:border-stone-700 dark:text-stone-400 dark:hover:bg-stone-800'
          }`}
        >
          <AgentIcon agent={option} className="size-4" />
          {AGENT_NAMES[option]}
        </button>
      ))}
    </div>
  )
}

/** How to connect an Assistant: uv, login of the computer, the plugin or the installer (0035). */
export function ConnectPage({ me }: { me: Me }) {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const chosen = params.get('agent')
  const agent: Agent = chosen === 'codex' || chosen === 'qwen' ? chosen : 'claude'
  const name = AGENT_NAMES[agent]
  const server = window.location.origin
  const number = (id: StepId) => STEPS.findIndex((step) => step.id === id) + 1
  return (
    <Page title={t('connect.title')}>
      <Card className="max-w-3xl">
        <div className="flex flex-col gap-6 p-5">
          <p className={muted}>{t('connect.lead')}</p>
          <AgentChoice agent={agent} onChange={(next) => setParams(next === 'claude' ? {} : { agent: next }, { replace: true })} />
          <div className="flex flex-wrap items-center gap-3 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 dark:border-amber-900 dark:bg-amber-950/30">
            <p className="min-w-0 flex-1 text-sm text-stone-700 dark:text-stone-300">{t('connect.forAi', { agent: name })}</p>
            <CopyButton text={agentInstruction(server, agent)} label={t('connect.copyForAi')} />
          </div>
          <ol className="flex flex-col gap-6">
            <Step number={number('uv')} title={t('connect.uv.title')}>
              <p className={muted}>
                <Trans
                  i18nKey="connect.uv.lead"
                  components={{
                    docs: (
                      <a
                        href="https://docs.astral.sh/uv/getting-started/installation/"
                        target="_blank"
                        rel="noreferrer noopener"
                        className="text-amber-700 hover:underline dark:text-amber-400"
                      />
                    ),
                  }}
                />
              </p>
              <p className="text-sm font-medium">{t('connect.uv.unix')}</p>
              <CommandLine command={UV_UNIX} />
              <p className="text-sm font-medium">{t('connect.uv.windows')}</p>
              <CommandLine command={UV_WINDOWS} />
              <p className={muted}>{t('connect.uv.path')}</p>
            </Step>
            <Step number={number('login')} title={t('connect.login.title')}>
              <p className={muted}>{t('connect.login.lead')}</p>
              <CommandLine command={server === CLOUD ? LOGIN : `COLOQO_URL=${server} ${LOGIN}`} />
              <p className={muted}>
                <Trans
                  i18nKey="connect.login.confirm"
                  components={{
                    device: <Link to="/device" className="text-amber-700 hover:underline dark:text-amber-400" />,
                    settings: <Link to="/profile/settings" className="text-amber-700 hover:underline dark:text-amber-400" />,
                  }}
                />
              </p>
            </Step>
            {agent === 'claude' ? (
              <Step number={number('plugin')} title={t('connect.plugin.title')}>
                <p className={muted}>{t('connect.plugin.lead')}</p>
                <CommandLine command={PLUGIN} />
                <p className={muted}>{t('connect.plugin.older')}</p>
                <CommandLine command={MARKETPLACE_ADD} />
                <CommandLine command={PLUGIN_OLD} />
                <p className={muted}>{t('connect.plugin.autoUpdate')}</p>
                <p className={muted}>{t('connect.plugin.restart')}</p>
              </Step>
            ) : (
              <Step number={number('plugin')} title={t('connect.installer.title', { agent: name })}>
                <p className={muted}>{t('connect.installer.lead', { agent: name })}</p>
                <CommandLine command={install(agent)} />
                <p className={muted}>
                  {t(agent === 'qwen' ? 'connect.installer.approveQwen' : 'connect.installer.approve', { agent: name })}
                </p>
                <p className={muted}>{t('connect.installer.update')}</p>
              </Step>
            )}
            <Step number={number('works')} title={t('connect.works.title')}>
              <p className={muted}>
                <Trans
                  i18nKey="connect.works.name"
                  values={{ name: `${me.pseudonym ?? 'alice'} · billing-api · vega`, agent: name }}
                  components={{ code }}
                />
              </p>
              <p className={muted}>{t('connect.works.tools')}</p>
              <p className={muted}>
                {agent === 'claude' ? t('connect.works.live') : t('connect.works.atPrompt', { link: LINK_SKILL[agent] })}
              </p>
            </Step>
          </ol>
        </div>
      </Card>
    </Page>
  )
}
