import { Home, Trophy, PlayCircle, User, Zap, Building2 } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'

const navItems = [
  { path: '/', icon: Home, label: 'Home' },
  { path: '/teams', icon: Building2, label: 'Teams' },
  { path: '/season-simulator-v2', icon: PlayCircle, label: 'Season Simulator' },
  { path: '/players', icon: User, label: 'Players' },
  { path: '/matches', icon: Trophy, label: 'Matches' },
  { path: '/fantasy', icon: Zap, label: 'Fantasy' }
]

const Sidebar = () => {
  const location = useLocation()

  return (
    <aside className="hidden w-64 border-r border-slate-200 bg-white md:block">
      <nav className="space-y-2 px-6 py-8">
        {navItems.map(({ path, icon: Icon, label }) => {
          const isActive =
            path === '/'
              ? location.pathname === '/'
              : location.pathname.startsWith(path)
          return (
            <Link
              key={path}
              to={path}
              className={`flex items-center space-x-3 rounded-lg px-4 py-3 text-sm font-medium transition-all ${
                isActive
                  ? 'bg-emerald-50 text-emerald-700 border-l-4 border-emerald-600'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-emerald-600'
              }`}
            >
              <Icon className="h-5 w-5" />
              <span>{label}</span>
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}

export default Sidebar
