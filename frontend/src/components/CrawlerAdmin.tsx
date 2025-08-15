import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Bug, Play, Pause, Square, RotateCcw, Settings, RefreshCw, ChevronLeft, ChevronRight, AlertTriangle, CheckCircle, Clock, Activity, Plus, Store, Tag, List, PlayCircle, Trash2 } from 'lucide-react'

interface CrawlerTask {
  task_id: string
  task_name: string
  shop_id: string
  shop_name: string
  platform: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'stopped'
  progress: number
  total_items: number
  completed_items: number
  failed_items: number
  started_at: string
  completed_at?: string
  error_message?: string
  next_run_time?: string
}

interface CrawlerConfig {
  config_id: string
  name: string
  platform: string
  enabled: boolean
  schedule_type: 'manual' | 'interval' | 'cron'
  interval_minutes?: number
  cron_expression?: string
  max_concurrent_tasks: number
  retry_count: number
  timeout_seconds: number
  last_updated: string
}

interface CrawlerStats {
  total_tasks: number
  running_tasks: number
  completed_tasks: number
  failed_tasks: number
  success_rate: number
  avg_completion_time: number
  items_crawled_today: number
  total_items_crawled: number
}

export default function CrawlerAdmin() {
  const [crawlerTasks, setCrawlerTasks] = useState<CrawlerTask[]>([])
  const [crawlerConfigs, setCrawlerConfigs] = useState<CrawlerConfig[]>([])
  const [crawlerStats, setCrawlerStats] = useState<CrawlerStats | null>(null)
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('tasks')
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [selectedStatus, setSelectedStatus] = useState<string>('all')
  const [selectedPlatform, setSelectedPlatform] = useState<string>('all')
  const [viewingTask, setViewingTask] = useState<CrawlerTask | null>(null)
  const [isViewDialogOpen, setIsViewDialogOpen] = useState(false)
  const [editingConfig, setEditingConfig] = useState<CrawlerConfig | null>(null)
  const [isConfigDialogOpen, setIsConfigDialogOpen] = useState(false)
  const [shopIds, setShopIds] = useState('')
  const [logMessages, setLogMessages] = useState<Array<{message: string, isError: boolean, timestamp: string}>>([])
  const [selectedTasks, setSelectedTasks] = useState<string[]>([])

  const pageSize = 20

  useEffect(() => {
    loadCrawlerTasks(1)
    loadCrawlerConfigs()
    loadCrawlerStats()
    
    // 添加欢迎日志
    addLog('爬虫管理页面已加载')
    
    // 设置定时刷新
    const interval = setInterval(() => {
      loadCrawlerTasks(currentPage)
      loadCrawlerStats()
    }, 5000) // 每5秒刷新一次

    return () => clearInterval(interval)
  }, [selectedStatus, selectedPlatform])

  const loadCrawlerTasks = async (page: number) => {
    setLoading(true)
    try {
      const offset = (page - 1) * pageSize
      let url = `/api/crawler/tasks?limit=${pageSize}&offset=${offset}`
      
      if (selectedStatus && selectedStatus !== 'all') {
        url += `&status=${selectedStatus}`
      }

      if (selectedPlatform && selectedPlatform !== 'all') {
        url += `&platform=${selectedPlatform}`
      }

      const response = await fetch(url)
      const data = await response.json()
      
      if (data.success) {
        setCrawlerTasks(data.data.tasks || [])
        setTotalPages(Math.ceil((data.data.total || 0) / pageSize))
        setCurrentPage(page)
      }
    } catch (error) {
      console.error('加载爬虫任务失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadCrawlerConfigs = async () => {
    try {
      const response = await fetch('/api/crawler/configs')
      const data = await response.json()
      
      if (data.success) {
        setCrawlerConfigs(data.data || [])
      }
    } catch (error) {
      console.error('加载爬虫配置失败:', error)
    }
  }

  const loadCrawlerStats = async () => {
    try {
      const response = await fetch('/api/crawler/stats')
      const data = await response.json()
      
      if (data.success) {
        setCrawlerStats(data.data)
      }
    } catch (error) {
      console.error('加载爬虫统计失败:', error)
    }
  }

  const handleStartCrawler = async (shopId?: string) => {
    try {
      const url = shopId ? `/api/crawler/start/${shopId}` : '/api/crawler/start'
      const response = await fetch(url, { method: 'POST' })
      const data = await response.json()
      
      if (data.success) {
        loadCrawlerTasks(currentPage)
        loadCrawlerStats()
      } else {
        alert(data.message || '启动失败')
      }
    } catch (error) {
      console.error('启动爬虫失败:', error)
      alert('网络错误，请稍后重试')
    }
  }

  const handleStopTask = async (taskId: string) => {
    try {
      const response = await fetch(`/api/crawler/tasks/${taskId}/stop`, { method: 'POST' })
      const data = await response.json()
      
      if (data.success) {
        loadCrawlerTasks(currentPage)
        loadCrawlerStats()
      } else {
        alert(data.message || '停止失败')
      }
    } catch (error) {
      console.error('停止任务失败:', error)
      alert('网络错误，请稍后重试')
    }
  }

  const handleRetryTask = async (taskId: string) => {
    try {
      const response = await fetch(`/api/crawler/tasks/${taskId}/retry`, { method: 'POST' })
      const data = await response.json()
      
      if (data.success) {
        loadCrawlerTasks(currentPage)
        loadCrawlerStats()
      } else {
        alert(data.message || '重试失败')
      }
    } catch (error) {
      console.error('重试任务失败:', error)
      alert('网络错误，请稍后重试')
    }
  }

  const handleToggleConfig = async (configId: string, enabled: boolean) => {
    try {
      const response = await fetch(`/api/crawler/configs/${configId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ enabled })
      })

      const data = await response.json()
      
      if (data.success) {
        loadCrawlerConfigs()
      } else {
        alert(data.message || '操作失败')
      }
    } catch (error) {
      console.error('切换配置失败:', error)
      alert('网络错误，请稍后重试')
    }
  }

  const handleViewTask = (task: CrawlerTask) => {
    setViewingTask(task)
    setIsViewDialogOpen(true)
  }

  const handleEditConfig = (config: CrawlerConfig) => {
    setEditingConfig(config)
    setIsConfigDialogOpen(true)
  }

  const addLog = (message: string, isError = false) => {
    const timestamp = new Date().toLocaleTimeString()
    setLogMessages(prev => [{ message, isError, timestamp }, ...prev.slice(0, 49)])
  }

  const addShops = async () => {
    if (!shopIds.trim()) {
      addLog('请输入店铺ID', true)
      return
    }

    const shopIdList = shopIds.split(',').map(s => s.trim()).filter(s => s)
    if (shopIdList.length === 0) {
      addLog('请输入有效的店铺ID', true)
      return
    }

    try {
      const response = await fetch('/crawler/shop/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(shopIdList)
      })
      const data = await response.json()
      
      if (data.success) {
        addLog(data.message || '店铺添加成功')
        setShopIds('')
        loadCrawlerStats()
      } else {
        addLog(data.message || '添加店铺失败', true)
      }
    } catch (error) {
      addLog('添加店铺失败: ' + (error as Error).message, true)
    }
  }

  const updateAllShops = async () => {
    try {
      addLog('正在更新所有店铺数据...')
      const response = await fetch('/crawler/update/all-shops', { method: 'POST' })
      const data = await response.json()
      
      if (data.success) {
        addLog(data.message || '店铺数据更新完成')
        loadCrawlerStats()
      } else {
        addLog(data.message || '更新失败', true)
      }
    } catch (error) {
      addLog('更新失败: ' + (error as Error).message, true)
    }
  }

  const updateDuozhuayuPrices = async () => {
    try {
      addLog('正在更新多抓鱼价格...')
      const response = await fetch('/crawler/update/duozhuayu-prices', { method: 'POST' })
      const data = await response.json()
      
      if (data.success) {
        addLog(data.message || '多抓鱼价格更新完成')
        loadCrawlerStats()
      } else {
        addLog(data.message || '更新价格失败', true)
      }
    } catch (error) {
      addLog('更新价格失败: ' + (error as Error).message, true)
    }
  }

  const runPendingTasks = async () => {
    try {
      addLog('正在执行待处理任务...')
      const response = await fetch('/crawler/tasks/run-pending', { method: 'POST' })
      const data = await response.json()
      
      if (data.success) {
        addLog(data.message || '待处理任务已启动')
        loadCrawlerTasks(currentPage)
        loadCrawlerStats()
      } else {
        addLog(data.message || '执行任务失败', true)
      }
    } catch (error) {
      addLog('执行任务失败: ' + (error as Error).message, true)
    }
  }

  const deleteSelectedTasks = async () => {
    if (selectedTasks.length === 0) {
      addLog('请选择要删除的任务', true)
      return
    }

    if (!confirm(`确定要删除选中的 ${selectedTasks.length} 个任务吗？`)) {
      return
    }

    try {
      const response = await fetch('/crawler/tasks/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_ids: selectedTasks })
      })
      const data = await response.json()
      
      if (data.success) {
        addLog(data.message || '任务删除成功')
        setSelectedTasks([])
        loadCrawlerTasks(currentPage)
        loadCrawlerStats()
      } else {
        addLog('删除任务失败: ' + (data.detail || data.message), true)
      }
    } catch (error) {
      addLog('删除任务失败: ' + (error as Error).message, true)
    }
  }

  const handleTaskSelection = (taskId: string, selected: boolean) => {
    if (selected) {
      setSelectedTasks(prev => [...prev, taskId])
    } else {
      setSelectedTasks(prev => prev.filter(id => id !== taskId))
    }
  }

  const handleSelectAll = (selected: boolean) => {
    if (selected) {
      setSelectedTasks(crawlerTasks.map(task => task.task_id))
    } else {
      setSelectedTasks([])
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return 'text-blue-600 bg-blue-100'
      case 'completed': return 'text-green-600 bg-green-100'
      case 'failed': return 'text-red-600 bg-red-100'
      case 'stopped': return 'text-orange-600 bg-orange-100'
      case 'pending': return 'text-gray-600 bg-gray-100'
      default: return 'text-gray-600 bg-gray-100'
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case 'running': return '运行中'
      case 'completed': return '已完成'
      case 'failed': return '失败'
      case 'stopped': return '已停止'
      case 'pending': return '等待中'
      default: return '未知'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running': return <Activity className="size-4" />
      case 'completed': return <CheckCircle className="size-4" />
      case 'failed': return <AlertTriangle className="size-4" />
      case 'stopped': return <Square className="size-4" />
      case 'pending': return <Clock className="size-4" />
      default: return <Clock className="size-4" />
    }
  }

  const formatDuration = (startTime: string, endTime?: string) => {
    const start = new Date(startTime).getTime()
    const end = endTime ? new Date(endTime).getTime() : Date.now()
    const duration = Math.floor((end - start) / 1000)
    
    const hours = Math.floor(duration / 3600)
    const minutes = Math.floor((duration % 3600) / 60)
    const seconds = duration % 60
    
    if (hours > 0) {
      return `${hours}h ${minutes}m ${seconds}s`
    } else if (minutes > 0) {
      return `${minutes}m ${seconds}s`
    } else {
      return `${seconds}s`
    }
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Bug className="size-8 text-primary" />
          <h1 className="text-3xl font-bold tracking-tight">爬虫管理</h1>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => { loadCrawlerTasks(currentPage); loadCrawlerStats() }}>
            <RefreshCw className="size-4 mr-2" />
            刷新
          </Button>
          <Button onClick={() => handleStartCrawler()}>
            <Play className="size-4 mr-2" />
            启动全部爬虫
          </Button>
        </div>
      </div>
        {/* Stats Cards */}
        {crawlerStats && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">总任务数</p>
                    <p className="text-2xl font-bold">{crawlerStats.total_tasks}</p>
                  </div>
                  <Bug className="size-8 text-muted-foreground" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">运行中</p>
                    <p className="text-2xl font-bold text-blue-600">{crawlerStats.running_tasks}</p>
                  </div>
                  <Activity className="size-8 text-blue-600" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">成功率</p>
                    <p className="text-2xl font-bold text-green-600">{crawlerStats.success_rate.toFixed(1)}%</p>
                  </div>
                  <CheckCircle className="size-8 text-green-600" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">今日爬取</p>
                    <p className="text-2xl font-bold text-purple-600">{crawlerStats.items_crawled_today}</p>
                  </div>
                  <div className="text-purple-600">📊</div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Filters */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex gap-4 items-center">
              <div className="flex gap-2 items-center">
                <label className="text-sm font-medium">状态:</label>
                <select
                  value={selectedStatus}
                  onChange={(e) => setSelectedStatus(e.target.value)}
                  className="flex h-9 w-32 rounded-md border border-input bg-background px-3 py-1 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <option value="all">全部</option>
                  <option value="running">运行中</option>
                  <option value="completed">已完成</option>
                  <option value="failed">失败</option>
                  <option value="stopped">已停止</option>
                  <option value="pending">等待中</option>
                </select>
              </div>
              
              <div className="flex gap-2 items-center">
                <label className="text-sm font-medium">平台:</label>
                <select
                  value={selectedPlatform}
                  onChange={(e) => setSelectedPlatform(e.target.value)}
                  className="flex h-9 w-32 rounded-md border border-input bg-background px-3 py-1 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <option value="all">全部</option>
                  <option value="kongfuzi">孔夫子</option>
                  <option value="duozhuayu">多抓鱼</option>
                </select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Shop Management Section */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Store className="size-5" />
              店铺管理
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2 items-center">
              <Input
                placeholder="输入店铺ID，多个用逗号分隔"
                value={shopIds}
                onChange={(e) => setShopIds(e.target.value)}
                className="flex-1"
              />
              <Button onClick={addShops}>
                <Plus className="size-4 mr-2" />
                添加店铺
              </Button>
            </div>
            <div className="flex gap-2 flex-wrap">
              <Button onClick={updateAllShops} variant="outline">
                <RefreshCw className="size-4 mr-2" />
                更新所有店铺数据
              </Button>
              <Button onClick={updateDuozhuayuPrices} variant="outline">
                <Tag className="size-4 mr-2" />
                更新多抓鱼价格
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Data Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="tasks">爬虫任务</TabsTrigger>
            <TabsTrigger value="configs">爬虫配置</TabsTrigger>
            <TabsTrigger value="logs">操作日志</TabsTrigger>
          </TabsList>

          <TabsContent value="tasks" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>爬虫任务列表</CardTitle>
                <CardDescription>
                  监控和管理所有爬虫任务的执行状态
                </CardDescription>
                <div className="flex gap-2 pt-4">
                  <Button onClick={runPendingTasks} size="sm">
                    <PlayCircle className="size-4 mr-2" />
                    执行待处理任务
                  </Button>
                  <Button 
                    onClick={deleteSelectedTasks} 
                    variant="destructive" 
                    size="sm"
                    disabled={selectedTasks.length === 0}
                  >
                    <Trash2 className="size-4 mr-2" />
                    删除选中任务 ({selectedTasks.length})
                  </Button>
                  <Button onClick={() => loadCrawlerTasks(currentPage)} variant="outline" size="sm">
                    <List className="size-4 mr-2" />
                    所有任务
                  </Button>
                </div>
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
                              checked={selectedTasks.length === crawlerTasks.length && crawlerTasks.length > 0}
                              onChange={(e) => handleSelectAll(e.target.checked)}
                              className="w-4 h-4"
                            />
                          </TableHead>
                          <TableHead>ID</TableHead>
                          <TableHead>任务名称</TableHead>
                          <TableHead>类型</TableHead>
                          <TableHead>状态</TableHead>
                          <TableHead>进度</TableHead>
                          <TableHead>创建时间</TableHead>
                          <TableHead>操作</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {crawlerTasks.length > 0 ? (
                          crawlerTasks.map((task, index) => (
                            <TableRow key={task.task_id}>
                              <TableCell>
                                <input 
                                  type="checkbox"
                                  checked={selectedTasks.includes(task.task_id)}
                                  onChange={(e) => handleTaskSelection(task.task_id, e.target.checked)}
                                  className="w-4 h-4"
                                />
                              </TableCell>
                              <TableCell className="font-mono text-sm">{index + 1}</TableCell>
                              <TableCell className="font-medium">{task.task_name}</TableCell>
                              <TableCell className="capitalize">
                                {task.platform === 'kongfuzi' ? '孔夫子爬虫' : task.platform}
                              </TableCell>
                              <TableCell>
                                <div className="flex items-center gap-2">
                                  {getStatusIcon(task.status)}
                                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(task.status)}`}>
                                    {getStatusText(task.status)}
                                  </span>
                                </div>
                              </TableCell>
                              <TableCell>
                                <div className="flex items-center gap-2">
                                  <div className="w-16 bg-secondary rounded-full h-2">
                                    <div 
                                      className="bg-primary h-2 rounded-full transition-all duration-300" 
                                      style={{ width: `${task.progress}%` }}
                                    ></div>
                                  </div>
                                  <span className="text-xs text-muted-foreground">{task.progress.toFixed(1)}%</span>
                                </div>
                              </TableCell>
                              <TableCell>
                                <span className="text-sm">
                                  {new Date(task.started_at).toLocaleString('zh-CN')}
                                </span>
                              </TableCell>
                              <TableCell>
                                <div className="flex gap-1">
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => handleViewTask(task)}
                                    title="查看详情"
                                  >
                                    👁️
                                  </Button>
                                  {task.status === 'running' && (
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      onClick={() => handleStopTask(task.task_id)}
                                      title="停止任务"
                                    >
                                      <Pause className="size-4" />
                                    </Button>
                                  )}
                                  {(task.status === 'failed' || task.status === 'stopped') && (
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      onClick={() => handleRetryTask(task.task_id)}
                                      title="重试任务"
                                    >
                                      <RotateCcw className="size-4" />
                                    </Button>
                                  )}
                                </div>
                              </TableCell>
                            </TableRow>
                          ))
                        ) : (
                          <TableRow>
                            <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">
                              暂无爬虫任务
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
                          onClick={() => loadCrawlerTasks(currentPage - 1)}
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
                          onClick={() => loadCrawlerTasks(currentPage + 1)}
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

          <TabsContent value="configs" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>爬虫配置</CardTitle>
                <CardDescription>
                  管理爬虫的运行配置和调度设置
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>配置名称</TableHead>
                      <TableHead>平台</TableHead>
                      <TableHead>状态</TableHead>
                      <TableHead>调度类型</TableHead>
                      <TableHead>并发数</TableHead>
                      <TableHead>重试次数</TableHead>
                      <TableHead>超时时间</TableHead>
                      <TableHead>操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {crawlerConfigs.length > 0 ? (
                      crawlerConfigs.map((config) => (
                        <TableRow key={config.config_id}>
                          <TableCell className="font-medium">{config.name}</TableCell>
                          <TableCell className="capitalize">
                            {config.platform === 'kongfuzi' ? '孔夫子' : config.platform}
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                                config.enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                              }`}>
                                {config.enabled ? '启用' : '禁用'}
                              </span>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleToggleConfig(config.config_id, !config.enabled)}
                                className="h-6 px-2 text-xs"
                              >
                                {config.enabled ? '禁用' : '启用'}
                              </Button>
                            </div>
                          </TableCell>
                          <TableCell>{config.schedule_type === 'manual' ? '手动' : config.schedule_type === 'interval' ? '间隔' : '定时'}</TableCell>
                          <TableCell>{config.max_concurrent_tasks}</TableCell>
                          <TableCell>{config.retry_count}</TableCell>
                          <TableCell>{config.timeout_seconds}s</TableCell>
                          <TableCell>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleEditConfig(config)}
                            >
                              <Settings className="size-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))
                    ) : (
                      <TableRow>
                        <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">
                          暂无爬虫配置
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="logs" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>操作日志</CardTitle>
                <CardDescription>
                  查看爬虫管理操作的实时日志信息
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="bg-muted rounded-lg p-4 h-80 overflow-y-auto font-mono text-sm space-y-2">
                  {logMessages.length > 0 ? (
                    logMessages.map((log, index) => (
                      <div 
                        key={index}
                        className={`flex items-start gap-2 p-2 rounded ${
                          log.isError 
                            ? 'bg-red-50 text-red-700 border border-red-200' 
                            : 'bg-green-50 text-green-700 border border-green-200'
                        }`}
                      >
                        <span className="text-xs opacity-60 min-w-fit">
                          [{log.timestamp}]
                        </span>
                        <span className="flex-1">{log.message}</span>
                        {log.isError ? (
                          <AlertTriangle className="size-4 text-red-500" />
                        ) : (
                          <CheckCircle className="size-4 text-green-500" />
                        )}
                      </div>
                    ))
                  ) : (
                    <div className="text-center text-muted-foreground py-8">
                      暂无日志记录
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

      {/* View Task Dialog */}
      <Dialog open={isViewDialogOpen} onOpenChange={setIsViewDialogOpen}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>任务详情</DialogTitle>
            <DialogDescription>
              查看爬虫任务的详细执行信息
            </DialogDescription>
          </DialogHeader>
          
          {viewingTask && (
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">任务ID</label>
                  <p className="text-sm font-mono">{viewingTask.task_id}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">任务名称</label>
                  <p className="text-sm font-medium">{viewingTask.task_name}</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">店铺</label>
                  <p className="text-sm">{viewingTask.shop_name}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">平台</label>
                  <p className="text-sm capitalize">
                    {viewingTask.platform === 'kongfuzi' ? '孔夫子旧书网' : viewingTask.platform}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">状态</label>
                  <div className="flex items-center gap-2">
                    {getStatusIcon(viewingTask.status)}
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(viewingTask.status)}`}>
                      {getStatusText(viewingTask.status)}
                    </span>
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">进度</label>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 bg-secondary rounded-full h-2">
                      <div 
                        className="bg-primary h-2 rounded-full" 
                        style={{ width: `${viewingTask.progress}%` }}
                      ></div>
                    </div>
                    <span className="text-xs">{viewingTask.progress.toFixed(1)}%</span>
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">运行时间</label>
                  <p className="text-sm">{formatDuration(viewingTask.started_at, viewingTask.completed_at)}</p>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">总项目数</label>
                  <p className="text-sm font-semibold">{viewingTask.total_items}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">已完成</label>
                  <p className="text-sm font-semibold text-green-600">{viewingTask.completed_items}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">失败数</label>
                  <p className="text-sm font-semibold text-red-600">{viewingTask.failed_items}</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">开始时间</label>
                  <p className="text-sm">{new Date(viewingTask.started_at).toLocaleString('zh-CN')}</p>
                </div>
                {viewingTask.completed_at && (
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">完成时间</label>
                    <p className="text-sm">{new Date(viewingTask.completed_at).toLocaleString('zh-CN')}</p>
                  </div>
                )}
              </div>

              {viewingTask.error_message && (
                <div>
                  <label className="text-sm font-medium text-muted-foreground">错误信息</label>
                  <div className="bg-red-50 border border-red-200 text-red-800 px-3 py-2 rounded-md text-sm">
                    {viewingTask.error_message}
                  </div>
                </div>
              )}

              {viewingTask.next_run_time && (
                <div>
                  <label className="text-sm font-medium text-muted-foreground">下次运行时间</label>
                  <p className="text-sm">{new Date(viewingTask.next_run_time).toLocaleString('zh-CN')}</p>
                </div>
              )}
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsViewDialogOpen(false)}>
              关闭
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}