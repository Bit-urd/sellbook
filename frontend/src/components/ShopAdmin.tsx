import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Store, Plus, Edit, Trash2, Search, RefreshCw, ChevronLeft, ChevronRight, Download, Upload, Rocket, RotateCcw, AlertCircle, CheckCircle2 } from 'lucide-react'

interface Shop {
  shop_id: string
  shop_name: string
  platform: string
  shop_type: string
  status: string
  last_crawled: string
  total_books: number
  success_rate: number
  crawl_status: 'completed' | 'partial' | 'not_started' | 'running'
  created_at: string
  updated_at: string
}

interface ShopForm {
  shop_name: string
  platform: string
  shop_type: string
  shop_url: string
}

export default function ShopAdmin() {
  const [shops, setShops] = useState<Shop[]>([])
  const [loading, setLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [editingShop, setEditingShop] = useState<Shop | null>(null)
  const [formData, setFormData] = useState<ShopForm>({
    shop_name: '',
    platform: 'kongfuzi',
    shop_type: 'individual',
    shop_url: ''
  })
  const [selectedShops, setSelectedShops] = useState<Set<string>>(new Set())
  const [alertMessage, setAlertMessage] = useState<{type: 'success' | 'error' | 'info', message: string} | null>(null)

  const pageSize = 20

  useEffect(() => {
    loadShops(1)
  }, [searchQuery])

  const loadShops = async (page: number) => {
    setLoading(true)
    try {
      const offset = (page - 1) * pageSize
      let url = `/api/shops?limit=${pageSize}&offset=${offset}`
      
      if (searchQuery.trim()) {
        url += `&search=${encodeURIComponent(searchQuery.trim())}`
      }

      const response = await fetch(url)
      const data = await response.json()
      
      if (data.success) {
        setShops(data.data.shops || [])
        setTotalPages(Math.ceil((data.data.total || 0) / pageSize))
        setCurrentPage(page)
      }
    } catch (error) {
      console.error('加载店铺失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleAddShop = () => {
    setEditingShop(null)
    setFormData({
      shop_name: '',
      platform: 'kongfuzi',
      shop_type: 'individual',
      shop_url: ''
    })
    setIsDialogOpen(true)
  }

  const handleEditShop = (shop: Shop) => {
    setEditingShop(shop)
    setFormData({
      shop_name: shop.shop_name,
      platform: shop.platform,
      shop_type: shop.shop_type,
      shop_url: ''
    })
    setIsDialogOpen(true)
  }

  const handleSubmitShop = async () => {
    try {
      const method = editingShop ? 'PUT' : 'POST'
      const url = editingShop ? `/api/shops/${editingShop.shop_id}` : '/api/shops'
      
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
      })

      const data = await response.json()
      
      if (data.success) {
        setIsDialogOpen(false)
        loadShops(currentPage)
      } else {
        alert(data.message || '操作失败')
      }
    } catch (error) {
      console.error('提交店铺失败:', error)
      alert('网络错误，请稍后重试')
    }
  }

  const handleDeleteShop = async (shopId: string) => {
    if (!confirm('确定要删除这个店铺吗？此操作不可恢复。')) {
      return
    }

    try {
      const response = await fetch(`/api/shops/${shopId}`, {
        method: 'DELETE'
      })

      const data = await response.json()
      
      if (data.success) {
        loadShops(currentPage)
      } else {
        alert(data.message || '删除失败')
      }
    } catch (error) {
      console.error('删除店铺失败:', error)
      alert('网络错误，请稍后重试')
    }
  }

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'active': return 'text-green-600 bg-green-100'
      case 'inactive': return 'text-red-600 bg-red-100'
      case 'crawling': return 'text-blue-600 bg-blue-100'
      default: return 'text-gray-600 bg-gray-100'
    }
  }

  const getStatusText = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'active': return '正常'
      case 'inactive': return '停用'
      case 'crawling': return '爬取中'
      default: return '未知'
    }
  }

  const getCrawlStatusText = (status: string) => {
    switch (status) {
      case 'completed': return '已完成'
      case 'partial': return '部分爬取'
      case 'not_started': return '未开始'
      case 'running': return '进行中'
      default: return '未知'
    }
  }

  const getCrawlStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'text-green-600 bg-green-100'
      case 'partial': return 'text-yellow-600 bg-yellow-100'
      case 'not_started': return 'text-gray-600 bg-gray-100'
      case 'running': return 'text-blue-600 bg-blue-100'
      default: return 'text-gray-600 bg-gray-100'
    }
  }

  const showAlert = (type: 'success' | 'error' | 'info', message: string) => {
    setAlertMessage({ type, message })
    setTimeout(() => setAlertMessage(null), 5000)
  }

  const crawlShop = async (shopId: string, incremental: boolean) => {
    const mode = incremental ? '增量' : '全量'
    showAlert('info', `正在${mode}爬取店铺 ${shopId}，请稍候...`)
    
    try {
      const response = await fetch(`/api/shops/${shopId}/crawl?incremental=${incremental}`, {
        method: 'POST'
      })
      const data = await response.json()
      
      if (data.success) {
        showAlert('success', data.message || `${mode}爬取已开始`)
        loadShops(currentPage)
      } else {
        showAlert('error', data.message || '爬取失败')
      }
    } catch (error) {
      showAlert('error', '爬取失败: ' + (error as Error).message)
    }
  }

  const batchCrawlShops = async (incremental: boolean) => {
    if (selectedShops.size === 0) {
      showAlert('error', '请先选择要爬取的店铺')
      return
    }

    const mode = incremental ? '增量' : '全量'
    if (!confirm(`确定要对选中的 ${selectedShops.size} 个店铺进行${mode}爬取吗？`)) {
      return
    }

    showAlert('info', `正在对 ${selectedShops.size} 个店铺进行${mode}爬取，请稍候...`)

    try {
      const response = await fetch(`/api/shops/batch-crawl?incremental=${incremental}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(Array.from(selectedShops))
      })
      const data = await response.json()

      if (data.success) {
        showAlert('success', data.message || `批量${mode}爬取已开始`)
        setSelectedShops(new Set())
        loadShops(currentPage)
      } else {
        showAlert('error', data.message || '批量爬取失败')
      }
    } catch (error) {
      showAlert('error', '批量爬取失败: ' + (error as Error).message)
    }
  }

  const toggleShopSelection = (shopId: string) => {
    const newSelected = new Set(selectedShops)
    if (newSelected.has(shopId)) {
      newSelected.delete(shopId)
    } else {
      newSelected.add(shopId)
    }
    setSelectedShops(newSelected)
  }

  const toggleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedShops(new Set(shops.map(shop => shop.shop_id)))
    } else {
      setSelectedShops(new Set())
    }
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Store className="size-8 text-primary" />
          <h1 className="text-3xl font-bold tracking-tight">店铺管理</h1>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => loadShops(currentPage)}>
            <RefreshCw className="size-4 mr-2" />
            刷新
          </Button>
          <Button onClick={handleAddShop}>
            <Plus className="size-4 mr-2" />
            添加店铺
          </Button>
        </div>
      </div>

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
                  {alertMessage.type === 'success' ? <CheckCircle2 className="size-5" /> : 
                   alertMessage.type === 'error' ? <AlertCircle className="size-5" /> : 
                   <AlertCircle className="size-5" />}
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

        {/* Batch Operations */}
        {selectedShops.size > 0 && (
          <Card className="border-orange-200 bg-orange-50">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <span className="text-orange-800 font-medium">
                  已选择 {selectedShops.size} 个店铺
                </span>
                <div className="flex gap-2">
                  <Button onClick={() => batchCrawlShops(true)} variant="outline" size="sm">
                    <Download className="size-4 mr-2" />
                    批量增量爬取
                  </Button>
                  <Button onClick={() => batchCrawlShops(false)} variant="outline" size="sm">
                    <Rocket className="size-4 mr-2" />
                    批量全量爬取
                  </Button>
                  <Button onClick={() => setSelectedShops(new Set())} variant="ghost" size="sm">
                    取消选择
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Search */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex gap-2 max-w-md">
              <Input
                placeholder="搜索店铺名称..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && loadShops(1)}
              />
              <Button onClick={() => loadShops(1)}>
                <Search className="size-4" />
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Shop Table */}
        <Card>
          <CardHeader>
            <CardTitle>店铺列表</CardTitle>
            <CardDescription>
              管理书籍销售店铺信息和爬虫配置
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
                      <TableHead className="w-12">
                        <input 
                          type="checkbox"
                          checked={selectedShops.size === shops.length && shops.length > 0}
                          onChange={(e) => toggleSelectAll(e.target.checked)}
                          className="w-4 h-4"
                        />
                      </TableHead>
                      <TableHead>店铺ID</TableHead>
                      <TableHead>店铺名称</TableHead>
                      <TableHead>平台</TableHead>
                      <TableHead>类型</TableHead>
                      <TableHead>状态</TableHead>
                      <TableHead>爬取状态</TableHead>
                      <TableHead>书籍数量</TableHead>
                      <TableHead>成功率</TableHead>
                      <TableHead>最后爬取</TableHead>
                      <TableHead>操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {shops.length > 0 ? (
                      shops.map((shop) => (
                        <TableRow key={shop.shop_id}>
                          <TableCell>
                            <input 
                              type="checkbox"
                              checked={selectedShops.has(shop.shop_id)}
                              onChange={(e) => toggleShopSelection(shop.shop_id)}
                              className="w-4 h-4"
                            />
                          </TableCell>
                          <TableCell className="font-mono text-sm">{shop.shop_id}</TableCell>
                          <TableCell className="font-medium">{shop.shop_name}</TableCell>
                          <TableCell>{shop.platform === 'kongfuzi' ? '孔夫子旧书网' : shop.platform}</TableCell>
                          <TableCell>{shop.shop_type === 'individual' ? '个人店铺' : '企业店铺'}</TableCell>
                          <TableCell>
                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(shop.status)}`}>
                              {getStatusText(shop.status)}
                            </span>
                          </TableCell>
                          <TableCell>
                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getCrawlStatusColor(shop.crawl_status || 'not_started')}`}>
                              {getCrawlStatusText(shop.crawl_status || 'not_started')}
                            </span>
                          </TableCell>
                          <TableCell>{shop.total_books || 0}</TableCell>
                          <TableCell>{(shop.success_rate || 0).toFixed(1)}%</TableCell>
                          <TableCell className="text-sm">
                            {shop.last_crawled ? new Date(shop.last_crawled).toLocaleString('zh-CN') : '从未爬取'}
                          </TableCell>
                          <TableCell>
                            <div className="flex gap-1">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => crawlShop(shop.shop_id, true)}
                                className="text-blue-600 hover:text-blue-700"
                                title="增量爬取"
                              >
                                <Download className="size-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => crawlShop(shop.shop_id, false)}
                                className="text-orange-600 hover:text-orange-700"
                                title="全量爬取"
                              >
                                <Rocket className="size-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleEditShop(shop)}
                                title="编辑"
                              >
                                <Edit className="size-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleDeleteShop(shop.shop_id)}
                                className="text-red-600 hover:text-red-700"
                                title="删除"
                              >
                                <Trash2 className="size-4" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))
                    ) : (
                      <TableRow>
                        <TableCell colSpan={11} className="text-center py-8 text-muted-foreground">
                          {searchQuery ? '没有找到匹配的店铺' : '暂无店铺数据'}
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
                      onClick={() => loadShops(currentPage - 1)}
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
                      onClick={() => loadShops(currentPage + 1)}
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

      {/* Add/Edit Shop Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>
              {editingShop ? '编辑店铺' : '添加店铺'}
            </DialogTitle>
            <DialogDescription>
              {editingShop ? '修改店铺信息' : '添加新的店铺到系统中'}
            </DialogDescription>
          </DialogHeader>
          
          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <label htmlFor="shop_name" className="text-sm font-medium">
                店铺名称 <span className="text-red-500">*</span>
              </label>
              <Input
                id="shop_name"
                value={formData.shop_name}
                onChange={(e) => setFormData({...formData, shop_name: e.target.value})}
                placeholder="请输入店铺名称"
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="platform" className="text-sm font-medium">
                平台 <span className="text-red-500">*</span>
              </label>
              <select
                id="platform"
                value={formData.platform}
                onChange={(e) => setFormData({...formData, platform: e.target.value})}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <option value="kongfuzi">孔夫子旧书网</option>
                <option value="duozhuayu">多抓鱼</option>
                <option value="other">其他</option>
              </select>
            </div>

            <div className="space-y-2">
              <label htmlFor="shop_type" className="text-sm font-medium">
                店铺类型
              </label>
              <select
                id="shop_type"
                value={formData.shop_type}
                onChange={(e) => setFormData({...formData, shop_type: e.target.value})}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <option value="individual">个人店铺</option>
                <option value="enterprise">企业店铺</option>
              </select>
            </div>

            <div className="space-y-2">
              <label htmlFor="shop_url" className="text-sm font-medium">
                店铺链接
              </label>
              <Input
                id="shop_url"
                value={formData.shop_url}
                onChange={(e) => setFormData({...formData, shop_url: e.target.value})}
                placeholder="请输入店铺URL（可选）"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDialogOpen(false)}>
              取消
            </Button>
            <Button onClick={handleSubmitShop}>
              {editingShop ? '保存' : '添加'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}