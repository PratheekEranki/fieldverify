import { BrowserRouter, Route, Routes } from 'react-router-dom'
import './App.css'
import { Layout } from './components/Layout'
import { AuditLog } from './pages/AuditLog'
import { Result } from './pages/Result'
import { Verify } from './pages/Verify'
import { VisitList } from './pages/VisitList'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<VisitList />} />
          <Route path="/visits/:visitId" element={<Verify />} />
          <Route path="/results/:resultId" element={<Result />} />
          <Route path="/audit" element={<AuditLog />} />
          <Route path="*" element={<p>Page not found.</p>} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
