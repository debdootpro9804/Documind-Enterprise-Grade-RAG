export default function MarkdownRenderer({ content }) {
  if (!content) return null

  const lines = content.split("\n")
  const elements = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    // Heading 3
    if (line.startsWith("### ")) {
      elements.push(
        <h3 key={i} className="text-sm font-semibold text-gray-900 mt-3 mb-1">
          {parseInline(line.slice(4))}
        </h3>
      )
    }
    // Heading 2
    else if (line.startsWith("## ")) {
      elements.push(
        <h2 key={i} className="text-sm font-semibold text-gray-900 mt-3 mb-1">
          {parseInline(line.slice(3))}
        </h2>
      )
    }
    // Heading 1
    else if (line.startsWith("# ")) {
      elements.push(
        <h1 key={i} className="text-sm font-semibold text-gray-900 mt-3 mb-1">
          {parseInline(line.slice(2))}
        </h1>
      )
    }
    // Horizontal rule (sources divider)
    else if (line.startsWith("---")) {
      elements.push(
        <hr key={i} className="my-2 border-gray-100" />
      )
    }
    // Bullet list item
    else if (line.startsWith("- ") || line.startsWith("* ")) {
      const items = []
      while (
        i < lines.length &&
        (lines[i].startsWith("- ") || lines[i].startsWith("* "))
      ) {
        items.push(
          <li key={i} className="ml-4 list-disc">
            {parseInline(lines[i].slice(2))}
          </li>
        )
        i++
      }
      elements.push(
        <ul key={`ul-${i}`} className="my-1 space-y-0.5 text-sm">
          {items}
        </ul>
      )
      continue
    }
    // Numbered list item
    else if (/^\d+\.\s/.test(line)) {
      const items = []
      while (i < lines.length && /^\d+\.\s/.test(lines[i])) {
        const text = lines[i].replace(/^\d+\.\s/, "")
        items.push(
          <li key={i} className="ml-4 list-decimal">
            {parseInline(text)}
          </li>
        )
        i++
      }
      elements.push(
        <ol key={`ol-${i}`} className="my-1 space-y-0.5 text-sm">
          {items}
        </ol>
      )
      continue
    }
    // Empty line — spacing
    else if (line.trim() === "") {
      elements.push(<div key={i} className="h-1" />)
    }
    // Regular paragraph
    else {
      elements.push(
        <p key={i} className="text-sm leading-relaxed">
          {parseInline(line)}
        </p>
      )
    }

    i++
  }

  return <div className="space-y-1">{elements}</div>
}

// Parse inline formatting: **bold**, *italic*, `code`, and plain text
function parseInline(text) {
  const parts = []
  // Pattern matches **bold**, *italic*, `code`
  const regex = /(\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`)/g
  let last = 0
  let match

  while ((match = regex.exec(text)) !== null) {
    // Text before the match
    if (match.index > last) {
      parts.push(text.slice(last, match.index))
    }

    if (match[2]) {
      // **bold**
      parts.push(
        <strong key={match.index} className="font-semibold">
          {match[2]}
        </strong>
      )
    } else if (match[3]) {
      // *italic*
      parts.push(
        <em key={match.index} className="italic">
          {match[3]}
        </em>
      )
    } else if (match[4]) {
      // `code`
      parts.push(
        <code
          key={match.index}
          className="px-1 py-0.5 rounded text-xs font-mono"
          style={{ background: "#EEEDFE", color: "#3C3489" }}
        >
          {match[4]}
        </code>
      )
    }

    last = match.index + match[0].length
  }

  // Remaining text after last match
  if (last < text.length) {
    parts.push(text.slice(last))
  }

  return parts.length === 0 ? text : parts
}