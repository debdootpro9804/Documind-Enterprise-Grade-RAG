import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import useAuthStore from "./store/authStore"
import Login    from "./pages/Login"
import Signup   from "./pages/Signup"
import Dashboard from "./pages/Dashboard"

function ProtectedRoute({ children }) {
  const token = useAuthStore((s) => s.token)
  return token ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login"  element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}