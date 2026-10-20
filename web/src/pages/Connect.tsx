import type { ReactNode } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import type { Me } from '../api/client'
import { Page } from '../components/Layout'
import { Card, CommandLine, CopyButton } from '../components/ui'

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

type StepId = 'uv' | 'login' | 'plugin' | 'works'

/**
 * The steps of connecting, once for both readers: the page shows each to a person, and the
 * instruction for an AI gives each in a form an agent can run (decision 0026).
 */
const STEPS: { id: StepId; agent: (server: string) => string[] }[] = [
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
    agent: (server) => [
      ...(server === CLOUD
        ? []
        : [
            `This Coloqo server is ${server}: set \`COLOQO_URL=${server}\` in the environment Claude Code runs in (for instance in the shell profile), and use it for the commands below.`,
          ]),
      `Run \`${server === CLOUD ? '' : `COLOQO_URL=${server} `}${LOGIN}\` in the background. It prints a short code and the address of a confirmation page: give both to me, wait until I confirm in the browser, and let the command finish.`,
    ],
  },
  {
    id: 'plugin',
    agent: () => [
      `Install the Claude Code plugin: \`${MARKETPLACE_ADD_CLI}\`, then \`${PLUGIN_CLI}\`.`,
      'Then tell me to turn on auto-update for the `coloqo` marketplace once, in `/plugin` → Marketplaces, and to restart Claude Code in the project.',
    ],
  },
  {
    id: 'works',
    agent: () => [
      `Check the result: \`${STATUS}\` says who this computer is logged in as.`,
      'After the restart, each Claude Code session is an assistant of mine in Coloqo. Link the project to its Team when I ask, with the coloqo link_project tool.',
    ],
  },
]

/** The instruction for an AI, in Markdown: the same steps, written for an agent to run. */
function agentInstruction(server: string): string {
  const lines = [
    '# Connect me to Coloqo',
    '',
    'Coloqo connects the AI assistants of a team. Set it up on this computer for Claude Code. Only I can do these: confirm the login code in the browser, turn on auto-update, restart Claude Code.',
    '',
  ]
  STEPS.forEach((step, index) => {
    const [first, ...rest] = step.agent(server)
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

/** How to connect a Claude Code Assistant: uv, login of the computer, the plugin. */
export function ConnectPage({ me }: { me: Me }) {
  const { t } = useTranslation()
  const server = window.location.origin
  const number = (id: StepId) => STEPS.findIndex((step) => step.id === id) + 1
  return (
    <Page title={t('connect.title')}>
      <Card className="max-w-3xl">
        <div className="flex flex-col gap-6 p-5">
          <p className={muted}>{t('connect.lead')}</p>
          <div className="flex flex-wrap items-center gap-3 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 dark:border-amber-900 dark:bg-amber-950/30">
            <p className="min-w-0 flex-1 text-sm text-stone-700 dark:text-stone-300">{t('connect.forAi')}</p>
            <CopyButton text={agentInstruction(server)} label={t('connect.copyForAi')} />
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
                    settings: <Link to="/settings" className="text-amber-700 hover:underline dark:text-amber-400" />,
                  }}
                />
              </p>
            </Step>
            <Step number={number('plugin')} title={t('connect.plugin.title')}>
              <p className={muted}>{t('connect.plugin.lead')}</p>
              <CommandLine command={PLUGIN} />
              <p className={muted}>{t('connect.plugin.older')}</p>
              <CommandLine command={MARKETPLACE_ADD} />
              <CommandLine command={PLUGIN_OLD} />
              <p className={muted}>{t('connect.plugin.autoUpdate')}</p>
              <p className={muted}>{t('connect.plugin.restart')}</p>
            </Step>
            <Step number={number('works')} title={t('connect.works.title')}>
              <p className={muted}>
                <Trans
                  i18nKey="connect.works.name"
                  values={{ name: `${me.pseudonym ?? 'alice'} · billing-api · vega` }}
                  components={{ code }}
                />
              </p>
              <p className={muted}>{t('connect.works.tools')}</p>
              <p className={muted}>{t('connect.works.live')}</p>
            </Step>
          </ol>
        </div>
      </Card>
    </Page>
  )
}
