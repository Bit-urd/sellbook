import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { 
  Home, 
  Store, 
  Book, 
  TrendingUp, 
  Bug, 
  Menu, 
  Settings,
  Sun,
  Moon
} from 'lucide-react'

interface SidebarItem {
  name: string
  path: string
  icon: React.ReactNode
  description: string
}

const sidebarItems: SidebarItem[] = [
  {
    name: '仪表板',
    path: '/',
    icon: <Home className="size-5" />,
    description: '数据分析仪表板'
  },
  {
    name: '店铺管理',
    path: '/shops',
    icon: <Store className="size-5" />,
    description: '管理书店信息'
  },
  {
    name: '书籍管理', 
    path: '/books',
    icon: <Book className="size-5" />,
    description: '管理书籍信息'
  },
  {
    name: '销售管理',
    path: '/sales',
    icon: <TrendingUp className="size-5" />,
    description: '销售数据分析'
  },
  {
    name: '爬虫管理',
    path: '/crawler',
    icon: <Bug className="size-5" />,
    description: '爬虫任务管理'
  }
]

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [isDark, setIsDark] = useState(false)

  const toggleTheme = () => {
    setIsDark(!isDark)
    document.documentElement.setAttribute('data-theme', !isDark ? 'dark' : 'light')
  }

  const toggleSidebar = () => {
    setSidebarOpen(!sidebarOpen)
  }

  return (
    <div className={`min-h-screen bg-background ${isDark ? 'dark' : ''}`}>
      {/* Mobile menu button */}
      <button
        onClick={toggleSidebar}
        className="lg:hidden fixed top-4 left-4 z-50 inline-flex items-center justify-center rounded-md p-2 text-foreground bg-card border shadow-md"
      >
        <Menu className="size-6" />
      </button>

      {/* Sidebar overlay for mobile */}
      {sidebarOpen && (
        <div 
          className="lg:hidden fixed inset-0 z-20 bg-black/50" 
          onClick={toggleSidebar}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed top-0 left-0 z-30 h-full w-64 transform bg-card border-r border-border transition-transform duration-200 ease-in-out
        lg:translate-x-0
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        {/* Logo */}
        <div className="flex items-center justify-between h-16 px-6 border-b border-border">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center text-primary-foreground font-bold">
              📚
            </div>
            <span className="font-semibold text-lg">SellBook</span>
          </div>
          <Button
            variant="ghost"
            size="sm" 
            onClick={toggleTheme}
            className="lg:hidden"
          >
            {isDark ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </Button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-4 py-6 space-y-2">
          {sidebarItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) => `
                flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
                hover:bg-accent hover:text-accent-foreground
                ${isActive 
                  ? 'bg-primary text-primary-foreground shadow-sm' 
                  : 'text-muted-foreground hover:text-foreground'
                }
              `}
            >
              {item.icon}
              <div className="flex-1">
                <div className="font-medium">{item.name}</div>
                <div className="text-xs opacity-70">{item.description}</div>
              </div>
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-4 py-4 border-t border-border">
          <button className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm font-medium text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors">
            <Settings className="size-5" />
            <div className="flex-1 text-left">
              <div className="font-medium">设置</div>
              <div className="text-xs opacity-70">系统配置</div>
            </div>
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="lg:ml-64 min-h-screen flex flex-col">
        {/* Top bar */}
        <header className="h-16 border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-20">
          <div className="h-full px-6 flex items-center justify-between">
            <div className="flex items-center gap-4">
              {/* Spacer for mobile menu button */}
              <div className="w-10 lg:w-0"></div>
            </div>
            
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={toggleTheme}
                className="hidden lg:flex"
              >
                {isDark ? <Sun className="size-4" /> : <Moon className="size-4" />}
              </Button>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  )
}