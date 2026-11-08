/**
 * A column over a run of stages that follow one another: how many it holds, in order. ``tone``
 * is its colour in the editor, kept by the column wherever it moves.
 */
export type Span = { name: string; waiting: boolean; size: number; tone: number }

type Column = { name: string; rule: 'stages' | 'waiting'; stages: string[] }

/**
 * The board's columns as runs of the workflow's stages, or ``null`` when they are not: a column
 * by stages must hold stages that follow one another, and the columns must follow the stages'
 * order. A waiting column holds none and stands where the board puts it.
 */
export function asSpans(stages: string[], columns: Column[]): Span[] | null {
  const spans: Span[] = []
  let next = 0
  for (const column of columns) {
    if (column.rule === 'waiting') {
      spans.push({ name: column.name, waiting: true, size: 0, tone: spans.length })
      continue
    }
    const at = column.stages.map((stage) => stages.indexOf(stage)).sort((a, b) => a - b)
    if (at.some((index, i) => index !== next + i)) return null
    spans.push({ name: column.name, waiting: false, size: at.length, tone: spans.length })
    next += at.length
  }
  return next === stages.length ? spans : null
}

