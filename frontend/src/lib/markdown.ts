// Minimal Markdown parsing for AI-generated chat text (Gemini/Groq/etc. all
// reply in Markdown — headers, bold, lists, horizontal rules). Deliberately
// NOT a full CommonMark parser rendered via {@html}: that would need a
// sanitizer (the text is model output, not trusted) for real safety. This
// instead parses into plain data, rendered by ordinary Svelte templating
// (auto-escaped, no {@html} anywhere) — covers what these models actually
// produce in practice, not the full spec.

export type MdBlock =
  | { type: 'heading'; level: 2 | 3 | 4; text: string }
  | { type: 'paragraph'; text: string }
  | { type: 'list'; ordered: boolean; items: string[] }
  | { type: 'hr' };

export function parseSimpleMarkdown(source: string): MdBlock[] {
  const lines = source.replace(/\r\n/g, '\n').split('\n');
  const blocks: MdBlock[] = [];
  let paragraphBuf: string[] = [];
  let i = 0;

  function flushParagraph() {
    if (paragraphBuf.length) {
      blocks.push({ type: 'paragraph', text: paragraphBuf.join(' ').trim() });
      paragraphBuf = [];
    }
  }

  while (i < lines.length) {
    const trimmed = lines[i].trim();

    if (trimmed === '') { flushParagraph(); i++; continue; }

    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      flushParagraph();
      blocks.push({ type: 'hr' });
      i++;
      continue;
    }

    const heading = trimmed.match(/^(#{2,4})\s+(.*)$/);
    if (heading) {
      flushParagraph();
      blocks.push({ type: 'heading', level: heading[1].length as 2 | 3 | 4, text: heading[2].trim() });
      i++;
      continue;
    }

    const bulletMatch = trimmed.match(/^[-*]\s+(.*)$/);
    const numberedMatch = trimmed.match(/^\d+\.\s+(.*)$/);
    if (bulletMatch || numberedMatch) {
      flushParagraph();
      const ordered = !!numberedMatch;
      const items: string[] = [];
      while (i < lines.length) {
        const t = lines[i].trim();
        const b = t.match(/^[-*]\s+(.*)$/);
        const n = t.match(/^\d+\.\s+(.*)$/);
        if (ordered && n) { items.push(n[1]); i++; }
        else if (!ordered && b) { items.push(b[1]); i++; }
        else break;
      }
      blocks.push({ type: 'list', ordered, items });
      continue;
    }

    paragraphBuf.push(trimmed);
    i++;
  }
  flushParagraph();
  return blocks;
}

export interface InlineSegment {
  text: string;
  bold?: boolean;
  italic?: boolean;
  code?: boolean;
}

const _INLINE_RE = /(\*\*[^*]+\*\*|__[^_]+__|`[^`]+`|\*[^*]+\*|_[^_]+_)/g;

export function parseInline(text: string): InlineSegment[] {
  const segments: InlineSegment[] = [];
  let lastIndex = 0;
  let m: RegExpExecArray | null;
  _INLINE_RE.lastIndex = 0;
  while ((m = _INLINE_RE.exec(text))) {
    if (m.index > lastIndex) segments.push({ text: text.slice(lastIndex, m.index) });
    const token = m[0];
    if (token.startsWith('**') || token.startsWith('__')) segments.push({ text: token.slice(2, -2), bold: true });
    else if (token.startsWith('`')) segments.push({ text: token.slice(1, -1), code: true });
    else segments.push({ text: token.slice(1, -1), italic: true });
    lastIndex = _INLINE_RE.lastIndex;
  }
  if (lastIndex < text.length) segments.push({ text: text.slice(lastIndex) });
  return segments;
}
