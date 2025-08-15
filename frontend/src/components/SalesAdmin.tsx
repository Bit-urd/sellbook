import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { TrendingUp, Calendar, DollarSign, BarChart3, Search, RefreshCw, ChevronLeft, ChevronRight, Eye, Download, Filter, Store, Rocket, RotateCcw } from 'lucide-react'

interface SalesRecord {
  id: string
  isbn: string
  title: string
  shop_name: string
  platform: string
  price: number
  quantity: number
  total_amount: number
  sale_date: string
  profit_margin: number
  status: string
}

interface SalesStats {
  total_sales: number
  total_revenue: number
  avg_price: number
  total_profit: number
  avg_profit_margin: number
  top_selling_books: Array<{
    isbn: string
    title: string
    total_sales: number
    total_revenue: number
  }>
  sales_by_platform: Array<{
    platform: string
    total_sales: number
    total_revenue: number
  }>
  daily_sales: Array<{
    date: string
    sales_count: number
    revenue: number
  }>
}

interface DateRange {
  start_date: string
  end_date: string
}

interface ShopInfo {
  shop_id: string
  shop_name: string
  platform: string
  status: string
  created_at: string
}

interface ShopStats {
  shop_info: ShopInfo
  statistics: {
    total_sales: number
    unique_books: number
    avg_price: number
    total_revenue: number
    min_price: number
    max_price: number
  }
  recent_books: Array<{
    isbn: string
    title: string
    is_crawled: boolean
    last_sales_update: string | null
  }>
}

export default function SalesAdmin() {
  const [salesRecords, setSalesRecords] = useState<SalesRecord[]>([])
  const [salesStats, setSalesStats] = useState<SalesStats | null>(null)
  const [loading, setLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [activeTab, setActiveTab] = useState('records')
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [viewingRecord, setViewingRecord] = useState<SalesRecord | null>(null)
  const [isViewDialogOpen, setIsViewDialogOpen] = useState(false)
  const [dateRange, setDateRange] = useState<DateRange>({
    start_date: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0], // 30 days ago
    end_date: new Date().toISOString().split('T')[0] // today
  })
  const [isFilterOpen, setIsFilterOpen] = useState(false)
  const [selectedPlatform, setSelectedPlatform] = useState('all')
  const [selectedStatus, setSelectedStatus] = useState('all')
  const [shops, setShops] = useState<ShopInfo[]>([])
  const [currentShopPage, setCurrentShopPage] = useState(1)
  const [shopStats, setShopStats] = useState<ShopStats | null>(null)
  const [isShopStatsOpen, setIsShopStatsOpen] = useState(false)
  const [alertMessage, setAlertMessage] = useState<{type: 'success' | 'error' | 'info', message: string} | null>(null)

  const pageSize = 20

  useEffect(() => {
    loadSalesRecords(1)
    loadSalesStats()
    loadShops()
  }, [searchQuery, dateRange, selectedPlatform, selectedStatus])

  const loadSalesRecords = async (page: number) => {
    setLoading(true)
    try {
      const offset = (page - 1) * pageSize
      let url = `/api/sales?limit=${pageSize}&offset=${offset}`
      
      if (searchQuery.trim()) {
        url += `&search=${encodeURIComponent(searchQuery.trim())}`
      }

      if (dateRange.start_date) {
        url += `&start_date=${dateRange.start_date}`
      }
      if (dateRange.end_date) {
        url += `&end_date=${dateRange.end_date}`
      }

      if (selectedPlatform && selectedPlatform !== 'all') {
        url += `&platform=${selectedPlatform}`
      }

      if (selectedStatus && selectedStatus !== 'all') {
        url += `&status=${selectedStatus}`
      }

      const response = await fetch(url)
      const data = await response.json()
      
      if (data.success) {
        setSalesRecords(data.data.sales || [])
        setTotalPages(Math.ceil((data.data.total || 0) / pageSize))
        setCurrentPage(page)
      }
    } catch (error) {
      console.error('加载销售记录失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadSalesStats = async () => {
    try {
      let url = '/api/sales/stats'
      const params = new URLSearchParams()

      if (dateRange.start_date) {
        params.append('start_date', dateRange.start_date)
      }
      if (dateRange.end_date) {
        params.append('end_date', dateRange.end_date)
      }

      if (params.toString()) {
        url += `?${params.toString()}`
      }

      const response = await fetch(url)
      const data = await response.json()
      
      if (data.success) {
        setSalesStats(data.data)
      }
    } catch (error) {
      console.error('加载销售统计失败:', error)
    }
  }

  const handleViewRecord = (record: SalesRecord) => {
    setViewingRecord(record)
    setIsViewDialogOpen(true)
  }

  const loadShops = async (page = 1) => {
    try {
      const response = await fetch(`/sales-data/shops?page=${page}&page_size=${pageSize}`)
      const data = await response.json()
      
      if (data.success) {
        setShops(data.data.shops || [])
        setCurrentShopPage(page)
      }
    } catch (error) {
      console.error('加载店铺列表失败:', error)
    }
  }

  const showAlert = (type: 'success' | 'error' | 'info', message: string) => {
    setAlertMessage({ type, message })
    setTimeout(() => setAlertMessage(null), 3000)
  }

  const crawlShopSales = async (shopId: string) => {
    if (!confirm(`确定要爬取店铺 ${shopId} 的销售数据吗？`)) {
      return
    }

    showAlert('info', `正在爬取店铺 ${shopId} 的销售数据，请稍候...`)

    try {
      const response = await fetch(`/sales-data/shop/${shopId}/crawl-sales`, {
        method: 'POST'
      })
      const data = await response.json()

      if (data.success) {
        showAlert('success', data.message)
        loadSalesStats() // 刷新统计数据
        loadSalesRecords(currentPage) // 刷新销售记录
      } else {
        showAlert('error', '爬取失败: ' + (data.detail || data.message))
      }
    } catch (error) {
      showAlert('error', '爬取失败: ' + (error as Error).message)
    }
  }

  const crawlAllShops = async () => {
    if (!confirm('确定要爬取所有店铺的销售数据吗？这可能需要较长时间。')) {
      return
    }

    showAlert('info', '正在创建爬取任务，请稍候...')

    try {
      const response = await fetch('/sales-data/crawl-all-shops', {
        method: 'POST'
      })
      const data = await response.json()

      if (data.success) {
        showAlert('success', data.message)
      } else {
        showAlert('error', '创建任务失败: ' + (data.detail || data.message))
      }
    } catch (error) {
      showAlert('error', '创建任务失败: ' + (error as Error).message)
    }
  }

  const viewShopStats = async (shopId: string) => {
    try {
      const response = await fetch(`/sales-data/shop/${shopId}/sales-stats`)
      const data = await response.json()

      if (data.success) {
        setShopStats(data.data)
        setIsShopStatsOpen(true)
      } else {
        showAlert('error', '获取统计失败')
      }
    } catch (error) {
      showAlert('error', '获取统计失败: ' + (error as Error).message)
    }
  }

  const handleExportData = async () => {
    try {
      let url = '/api/sales/export'
      const params = new URLSearchParams()

      if (dateRange.start_date) {
        params.append('start_date', dateRange.start_date)
      }
      if (dateRange.end_date) {
        params.append('end_date', dateRange.end_date)
      }
      if (selectedPlatform && selectedPlatform !== 'all') {
        params.append('platform', selectedPlatform)
      }

      if (params.toString()) {
        url += `?${params.toString()}`
      }

      const response = await fetch(url)
      const blob = await response.blob()
      
      const downloadUrl = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = downloadUrl
      link.download = `sales_data_${dateRange.start_date}_to_${dateRange.end_date}.csv`
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(downloadUrl)
    } catch (error) {
      console.error('导出失败:', error)
      alert('导出失败，请稍后重试')
    }
  }

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'completed': return 'text-green-600 bg-green-100'
      case 'pending': return 'text-yellow-600 bg-yellow-100'
      case 'cancelled': return 'text-red-600 bg-red-100'
      default: return 'text-gray-600 bg-gray-100'
    }
  }

  const getStatusText = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'completed': return '已完成'
      case 'pending': return '进行中'
      case 'cancelled': return '已取消'
      default: return '未知'
    }
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('zh-CN', {
      style: 'currency',
      currency: 'CNY'
    }).format(amount)
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <TrendingUp className="size-8 text-primary" />
          <h1 className="text-3xl font-bold tracking-tight">销售数据管理</h1>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => setIsFilterOpen(!isFilterOpen)}>
            <Filter className="size-4 mr-2" />
            筛选
          </Button>
          <Button variant="ghost" size="sm" onClick={handleExportData}>
            <Download className="size-4 mr-2" />
            导出
          </Button>
          <Button variant="ghost" size="sm" onClick={() => { loadSalesRecords(currentPage); loadSalesStats() }}>
            <RefreshCw className="size-4 mr-2" />
            刷新
          </Button>
        </div>
      </div>
        {/* Filter Panel */}
        {isFilterOpen && (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">数据筛选</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">开始日期</label>
                  <Input
                    type="date"
                    value={dateRange.start_date}
                    onChange={(e) => setDateRange({...dateRange, start_date: e.target.value})}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">结束日期</label>
                  <Input
                    type="date"
                    value={dateRange.end_date}
                    onChange={(e) => setDateRange({...dateRange, end_date: e.target.value})}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">平台</label>
                  <select
                    value={selectedPlatform}
                    onChange={(e) => setSelectedPlatform(e.target.value)}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <option value="all">全部平台</option>
                    <option value="kongfuzi">孔夫子旧书网</option>
                    <option value="duozhuayu">多抓鱼</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">状态</label>
                  <select
                    value={selectedStatus}
                    onChange={(e) => setSelectedStatus(e.target.value)}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <option value="all">全部状态</option>
                    <option value="completed">已完成</option>
                    <option value="pending">进行中</option>
                    <option value="cancelled">已取消</option>
                  </select>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Stats Cards */}
        {salesStats && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">总销量</p>
                    <p className="text-2xl font-bold">{salesStats.total_sales}</p>
                  </div>
                  <BarChart3 className="size-8 text-muted-foreground" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">总收入</p>
                    <p className="text-2xl font-bold text-green-600">{formatCurrency(salesStats.total_revenue)}</p>
                  </div>
                  <DollarSign className="size-8 text-green-600" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">平均售价</p>
                    <p className="text-2xl font-bold text-blue-600">{formatCurrency(salesStats.avg_price)}</p>
                  </div>
                  <div className="text-blue-600">💰</div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">总利润</p>
                    <p className="text-2xl font-bold text-purple-600">{formatCurrency(salesStats.total_profit)}</p>
                  </div>
                  <div className="text-purple-600">📈</div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">平均利润率</p>
                    <p className="text-2xl font-bold text-orange-600">{salesStats.avg_profit_margin.toFixed(1)}%</p>
                  </div>
                  <div className="text-orange-600">📊</div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Alert Container */}
        {alertMessage && (
          <Card className={`border-l-4 ${
            alertMessage.type === 'success' ? 'border-green-500 bg-green-50' :
            alertMessage.type === 'error' ? 'border-red-500 bg-red-50' :
            'border-blue-500 bg-blue-50'
          }`}>
            <CardContent className="pt-6">
              <div className="flex items-center">
                <div className={`mr-3 ${
                  alertMessage.type === 'success' ? 'text-green-600' :
                  alertMessage.type === 'error' ? 'text-red-600' :
                  'text-blue-600'
                }`}>
                  {alertMessage.type === 'success' ? '✓' : alertMessage.type === 'error' ? '✗' : 'ℹ'}
                </div>
                <div className={`${
                  alertMessage.type === 'success' ? 'text-green-800' :
                  alertMessage.type === 'error' ? 'text-red-800' :
                  'text-blue-800'
                }`}>
                  {alertMessage.message}
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Shop Management */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Store className="size-5" />
              店铺列表
            </CardTitle>
            <CardDescription>
              管理店铺信息并爬取销售数据
            </CardDescription>
            <div className="flex gap-2 pt-4">
              <Button onClick={crawlAllShops} className="bg-orange-600 hover:bg-orange-700">
                <Rocket className="size-4 mr-2" />
                一键爬取所有店铺
              </Button>
              <Button onClick={() => loadShops(currentShopPage)} variant="outline">
                <RotateCcw className="size-4 mr-2" />
                刷新列表
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {shops.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>店铺ID</TableHead>
                    <TableHead>店铺名称</TableHead>
                    <TableHead>平台</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>创建时间</TableHead>
                    <TableHead>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {shops.map((shop) => (
                    <TableRow key={shop.shop_id}>
                      <TableCell className="font-mono text-sm">{shop.shop_id}</TableCell>
                      <TableCell className="font-medium">{shop.shop_name}</TableCell>
                      <TableCell>{shop.platform || 'kongfuzi'}</TableCell>
                      <TableCell>
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          shop.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                        }`}>
                          {shop.status === 'active' ? '活跃' : '未激活'}
                        </span>
                      </TableCell>
                      <TableCell className="text-sm">
                        {new Date(shop.created_at).toLocaleString('zh-CN')}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => crawlShopSales(shop.shop_id)}
                            className="text-blue-600 hover:text-blue-700"
                          >
                            爬取销售数据
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => viewShopStats(shop.shop_id)}
                            className="text-green-600 hover:text-green-700"
                          >
                            查看统计
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                暂无店铺数据
              </div>
            )}
          </CardContent>
        </Card>

        {/* Search */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex gap-2 max-w-md">
              <Input
                placeholder="搜索书名、ISBN或店铺..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && loadSalesRecords(1)}
              />
              <Button onClick={() => loadSalesRecords(1)}>
                <Search className="size-4" />
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Data Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="records">销售记录</TabsTrigger>
            <TabsTrigger value="analytics">数据分析</TabsTrigger>
          </TabsList>

          <TabsContent value="records" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>销售记录</CardTitle>
                <CardDescription>
                  查看和管理所有销售交易记录
                </CardDescription>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="flex justify-center py-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                  </div>
                ) : (
                  <>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>书名</TableHead>
                          <TableHead>ISBN</TableHead>
                          <TableHead>店铺</TableHead>
                          <TableHead>平台</TableHead>
                          <TableHead>单价</TableHead>
                          <TableHead>数量</TableHead>
                          <TableHead>总金额</TableHead>
                          <TableHead>利润率</TableHead>
                          <TableHead>状态</TableHead>
                          <TableHead>销售日期</TableHead>
                          <TableHead>操作</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {salesRecords.length > 0 ? (
                          salesRecords.map((record) => (
                            <TableRow key={record.id}>
                              <TableCell className="font-medium max-w-[200px] truncate" title={record.title}>
                                {record.title}
                              </TableCell>
                              <TableCell>{record.isbn}</TableCell>
                              <TableCell>{record.shop_name}</TableCell>
                              <TableCell className="capitalize">
                                {record.platform === 'kongfuzi' ? '孔夫子' : record.platform}
                              </TableCell>
                              <TableCell className="font-semibold text-green-600">
                                {formatCurrency(record.price)}
                              </TableCell>
                              <TableCell>{record.quantity}</TableCell>
                              <TableCell className="font-semibold text-blue-600">
                                {formatCurrency(record.total_amount)}
                              </TableCell>
                              <TableCell>
                                <span className={`font-semibold ${
                                  record.profit_margin > 20 ? 'text-green-600' : 
                                  record.profit_margin > 10 ? 'text-orange-600' : 'text-red-600'
                                }`}>
                                  {record.profit_margin}%
                                </span>
                              </TableCell>
                              <TableCell>
                                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(record.status)}`}>
                                  {getStatusText(record.status)}
                                </span>
                              </TableCell>
                              <TableCell>
                                {new Date(record.sale_date).toLocaleDateString('zh-CN')}
                              </TableCell>
                              <TableCell>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleViewRecord(record)}
                                >
                                  <Eye className="size-4" />
                                </Button>
                              </TableCell>
                            </TableRow>
                          ))
                        ) : (
                          <TableRow>
                            <TableCell colSpan={11} className="text-center py-8 text-muted-foreground">
                              {searchQuery ? '没有找到匹配的记录' : '暂无销售记录'}
                            </TableCell>
                          </TableRow>
                        )}
                      </TableBody>
                    </Table>

                    {/* Pagination */}
                    {totalPages > 1 && (
                      <div className="flex justify-center items-center gap-2 mt-4">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => loadSalesRecords(currentPage - 1)}
                          disabled={currentPage === 1}
                        >
                          <ChevronLeft className="size-4" />
                        </Button>
                        <span className="text-muted-foreground">
                          第 {currentPage} 页 / 共 {totalPages} 页
                        </span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => loadSalesRecords(currentPage + 1)}
                          disabled={currentPage === totalPages}
                        >
                          <ChevronRight className="size-4" />
                        </Button>
                      </div>
                    )}
                  </>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="analytics" className="space-y-4">
            {salesStats && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Top Selling Books */}
                <Card>
                  <CardHeader>
                    <CardTitle>热销书籍 Top 10</CardTitle>
                    <CardDescription>销量最高的书籍排行榜</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {salesStats.top_selling_books.slice(0, 10).map((book, index) => (
                        <div key={book.isbn} className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <span className="flex items-center justify-center w-6 h-6 rounded-full bg-primary text-primary-foreground text-xs font-bold">
                              {index + 1}
                            </span>
                            <div>
                              <p className="font-medium text-sm truncate max-w-[200px]" title={book.title}>
                                {book.title}
                              </p>
                              <p className="text-xs text-muted-foreground">{book.isbn}</p>
                            </div>
                          </div>
                          <div className="text-right">
                            <p className="font-semibold">{book.total_sales}</p>
                            <p className="text-xs text-muted-foreground">{formatCurrency(book.total_revenue)}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                {/* Platform Performance */}
                <Card>
                  <CardHeader>
                    <CardTitle>平台表现</CardTitle>
                    <CardDescription>各平台销售数据对比</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {salesStats.sales_by_platform.map((platform) => (
                        <div key={platform.platform} className="space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="font-medium">
                              {platform.platform === 'kongfuzi' ? '孔夫子旧书网' : platform.platform}
                            </span>
                            <span className="font-semibold">{formatCurrency(platform.total_revenue)}</span>
                          </div>
                          <div className="w-full bg-secondary rounded-full h-2">
                            <div 
                              className="bg-primary h-2 rounded-full" 
                              style={{
                                width: `${(platform.total_revenue / Math.max(...salesStats.sales_by_platform.map(p => p.total_revenue))) * 100}%`
                              }}
                            ></div>
                          </div>
                          <div className="flex justify-between text-xs text-muted-foreground">
                            <span>销量: {platform.total_sales}</span>
                            <span>收入: {formatCurrency(platform.total_revenue)}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}
          </TabsContent>
        </Tabs>

      {/* View Sales Record Dialog */}
      <Dialog open={isViewDialogOpen} onOpenChange={setIsViewDialogOpen}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>销售记录详情</DialogTitle>
            <DialogDescription>
              查看销售记录的详细信息
            </DialogDescription>
          </DialogHeader>
          
          {viewingRecord && (
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">记录ID</label>
                  <p className="text-sm font-mono">{viewingRecord.id}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">ISBN</label>
                  <p className="text-sm font-mono">{viewingRecord.isbn}</p>
                </div>
              </div>

              <div>
                <label className="text-sm font-medium text-muted-foreground">书名</label>
                <p className="text-sm font-medium">{viewingRecord.title}</p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">店铺名称</label>
                  <p className="text-sm">{viewingRecord.shop_name}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">平台</label>
                  <p className="text-sm capitalize">
                    {viewingRecord.platform === 'kongfuzi' ? '孔夫子旧书网' : viewingRecord.platform}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">单价</label>
                  <p className="text-sm font-semibold text-green-600">{formatCurrency(viewingRecord.price)}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">数量</label>
                  <p className="text-sm font-semibold">{viewingRecord.quantity}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">总金额</label>
                  <p className="text-sm font-semibold text-blue-600">{formatCurrency(viewingRecord.total_amount)}</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">利润率</label>
                  <p className={`text-sm font-semibold ${
                    viewingRecord.profit_margin > 20 ? 'text-green-600' : 
                    viewingRecord.profit_margin > 10 ? 'text-orange-600' : 'text-red-600'
                  }`}>
                    {viewingRecord.profit_margin}%
                  </p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">状态</label>
                  <p className="text-sm">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(viewingRecord.status)}`}>
                      {getStatusText(viewingRecord.status)}
                    </span>
                  </p>
                </div>
              </div>

              <div>
                <label className="text-sm font-medium text-muted-foreground">销售日期</label>
                <p className="text-sm">{new Date(viewingRecord.sale_date).toLocaleString('zh-CN')}</p>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsViewDialogOpen(false)}>
              关闭
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Shop Statistics Dialog */}
      <Dialog open={isShopStatsOpen} onOpenChange={setIsShopStatsOpen}>
        <DialogContent className="sm:max-w-[700px]">
          <DialogHeader>
            <DialogTitle>店铺统计</DialogTitle>
            <DialogDescription>
              查看店铺的详细销售统计信息
            </DialogDescription>
          </DialogHeader>
          
          {shopStats && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold mb-4">
                  {shopStats.shop_info.shop_name} - 统计信息
                </h3>
                
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  <Card>
                    <CardContent className="p-4 text-center">
                      <div className="text-2xl font-bold text-primary mb-1">
                        {shopStats.statistics.total_sales || 0}
                      </div>
                      <div className="text-sm text-muted-foreground">总销售记录</div>
                    </CardContent>
                  </Card>
                  
                  <Card>
                    <CardContent className="p-4 text-center">
                      <div className="text-2xl font-bold text-primary mb-1">
                        {shopStats.statistics.unique_books || 0}
                      </div>
                      <div className="text-sm text-muted-foreground">不同书籍</div>
                    </CardContent>
                  </Card>
                  
                  <Card>
                    <CardContent className="p-4 text-center">
                      <div className="text-2xl font-bold text-green-600 mb-1">
                        ¥{(shopStats.statistics.avg_price || 0).toFixed(2)}
                      </div>
                      <div className="text-sm text-muted-foreground">平均价格</div>
                    </CardContent>
                  </Card>
                  
                  <Card>
                    <CardContent className="p-4 text-center">
                      <div className="text-2xl font-bold text-green-600 mb-1">
                        ¥{(shopStats.statistics.total_revenue || 0).toFixed(2)}
                      </div>
                      <div className="text-sm text-muted-foreground">总销售额</div>
                    </CardContent>
                  </Card>
                </div>

                <div className="mt-6">
                  <h4 className="text-md font-semibold mb-2">价格区间</h4>
                  <p className="text-sm">
                    最低价: ¥{(shopStats.statistics.min_price || 0).toFixed(2)} | 
                    最高价: ¥{(shopStats.statistics.max_price || 0).toFixed(2)}
                  </p>
                </div>

                <div className="mt-6">
                  <h4 className="text-md font-semibold mb-3">最近爬取的书籍</h4>
                  {shopStats.recent_books.length > 0 ? (
                    <div className="space-y-2">
                      {shopStats.recent_books.map((book, index) => {
                        const updateTime = book.last_sales_update 
                          ? new Date(book.last_sales_update).toLocaleString('zh-CN')
                          : '未更新'
                        const crawledStatus = book.is_crawled ? '已爬取' : '未爬取'
                        
                        return (
                          <div key={index} className="flex justify-between items-center p-2 bg-muted rounded">
                            <div className="flex-1">
                              <div className="font-medium text-sm">{book.title}</div>
                              <div className="text-xs text-muted-foreground">ISBN: {book.isbn}</div>
                            </div>
                            <div className="text-right">
                              <div className={`text-xs px-2 py-1 rounded ${
                                book.is_crawled ? 'bg-green-100 text-green-800' : 'bg-orange-100 text-orange-800'
                              }`}>
                                {crawledStatus}
                              </div>
                              <div className="text-xs text-muted-foreground mt-1">
                                更新: {updateTime}
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">暂无数据</p>
                  )}
                </div>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsShopStatsOpen(false)}>
              关闭
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}