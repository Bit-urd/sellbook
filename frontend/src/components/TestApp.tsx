import React from 'react'

export default function TestApp() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          🎉 React App Working! 
        </h1>
        <p className="text-lg text-gray-600 mb-8">
          SellBook - 书籍销售数据管理系统
        </p>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <div className="bg-white p-4 rounded-lg shadow-md">
            <h3 className="font-semibold text-blue-600">📊 仪表板</h3>
            <p className="text-sm text-gray-500">数据分析</p>
          </div>
          <div className="bg-white p-4 rounded-lg shadow-md">
            <h3 className="font-semibold text-green-600">🏪 店铺管理</h3>
            <p className="text-sm text-gray-500">店铺信息</p>
          </div>
          <div className="bg-white p-4 rounded-lg shadow-md">
            <h3 className="font-semibold text-purple-600">📚 书籍管理</h3>
            <p className="text-sm text-gray-500">书籍信息</p>
          </div>
          <div className="bg-white p-4 rounded-lg shadow-md">
            <h3 className="font-semibold text-orange-600">📈 销售管理</h3>
            <p className="text-sm text-gray-500">销售数据</p>
          </div>
          <div className="bg-white p-4 rounded-lg shadow-md">
            <h3 className="font-semibold text-red-600">🕷️ 爬虫管理</h3>
            <p className="text-sm text-gray-500">爬虫任务</p>
          </div>
        </div>
      </div>
    </div>
  )
}