import { useState, useRef, useEffect } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm     from "remark-gfm"
import useAuthStore  from "../store/authStore"

const SUGGESTIONS = [
  "Summarize the document",
  "What are the key points?",
  "Explain the main topics",
]

export default function ChatPanel({ selectedDocIds, sessionId, onSessionStart }) {
  const [messages, setMessages] = useState([])
  const [input,    setInput]    = useState("")
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState("")
  const bottomRef  = useRef()
  const inputRef   = useRef()
  const token      = useAuthStore((s) => s.token)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  useEffect(() => { inputRef.current?.focus() }, [])

  async function handleSend(text) {
    const question = (text || input).trim()
    if (!question || loading) return

    setInput("")
    setError("")

    const userMsg = { role: "user", content: question, id: Date.now() }
    const asstId  = Date.now() + 1
    setMessages((prev) => [
      ...prev,
      userMsg,
      { role: "assistant", content: "", id: asstId, streaming: true },
    ])
    setLoading(true)

    try {
      const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000"
      const response = await fetch(`${apiUrl}/api/chat/stream`,  {
        method:  "POST",
        headers: {
          "Content-Type":  "application/json",
          "Authorization": `Bearer ${token}`,
        },
        body: JSON.stringify({
          question,
          session_id:   sessionId || undefined,
          document_ids: selectedDocIds.length > 0 ? selectedDocIds : undefined,
        }),
      })

      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || "Request failed")
      }

      const reader  = response.body.getReader()
      const decoder = new TextDecoder()
      let   buffer  = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n\n")
        buffer = lines.pop()

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue
          const data = line.slice(6).trim()
          if (data === "[DONE]") continue
          try {
            const parsed = JSON.parse(data)
            if (parsed.error) { setError(parsed.error); break }
            if (parsed.token) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === asstId
                    ? { ...m, content: m.content + parsed.token }
                    : m
                )
              )
              const sid = response.headers.get("X-Session-Id")
              if (sid && !sessionId) onSessionStart(sid)
            }
          } catch {}
        }
      }
    } catch (err) {
      setError(err.message || "Something went wrong. Please try again.")
      setMessages((prev) => prev.filter((m) => m.id !== asstId))
    } finally {
      setMessages((prev) =>
        prev.map((m) => m.id === asstId ? { ...m, streaming: false } : m)
      )
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  return (
    <div className="flex-1 flex flex-col h-screen" style={{ background: "#f5f4f0" }}>

      {/* Header */}
      <div className="px-6 py-4 flex items-center justify-between bg-white"
           style={{ borderBottom: "1px solid #e8e7e3" }}>
        <div>
          <h2 className="text-sm font-semibold text-gray-900">
            {selectedDocIds.length === 0
              ? "Chat with all documents"
              : `Searching ${selectedDocIds.length} selected document${selectedDocIds.length > 1 ? "s" : ""}`
            }
          </h2>
          <p className="text-xs text-gray-400 mt-0.5">
            Powered by DocuMind RAG 
          </p>
        </div>
        {/* Status pill */}
        <div className="flex items-center gap-1.5 px-3 py-1 rounded-full"
             style={{ background: "#E1F5EE", border: "1px solid #9FE1CB" }}>
          <div className="w-1.5 h-1.5 rounded-full" style={{ background: "#1D9E75" }}/>
          <span className="text-xs font-medium" style={{ color: "#085041" }}>Live</span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {messages.length === 0 ? (
          <EmptyState onSuggest={handleSend} />
        ) : (
          <div className="max-w-3xl mx-auto space-y-5">
            {messages.map((msg) => (
              <Message key={msg.id} message={msg} />
            ))}
            {error && (
              <div className="text-sm rounded-xl px-4 py-3"
                   style={{ background: "#FCEBEB", border: "1px solid #F7C1C1", color: "#A32D2D" }}>
                {error}
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <div className="px-6 py-4 bg-white" style={{ borderTop: "1px solid #e8e7e3" }}>
        <div className="max-w-3xl mx-auto">
          <div className="flex gap-3 items-end">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything about your documents…"
              rows={1}
              disabled={loading}
              className="flex-1 resize-none px-4 py-3 text-sm rounded-xl outline-none transition-all"
              style={{
                border: "1.5px solid #e0dfd8",
                background: "#fafaf8",
                color: "#1a1a19",
                lineHeight: 1.5,
                maxHeight: 128,
                overflowY: "auto",
              }}
              onInput={(e) => {
                e.target.style.height = "auto"
                e.target.style.height = e.target.scrollHeight + "px"
              }}
            />
            <button
              onClick={() => handleSend()}
              disabled={loading || !input.trim()}
              className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 transition-all"
              style={{
                background: loading || !input.trim()
                  ? "#e0dfd8"
                  : "linear-gradient(135deg, #534AB7, #7F77DD)",
              }}
            >
              {loading ? (
                <div className="w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin"/>
              ) : (
                <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
                  <path d="M7.5 12V3M3 7.5l4.5-4.5 4.5 4.5"
                        stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              )}
            </button>
          </div>
          <p className="text-xs text-center mt-2" style={{ color: "#b4b2a9" }}>
            Enter to send · Shift+Enter for new line
          </p>
        </div>
      </div>

    </div>
  )
}

function Message({ message }) {
  const isUser = message.role === "user"

  if (isUser) {
    return (
      <div className="flex justify-end msg-enter">
        <div className="max-w-[72%] rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed text-white"
             style={{ background: "linear-gradient(135deg, #534AB7, #7F77DD)" }}>
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className="flex gap-3 items-start msg-enter">
      {/* Avatar */}
      <div className="w-7 h-7 min-w-7 rounded-full flex items-center justify-center mt-0.5 flex-shrink-0"
           style={{ background: "linear-gradient(135deg, #534AB7, #1D9E75)" }}>
        <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
          <circle cx="6.5" cy="6.5" r="5" stroke="white" strokeWidth="1.2"/>
          <path d="M4 7.5c0-1.38 1.12-2.5 2.5-2.5s2.5 1.12 2.5 2.5"
                stroke="white" strokeWidth="1.2" strokeLinecap="round"/>
        </svg>
      </div>

      <div className="flex-1 min-w-0">
        {message.streaming && message.content === "" ? (
          <div className="inline-flex items-center gap-1.5 px-4 py-3 rounded-2xl rounded-tl-sm bg-white"
               style={{ border: "1px solid #e8e7e3" }}>
            <span className="typing-dot"/>
            <span className="typing-dot"/>
            <span className="typing-dot"/>
          </div>
        ) : (
          <div className="px-4 py-3 rounded-2xl rounded-tl-sm text-sm leading-relaxed bg-white prose max-w-none"
               style={{ border: "1px solid #e8e7e3", color: "#1a1a19" }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
            {message.streaming && (
              <span className="inline-block w-0.5 h-4 ml-0.5 align-middle animate-pulse"
                    style={{ background: "#534AB7" }}/>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function EmptyState({ onSuggest }) {
  return (
    <div className="h-full flex flex-col items-center justify-center text-center px-6">
      {/* Icon */}
      <div className="w-16 h-16 rounded-3xl flex items-center justify-center mb-5"
           style={{ background: "linear-gradient(135deg, #534AB7, #7F77DD)" }}>
        <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
          <circle cx="14" cy="14" r="11" stroke="white" strokeWidth="1.5"/>
          <path d="M9 15.5c0-2.76 2.24-5 5-5s5 2.24 5 5"
                stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
          <circle cx="14" cy="19" r="1.5" fill="white"/>
        </svg>
      </div>

      <h3 className="text-lg font-semibold text-gray-900 mb-2">
        Ask anything about your documents
      </h3>
      <p className="text-sm text-gray-400 max-w-sm leading-relaxed">
        Upload a PDF, DOCX, or TXT in the sidebar, then ask questions.
        DocuMind finds the relevant sections and answers from them.
      </p>

      {/* Suggestion chips */}
      <div className="mt-6 flex flex-wrap gap-2 justify-center">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => onSuggest(s)}
            className="px-4 py-2 text-sm rounded-full transition-all hover:scale-105"
            style={{
              background: "#EEEDFE",
              border: "1px solid #AFA9EC",
              color: "#3C3489",
            }}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Feature pills */}
      <div className="mt-8 flex flex-wrap gap-2 justify-center">
        {[
          { label: "RAG powered",       color: "#EEEDFE", text: "#534AB7" },
          { label: "Streaming answers", color: "#E1F5EE", text: "#085041" },
          { label: "Source citations",  color: "#FAEEDA", text: "#633806" },
          { label: "Multi-doc search",  color: "#FAECE7", text: "#712B13" },
        ].map(({ label, color, text }) => (
          <span
            key={label}
            className="px-3 py-1 text-xs rounded-full font-medium"
            style={{ background: color, color: text }}
          >
            {label}
          </span>
        ))}
      </div>
    </div>
  )
}