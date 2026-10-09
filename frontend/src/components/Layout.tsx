import { NavLink, Outlet } from 'react-router-dom'

export function Layout() {
  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <NavLink to="/" className="brand">
            <span className="brand-mark" aria-hidden="true">
              FV
            </span>
            FieldVerify
          </NavLink>
          <nav>
            <NavLink to="/" end>
              Today's visits
            </NavLink>
            <NavLink to="/audit">Audit log</NavLink>
          </nav>
        </div>
      </header>
      <main className="shell">
        <Outlet />
      </main>
    </>
  )
}
