import { ReactNode } from 'react'
import Header from './Header'
import Sidebar from './Sidebar'

interface MainLayoutProps {
  children: ReactNode
}

const MainLayout = ({ children }: MainLayoutProps) => (
  <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
    <Header />
    <div className="flex">
      <Sidebar />
      <main className="flex-1 overflow-x-hidden px-4 py-6 md:px-10">
        <div className="mx-auto max-w-7xl space-y-8">{children}</div>
      </main>
    </div>
  </div>
)

export default MainLayout
