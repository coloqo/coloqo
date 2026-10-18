import type { ReactNode } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import type { Me } from '../api/client'
import { Page } from '../components/Layout'
import { Card, CommandLine } from '../components/ui'

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
  return (
    <Page title={t('connect.title')}>
      <Card className="max-w-3xl">
        <div className="flex flex-col gap-6 p-5">
          <p className={muted}>{t('connect.lead')}</p>
          <ol className="flex flex-col gap-6">
            <Step number={1} title={t('connect.uv.title')}>
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
              <CommandLine command="curl -LsSf https://astral.sh/uv/install.sh | sh" />
              <p className="text-sm font-medium">{t('connect.uv.windows')}</p>
              <CommandLine command={'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'} />
              <p className={muted}>{t('connect.uv.path')}</p>
            </Step>
            <Step number={2} title={t('connect.login.title')}>
              <p className={muted}>{t('connect.login.lead')}</p>
              <CommandLine command="uvx coloqo login" />
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
            <Step number={3} title={t('connect.plugin.title')}>
              <p className={muted}>{t('connect.plugin.lead')}</p>
              <CommandLine command="/plugin install coloqo --marketplace coloqo/coloqo" />
              <p className={muted}>{t('connect.plugin.older')}</p>
              <CommandLine command="/plugin marketplace add coloqo/coloqo" />
              <CommandLine command="/plugin install coloqo@coloqo" />
              <p className={muted}>{t('connect.plugin.restart')}</p>
            </Step>
            <Step number={4} title={t('connect.works.title')}>
              <p className={muted}>
                <Trans
                  i18nKey="connect.works.name"
                  values={{ name: `${me.pseudonym ?? 'alice'} · billing-api` }}
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
