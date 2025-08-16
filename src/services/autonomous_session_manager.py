#!/usr/bin/env python3
"""
自主会话管理器 - 完全自包含的窗口池和任务处理系统
业务层只需要将任务放入队列，会话管理器自主处理所有窗口管理和任务执行
"""
import asyncio
import logging
import time
import aiohttp
from typing import Dict, List, Optional, Any, Callable, Set
from enum import Enum
from dataclasses import dataclass, field
from collections import deque
from patchright.async_api import async_playwright, Page, Browser, BrowserContext

logger = logging.getLogger(__name__)


class SiteStatus(Enum):
    """网站访问状态"""
    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"
    LOGIN_REQUIRED = "login_required"
    BLOCKED = "blocked"
    ERROR = "error"


class TaskStatus(Enum):
    """任务执行状态"""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


@dataclass
class SiteState:
    """单个网站在窗口中的状态"""
    site_name: str
    status: SiteStatus = SiteStatus.AVAILABLE
    blocked_until: float = 0  # 解封时间戳
    error_count: int = 0
    last_success_time: float = 0
    last_error_message: str = ""
    
    def is_available(self) -> bool:
        """检查是否可用"""
        if self.status == SiteStatus.AVAILABLE:
            return True
        if self.status == SiteStatus.RATE_LIMITED and time.time() > self.blocked_until:
            # 自动解封
            self.status = SiteStatus.AVAILABLE
            self.blocked_until = 0
            return True
        return False
    
    def mark_rate_limited(self, duration_minutes: int = 6):
        """标记为频率限制"""
        self.status = SiteStatus.RATE_LIMITED
        self.blocked_until = time.time() + duration_minutes * 60
        self.error_count += 1
        logger.warning(f"网站 {self.site_name} 被频率限制，解封时间: {time.strftime('%H:%M:%S', time.localtime(self.blocked_until))}")
    
    def mark_login_required(self):
        """标记为需要登录"""
        self.status = SiteStatus.LOGIN_REQUIRED
        self.error_count += 1
        logger.warning(f"网站 {self.site_name} 需要登录")
    
    def mark_success(self):
        """标记成功访问"""
        self.status = SiteStatus.AVAILABLE
        self.blocked_until = 0
        self.error_count = 0
        self.last_success_time = time.time()
        self.last_error_message = ""
    
    def mark_error(self, error_message: str):
        """标记错误"""
        self.status = SiteStatus.ERROR
        self.error_count += 1
        self.last_error_message = error_message
        logger.error(f"网站 {self.site_name} 出现错误: {error_message}")


@dataclass
class WindowSession:
    """窗口会话 - 每个窗口代表一个账号，管理多个网站状态"""
    window_id: str
    page: Page
    context: BrowserContext
    account_name: str = "default"
    is_busy: bool = False
    created_at: float = field(default_factory=time.time)
    sites: Dict[str, SiteState] = field(default_factory=dict)
    
    def get_site_state(self, site_name: str) -> SiteState:
        """获取网站状态，不存在则创建"""
        if site_name not in self.sites:
            self.sites[site_name] = SiteState(site_name)
        return self.sites[site_name]
    
    def is_site_available(self, site_name: str) -> bool:
        """检查指定网站是否可用"""
        return self.get_site_state(site_name).is_available()
    
    def get_available_sites(self) -> List[str]:
        """获取所有可用的网站列表"""
        return [site_name for site_name, state in self.sites.items() if state.is_available()]


@dataclass
class TaskRequest:
    """任务请求"""
    task_id: int
    task_type: str
    target_platform: str
    params: Dict[str, Any]
    priority: int = 5
    created_at: float = field(default_factory=time.time)
    status: TaskStatus = TaskStatus.QUEUED
    error_message: str = ""
    execution_start: float = 0
    execution_end: float = 0


class AutonomousSessionManager:
    """自主会话管理器 - 完全自包含的任务处理系统"""
    
    def __init__(self, max_windows: int = 3):
        self.max_windows = max_windows
        
        # 内置窗口池
        self.sessions: Dict[str, WindowSession] = {}
        self.available_sessions: Set[str] = set()
        self.busy_sessions: Set[str] = set()
        
        # 浏览器相关
        self.playwright = None
        self.browser = None
        self.connected = False
        
        # 任务队列（从数据库读取）
        self.task_queue = deque()
        self.processing_tasks: Dict[int, TaskRequest] = {}
        
        # 控制器
        self._lock = asyncio.Lock()
        self._running = False
        self._main_loop_task = None
        self._initialized = False
        
        # 统计信息
        self.stats = {
            "tasks_processed": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "tasks_rejected": 0,
            "last_activity": time.time()
        }
        
        # 使用懒加载模式，在第一次需要时自动启动
        self._startup_lock = asyncio.Lock()
        self._startup_attempted = False
    
    async def _ensure_started(self):
        """确保会话管理器已启动（懒加载）"""
        if self._initialized:
            return True
        
        async with self._startup_lock:
            if self._initialized:
                return True
            
            if self._startup_attempted:
                return self._running
            
            self._startup_attempted = True
            
            try:
                logger.info("首次使用，自动启动会话管理器...")
                success = await self._initialize()
                if success:
                    logger.info("会话管理器自动启动成功")
                    return True
                else:
                    logger.error("会话管理器自动启动失败")
                    return False
            except Exception as e:
                logger.error(f"自动启动异常: {e}")
                return False
    
    async def _retry_initialization(self):
        """重试初始化机制"""
        retry_count = 0
        max_retries = 10
        
        while not self._initialized and retry_count < max_retries:
            try:
                await asyncio.sleep(30)  # 等待30秒后重试
                retry_count += 1
                logger.info(f"重试初始化会话管理器 ({retry_count}/{max_retries})")
                
                success = await self._initialize()
                if success:
                    logger.info("重试初始化成功")
                    break
                    
            except Exception as e:
                logger.error(f"重试初始化失败: {e}")
        
        if retry_count >= max_retries:
            logger.error("达到最大重试次数，会话管理器启动失败")
    
    async def _initialize(self) -> bool:
        """初始化会话管理器"""
        async with self._lock:
            if self._running:
                return True
            
            try:
                # 启动浏览器
                if not await self._connect_browser():
                    return False
                
                # 创建窗口会话
                for i in range(self.max_windows):
                    session = await self._create_session(f"account_{i+1}")
                    if session:
                        self.sessions[session.window_id] = session
                        self.available_sessions.add(session.window_id)
                
                self._running = True
                
                # 启动主循环
                self._main_loop_task = asyncio.create_task(self._main_loop())
                
                logger.info(f"自主会话管理器初始化完成，创建了 {len(self.sessions)} 个窗口")
                return True
                
            except Exception as e:
                logger.error(f"初始化失败: {e}")
                return False
    
    async def _connect_browser(self) -> bool:
        """连接到Chrome浏览器"""
        try:
            # 获取Chrome调试信息
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:9222/json/version") as response:
                    if response.status == 200:
                        version_info = await response.json()
                        ws_url = version_info.get('webSocketDebuggerUrl', '')
                    else:
                        logger.error("无法获取Chrome调试信息")
                        return False
            
            # 连接到浏览器
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.connect_over_cdp(ws_url)
            
            self.connected = True
            logger.info("成功连接到Chrome浏览器")
            return True
            
        except Exception as e:
            logger.error(f"Chrome连接失败: {e}")
            return False
    
    async def _create_session(self, account_name: str) -> Optional[WindowSession]:
        """创建新的窗口会话"""
        try:
            context = await self.browser.new_context()
            page = await context.new_page()
            
            window_id = f"window_{len(self.sessions)+1}_{int(time.time())}"
            session = WindowSession(
                window_id=window_id,
                page=page,
                context=context,
                account_name=account_name
            )
            
            # 导航到默认页面
            try:
                await page.goto("https://www.kongfz.com/", wait_until="domcontentloaded", timeout=10000)
            except:
                pass
            
            logger.info(f"创建窗口会话: {window_id} (账号: {account_name})")
            return session
            
        except Exception as e:
            logger.error(f"创建窗口会话失败: {e}")
            return None
    
    async def _main_loop(self):
        """主循环 - 持续轮询任务队列并处理"""
        logger.info("自主会话管理器主循环启动")
        
        while self._running:
            try:
                # 1. 从数据库加载新任务
                await self._load_new_tasks()
                
                # 2. 处理队列中的任务
                await self._process_task_queue()
                
                # 3. 检查超时任务
                await self._check_timeout_tasks()
                
                # 4. 更新统计信息
                self.stats["last_activity"] = time.time()
                
                # 短暂等待
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"主循环异常: {e}")
                await asyncio.sleep(5)
        
        logger.info("自主会话管理器主循环停止")
    
    async def _load_new_tasks(self):
        """从数据库加载新的待处理任务"""
        try:
            from ..models.repositories import CrawlTaskRepository
            task_repo = CrawlTaskRepository()
            
            # 获取所有pending状态的任务
            pending_tasks = task_repo.get_pending_tasks()
            
            for task_data in pending_tasks:
                task_id = task_data['id']
                
                # 检查是否已经在处理中
                if task_id in self.processing_tasks or any(t.task_id == task_id for t in self.task_queue):
                    continue
                
                # 创建任务请求
                task_request = TaskRequest(
                    task_id=task_id,
                    task_type=task_data['task_type'],
                    target_platform=task_data.get('target_platform', 'unknown'),
                    params={
                        'target_isbn': task_data.get('target_isbn'),
                        'target_url': task_data.get('target_url'),
                        'shop_id': task_data.get('shop_id'),
                        'book_title': task_data.get('book_title'),
                        'task_params': task_data.get('task_params')
                    },
                    priority=task_data.get('priority', 5)
                )
                
                self.task_queue.append(task_request)
                logger.debug(f"加载新任务: {task_id} ({task_request.task_type}) 平台: {task_request.target_platform}")
                
        except Exception as e:
            logger.error(f"加载任务失败: {e}")
    
    async def _process_task_queue(self):
        """处理任务队列"""
        if not self.task_queue:
            return
        
        # 按优先级排序队列
        self.task_queue = deque(sorted(self.task_queue, key=lambda t: t.priority, reverse=True))
        
        # 查找可执行的任务
        task_to_execute = None
        for i, task in enumerate(self.task_queue):
            if self._can_handle_task(task):
                task_to_execute = task
                del list(self.task_queue)[i]
                self.task_queue = deque(list(self.task_queue))
                break
        
        if task_to_execute:
            # 异步执行任务
            asyncio.create_task(self._execute_task(task_to_execute))
    
    def _can_handle_task(self, task: TaskRequest) -> bool:
        """检查是否有可用窗口处理任务"""
        platform = task.target_platform
        
        for session_id in self.available_sessions:
            session = self.sessions[session_id]
            if session.is_site_available(platform):
                return True
        
        return False
    
    async def _execute_task(self, task: TaskRequest):
        """执行单个任务"""
        task_id = task.task_id
        platform = task.target_platform
        
        # 获取可用会话
        session = await self._get_session_for_platform(platform)
        if not session:
            await self._reject_task(task, f"网站 {platform} 暂时不可用")
            return
        
        # 标记任务开始处理
        task.status = TaskStatus.PROCESSING
        task.execution_start = time.time()
        self.processing_tasks[task_id] = task
        
        try:
            # 更新数据库状态
            await self._update_task_status(task_id, 'running')
            
            # 执行具体的爬虫任务
            result = await self._execute_crawler_task(task, session)
            
            # 任务完成
            task.status = TaskStatus.COMPLETED
            task.execution_end = time.time()
            
            await self._update_task_status(task_id, 'completed')
            
            # 标记网站成功
            session.get_site_state(platform).mark_success()
            
            self.stats["tasks_completed"] += 1
            logger.info(f"任务 {task_id} 执行成功，耗时 {task.execution_end - task.execution_start:.2f}s")
            
        except Exception as e:
            # 任务失败
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.execution_end = time.time()
            
            await self._update_task_status(task_id, 'failed', str(e))
            
            # 根据错误类型标记网站状态
            await self._handle_task_error(session, platform, str(e))
            
            self.stats["tasks_failed"] += 1
            logger.error(f"任务 {task_id} 执行失败: {e}")
            
        finally:
            # 清理
            self.processing_tasks.pop(task_id, None)
            await self._return_session(session)
            self.stats["tasks_processed"] += 1
    
    async def _get_session_for_platform(self, platform: str) -> Optional[WindowSession]:
        """为指定平台获取可用会话"""
        async with self._lock:
            for session_id in list(self.available_sessions):
                session = self.sessions[session_id]
                if session.is_site_available(platform):
                    # 标记为忙碌
                    self.available_sessions.remove(session_id)
                    self.busy_sessions.add(session_id)
                    session.is_busy = True
                    
                    logger.debug(f"分配窗口 {session_id} 用于平台 {platform}")
                    return session
            
            return None
    
    async def _return_session(self, session: WindowSession):
        """归还会话"""
        async with self._lock:
            session_id = session.window_id
            if session_id in self.busy_sessions:
                self.busy_sessions.remove(session_id)
                self.available_sessions.add(session_id)
                session.is_busy = False
                
                logger.debug(f"归还窗口 {session_id}")
    
    async def _execute_crawler_task(self, task: TaskRequest, session: WindowSession) -> Any:
        """执行具体的爬虫任务"""
        # 这里需要根据task_type调用相应的爬虫方法
        # 为了简化，这里只是模拟执行
        
        task_type = task.task_type
        params = task.params
        page = session.page
        
        # 模拟执行不同类型的任务
        if task_type == 'book_sales_crawl':
            # 模拟孔夫子书籍销售爬取
            await page.goto(f"https://www.kongfz.com/book/{params.get('target_isbn', '')}")
            await asyncio.sleep(2)  # 模拟爬取时间
            return {"crawled_records": 10, "success": True}
            
        elif task_type == 'shop_books_crawl':
            # 模拟店铺书籍列表爬取
            await page.goto(params.get('target_url', 'https://www.kongfz.com/'))
            await asyncio.sleep(3)  # 模拟爬取时间
            return {"crawled_books": 25, "success": True}
            
        elif task_type == 'duozhuayu_price':
            # 模拟多抓鱼价格更新
            await page.goto(f"https://www.duozhuayu.com/book/{params.get('target_isbn', '')}")
            await asyncio.sleep(1)
            return {"price_updated": True, "success": True}
            
        else:
            raise ValueError(f"不支持的任务类型: {task_type}")
    
    async def _reject_task(self, task: TaskRequest, reason: str):
        """拒绝任务"""
        task.status = TaskStatus.REJECTED
        task.error_message = reason
        
        await self._update_task_status(task.task_id, 'failed', reason)
        
        self.stats["tasks_rejected"] += 1
        logger.warning(f"拒绝任务 {task.task_id}: {reason}")
    
    async def _handle_task_error(self, session: WindowSession, platform: str, error_msg: str):
        """处理任务错误，更新网站状态"""
        site_state = session.get_site_state(platform)
        
        if "rate" in error_msg.lower() or "限制" in error_msg or "频次" in error_msg:
            site_state.mark_rate_limited()
        elif "login" in error_msg.lower() or "登录" in error_msg:
            site_state.mark_login_required()
        else:
            site_state.mark_error(error_msg)
    
    async def _update_task_status(self, task_id: int, status: str, error_message: str = None):
        """更新数据库中的任务状态"""
        try:
            from ..models.repositories import CrawlTaskRepository
            task_repo = CrawlTaskRepository()
            task_repo.update_status(task_id, status, error_message=error_message)
        except Exception as e:
            logger.error(f"更新任务状态失败: {e}")
    
    async def _check_timeout_tasks(self):
        """检查超时任务"""
        current_time = time.time()
        timeout_threshold = 300  # 5分钟超时
        
        for task_id, task in list(self.processing_tasks.items()):
            if current_time - task.execution_start > timeout_threshold:
                task.status = TaskStatus.FAILED
                task.error_message = "任务执行超时"
                
                await self._update_task_status(task_id, 'failed', '任务执行超时')
                
                self.processing_tasks.pop(task_id)
                logger.warning(f"任务 {task_id} 执行超时")
    
    async def get_status(self) -> Dict[str, Any]:
        """获取管理器状态（自动启动）"""
        # 确保已启动
        await self._ensure_started()
        
        available_by_platform = {}
        
        # 统计每个平台的可用窗口数
        all_platforms = set()
        for session in self.sessions.values():
            all_platforms.update(session.sites.keys())
        
        for platform in all_platforms:
            count = sum(1 for session in self.sessions.values() 
                       if not session.is_busy and session.is_site_available(platform))
            available_by_platform[platform] = count
        
        return {
            "running": self._running,
            "connected": self.connected,
            "total_windows": len(self.sessions),
            "available_windows": len(self.available_sessions),
            "busy_windows": len(self.busy_sessions),
            "queue_size": len(self.task_queue),
            "processing_tasks": len(self.processing_tasks),
            "available_by_platform": available_by_platform,
            "statistics": self.stats.copy(),
            "sessions": [
                {
                    "window_id": session.window_id,
                    "account_name": session.account_name,
                    "is_busy": session.is_busy,
                    "total_sites": len(session.sites),
                    "available_sites": len(session.get_available_sites()),
                    "sites_detail": {
                        name: {
                            "status": state.status.value,
                            "error_count": state.error_count,
                            "blocked_until": state.blocked_until if state.blocked_until > time.time() else 0
                        }
                        for name, state in session.sites.items()
                    }
                }
                for session in self.sessions.values()
            ]
        }
    
    async def stop(self):
        """停止会话管理器"""
        async with self._lock:
            self._running = False
            
            if self._main_loop_task:
                self._main_loop_task.cancel()
                try:
                    await self._main_loop_task
                except asyncio.CancelledError:
                    pass
            
            # 关闭所有窗口
            for session in self.sessions.values():
                try:
                    await session.context.close()
                except:
                    pass
            
            # 关闭浏览器
            if self.browser:
                try:
                    await self.browser.close()
                except:
                    pass
            
            if self.playwright:
                try:
                    await self.playwright.stop()
                except:
                    pass
            
            self.sessions.clear()
            self.available_sessions.clear()
            self.busy_sessions.clear()
            self.connected = False
            
            logger.info("自主会话管理器已停止")


# 全局实例
autonomous_session_manager = AutonomousSessionManager(max_windows=3)