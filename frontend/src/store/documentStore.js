import { create } from "zustand"
import client from "../api/client"

const useDocumentStore = create((set) => ({
  documents:  [],
  loading:    false,
  error:      null,

  fetchDocuments: async () => {
    set({ loading: true, error: null })
    try {
      const res = await client.get("/api/documents/")
      set({ documents: res.data, loading: false })
    } catch (err) {
      set({ error: "Failed to load documents", loading: false })
    }
  },

  addDocument: (doc) =>
    set((state) => ({ documents: [doc, ...state.documents] })),

  removeDocument: (id) =>
    set((state) => ({
      documents: state.documents.filter((d) => d.id !== id),
    })),
}))

export default useDocumentStore