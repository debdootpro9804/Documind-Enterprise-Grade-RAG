import { useState } from "react"
import { useNavigate, Link } from "react-router-dom"
import client from "../api/client"

export default function Signup() {
  const [fullName, setFullName] = useState("")
  const [email,    setEmail]    = useState("")
  const [password, setPassword] = useState("")
  const [error,    setError]    = useState("")
  const [loading,  setLoading]  = useState(false)
  const [success,  setSuccess]  = useState(false)
  const navigate = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    setError("")
    setLoading(true)
    try {
      await client.post("/api/auth/signup", { full_name: fullName, email, password })
      setSuccess(true)
      setTimeout(() => navigate("/login"), 2000)
    } catch (err) {
      setError(err.response?.data?.detail || "Signup failed. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center"
           style={{ background: "linear-gradient(135deg, #0f0e1a 0%, #1a1040 50%, #0f1a2e 100%)" }}>
        <div className="text-center">
          <div className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4"
               style={{ background: "rgba(29,158,117,0.2)", border: "1px solid rgba(29,158,117,0.4)" }}>
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
              <path d="M6 14l6 6L22 8" stroke="#1D9E75" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-white">Account created</h2>
          <p className="text-sm mt-1" style={{ color: "rgba(255,255,255,0.4)" }}>Redirecting to login…</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center"
         style={{ background: "linear-gradient(135deg, #0f0e1a 0%, #1a1040 50%, #0f1a2e 100%)" }}>
      <div style={{
        position: "absolute", top: "15%", right: "10%",
        width: 280, height: 280, borderRadius: "50%",
        background: "rgba(83,74,183,0.15)", filter: "blur(60px)", pointerEvents: "none"
      }}/>

      <div className="w-full max-w-md relative z-10 px-4">
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
          <h1 className="text-2xl font-semibold text-white">Create account</h1>
          <p className="text-sm mt-1" style={{ color: "rgba(255,255,255,0.45)" }}>
            Start chatting with your documents
          </p>
        </div>

        <div className="rounded-2xl p-8"
             style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)" }}>
          <div className="space-y-4">
            {[
              { label: "Full name", type: "text", value: fullName, set: setFullName, placeholder: "Arjun Kumar" },
              { label: "Email",     type: "email",    value: email,    set: setEmail,    placeholder: "you@example.com" },
              { label: "Password",  type: "password", value: password, set: setPassword, placeholder: "Min. 8 characters" },
            ].map(({ label, type, value, set, placeholder }) => (
              <div key={label}>
                <label className="block text-sm font-medium mb-1.5"
                       style={{ color: "rgba(255,255,255,0.7)" }}>
                  {label}
                </label>
                <input
                  type={type}
                  value={value}
                  onChange={(e) => set(e.target.value)}
                  placeholder={placeholder}
                  className="w-full px-4 py-2.5 rounded-xl text-sm outline-none"
                  style={{
                    background: "rgba(255,255,255,0.08)",
                    border: "1px solid rgba(255,255,255,0.12)",
                    color: "white",
                  }}
                />
              </div>
            ))}

            {error && (
              <div className="text-sm rounded-xl px-4 py-3"
                   style={{ background: "rgba(226,75,74,0.15)", border: "1px solid rgba(226,75,74,0.3)", color: "#F09595" }}>
                {error}
              </div>
            )}

            <button
              onClick={handleSubmit}
              disabled={loading}
              className="w-full py-2.5 rounded-xl text-sm font-medium text-white"
              style={{ background: loading ? "#3C3489" : "linear-gradient(135deg, #534AB7, #7F77DD)" }}
            >
              {loading ? "Creating account…" : "Create account"}
            </button>
          </div>

          <p className="text-center text-sm mt-5"
             style={{ color: "rgba(255,255,255,0.4)" }}>
            Have an account?{" "}
            <Link to="/login" style={{ color: "#AFA9EC" }} className="hover:underline">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}