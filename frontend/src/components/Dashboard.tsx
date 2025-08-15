import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Search, Calendar, BarChart, RefreshCw, ChevronLeft, ChevronRight } from 'lucide-react'

interface DashboardData {
  today_stats: {
    total_sales: number
  }
  business_opportunity_stats: {
    total_books_monitored: number
    avg_market_price: number
    max_price: number
    min_price: number
    price_range: string
    profitable_opportunities: number
    profit_discovery_rate: number
    monitored_shops: number
    avg_profit_margin: number
  }
}

interface SalesItem {
  title: string
  isbn: string
  sales_count: number
  avg_price: number
  total_revenue: number
}

interface ProfitableItem {
  title: string
  isbn: string
  kongfuzi_price: number
  duozhuayu_price: number
  price_diff: number
  profit_rate: number
}

interface ISBNAnalysisData {
  isbn: string
  stats: {
    sales_1_day: number
    sales_7_days: number
    sales_30_days: number
    total_records: number
    average_price: number
    price_range: {
      min: number
      max: number
    }
    latest_sale_date: string
  }
}

export default function Dashboard() {
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null)
  const [salesData, setSalesData] = useState<SalesItem[]>([])
  const [profitableData, setProfitableData] = useState<ProfitableItem[]>([])
  const [currentDays, setCurrentDays] = useState(3)
  const [activeTab, setActiveTab] = useState('salesRank')
  const [currentSalesPage, setCurrentSalesPage] = useState(1)
  const [currentDiffPage, setCurrentDiffPage] = useState(1)
  const [currentProfitPage, setCurrentProfitPage] = useState(1)
  const [isbnInput, setIsbnInput] = useState('')
  const [isbnResults, setIsbnResults] = useState<ISBNAnalysisData | null>(null)
  const [isbnLoading, setIsbnLoading] = useState(false)
  const [isbnError, setIsbnError] = useState('')
  const [searchInput, setSearchInput] = useState('')
  
  const pageSize = 20

  useEffect(() => {
    loadDashboardData()
    loadSalesRank(1)
  }, [])

  const loadDashboardData = async () => {
    try {
      const response = await fetch('/api/dashboard')
      const data = await response.json()
      if (data.success) {
        setDashboardData(data.data)
      }
    } catch (error) {
      console.error('加载数据失败:', error)
    }
  }

  const loadSalesRank = async (page: number) => {
    try {
      const offset = (page - 1) * pageSize
      const days = currentDays === 0 ? 9999 : currentDays
      const response = await fetch(`/api/sales/hot?days=${days}&limit=${pageSize}&offset=${offset}`)
      const data = await response.json()
      
      if (data.success) {
        setSalesData(data.data)
        setCurrentSalesPage(page)
      }
    } catch (error) {
      console.error('加载销量排行失败:', error)
    }
  }

  const loadPriceDiffRank = async (page: number) => {
    try {
      const offset = (page - 1) * pageSize
      const response = await fetch(`/api/profitable/items?min_margin=0&limit=${pageSize}&offset=${offset}`)
      const data = await response.json()
      
      if (data.success) {
        setProfitableData(data.data)
        setCurrentDiffPage(page)
      }
    } catch (error) {
      console.error('加载差价排行失败:', error)
    }
  }

  const analyzeBookISBN = async () => {
    if (!isbnInput.trim()) {
      setIsbnError('请输入ISBN号码')
      return
    }

    if (isbnInput.length < 10) {
      setIsbnError('请输入有效的ISBN号码')
      return
    }

    setIsbnLoading(true)
    setIsbnError('')
    setIsbnResults(null)

    try {
      const response = await fetch(`/api/book/analyze?isbn=${encodeURIComponent(isbnInput)}`, {
        method: 'POST'
      })
      const data = await response.json()

      if (data.success) {
        setIsbnResults(data)
      } else {
        setIsbnError(data.message || '分析失败，请稍后重试')
      }
    } catch (error) {
      console.error('分析失败:', error)
      setIsbnError('网络错误，请检查连接后重试')
    } finally {
      setIsbnLoading(false)
    }
  }

  const handleTabChange = (value: string) => {
    setActiveTab(value)
    switch(value) {
      case 'salesRank':
        setCurrentSalesPage(1)
        loadSalesRank(1)
        break
      case 'priceDiffRank':
        setCurrentDiffPage(1)
        loadPriceDiffRank(1)
        break
      case 'profitRank':
        setCurrentProfitPage(1)
        loadSalesRank(1) // Using sales data for now
        break
    }
  }

  const handleDaysFilter = (days: number) => {
    setCurrentDays(days)
    loadDashboardData()
    if (activeTab === 'salesRank') {
      loadSalesRank(1)
    }
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight">数据分析仪表板</h1>
        <Button variant="ghost" size="sm" onClick={loadDashboardData}>
          <RefreshCw className="size-4 mr-2" />
          刷新
        </Button>
      </div>
        {/* ISBN Search Section */}
        <Card>
          <CardHeader className="text-center">
            <CardTitle>ISBN实时搜索分析</CardTitle>
            <CardDescription>输入ISBN号码，实时分析书籍销售数据</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2 max-w-2xl mx-auto">
              <Input
                placeholder="请输入书籍ISBN号码，例如：9787521724493"
                value={isbnInput}
                onChange={(e) => setIsbnInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && analyzeBookISBN()}
              />
              <Button onClick={analyzeBookISBN} disabled={isbnLoading}>
                <Search className="size-4 mr-2" />
                分析
              </Button>
            </div>

            {isbnLoading && (
              <div className="text-center py-4">
                <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
                <p className="mt-2 text-muted-foreground">正在分析数据，请稍候...</p>
              </div>
            )}

            {isbnError && (
              <div className="bg-destructive/10 border border-destructive/20 text-destructive px-4 py-3 rounded-md">
                {isbnError}
              </div>
            )}

            {isbnResults && (
              <div className="space-y-4">
                <div className="bg-blue-50 border border-blue-200 text-blue-800 px-4 py-3 rounded-md font-medium">
                  ISBN: {isbnResults.isbn}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  <Card>
                    <CardContent className="p-4 text-center">
                      <div className="flex items-center justify-center mb-2">
                        <Calendar className="size-4 mr-2 text-muted-foreground" />
                        <span className="text-sm text-muted-foreground">1天内销量</span>
                      </div>
                      <div className="text-2xl font-bold text-primary">
                        {isbnResults.stats.sales_1_day || 0}
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardContent className="p-4 text-center">
                      <div className="flex items-center justify-center mb-2">
                        <Calendar className="size-4 mr-2 text-muted-foreground" />
                        <span className="text-sm text-muted-foreground">7天内销量</span>
                      </div>
                      <div className="text-2xl font-bold text-primary">
                        {isbnResults.stats.sales_7_days || 0}
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardContent className="p-4 text-center">
                      <div className="flex items-center justify-center mb-2">
                        <Calendar className="size-4 mr-2 text-muted-foreground" />
                        <span className="text-sm text-muted-foreground">30天内销量</span>
                      </div>
                      <div className="text-2xl font-bold text-primary">
                        {isbnResults.stats.sales_30_days || 0}
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardContent className="p-4 text-center">
                      <div className="flex items-center justify-center mb-2">
                        <BarChart className="size-4 mr-2 text-muted-foreground" />
                        <span className="text-sm text-muted-foreground">总记录数</span>
                      </div>
                      <div className="text-2xl font-bold text-primary">
                        {isbnResults.stats.total_records || 0}
                      </div>
                    </CardContent>
                  </Card>
                </div>

                <Card>
                  <CardHeader>
                    <CardTitle>💰 价格统计</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div className="text-center p-3 bg-secondary rounded-lg">
                        <div className="text-sm text-muted-foreground mb-1">平均价格</div>
                        <div className="text-lg font-semibold text-green-600">
                          ¥{isbnResults.stats.average_price || 0}
                        </div>
                      </div>
                      <div className="text-center p-3 bg-secondary rounded-lg">
                        <div className="text-sm text-muted-foreground mb-1">最低价格</div>
                        <div className="text-lg font-semibold text-green-600">
                          ¥{isbnResults.stats.price_range?.min || 0}
                        </div>
                      </div>
                      <div className="text-center p-3 bg-secondary rounded-lg">
                        <div className="text-sm text-muted-foreground mb-1">最高价格</div>
                        <div className="text-lg font-semibold text-green-600">
                          ¥{isbnResults.stats.price_range?.max || 0}
                        </div>
                      </div>
                      <div className="text-center p-3 bg-secondary rounded-lg">
                        <div className="text-sm text-muted-foreground mb-1">最新销售</div>
                        <div className="text-lg font-semibold text-green-600">
                          {isbnResults.stats.latest_sale_date ? 
                            new Date(isbnResults.stats.latest_sale_date).toLocaleDateString('zh-CN') : 
                            '-'
                          }
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Time Filters */}
        <div className="flex justify-center gap-2">
          {[3, 7, 30, 0].map((days) => (
            <Button
              key={days}
              variant={currentDays === days ? "default" : "outline"}
              size="sm"
              onClick={() => handleDaysFilter(days)}
            >
              {days === 0 ? '全部' : `${days}天`}
            </Button>
          ))}
        </div>

        {/* Data Tabs */}
        <Tabs value={activeTab} onValueChange={handleTabChange}>
          <TabsList>
            <TabsTrigger value="salesRank">📊 销量排行</TabsTrigger>
            <TabsTrigger value="priceDiffRank">💰 差价排行</TabsTrigger>
            <TabsTrigger value="profitRank">🎯 预期利润</TabsTrigger>
          </TabsList>

          <TabsContent value="salesRank" className="space-y-4">
            <Card>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>排名</TableHead>
                    <TableHead>书名</TableHead>
                    <TableHead>ISBN</TableHead>
                    <TableHead>销量</TableHead>
                    <TableHead>平均价格</TableHead>
                    <TableHead>总成本</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {salesData.length > 0 ? (
                    salesData.map((item, index) => (
                      <TableRow key={item.isbn}>
                        <TableCell>
                          <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-primary text-primary-foreground text-sm font-semibold">
                            {(currentSalesPage - 1) * pageSize + index + 1}
                          </span>
                        </TableCell>
                        <TableCell>{item.title || '-'}</TableCell>
                        <TableCell>{item.isbn || '-'}</TableCell>
                        <TableCell>{item.sales_count}</TableCell>
                        <TableCell className="font-semibold text-green-600">¥{item.avg_price || 0}</TableCell>
                        <TableCell className="font-semibold text-green-600">¥{item.total_revenue || 0}</TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center">暂无数据</TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
              
              <div className="flex justify-center items-center gap-2 p-4">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => loadSalesRank(currentSalesPage - 1)}
                  disabled={currentSalesPage === 1}
                >
                  <ChevronLeft className="size-4" />
                </Button>
                <span className="text-muted-foreground">第 {currentSalesPage} 页</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => loadSalesRank(currentSalesPage + 1)}
                  disabled={salesData.length < pageSize}
                >
                  <ChevronRight className="size-4" />
                </Button>
              </div>
            </Card>
          </TabsContent>

          <TabsContent value="priceDiffRank" className="space-y-4">
            <Card>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>排名</TableHead>
                    <TableHead>书名</TableHead>
                    <TableHead>ISBN</TableHead>
                    <TableHead>孔夫子价格</TableHead>
                    <TableHead>多抓鱼价格</TableHead>
                    <TableHead>差价</TableHead>
                    <TableHead>利润率</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {profitableData.length > 0 ? (
                    profitableData.map((item, index) => (
                      <TableRow key={item.isbn}>
                        <TableCell>
                          <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-primary text-primary-foreground text-sm font-semibold">
                            {(currentDiffPage - 1) * pageSize + index + 1}
                          </span>
                        </TableCell>
                        <TableCell>{item.title || '-'}</TableCell>
                        <TableCell>{item.isbn || '-'}</TableCell>
                        <TableCell className="font-semibold text-green-600">¥{item.kongfuzi_price || 0}</TableCell>
                        <TableCell className="font-semibold text-green-600">¥{item.duozhuayu_price || 0}</TableCell>
                        <TableCell className="font-semibold text-red-600">¥{item.price_diff || 0}</TableCell>
                        <TableCell className="font-semibold text-red-600">{item.profit_rate || 0}%</TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center">暂无数据</TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
              
              <div className="flex justify-center items-center gap-2 p-4">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => loadPriceDiffRank(currentDiffPage - 1)}
                  disabled={currentDiffPage === 1}
                >
                  <ChevronLeft className="size-4" />
                </Button>
                <span className="text-muted-foreground">第 {currentDiffPage} 页</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => loadPriceDiffRank(currentDiffPage + 1)}
                  disabled={profitableData.length < pageSize}
                >
                  <ChevronRight className="size-4" />
                </Button>
              </div>
            </Card>
          </TabsContent>

          <TabsContent value="profitRank" className="space-y-4">
            <Card>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>排名</TableHead>
                    <TableHead>书名</TableHead>
                    <TableHead>ISBN</TableHead>
                    <TableHead>销量</TableHead>
                    <TableHead>差价</TableHead>
                    <TableHead>预期利润</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {salesData.length > 0 ? (
                    salesData.map((item, index) => {
                      const priceDiff = Math.random() * 50 + 10
                      const expectedProfit = item.sales_count * priceDiff
                      return (
                        <TableRow key={item.isbn}>
                          <TableCell>
                            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-primary text-primary-foreground text-sm font-semibold">
                              {(currentProfitPage - 1) * pageSize + index + 1}
                            </span>
                          </TableCell>
                          <TableCell>{item.title || '-'}</TableCell>
                          <TableCell>{item.isbn || '-'}</TableCell>
                          <TableCell>{item.sales_count}</TableCell>
                          <TableCell className="font-semibold text-red-600">¥{priceDiff.toFixed(2)}</TableCell>
                          <TableCell className="font-semibold text-red-600">¥{expectedProfit.toFixed(2)}</TableCell>
                        </TableRow>
                      )
                    })
                  ) : (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center">暂无数据</TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
              
              <div className="flex justify-center items-center gap-2 p-4">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => loadSalesRank(currentProfitPage - 1)}
                  disabled={currentProfitPage === 1}
                >
                  <ChevronLeft className="size-4" />
                </Button>
                <span className="text-muted-foreground">第 {currentProfitPage} 页</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => loadSalesRank(currentProfitPage + 1)}
                  disabled={salesData.length < pageSize}
                >
                  <ChevronRight className="size-4" />
                </Button>
              </div>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Search and Stats Section */}
        <div className="space-y-6">
          <Card>
            <CardHeader className="text-center">
              <CardTitle>本地库书籍查询</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-2 max-w-lg mx-auto">
                <Input
                  placeholder="搜索书籍名称..."
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                />
                <Button>
                  <Search className="size-4 mr-2" />
                  搜索
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Dashboard Stats */}
          {dashboardData && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <BarChart className="size-5" />
                    销量统计
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold text-primary mb-2">
                    {dashboardData.business_opportunity_stats.total_books_monitored || dashboardData.today_stats.total_sales || 0}
                  </div>
                  <div className="text-sm text-muted-foreground mb-4">总销售记录</div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="text-center p-2 bg-secondary rounded">
                      <div className="text-sm">今日</div>
                      <div className="font-bold">{dashboardData.today_stats.total_sales || 0}</div>
                    </div>
                    <div className="text-center p-2 bg-secondary rounded">
                      <div className="text-sm">增长率</div>
                      <div className="font-bold text-green-600">0%</div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    💰 价格分析
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold text-primary mb-2">
                    ¥{dashboardData.business_opportunity_stats.avg_market_price || 0}
                  </div>
                  <div className="text-sm text-muted-foreground mb-4">平均售价</div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="text-center p-2 bg-secondary rounded">
                      <div className="text-sm">最高价</div>
                      <div className="font-bold">¥{dashboardData.business_opportunity_stats.max_price || 0}</div>
                    </div>
                    <div className="text-center p-2 bg-secondary rounded">
                      <div className="text-sm">最低价</div>
                      <div className="font-bold">¥{dashboardData.business_opportunity_stats.min_price || 0}</div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    🎯 商机分析
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold text-primary mb-2">
                    {dashboardData.business_opportunity_stats.total_books_monitored || 0}
                  </div>
                  <div className="text-sm text-muted-foreground mb-4">监控书籍数</div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="text-center p-2 bg-secondary rounded">
                      <div className="text-sm">盈利机会</div>
                      <div className="font-bold text-green-600">{dashboardData.business_opportunity_stats.profitable_opportunities || 0}</div>
                    </div>
                    <div className="text-center p-2 bg-secondary rounded">
                      <div className="text-sm">平均收益率</div>
                      <div className="font-bold">{dashboardData.business_opportunity_stats.avg_profit_margin || 0}%</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
    </div>
  )
}