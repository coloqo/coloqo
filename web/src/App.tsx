import { useTranslation } from 'react-i18next'

function Bell() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className="size-14 fill-amber-600 dark:fill-amber-400">
      <path d="M16 3a2 2 0 0 1 2 2v1.2c4.6.9 8 4.9 8 9.8v5.5l2.3 3.1A.9.9 0 0 1 27.6 26H4.4a.9.9 0 0 1-.7-1.4L6 21.5V16c0-4.9 3.4-8.9 8-9.8V5a2 2 0 0 1 2-2Z" />
      <path d="M12.5 27.5h7a3.5 3.5 0 0 1-7 0Z" />
    </svg>
  )
}

export default function App() {
  const { t, i18n } = useTranslation()
  const other = i18n.resolvedLanguage === 'en' ? 'ru' : 'en'

  return (
    <div className="min-h-dvh">
      <header className="flex justify-end px-4 py-4 sm:px-8">
        <button
          type="button"
          onClick={() => void i18n.changeLanguage(other)}
          className="rounded-md px-3 py-1.5 text-sm text-stone-600 hover:bg-stone-200 dark:text-stone-400 dark:hover:bg-stone-800"
        >
          {t('language')}
        </button>
      </header>
      <main className="mx-auto flex max-w-2xl flex-col gap-6 px-4 pt-16 pb-24 sm:px-8 sm:pt-24">
        <Bell />
        <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">{t('welcome.title')}</h1>
        <p className="text-lg leading-relaxed text-stone-700 dark:text-stone-300">{t('welcome.lead')}</p>
        <p className="text-sm text-stone-500 dark:text-stone-400">{t('welcome.status')}</p>
      </main>
    </div>
  )
}
