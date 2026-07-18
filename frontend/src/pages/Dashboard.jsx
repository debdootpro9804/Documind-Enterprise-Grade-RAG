import { useState, useEffect } from "react"
import Sidebar from "../components/Sidebar"
import ChatPanel from "../components/ChatPanel"
import useDocumentStore from "../store/documentStore"

export default function Dashboard() {
  const [selectedDocIds, setSelectedDocIds] = useState([])
  const [sessionId,      setSessionId]      = useState(null)
  const fetchDocuments = useDocumentStore((s) => s.fetchDocuments)

  // Load documents when the dashboard first mounts
  useEffect(() => {
    fetchDocuments()
  }, [])

  function handleNewChat() {
    setSessionId(null)
    setSelectedDocIds([])
  }

  return (
    <div className="flex h-screen bg-[#f8f8f7] overflow-hidden">
      <Sidebar
        selectedDocIds={selectedDocIds}
        onSelectDoc={(id) => {
          setSelectedDocIds((prev) =>
            prev.includes(id)
              ? prev.filter((d) => d !== id)
              : [...prev, id]
          )
        }}
        onNewChat={handleNewChat}
      />
      <ChatPanel
        selectedDocIds={selectedDocIds}
        sessionId={sessionId}
        onSessionStart={(id) => setSessionId(id)}
      />
    </div>
  )
}