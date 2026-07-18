import { create } from "zustand"

const useAuthStore = create((set) => ({
  user:  JSON.parse(localStorage.getItem("user") || "null"),
  token: localStorage.getItem("access_token") || null,

  login: (user, token) => {
    localStorage.setItem("access_token", token)
    localStorage.setItem("user", JSON.stringify(user))
    set({ user, token })
  },

  logout: () => {
    localStorage.removeItem("access_token")
    localStorage.removeItem("user")
    set({ user: null, token: null })
  },
}))

export default useAuthStore