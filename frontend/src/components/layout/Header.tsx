import { Menu, X } from 'lucide-react'
import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

const Header = () => {
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()

  const links = [
    { to: '/', label: 'Home' },
    { to: '/teams', label: 'Teams' },
    { to: '/season-simulator-v2', label: 'Season Simulator' },
    { to: '/players', label: 'Player Profiler' },
    { to: '/matches', label: 'Match Predictor' },
    { to: '/fantasy', label: 'Fantasy Optimizer' }
  ]

  const isActive = (path: string) =>
    location.pathname === path
      ? 'text-emerald-600 font-semibold border-b-2 border-emerald-600'
      : 'text-slate-600 hover:text-emerald-600 transition-colors'

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/80 backdrop-blur-sm shadow-sm">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
        <Link to="/" className="text-2xl font-bold">
          <span className="bg-gradient-to-r from-emerald-600 to-emerald-500 bg-clip-text text-transparent">
            SA20 Predictor
          </span>
        </Link>
        <nav className="hidden items-center space-x-6 md:flex">
          {links.map((link) => (
            <Link
              key={link.to}
              className={`text-sm font-medium pb-1 ${isActive(link.to)}`}
              to={link.to}
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <button
          className="inline-flex items-center justify-center rounded-md border border-slate-300 bg-white p-2 text-slate-700 transition hover:bg-slate-50 md:hidden"
          onClick={() => setMobileOpen((prev) => !prev)}
          aria-label="Toggle navigation"
        >
          {mobileOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
        </button>
      </div>
      {mobileOpen && (
        <nav className="border-t border-slate-200 bg-white px-6 py-4 md:hidden">
          <div className="flex flex-col space-y-3">
            {links.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                className={`text-base font-medium transition ${isActive(link.to)}`}
                onClick={() => setMobileOpen(false)}
              >
                {link.label}
              </Link>
            ))}
          </div>
        </nav>
      )}
    </header>
  )
}

export default Header
