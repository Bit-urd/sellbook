import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Book, Plus, Edit, Trash2, Search, RefreshCw, ChevronLeft, ChevronRight, Eye, BookOpen } from 'lucide-react'

interface Book {
  isbn: string
  title: string
  author: string
  publisher: string
  publish_date: string
  category: string
  is_crawled: boolean
  last_crawled: string
  total_sales: number
  avg_price: number
  market_price: number
  profit_margin: number
}

interface BookForm {
  isbn: string
  title: string
  author: string
  publisher: string
  publish_date: string
  category: string
  market_price: number
}

interface BookStats {
  total_books: number
  crawled_books: number
  uncrawled_books: number
  avg_profit_margin: number
  total_market_value: number
  categories: Array<{
    category: string
    count: number
  }>
}

export default function BookAdmin() {
  const [books, setBooks] = useState<Book[]>([])
  const [bookStats, setBookStats] = useState<BookStats | null>(null)
  const [loading, setLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [activeTab, setActiveTab] = useState('all')
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [editingBook, setEditingBook] = useState<Book | null>(null)
  const [viewingBook, setViewingBook] = useState<Book | null>(null)
  const [isViewDialogOpen, setIsViewDialogOpen] = useState(false)
  const [formData, setFormData] = useState<BookForm>({
    isbn: '',
    title: '',
    author: '',
    publisher: '',
    publish_date: '',
    category: '',
    market_price: 0
  })

  const pageSize = 20

  useEffect(() => {
    loadBooks(1)
    loadBookStats()
  }, [searchQuery, activeTab])

  const loadBooks = async (page: number) => {
    setLoading(true)
    try {
      const offset = (page - 1) * pageSize
      let url = `/api/books?limit=${pageSize}&offset=${offset}`
      
      if (searchQuery.trim()) {
        url += `&search=${encodeURIComponent(searchQuery.trim())}`
      }

      if (activeTab === 'crawled') {
        url += `&is_crawled=true`
      } else if (activeTab === 'uncrawled') {
        url += `&is_crawled=false`
      }

      const response = await fetch(url)
      const data = await response.json()
      
      if (data.success) {
        setBooks(data.data.books || [])
        setTotalPages(Math.ceil((data.data.total || 0) / pageSize))
        setCurrentPage(page)
      }
    } catch (error) {
      console.error('加载书籍失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadBookStats = async () => {
    try {
      const response = await fetch('/api/books/stats')
      const data = await response.json()
      
      if (data.success) {
        setBookStats(data.data)
      }
    } catch (error) {
      console.error('加载书籍统计失败:', error)
    }
  }

  const handleAddBook = () => {
    setEditingBook(null)
    setFormData({
      isbn: '',
      title: '',
      author: '',
      publisher: '',
      publish_date: '',
      category: '',
      market_price: 0
    })
    setIsDialogOpen(true)
  }

  const handleEditBook = (book: Book) => {
    setEditingBook(book)
    setFormData({
      isbn: book.isbn,
      title: book.title,
      author: book.author,
      publisher: book.publisher,
      publish_date: book.publish_date,
      category: book.category,
      market_price: book.market_price
    })
    setIsDialogOpen(true)
  }

  const handleViewBook = (book: Book) => {
    setViewingBook(book)
    setIsViewDialogOpen(true)
  }

  const handleSubmitBook = async () => {
    try {
      const method = editingBook ? 'PUT' : 'POST'
      const url = editingBook ? `/api/books/${editingBook.isbn}` : '/api/books'
      
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
        loadBooks(currentPage)
        loadBookStats()
      } else {
        alert(data.message || '操作失败')
      }
    } catch (error) {
      console.error('提交书籍失败:', error)
      alert('网络错误，请稍后重试')
    }
  }

  const handleDeleteBook = async (isbn: string) => {
    if (!confirm('确定要删除这本书吗？此操作不可恢复。')) {
      return
    }

    try {
      const response = await fetch(`/api/books/${isbn}`, {
        method: 'DELETE'
      })

      const data = await response.json()
      
      if (data.success) {
        loadBooks(currentPage)
        loadBookStats()
      } else {
        alert(data.message || '删除失败')
      }
    } catch (error) {
      console.error('删除书籍失败:', error)
      alert('网络错误，请稍后重试')
    }
  }

  const handleToggleCrawl = async (isbn: string, shouldCrawl: boolean) => {
    try {
      const response = await fetch(`/api/books/${isbn}/crawl`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ is_crawled: shouldCrawl })
      })

      const data = await response.json()
      
      if (data.success) {
        loadBooks(currentPage)
        loadBookStats()
      } else {
        alert(data.message || '操作失败')
      }
    } catch (error) {
      console.error('更新爬取状态失败:', error)
      alert('网络错误，请稍后重试')
    }
  }

  const getTabCount = (tab: string) => {
    if (!bookStats) return 0
    switch (tab) {
      case 'all': return bookStats.total_books
      case 'crawled': return bookStats.crawled_books
      case 'uncrawled': return bookStats.uncrawled_books
      default: return 0
    }
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Book className="size-8 text-primary" />
          <h1 className="text-3xl font-bold tracking-tight">书籍管理</h1>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => { loadBooks(currentPage); loadBookStats() }}>
            <RefreshCw className="size-4 mr-2" />
            刷新
          </Button>
          <Button onClick={handleAddBook}>
            <Plus className="size-4 mr-2" />
            添加书籍
          </Button>
        </div>
      </div>
        {/* Stats Cards */}
        {bookStats && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">总书籍数</p>
                    <p className="text-2xl font-bold">{bookStats.total_books}</p>
                  </div>
                  <BookOpen className="size-8 text-muted-foreground" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">已爬取</p>
                    <p className="text-2xl font-bold text-green-600">{bookStats.crawled_books}</p>
                  </div>
                  <div className="text-green-600">✓</div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">未爬取</p>
                    <p className="text-2xl font-bold text-orange-600">{bookStats.uncrawled_books}</p>
                  </div>
                  <div className="text-orange-600">⏳</div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">平均利润率</p>
                    <p className="text-2xl font-bold text-blue-600">{bookStats.avg_profit_margin.toFixed(1)}%</p>
                  </div>
                  <div className="text-blue-600">📈</div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Search */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex gap-2 max-w-md">
              <Input
                placeholder="搜索书名、ISBN或作者..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && loadBooks(1)}
              />
              <Button onClick={() => loadBooks(1)}>
                <Search className="size-4" />
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Book Table */}
        <Card>
          <CardHeader>
            <CardTitle>书籍列表</CardTitle>
            <CardDescription>
              管理书籍信息和爬取状态
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs value={activeTab} onValueChange={(value) => { setActiveTab(value); setCurrentPage(1) }}>
              <TabsList>
                <TabsTrigger value="all">全部 ({getTabCount('all')})</TabsTrigger>
                <TabsTrigger value="crawled">已爬取 ({getTabCount('crawled')})</TabsTrigger>
                <TabsTrigger value="uncrawled">未爬取 ({getTabCount('uncrawled')})</TabsTrigger>
              </TabsList>

              <TabsContent value={activeTab} className="space-y-4">
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
                          <TableHead>作者</TableHead>
                          <TableHead>出版社</TableHead>
                          <TableHead>分类</TableHead>
                          <TableHead>爬取状态</TableHead>
                          <TableHead>市场价</TableHead>
                          <TableHead>利润率</TableHead>
                          <TableHead>操作</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {books.length > 0 ? (
                          books.map((book) => (
                            <TableRow key={book.isbn}>
                              <TableCell className="font-medium max-w-[200px] truncate" title={book.title}>
                                {book.title}
                              </TableCell>
                              <TableCell>{book.isbn}</TableCell>
                              <TableCell>{book.author || '-'}</TableCell>
                              <TableCell>{book.publisher || '-'}</TableCell>
                              <TableCell>{book.category || '-'}</TableCell>
                              <TableCell>
                                <div className="flex items-center gap-2">
                                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                                    book.is_crawled 
                                      ? 'bg-green-100 text-green-800' 
                                      : 'bg-orange-100 text-orange-800'
                                  }`}>
                                    {book.is_crawled ? '已爬取' : '未爬取'}
                                  </span>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => handleToggleCrawl(book.isbn, !book.is_crawled)}
                                    className="h-6 px-2 text-xs"
                                  >
                                    {book.is_crawled ? '停止' : '启用'}
                                  </Button>
                                </div>
                              </TableCell>
                              <TableCell className="font-semibold text-green-600">
                                ¥{book.market_price || 0}
                              </TableCell>
                              <TableCell className="font-semibold">
                                <span className={book.profit_margin > 20 ? 'text-green-600' : book.profit_margin > 10 ? 'text-orange-600' : 'text-red-600'}>
                                  {book.profit_margin || 0}%
                                </span>
                              </TableCell>
                              <TableCell>
                                <div className="flex gap-1">
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => handleViewBook(book)}
                                  >
                                    <Eye className="size-4" />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => handleEditBook(book)}
                                  >
                                    <Edit className="size-4" />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => handleDeleteBook(book.isbn)}
                                    className="text-red-600 hover:text-red-700"
                                  >
                                    <Trash2 className="size-4" />
                                  </Button>
                                </div>
                              </TableCell>
                            </TableRow>
                          ))
                        ) : (
                          <TableRow>
                            <TableCell colSpan={9} className="text-center py-8 text-muted-foreground">
                              {searchQuery ? '没有找到匹配的书籍' : '暂无书籍数据'}
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
                          onClick={() => loadBooks(currentPage - 1)}
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
                          onClick={() => loadBooks(currentPage + 1)}
                          disabled={currentPage === totalPages}
                        >
                          <ChevronRight className="size-4" />
                        </Button>
                      </div>
                    )}
                  </>
                )}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

      {/* Add/Edit Book Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>
              {editingBook ? '编辑书籍' : '添加书籍'}
            </DialogTitle>
            <DialogDescription>
              {editingBook ? '修改书籍信息' : '添加新书籍到系统中'}
            </DialogDescription>
          </DialogHeader>
          
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label htmlFor="isbn" className="text-sm font-medium">
                  ISBN <span className="text-red-500">*</span>
                </label>
                <Input
                  id="isbn"
                  value={formData.isbn}
                  onChange={(e) => setFormData({...formData, isbn: e.target.value})}
                  placeholder="978-7-XXXXXXXXX"
                  disabled={!!editingBook}
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="category" className="text-sm font-medium">
                  分类
                </label>
                <Input
                  id="category"
                  value={formData.category}
                  onChange={(e) => setFormData({...formData, category: e.target.value})}
                  placeholder="如：文学、科技等"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label htmlFor="title" className="text-sm font-medium">
                书名 <span className="text-red-500">*</span>
              </label>
              <Input
                id="title"
                value={formData.title}
                onChange={(e) => setFormData({...formData, title: e.target.value})}
                placeholder="请输入书名"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label htmlFor="author" className="text-sm font-medium">
                  作者
                </label>
                <Input
                  id="author"
                  value={formData.author}
                  onChange={(e) => setFormData({...formData, author: e.target.value})}
                  placeholder="请输入作者"
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="publisher" className="text-sm font-medium">
                  出版社
                </label>
                <Input
                  id="publisher"
                  value={formData.publisher}
                  onChange={(e) => setFormData({...formData, publisher: e.target.value})}
                  placeholder="请输入出版社"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label htmlFor="publish_date" className="text-sm font-medium">
                  出版日期
                </label>
                <Input
                  id="publish_date"
                  type="date"
                  value={formData.publish_date}
                  onChange={(e) => setFormData({...formData, publish_date: e.target.value})}
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="market_price" className="text-sm font-medium">
                  市场价格 (¥)
                </label>
                <Input
                  id="market_price"
                  type="number"
                  step="0.01"
                  value={formData.market_price}
                  onChange={(e) => setFormData({...formData, market_price: parseFloat(e.target.value) || 0})}
                  placeholder="0.00"
                />
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDialogOpen(false)}>
              取消
            </Button>
            <Button onClick={handleSubmitBook}>
              {editingBook ? '保存' : '添加'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* View Book Dialog */}
      <Dialog open={isViewDialogOpen} onOpenChange={setIsViewDialogOpen}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>书籍详情</DialogTitle>
            <DialogDescription>
              查看书籍的详细信息和销售数据
            </DialogDescription>
          </DialogHeader>
          
          {viewingBook && (
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">ISBN</label>
                  <p className="text-sm font-mono">{viewingBook.isbn}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">分类</label>
                  <p className="text-sm">{viewingBook.category || '-'}</p>
                </div>
              </div>

              <div>
                <label className="text-sm font-medium text-muted-foreground">书名</label>
                <p className="text-sm font-medium">{viewingBook.title}</p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">作者</label>
                  <p className="text-sm">{viewingBook.author || '-'}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">出版社</label>
                  <p className="text-sm">{viewingBook.publisher || '-'}</p>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">市场价格</label>
                  <p className="text-sm font-semibold text-green-600">¥{viewingBook.market_price || 0}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">平均售价</label>
                  <p className="text-sm font-semibold text-blue-600">¥{viewingBook.avg_price || 0}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">利润率</label>
                  <p className={`text-sm font-semibold ${viewingBook.profit_margin > 20 ? 'text-green-600' : viewingBook.profit_margin > 10 ? 'text-orange-600' : 'text-red-600'}`}>
                    {viewingBook.profit_margin || 0}%
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">爬取状态</label>
                  <p className="text-sm">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      viewingBook.is_crawled 
                        ? 'bg-green-100 text-green-800' 
                        : 'bg-orange-100 text-orange-800'
                    }`}>
                      {viewingBook.is_crawled ? '已爬取' : '未爬取'}
                    </span>
                  </p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">总销量</label>
                  <p className="text-sm font-semibold">{viewingBook.total_sales || 0}</p>
                </div>
              </div>

              {viewingBook.last_crawled && (
                <div>
                  <label className="text-sm font-medium text-muted-foreground">最后爬取时间</label>
                  <p className="text-sm">{new Date(viewingBook.last_crawled).toLocaleString('zh-CN')}</p>
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