import { defaultKeymap, history, historyKeymap } from '@codemirror/commands'
import { markdown } from '@codemirror/lang-markdown'
import { syntaxTree } from '@codemirror/language'
import { EditorState, type Extension, type Range } from '@codemirror/state'
import {
  Decoration,
  type DecorationSet,
  EditorView,
  ViewPlugin,
  type ViewUpdate,
  WidgetType,
  keymap,
  placeholder as placeholderText,
} from '@codemirror/view'
import { GFM } from '@lezer/markdown'
import { useEffect, useRef } from 'react'

/** A list item's marker drawn as a bullet off the line being edited. */
class Bullet extends WidgetType {
  toDOM() {
    const span = document.createElement('span')
    span.className = 'cm-md-bullet'
    span.textContent = '•'
    return span
  }
}

const hidden = Decoration.replace({})
const bullet = Decoration.replace({ widget: new Bullet() })

/** Marks shown only on the line being edited; elsewhere the text reads as rendered. */
const MARKS = new Set(['HeaderMark', 'EmphasisMark', 'CodeMark', 'LinkMark', 'QuoteMark', 'StrikethroughMark'])

/** Styles of whole constructs, shown on every line, edited or not. */
const STYLES: Record<string, string> = {
  Emphasis: 'cm-md-em',
  StrongEmphasis: 'cm-md-strong',
  InlineCode: 'cm-md-code',
  Strikethrough: 'cm-md-strike',
  Link: 'cm-md-link',
}

/** The lines the cursor or a selection touches, while the editor has the focus. */
function activeLines(view: EditorView): Set<number> {
  const lines = new Set<number>()
  if (!view.hasFocus) return lines
  for (const range of view.state.selection.ranges) {
    const first = view.state.doc.lineAt(range.from).number
    const last = view.state.doc.lineAt(range.to).number
    for (let line = first; line <= last; line++) lines.add(line)
  }
  return lines
}

/**
 * Live preview (the author, 2026-11-09): CodeMirror parses the Markdown; off the lines being edited
 * its marks are hidden and the constructs styled, so the text reads as rendered, and the line under
 * the cursor shows its Markdown.
 */
function decorate(view: EditorView): DecorationSet {
  const active = activeLines(view)
  const doc = view.state.doc
  const found: Range<Decoration>[] = []
  const editing = (from: number) => active.has(doc.lineAt(from).number)
  for (const { from, to } of view.visibleRanges) {
    syntaxTree(view.state).iterate({
      from,
      to,
      enter: (node) => {
        const name = node.name
        const heading = /^ATXHeading(\d)$/.exec(name)
        if (heading) {
          found.push(Decoration.line({ class: `cm-md-h${heading[1]}` }).range(doc.lineAt(node.from).from))
          return
        }
        if (name === 'Blockquote') {
          for (let line = doc.lineAt(node.from).number; line <= doc.lineAt(node.to).number; line++) {
            found.push(Decoration.line({ class: 'cm-md-quote' }).range(doc.line(line).from))
          }
          return
        }
        if (name === 'FencedCode') {
          const first = doc.lineAt(node.from).number
          const last = doc.lineAt(node.to).number
          const inside = [...Array(last - first + 1).keys()].some((i) => active.has(first + i))
          for (let line = first; line <= last; line++) {
            const fence = line === first || line === last
            found.push(Decoration.line({ class: fence && !inside ? 'cm-md-fence' : 'cm-md-pre' }).range(doc.line(line).from))
            // The fences read as the block's edges until the cursor enters the block.
            if (fence && !inside && doc.line(line).length > 0) found.push(hidden.range(doc.line(line).from, doc.line(line).to))
          }
          return false
        }
        if (STYLES[name] && node.to > node.from) {
          found.push(Decoration.mark({ class: STYLES[name] }).range(node.from, node.to))
        }
        if (name === 'URL' && node.node.parent?.name === 'Link' && !editing(node.from)) {
          // A link reads as its text; the address shows on the line being edited.
          const open = doc.sliceString(node.from - 2, node.from)
          found.push(hidden.range(open === '](' ? node.from - 1 : node.from, node.to))
          return
        }
        if (name === 'ListMark' && !editing(node.from)) {
          const text = doc.sliceString(node.from, node.to)
          if (text === '-' || text === '*' || text === '+') found.push(bullet.range(node.from, node.to))
          return
        }
        if (MARKS.has(name) && !editing(node.from)) {
          // A heading's mark takes the space after it too.
          const end = name === 'HeaderMark' && doc.sliceString(node.to, node.to + 1) === ' ' ? node.to + 1 : node.to
          if (end > node.from) found.push(hidden.range(node.from, end))
        }
      },
    })
  }
  return Decoration.set(found, true)
}

const livePreview = ViewPlugin.fromClass(
  class {
    decorations: DecorationSet
    constructor(view: EditorView) {
      this.decorations = decorate(view)
    }
    update(update: ViewUpdate) {
      if (update.docChanged || update.selectionSet || update.viewportChanged || update.focusChanged) {
        this.decorations = decorate(update.view)
      }
    }
  },
  { decorations: (plugin) => plugin.decorations },
)

const look = EditorView.theme({
  '&': { fontSize: '0.875rem' },
  '&.cm-focused': { outline: 'none' },
  '.cm-content': { fontFamily: 'inherit', padding: '0' },
  '.cm-line': { padding: '0', lineHeight: '1.6' },
  '.cm-scroller': { fontFamily: 'inherit' },
})

/**
 * A Markdown field edited the way Obsidian edits it: the line under the cursor shows its
 * Markdown, the others read as rendered. CodeMirror does the editing; this adds the look.
 *
 * Args (props):
 *   value: The text; a new value from outside replaces it, the user's typing does not echo.
 *   onChange: Called with the text after each change.
 *   placeholder: Shown while it is empty.
 */
export function MarkdownEditor({
  value,
  onChange,
  placeholder,
}: {
  value: string
  onChange: (text: string) => void
  placeholder?: string
}) {
  const host = useRef<HTMLDivElement>(null)
  const view = useRef<EditorView | null>(null)
  const changed = useRef(onChange)
  useEffect(() => {
    changed.current = onChange
  }, [onChange])

  useEffect(() => {
    if (!host.current) return
    const extensions: Extension[] = [
      history(),
      keymap.of([...defaultKeymap, ...historyKeymap]),
      markdown({ extensions: GFM }),
      EditorView.lineWrapping,
      livePreview,
      look,
      EditorView.updateListener.of((update) => {
        if (update.docChanged) changed.current(update.state.doc.toString())
      }),
    ]
    if (placeholder) extensions.push(placeholderText(placeholder))
    view.current = new EditorView({
      parent: host.current,
      state: EditorState.create({ doc: value, extensions }),
    })
    return () => {
      view.current?.destroy()
      view.current = null
    }
    // The editor is made once; later values come through the effect below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const editor = view.current
    if (editor && editor.state.doc.toString() !== value) {
      editor.dispatch({ changes: { from: 0, to: editor.state.doc.length, insert: value } })
    }
  }, [value])

  return <div ref={host} className="md-editor" />
}
