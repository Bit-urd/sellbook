import React, { useState } from 'react'
import { BrowserRouter as Router, Routes, Route, NavLink } from 'react-router-dom'

// 简化版组件
function SimpleDashboard() {
  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-6">📊 数据分析仪表板</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white p-6 rounded-lg shadow-md">
          <h3 className="text-lg font-semibold text-blue-600 mb-2">总销量</h3>
          <p className="text-3xl font-bold">1,234</p>
          <p className="text-sm text-gray-500">本月销售记录</p>
        </div>
        <div className="bg-white p-6 rounded-lg shadow-md">
          <h3 className="text-lg font-semibold text-green-600 mb-2">总收入</h3>
          <p className="text-3xl font-bold">¥12,345</p>
          <p className="text-sm text-gray-500">平均售价</p>
        </div>
        <div className="bg-white p-6 rounded-lg shadow-md">
          <h3 className="text-lg font-semibold text-purple-600 mb-2">监控书籍</h3>
          <p className="text-3xl font-bold">567</p>
          <p className="text-sm text-gray-500">系统中书籍数</p>
        </div>
      </div>
    </div>
  )
}

function SimpleShopAdmin() {
  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-6">🏪 店铺管理</h1>
      <div className="bg-white p-6 rounded-lg shadow-md">
        <h3 className="text-lg font-semibold mb-4">店铺列表</h3>
        <div className="space-y-2">
          <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
            <span>孔夫子旧书网店铺1</span>
            <span className="px-2 py-1 bg-green-100 text-green-800 rounded text-sm">正常</span>
          </div>
          <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
            <span>多抓鱼店铺2</span>
            <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-sm">爬取中</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function SimpleBookAdmin() {
  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-6">📚 书籍管理</h1>
      <div className="bg-white p-6 rounded-lg shadow-md">
        <h3 className="text-lg font-semibold mb-4">书籍列表</h3>
        <div className="space-y-2">
          <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
            <div>
              <span className="font-medium">《代码大全》</span>
              <span className="text-sm text-gray-500 ml-2">ISBN: 9787121022982</span>
            </div>
            <span className="px-2 py-1 bg-green-100 text-green-800 rounded text-sm">已爬取</span>
          </div>
          <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
            <div>
              <span className="font-medium">《计算机程序设计艺术》</span>
              <span className="text-sm text-gray-500 ml-2">ISBN: 9787115171641</span>
            </div>
            <span className="px-2 py-1 bg-orange-100 text-orange-800 rounded text-sm">未爬取</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function SimpleSalesAdmin() {
  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-6">📈 销售管理</h1>
      <div className="bg-white p-6 rounded-lg shadow-md">
        <h3 className="text-lg font-semibold mb-4">最近销售</h3>
        <div className="space-y-2">
          <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
            <div>
              <span className="font-medium">《代码大全》</span>
              <span className="text-sm text-gray-500 ml-2">2024-01-15</span>
            </div>
            <span className="font-semibold text-green-600">¥89.00</span>
          </div>
          <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
            <div>
              <span className="font-medium">《设计模式》</span>
              <span className="text-sm text-gray-500 ml-2">2024-01-14</span>
            </div>
            <span className="font-semibold text-green-600">¥65.00</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function SimpleCrawlerAdmin() {
  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-6">🕷️ 爬虫管理</h1>
      <div className="bg-white p-6 rounded-lg shadow-md">
        <h3 className="text-lg font-semibold mb-4">爬虫任务</h3>
        <div className="space-y-2">
          <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
            <div>
              <span className="font-medium">孔夫子爬取任务</span>
              <span className="text-sm text-gray-500 ml-2">进度: 85%</span>
            </div>
            <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-sm">运行中</span>
          </div>
          <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
            <div>
              <span className="font-medium">多抓鱼爬取任务</span>
              <span className="text-sm text-gray-500 ml-2">进度: 100%</span>
            </div>
            <span className="px-2 py-1 bg-green-100 text-green-800 rounded text-sm">已完成</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function SimpleLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const navItems = [
    { name: '仪表板', path: '/', icon: '📊' },
    { name: '店铺管理', path: '/shops', icon: '🏪' },
    { name: '书籍管理', path: '/books', icon: '📚' },
    { name: '销售管理', path: '/sales', icon: '📈' },
    { name: '爬虫管理', path: '/crawler', icon: '🕷️' }
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 移动端菜单按钮 */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className="lg:hidden fixed top-4 left-4 z-50 bg-white p-2 rounded-md shadow-md"
      >
        ☰
      </button>

      {/* 侧边栏遮罩 */}
      {sidebarOpen && (
        <div 
          className="lg:hidden fixed inset-0 z-40 bg-black bg-opacity-50" 
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* 侧边栏 */}
      <aside className={`
        fixed top-0 left-0 z-40 h-full w-64 bg-white border-r border-gray-200 transition-transform duration-200
        lg:translate-x-0 lg:static lg:inset-0
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        {/* Logo */}
        <div className="flex items-center gap-2 h-16 px-6 border-b border-gray-200">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold">
            📚
          </div>
          <span className="font-semibold text-lg">SellBook</span>
        </div>

        {/* 导航 */}
        <nav className="px-4 py-6 space-y-2">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) => `
                flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
                hover:bg-gray-100
                ${isActive 
                  ? 'bg-blue-50 text-blue-700 border-r-2 border-blue-600' 
                  : 'text-gray-700 hover:text-gray-900'
                }
              `}
            >
              <span className="text-lg">{item.icon}</span>
              {item.name}
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* 主内容 */}
      <div className="lg:ml-64">
        {/* 顶部栏 */}
        <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6">
          <div className="lg:hidden w-10"></div>
          <div className="text-sm text-gray-500">
            SellBook - 书籍销售数据管理系统
          </div>
        </header>

        {/* 页面内容 */}
        <main>
          <Routes>
            <Route path="/" element={<SimpleDashboard />} />
            <Route path="/shops" element={<SimpleShopAdmin />} />
            <Route path="/books" element={<SimpleBookAdmin />} />
            <Route path="/sales" element={<SimpleSalesAdmin />} />
            <Route path="/crawler" element={<SimpleCrawlerAdmin />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}

export default function SimpleApp() {
  return (
    <Router>
      <SimpleLayout />
    </Router>
  )
}