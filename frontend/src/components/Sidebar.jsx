import { useRef, useState } from "react"
import useDocumentStore from "../store/documentStore"
import useAuthStore     from "../store/authStore"
import client           from "../api/client"

const DOC_COLORS = [
  { bg: "#EEEDFE", border: "#AFA9EC", text: "#3C3489", dot: "#534AB7" },
  { bg: "#E1F5EE", border: "#5DCAA5", text: "#085041", dot: "#1D9E75" },
  { bg: "#FAEEDA", border: "#EF9F27", text: "#633806", dot: "#BA7517" },
  { bg: "#FAECE7", border: "#F0997B", text: "#712B13", dot: "#D85A30" },
  { bg: "#FBEAF0", border: "#ED93B1", text: "#72243E", dot: "#D4537E" },
]

function colorFor(index) {
  return DOC_COLORS[index % DOC_COLORS.length]
}

function formatSize(bytes) {
  if (!bytes) return ""
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function Sidebar({ selectedDocIds, onSelectDoc, onNewChat }) {
  const { documents, addDocument, removeDocument } = useDocumentStore()
  const { user, logout } = useAuthStore()
  const [uploading,   setUploading]   = useState(false)
  const [uploadError, setUploadError] = useState("")
  const [dragOver,    setDragOver]    = useState(false)
  const fileRef = useRef()

  const initials = user?.full_name
    ? user.full_name.split(" ").map((n) => n[0]).join("").toUpperCase().slice(0, 2)
    : "?"

  async function uploadFile(file) {
    if (!file) return
    setUploading(true)
    setUploadError("")
    const formData = new FormData()
    formData.append("file", file)
    try {
      const res = await client.post("/api/documents/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      addDocument({
        id:          res.data.document_id,
        filename:    res.data.filename,
        chunk_count: res.data.chunks,
        status:      "ready",
      })
    } catch (err) {
      setUploadError(err.response?.data?.detail || "Upload failed.")
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ""
    }
  }

  async function handleDelete(e, docId) {
    e.stopPropagation()
    try {
      await client.delete(`/api/documents/${docId}`)
      removeDocument(docId)
    } catch {}
  }

  return (
    <div className="w-64 min-w-64 h-screen flex flex-col"
         style={{ background: "#12102b", borderRight: "1px solid rgba(255,255,255,0.07)" }}>

      {/* Header */}
      <div className="px-4 py-4 flex items-center justify-between"
           style={{ borderBottom: "1px solid rgba(255,255,255,0.07)" }}>
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
               style={{ background: "linear-gradient(135deg, #534AB7, #7F77DD)" }}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="6" stroke="white" strokeWidth="1.3"/>
              <path d="M5.5 9c0-1.38 1.12-2.5 2.5-2.5s2.5 1.12 2.5 2.5"
                    stroke="white" strokeWidth="1.3" strokeLinecap="round"/>
            </svg>
          </div>
          <div>
            <p className="text-sm font-semibold text-white">DocuMind</p>
            <p className="text-xs" style={{ color: "rgba(255,255,255,0.35)" }}>AI assistant</p>
          </div>
        </div>
        <button
          onClick={onNewChat}
          title="New chat"
          className="w-7 h-7 rounded-lg flex items-center justify-center transition-all"
          style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)" }}
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M6 1v10M1 6h10" stroke="rgba(255,255,255,0.6)" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </button>
      </div>

      {/* Document list */}
      <div className="flex-1 overflow-y-auto px-3 py-3">
        <p className="text-xs font-medium mb-2 px-1 uppercase tracking-wider"
           style={{ color: "rgba(255,255,255,0.3)" }}>
          Documents
        </p>

        {documents.length === 0 && !uploading && (
          <p className="text-xs px-1 py-1" style={{ color: "rgba(255,255,255,0.3)" }}>
            No documents yet.
          </p>
        )}

        <div className="space-y-1.5">
          {documents.map((doc, i) => {
            const c        = colorFor(i)
            const selected = selectedDocIds.includes(doc.id)
            return (
              <div
                key={doc.id}
                onClick={() => onSelectDoc(doc.id)}
                className="group relative flex items-start gap-2.5 px-2.5 py-2.5 rounded-xl cursor-pointer transition-all"
                style={{
                  background: selected ? c.bg : "rgba(255,255,255,0.04)",
                  border:     selected
                    ? `1.5px solid ${c.border}`
                    : "1.5px solid transparent",
                }}
              >
                {/* Colored dot */}
                <div className="mt-0.5 w-2 h-2 rounded-full flex-shrink-0"
                     style={{ background: selected ? c.dot : "rgba(255,255,255,0.25)", marginTop: 5 }}/>

                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium truncate"
                     style={{ color: selected ? c.text : "rgba(255,255,255,0.75)" }}>
                    {doc.filename}
                  </p>
                  <p className="text-xs mt-0.5"
                     style={{ color: selected ? c.dot : "rgba(255,255,255,0.3)" }}>
                    {doc.chunk_count} chunks
                    {doc.file_size ? ` · ${formatSize(doc.file_size)}` : ""}
                  </p>
                </div>

                {/* Delete */}
                <button
                  onClick={(e) => handleDelete(e, doc.id)}
                  className="opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 mt-0.5"
                  style={{ color: "rgba(255,255,255,0.3)" }}
                >
                  <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
                    <path d="M1 1l9 9M10 1L1 10" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
                  </svg>
                </button>
              </div>
            )
          })}
        </div>

        {/* Upload zone */}
        <div className="mt-3">
          <input
            ref={fileRef}
            type="file"
            
            accept=".pdf,.docx,.txt,.jpg,.jpeg,.png,.webp"
            onChange={(e) => uploadFile(e.target.files[0])}
            className="hidden"
            id="file-upload"
          />
          <label
            htmlFor="file-upload"
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDragOver(false)
              uploadFile(e.dataTransfer.files[0])
            }}
            className="flex flex-col items-center gap-1.5 px-3 py-5 rounded-xl cursor-pointer transition-all"
            style={{
              border: `1.5px dashed ${dragOver ? "#7F77DD" : "rgba(255,255,255,0.15)"}`,
              background: dragOver ? "rgba(83,74,183,0.12)" : "rgba(255,255,255,0.03)",
            }}
          >
            {uploading ? (
              <>
                <div className="w-5 h-5 rounded-full border-2 border-t-transparent animate-spin"
                     style={{ borderColor: "#7F77DD", borderTopColor: "transparent" }}/>
                <span className="text-xs" style={{ color: "#AFA9EC" }}>Processing…</span>
              </>
            ) : (
              <>
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                  <path d="M9 1v11M5 5l4-4 4 4M2 15h14"
                        stroke="rgba(255,255,255,0.3)" strokeWidth="1.4"
                        strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                
                <span className="text-xs text-center" style={{ color: "rgba(255,255,255,0.35)" }}>
                  Upload or drop file
                </span>
                <span className="text-xs" style={{ color: "rgba(255,255,255,0.2)" }}>
                  PDF · DOCX · TXT · JPG · PNG · max 20 MB
                </span>
              </>
            )}
          </label>

          {uploadError && (
            <p className="text-xs mt-2 px-1" style={{ color: "#F09595" }}>{uploadError}</p>
          )}
        </div>

        {/* Filter hint */}
        {documents.length > 0 && (
          <p className="text-xs mt-3 px-1" style={{ color: "rgba(255,255,255,0.25)" }}>
            {selectedDocIds.length === 0
              ? "Click a document to filter"
              : `Filtering ${selectedDocIds.length} doc${selectedDocIds.length > 1 ? "s" : ""}`
            }
          </p>
        )}
      </div>

      {/* User footer */}
      <div className="px-3 py-3" style={{ borderTop: "1px solid rgba(255,255,255,0.07)" }}>
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold flex-shrink-0"
               style={{ background: "linear-gradient(135deg, #534AB7, #1D9E75)", color: "white" }}>
            {initials}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium truncate text-white">
              {user?.full_name || "User"}
            </p>
            <p className="text-xs truncate" style={{ color: "rgba(255,255,255,0.35)" }}>
              {user?.email}
            </p>
          </div>
          <button
            onClick={logout}
            title="Sign out"
            style={{ color: "rgba(255,255,255,0.25)" }}
            className="hover:text-white transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M5 7h8M10 4l3 3-3 3M5 2H2a1 1 0 00-1 1v8a1 1 0 001 1h3"
                    stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>
      </div>

    </div>
  )
}