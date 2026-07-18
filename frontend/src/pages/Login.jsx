import { useState } from "react"
import { useNavigate, Link } from "react-router-dom"
import client from "../api/client"
import useAuthStore from "../store/authStore"

export default function Login() {
  const [email,    setEmail]    = useState("")
  const [password, setPassword] = useState("")
  const [error,    setError]    = useState("")
  const [loading,  setLoading]  = useState(false)
  const navigate = useNavigate()
  const login    = useAuthStore((s) => s.login)

  async function handleSubmit(e) {
    e.preventDefault()
    setError("")
    setLoading(true)
    try {
      const res = await client.post("/api/auth/login", { email, password })
      login(res.data.user, res.data.access_token)
      navigate("/")
    } catch (err) {
      setError(err.response?.data?.detail || "Login failed. Check your credentials.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center"
         style={{ background: "linear-gradient(135deg, #0f0e1a 0%, #1a1040 50%, #0f1a2e 100%)" }}>

      {/* Decorative blobs */}
      <div style={{
        position: "absolute", top: "15%", left: "10%",
        width: 300, height: 300, borderRadius: "50%",
        background: "rgba(83,74,183,0.15)", filter: "blur(60px)", pointerEvents: "none"
      }}/>
      <div style={{
        position: "absolute", bottom: "20%", right: "10%",
        width: 250, height: 250, borderRadius: "50%",
        background: "rgba(29,158,117,0.12)", filter: "blur(60px)", pointerEvents: "none"
      }}/>

      <div className="w-full max-w-md relative z-10 px-4">

        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl mb-4"
               style={{ background: "linear-gradient(135deg, #534AB7, #7F77DD)" }}>
            <svg width="26" height="26" viewBox="0 0 26 26" fill="none">
              <circle cx="13" cy="13" r="10" stroke="white" strokeWidth="1.5"/>
              <path d="M8.5 14c0-2.485 2.015-4.5 4.5-4.5s4.5 2.015 4.5 4.5"
                    stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
              <circle cx="13" cy="17" r="1.5" fill="white"/>
            </svg>
          </div>
          <h1 className="text-2xl font-semibold text-white">DocuMind</h1>
          <p className="text-sm mt-1" style={{ color: "rgba(255,255,255,0.45)" }}>
            Sign in to your workspace
          </p>
        </div>

        {/* Card */}
        <div className="rounded-2xl p-8"
             style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", backdropFilter: "blur(12px)" }}>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1.5"
                     style={{ color: "rgba(255,255,255,0.7)" }}>
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSubmit(e)}
                placeholder="you@example.com"
                className="w-full px-4 py-2.5 rounded-xl text-sm outline-none transition-all"
                style={{
                  background: "rgba(255,255,255,0.08)",
                  border: "1px solid rgba(255,255,255,0.12)",
                  color: "white",
                }}
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1.5"
                     style={{ color: "rgba(255,255,255,0.7)" }}>
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSubmit(e)}
                placeholder="••••••••"
                className="w-full px-4 py-2.5 rounded-xl text-sm outline-none"
                style={{
                  background: "rgba(255,255,255,0.08)",
                  border: "1px solid rgba(255,255,255,0.12)",
                  color: "white",
                }}
              />
            </div>

            {error && (
              <div className="text-sm rounded-xl px-4 py-3"
                   style={{ background: "rgba(226,75,74,0.15)", border: "1px solid rgba(226,75,74,0.3)", color: "#F09595" }}>
                {error}
              </div>
            )}

            <button
              onClick={handleSubmit}
              disabled={loading}
              className="w-full py-2.5 rounded-xl text-sm font-medium text-white transition-all"
              style={{ background: loading ? "#3C3489" : "linear-gradient(135deg, #534AB7, #7F77DD)" }}
            >
              {loading ? "Signing in…" : "Sign in"}
            </button>
          </div>

          <p className="text-center text-sm mt-5"
             style={{ color: "rgba(255,255,255,0.4)" }}>
            No account?{" "}
            <Link to="/signup" style={{ color: "#AFA9EC" }} className="hover:underline">
              Sign up free
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}