import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { downloadUrl, fileUrl, type FileInfo } from '../api/client'
import { fileSize } from '../lib/format'

/** Images attached to a Message, reduced; a click opens them over the page (decision 0018). */
export function MessageImages({ images }: { images: FileInfo[] }) {
  const [open, setOpen] = useState<number | null>(null)
  return (
    <>
      <div className="mt-2 flex flex-wrap gap-3">
        {images.map((file, index) => (
          <Thumbnail key={file.id} file={file} onOpen={() => setOpen(index)} />
        ))}
      </div>
      {open !== null && <ImageViewer images={images} index={open} onIndex={setOpen} onClose={() => setOpen(null)} />}
    </>
  )
}

type Frame = { tall: boolean; width: number; height: number }

/**
 * Crop an image of an extreme shape to its start: reduced whole, a full-page screenshot would
 * be a strip a few dozen pixels wide.
 */
function frameOf(width: number, height: number): Frame | null {
  if (height > width * 2) return { tall: true, width: Math.min(width, 240), height: Math.min(height, 320) }
  if (width > height * 4) return { tall: false, width, height: Math.min(height, 160) }
  return null
}

function Thumbnail({ file, onOpen }: { file: FileInfo; onOpen: () => void }) {
  const { t, i18n } = useTranslation()
  const [frame, setFrame] = useState<Frame | null>(null)
  const wide = frame !== null && !frame.tall
  // A wide frame takes the column, up to the image's own width; the others keep their own.
  return (
    <figure className="flex max-w-full flex-col gap-1" style={wide ? { width: `min(${frame.width}px, 100%)` } : undefined}>
      <button
        type="button"
        className={`group ${wide ? 'self-stretch' : 'self-start'} overflow-hidden rounded-md border border-stone-200 bg-stone-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-500 dark:border-stone-700 dark:bg-stone-800`}
        onClick={onOpen}
        aria-label={t('images.open', { name: file.name })}
      >
        <img
          src={fileUrl(file)}
          alt={file.name}
          loading="lazy"
          onLoad={(event) => setFrame(frameOf(event.currentTarget.naturalWidth, event.currentTarget.naturalHeight))}
          style={frame ? { width: frame.tall ? frame.width : undefined, height: frame.height } : undefined}
          className={`block max-w-full transition-opacity group-hover:opacity-90 ${
            frame ? (frame.tall ? 'object-cover object-top' : 'w-full object-cover object-left') : 'max-h-80 object-contain'
          }`}
        />
      </button>
      <figcaption className="flex min-w-0 items-center gap-1.5 text-xs text-stone-500 dark:text-stone-400">
        <span className="truncate">{file.name}</span>
        <span className="shrink-0">· {fileSize(file.size, i18n.resolvedLanguage ?? 'ru')} ·</span>
        <a href={downloadUrl(file)} download={file.name} className="shrink-0 text-amber-700 hover:underline dark:text-amber-400">
          {t('images.download')}
        </a>
      </figcaption>
    </figure>
  )
}

const control =
  'inline-flex items-center justify-center rounded-md text-white/85 hover:bg-white/15 hover:text-white ' +
  'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-400'

function ImageViewer({
  images,
  index,
  onIndex,
  onClose,
}: {
  images: FileInfo[]
  index: number
  onIndex: (index: number) => void
  onClose: () => void
}) {
  const { t, i18n } = useTranslation()
  const dialog = useRef<HTMLDialogElement>(null)
  const file = images[index]
  const many = images.length > 1
  const step = (delta: number) => onIndex((index + delta + images.length) % images.length)

  useEffect(() => {
    const element = dialog.current
    element?.showModal()
    const root = document.documentElement
    const overflow = root.style.overflow
    root.style.overflow = 'hidden'
    return () => {
      root.style.overflow = overflow
      element?.close()
    }
  }, [])

  return (
    <dialog
      ref={dialog}
      aria-label={file.name}
      className="fixed inset-0 m-0 h-dvh max-h-none w-dvw max-w-none bg-transparent p-0 text-white backdrop:bg-black/90"
      onClose={onClose}
      onKeyDown={(event) => {
        if (!many) return
        if (event.key === 'ArrowLeft') step(-1)
        else if (event.key === 'ArrowRight') step(1)
        else return
        event.preventDefault()
      }}
    >
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between gap-3 px-3 py-2 sm:px-4">
          <span className="text-sm text-white/70 tabular-nums">{many && t('images.position', { index: index + 1, count: images.length })}</span>
          <button type="button" className={`${control} size-11 text-2xl`} onClick={onClose} aria-label={t('images.close')}>
            ×
          </button>
        </div>
        <div
          className="relative flex min-h-0 flex-1 items-center justify-center px-2 sm:px-16"
          onClick={(event) => {
            if (event.target === event.currentTarget) onClose()
          }}
        >
          <img key={file.id} src={fileUrl(file)} alt={file.name} className="max-h-full max-w-full object-contain" />
          {many && (
            <>
              <button
                type="button"
                className={`${control} absolute top-1/2 left-1 size-11 -translate-y-1/2 bg-black/40 text-2xl sm:left-3`}
                onClick={() => step(-1)}
                aria-label={t('images.previous')}
              >
                ‹
              </button>
              <button
                type="button"
                className={`${control} absolute top-1/2 right-1 size-11 -translate-y-1/2 bg-black/40 text-2xl sm:right-3`}
                onClick={() => step(1)}
                aria-label={t('images.next')}
              >
                ›
              </button>
            </>
          )}
        </div>
        <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 px-3 py-3 text-sm sm:px-4">
          <span className="min-w-0 truncate text-white/70">
            {file.name} · {fileSize(file.size, i18n.resolvedLanguage ?? 'ru')}
          </span>
          <span className="flex gap-2">
            <a href={fileUrl(file)} target="_blank" rel="noopener" className={`${control} min-h-11 px-3`}>
              {t('images.original')}
            </a>
            <a href={downloadUrl(file)} download={file.name} className={`${control} min-h-11 px-3`}>
              {t('images.save')}
            </a>
          </span>
        </div>
      </div>
    </dialog>
  )
}
