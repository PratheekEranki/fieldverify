import { useEffect, useState } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import './App.css'

type Health = { status: string; credence_configured: boolean }

// Placeholder home page for T02: proves the web app can reach the backend.
// Replaced by the visit list in T11.
function Home() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
      .then(setHealth)
      .catch((err: Error) => setError(err.message))
  }, [])

  return (
    <main className="shell">
      <h1>FieldVerify</h1>
      <p className="subtitle">Provider identity verification for Medicaid site visits</p>
      <section className="card">
        <h2>Backend status</h2>
        {error && <p className="bad">Backend unreachable: {error}</p>}
        {!error && !health && <p>Checking…</p>}
        {health && (
          <ul>
            <li>
              API: <strong className="good">{health.status}</strong>
            </li>
            <li>
              Credence Cloud SDK configured:{' '}
              <strong className={health.credence_configured ? 'good' : 'warn'}>
                {health.credence_configured ? 'yes' : 'not yet'}
              </strong>
            </li>
          </ul>
        )}
      </section>
    </main>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="*" element={<Home />} />
      </Routes>
    </BrowserRouter>
  )
}
