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
from ..models.database import db

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
    status: TaskStatus = TaskStatus.PROCESSING
    error_message: str = ""
    execution_start: float = 0
    execution_end: float = 0


class AutonomousSessionManager:
    """自主会话管理器 - 完全自包含的任务处理系统"""
    
    def __init__(self, max_windows: int = 3):
        self.max_windows = max_windows
        
        # 内置窗口池 - 合并window_pool功能
        self.sessions: Dict[str, WindowSession] = {}
        self.available_sessions: Set[str] = set()
        self.busy_sessions: Set[str] = set()
        
        # 窗口池核心功能
        self.available_windows = deque()  # 可用窗口队列
        self.busy_windows = {}  # 忙碌窗口字典 {window_id: page}
        self.window_info = {}  # 窗口信息 {window_id: {'created_at': time, 'used_count': int}}
        
        # 封控状态追踪
        self.rate_limited_windows = {}  # 被频率限制的窗口ID字典 {window_id: unban_time}
        self.login_required_windows = {}  # 需要登录的窗口ID字典 {window_id: error_time}
        self.last_success_time = {}  # 每个窗口最后成功时间 {window_id: timestamp}
        
        # 浏览器相关
        self.patchright = None
        self.browser = None
        self.connected = False
        
        # 任务处理
        self.processing_tasks: Dict[int, TaskRequest] = {}
        self.simple_task_queue = None  # 延迟初始化避免循环导入
        
        # 控制器
        self._lock = asyncio.Lock()
        self._init_lock = asyncio.Lock()
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
    
    def _get_task_queue(self):
        """延迟初始化SimpleTaskQueue避免循环导入"""
        if self.simple_task_queue is None:
            from .simple_task_queue import simple_task_queue
            self.simple_task_queue = simple_task_queue
        return self.simple_task_queue
    
    async def _ensure_started(self):
        """确保会话管理器已启动（仅返回状态，不自动初始化）"""
        # 移除自动初始化逻辑，只能通过窗口池管理页面手动初始化
        return self._initialized
    
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
                # 初始化窗口池（只在手动调用时初始化）
                if not await self.initialize_pool():
                    return False
                
                # 基于已创建的窗口创建会话
                session_count = 0
                for page in list(self.available_windows):
                    session = WindowSession(
                        window_id=str(id(page)),
                        page=page,
                        context=page.context,
                        account_name=f"account_{session_count+1}"
                    )
                    self.sessions[session.window_id] = session
                    self.available_sessions.add(session.window_id)
                    session_count += 1
                
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
        if self.connected:
            return True
        
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
            self.patchright = await async_playwright().start()
            self.browser = await self.patchright.chromium.connect_over_cdp(ws_url)
            
            self.connected = True
            logger.info("成功连接到Chrome浏览器")
            
            return True
            
        except Exception as e:
            logger.error(f"Chrome连接失败: {e}")
            self.connected = False
            return False
    
    async def _create_session(self, account_name: str) -> Optional[WindowSession]:
        """创建新的窗口会话"""
        try:
            # 创建新的浏览器窗口
            page = await self._create_window()
            if not page:
                logger.warning(f"无法创建窗口，会话 {account_name} 创建失败")
                return None
            
            window_id = str(id(page))  # 使用页面对象的ID作为窗口ID
            
            session = WindowSession(
                window_id=window_id,
                page=page,
                context=page.context,  # 使用页面的上下文
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
        """主循环 - 持续轮询任务队列带处理（仅在手动初始化后运行）"""
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
        """从SimpleTaskQueue加载新的待处理任务"""
        try:
            task_queue = self._get_task_queue()
            
            # 获取所有pending状态的任务（从数据库获取待处理任务）
            pending_tasks = task_queue.get_pending_tasks()
            
            if pending_tasks:
                logger.info(f"发现 {len(pending_tasks)} 个pending状态的任务待处理")
            
            for task_data in pending_tasks:
                task_id = task_data['id']
                
                # 检查是否已经在处理中
                if task_id in self.processing_tasks:
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
                
                # 直接尝试执行任务，不维护内存队列
                await self._try_execute_task(task_request)
                logger.debug(f"处理任务: {task_id} ({task_request.task_type}) 平台: {task_request.target_platform}")
                
        except Exception as e:
            logger.error(f"加载任务失败: {e}")
    
    async def _process_task_queue(self):
        """处理任务队列 - 直接从SimpleTaskQueue获取任务"""
        # 现在任务处理在_load_new_tasks中完成
        # 这个方法保持为兼容性，但实际工作已转移
        pass
    
    async def _try_execute_task(self, task_request: TaskRequest):
        """尝试执行单个任务"""
        if self._can_handle_task(task_request):
            window_session = await self._get_session_for_platform(task_request.target_platform)
            if window_session:
                await self._execute_task(task_request, window_session)
    
    def _can_handle_task(self, task: TaskRequest) -> bool:
        """检查是否有可用窗口处理任务"""
        platform = task.target_platform
        
        for session_id in self.available_sessions:
            session = self.sessions[session_id]
            if session.is_site_available(platform):
                return True
        
        return False
    
    async def _execute_task(self, task: TaskRequest, session: WindowSession = None):
        """执行单个任务"""
        task_id = task.task_id
        platform = task.target_platform
        
        # 如果没有传入session，获取可用会话
        if not session:
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
                
                logger.debug(f"归还窗口 {session_id} 到会话管理器")
    
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
            
        elif task_type == 'isbn_analysis':
            # 模拟ISBN分析任务
            await page.goto(f"https://www.kongfz.com/book/{params.get('target_isbn', '')}")
            await asyncio.sleep(2)
            return {"analysis_completed": True, "success": True}
            
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
        """获取管理器状态（不自动启动）"""
        # 如果未初始化，返回基本状态
        if not self._initialized:
            return {
                "running": False,
                "connected": False,
                "total_windows": 0,
                "available_windows": 0,
                "busy_windows": 0,
                "queue_size": 0,
                "processing_tasks": 0,
                "available_by_platform": {},
                "statistics": self.stats.copy(),
                "sessions": []
            }
        
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
            "queue_size": len(self._get_task_queue().get_pending_tasks()) if hasattr(self, '_get_task_queue') else 0,
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
    
    async def acquire_window(self, platform: str) -> Optional['WindowSession']:
        """获取指定平台的可用窗口
        
        Args:
            platform: 平台名称（如 'kongfz', 'duozhuayu'）
            
        Returns:
            WindowSession: 可用的窗口会话，如果没有可用窗口则返回None
        """
        # 检查会话管理器是否已启动（不自动启动）
        if not await self._ensure_started():
            logger.warning("会话管理器未初始化，请先在窗口池管理页面初始化")
            return None
        
        return await self._get_session_for_platform(platform)
    
    async def release_window(self, session: 'WindowSession'):
        """释放窗口会话
        
        Args:
            session: 要释放的窗口会话
        """
        await self._return_session(session)

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
    
    # === Window Pool 核心功能 ===
    
    async def _create_window(self) -> Optional[Page]:
        """创建新的浏览器窗口"""
        try:
            if not self.connected or not self.browser:
                # 尝试重新连接浏览器
                if not await self._connect_browser():
                    return None
            
            # 创建新的上下文和页面
            context = await self.browser.new_context()
            page = await context.new_page()
            
            # 记录窗口信息
            window_id = id(page)
            self.window_info[window_id] = {
                'created_at': time.time(),
                'used_count': 0,
                'context': context  # 保存context引用，用于关闭
            }
            
            logger.info(f"创建新窗口: {window_id}")
            return page
            
        except Exception as e:
            logger.error(f"创建窗口失败: {e}")
            # 如果是连接错误，尝试重置连接状态
            if "Connection closed" in str(e) or "WebSocket" in str(e):
                logger.warning("检测到浏览器连接断开，重置连接状态")
                self.connected = False
                self.browser = None
                if self.patchright:
                    try:
                        await self.patchright.stop()
                    except:
                        pass
                    self.patchright = None
            return None
    
    async def get_window(self, timeout: float = 30.0) -> Optional[Page]:
        """获取一个可用的窗口
        
        Args:
            timeout: 等待可用窗口的超时时间（秒）
        
        Returns:
            可用的页面对象，如果超时返回None
        """
        # 检查窗口池是否已初始化（不自动初始化）
        if not self._initialized:
            logger.warning("窗口池未初始化，请先在窗口池管理页面初始化")
            return None
        
        start_time = time.time()
        
        while True:
            async with self._lock:
                # 从可用窗口池中获取
                if self.available_windows:
                    page = self.available_windows.popleft()
                    window_id = id(page)

                    # 检查窗口是否被频率限制
                    if window_id in self.rate_limited_windows:
                        unban_time = self.rate_limited_windows[window_id]
                        if time.time() < unban_time:
                            # 仍在频率限制期，放回队列末尾，并继续查找
                            self.available_windows.append(page)
                            logger.debug(f"窗口 {window_id} 仍在频率限制期，跳过")
                            continue # 继续循环查找下一个可用窗口
                        else:
                            # 频率限制已过，解除限制
                            self.rate_limited_windows.pop(window_id, None)
                            logger.info(f"窗口 {window_id} 频率限制期已过，已自动解封")
                    
                    # 检查窗口是否需要登录（登录错误不会自动恢复，需要人工处理）
                    if window_id in self.login_required_windows:
                        # 登录错误窗口跳过，不自动恢复
                        self.available_windows.append(page)
                        logger.debug(f"窗口 {window_id} 需要登录，跳过")
                        continue # 继续循环查找下一个可用窗口
                    
                    # 检查窗口是否仍然有效
                    try:
                        await page.evaluate("() => true")  # 简单的检查
                        # 检查URL，如果是about:blank或错误页面，导航到主页
                        current_url = page.url
                        if "about:blank" in current_url:
                            logger.info(f"窗口 {window_id} 处于空白页，导航到本地页面")
                            await page.goto("http://localhost:8282/", wait_until="domcontentloaded", timeout=10000)
                        
                        self.busy_windows[window_id] = page
                        self.window_info[window_id]['used_count'] += 1
                        logger.debug(f"从池中获取窗口: {window_id}, URL: {current_url}")
                        return page
                    except:
                        # 窗口已失效，移除并创建新的
                        await self._remove_window_unsafe(page)
                        new_page = await self._create_window()
                        if new_page:
                            window_id = id(new_page)
                            self.busy_windows[window_id] = new_page
                            self.window_info[window_id]['used_count'] += 1
                            return new_page
                
                # 如果池中没有可用窗口，且还能创建新窗口
                total_windows = len(self.busy_windows) + len(self.available_windows)
                if total_windows < self.max_windows:
                    page = await self._create_window()
                    if page:
                        window_id = id(page)
                        self.busy_windows[window_id] = page
                        self.window_info[window_id]['used_count'] += 1
                        logger.debug(f"创建新窗口: {window_id}")
                        return page
            
            # 检查超时
            if time.time() - start_time > timeout:
                logger.warning(f"获取窗口超时（{timeout}秒），所有窗口都在使用中")
                return None
            
            # 等待一小段时间后重试
            await asyncio.sleep(0.5)
    
    async def return_window(self, page: Page, keep_alive: bool = True):
        """归还窗口到池中
        
        Args:
            page: 要归还的页面
            keep_alive: 是否保持窗口存活（默认True，保持登录状态）
        """
        async with self._lock:
            window_id = id(page)
            
            if window_id in self.busy_windows:
                del self.busy_windows[window_id]
                
                if keep_alive:
                    # 检查窗口是否仍然有效
                    try:
                        await page.evaluate("() => true")
                        # 不要导航到空白页，保持当前页面和登录状态
                        # 只是检查一下URL，如果是错误页面就导航回主页
                        current_url = page.url
                        if "about:blank" in current_url or "error" in current_url.lower():
                            try:
                                await page.goto("http://localhost:8282/", wait_until="domcontentloaded", timeout=5000)
                            except:
                                pass
                        self.available_windows.append(page)
                        logger.debug(f"窗口归还到池(保持存活): {window_id}, URL: {current_url}")
                    except:
                        # 窗口已失效，直接移除
                        await self._remove_window_unsafe(page)
                        logger.debug(f"移除失效窗口: {window_id}")
                        # 创建新窗口补充
                        new_page = await self._create_window()
                        if new_page:
                            self.available_windows.append(new_page)
                else:
                    # 用户要求关闭窗口
                    await self._remove_window_unsafe(page)
                    logger.debug(f"按要求关闭窗口: {window_id}")
                    # 创建新窗口补充
                    new_page = await self._create_window()
                    if new_page:
                        self.available_windows.append(new_page)
    
    async def _remove_window_unsafe(self, page: Page):
        """移除窗口（不加锁，内部使用）"""
        window_id = id(page)
        
        # 从各个集合中移除
        self.busy_windows.pop(window_id, None)
        if page in self.available_windows:
            self.available_windows.remove(page)
        
        # 关闭context和页面
        window_info = self.window_info.pop(window_id, None)
        if window_info:
            context = window_info.get('context')
            try:
                await page.close()
            except:
                pass
            if context:
                try:
                    await context.close()
                except:
                    pass
    
    def mark_window_rate_limited(self, page: Page, duration_minutes: int = 6):
        """标记窗口为被频率限制状态
        
        Args:
            page: 要标记的页面
            duration_minutes: 频率限制持续时间（分钟）
        """
        window_id = id(page)
        unban_time = time.time() + duration_minutes * 60
        self.rate_limited_windows[window_id] = unban_time
        
        # 清除登录错误状态（如果有）
        self.login_required_windows.pop(window_id, None)
        
        # 格式化解封时间
        unban_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(unban_time))
        logger.warning(f"窗口 {window_id} 被标记为频率限制状态，将在 {unban_time_str} 后解封")
    
    def mark_window_login_required(self, page: Page):
        """标记窗口为需要登录状态
        
        Args:
            page: 要标记的页面
        """
        window_id = id(page)
        error_time = time.time()
        self.login_required_windows[window_id] = error_time
        
        # 清除频率限制状态（如果有）
        self.rate_limited_windows.pop(window_id, None)
        
        error_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(error_time))
        logger.error(f"窗口 {window_id} 需要登录，请在浏览器中手动登录。错误时间: {error_time_str}")
    
    def mark_window_success(self, page: Page):
        """标记窗口成功访问，清除所有错误状态"""
        window_id = id(page)
        # 清除频率限制状态
        self.rate_limited_windows.pop(window_id, None)
        # 清除登录错误状态
        self.login_required_windows.pop(window_id, None)
        self.last_success_time[window_id] = time.time()
        logger.debug(f"窗口 {window_id} 成功访问，清除所有错误状态")
    
    async def navigate_window_to_url(self, window_id: str, url: str) -> bool:
        """控制指定窗口导航到指定URL
        
        Args:
            window_id: 窗口ID（字符串形式）
            url: 要导航到的URL
            
        Returns:
            bool: 导航是否成功
        """
        try:
            # 将字符串window_id转换为实际的窗口ID进行查承
            target_page = None
            
            # 在可用窗口中查承
            for page in self.available_windows:
                if str(id(page)) == window_id:
                    target_page = page
                    break
            
            # 在忙碌窗口中查承
            if not target_page:
                for win_id, page in self.busy_windows.items():
                    if str(win_id) == window_id:
                        target_page = page
                        break
            
            if not target_page:
                logger.error(f"未找到窗口ID {window_id}")
                return False
            
            # 检查窗口是否被封控
            actual_window_id = id(target_page)
            if actual_window_id in self.rate_limited_windows:
                unban_time = self.rate_limited_windows[actual_window_id]
                if time.time() < unban_time:
                    logger.warning(f"窗口 {window_id} 仍在频率限制期，无法导航")
                    return False
            
            if actual_window_id in self.login_required_windows:
                logger.warning(f"窗口 {window_id} 需要登录，无法导航")
                return False
            
            # 执行导航
            logger.info(f"正在控制窗口 {window_id} 导航到: {url}")
            await target_page.goto(url, wait_until="domcontentloaded", timeout=10000)
            
            # 标记成功
            self.mark_window_success(target_page)
            logger.info(f"窗口 {window_id} 成功导航到: {url}")
            return True
            
        except Exception as e:
            logger.error(f"窗口 {window_id} 导航到 {url} 失败: {e}")
            return False
    
    def get_pool_status(self) -> Dict[str, Any]:
        """获取窗口池状态"""
        window_details = []
        for window_id, info in self.window_info.items():
            status = "busy" if window_id in self.busy_windows else "available"
            is_rate_limited = window_id in self.rate_limited_windows
            is_login_required = window_id in self.login_required_windows
            unban_time = self.rate_limited_windows.get(window_id)
            login_error_time = self.login_required_windows.get(window_id)
            
            # 判断窗口实际状态
            if is_login_required:
                actual_status = "需要登录"
            elif is_rate_limited:
                actual_status = "频率限制"
            elif status == "busy":
                actual_status = "使用中"
            else:
                actual_status = "正常"
            
            window_details.append({
                "window_id": window_id,
                "status": actual_status,
                "is_rate_limited": is_rate_limited,
                "is_login_required": is_login_required,
                "unban_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(unban_time)) if unban_time else None,
                "login_error_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(login_error_time)) if login_error_time else None,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(info['created_at'])),
                "used_count": info['used_count'],
                "last_success": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.last_success_time.get(window_id, 0))) if window_id in self.last_success_time else "从未成功"
            })
        
        return {
            "connected": self.connected,
            "initialized": self._initialized,
            "pool_size": self.max_windows,
            "available_count": len(self.available_windows),
            "busy_count": len(self.busy_windows),
            "total_windows": len(self.available_windows) + len(self.busy_windows),
            "window_details": window_details
        }
    
    async def initialize_pool(self):
        """初始化窗口池，智能管理窗口数量"""
        async with self._init_lock:
            if self._initialized:
                # 已初始化，检查是否需要调整窗口数量
                current_count = len(self.available_windows) + len(self.busy_windows)
                if current_count == self.max_windows:
                    logger.info(f"窗口池已初始化，当前有 {current_count} 个窗口")
                    return True
                else:
                    # 需要调整窗口数量
                    return await self._adjust_window_count()
            
            # 连接浏览器
            if not await self._connect_browser():
                return False
            
            # 检查是否已有打开的窗口
            existing_windows = await self._detect_existing_windows()
            existing_count = len(existing_windows)
            
            if existing_count > 0:
                logger.info(f"检测到 {existing_count} 个已打开的窗口")
                # 将现有窗口加入池中
                for page in existing_windows:
                    window_id = id(page)
                    self.window_info[window_id] = {
                        'created_at': time.time(),
                        'used_count': 0,
                        'context': None  # 现有窗口没有context引用
                    }
                    self.available_windows.append(page)
            
            # 计算还需要创建多少窗口
            needed = self.max_windows - existing_count
            
            if needed > 0:
                logger.info(f"需要创建 {needed} 个新窗口")
                login_urls = []
                for i in range(needed):
                    page = await self._create_window()
                    if page:
                        # 导航到本地管理页面
                        try:
                            await page.goto("http://localhost:8282/", wait_until="domcontentloaded", timeout=10000)
                            login_urls.append(f"新窗口{i+1}: http://localhost:8282/")
                        except:
                            pass
                        self.available_windows.append(page)
                        logger.info(f"创建新窗口 {i+1}/{needed} 成功")
                
                # 提示用户登录新窗口
                if login_urls:
                    logger.info("=" * 60)
                    logger.info("请在新打开的Chrome窗口中登录孔夫子旧书网账号")
                    for url in login_urls:
                        logger.info(f"  {url}")
                    logger.info("登录完成后，窗口将保持登录状态供爬虫使用")
                    logger.info("=" * 60)
            elif needed < 0:
                # 窗口数量超过需求，关闭多余的窗口
                logger.info(f"当前有 {existing_count} 个窗口，超过设定的 {self.max_windows} 个，将关闭 {-needed} 个窗口")
                for _ in range(-needed):
                    if self.available_windows:
                        page = self.available_windows.popleft()
                        await self._remove_window_unsafe(page)
            
            self._initialized = True
            final_count = len(self.available_windows) + len(self.busy_windows)
            logger.info(f"窗口池初始化完成，共有 {final_count} 个窗口")
            
            return True
    
    async def _detect_existing_windows(self):
        """检测浏览器中已打开的窗口"""
        existing_windows = []
        try:
            if self.browser:
                # 获取所有上下文
                contexts = self.browser.contexts
                for context in contexts:
                    # 获取每个上下文的所有页面
                    pages = context.pages
                    for page in pages:
                        # 检查页面是否有效
                        try:
                            await page.evaluate("() => true")
                            existing_windows.append(page)
                        except:
                            # 页面无效，跳过
                            pass
        except Exception as e:
            logger.debug(f"检测现有窗口时出错: {e}")
        
        return existing_windows
    
    async def _adjust_window_count(self):
        """调整窗口数量以匹配设定值"""
        current_count = len(self.available_windows) + len(self.busy_windows)
        needed = self.max_windows - current_count
        
        if needed > 0:
            # 需要创建更多窗口
            logger.info(f"当前有 {current_count} 个窗口，需要创建 {needed} 个新窗口")
            login_urls = []
            for i in range(needed):
                page = await self._create_window()
                if page:
                    try:
                        await page.goto("http://localhost:8282/", wait_until="domcontentloaded", timeout=10000)
                        login_urls.append(f"新窗口{i+1}: http://localhost:8282/")
                    except:
                        pass
                    self.available_windows.append(page)
                    logger.info(f"创建新窗口 {i+1}/{needed} 成功")
            
            if login_urls:
                logger.info("=" * 60)
                logger.info("请在新打开的Chrome窗口中登录孔夫子旧书网账号")
                for url in login_urls:
                    logger.info(f"  {url}")
                logger.info("=" * 60)
        elif needed < 0:
            # 窗口太多，需要关闭一些
            logger.info(f"当前有 {current_count} 个窗口，超过设定的 {self.max_windows} 个，将关闭 {-needed} 个窗口")
            closed = 0
            # 优先关闭可用窗口（未在使用中的）
            while closed < -needed and self.available_windows:
                page = self.available_windows.popleft()
                await self._remove_window_unsafe(page)
                closed += 1
                logger.info(f"关闭窗口 {closed}/{-needed}")
            
            if closed < -needed:
                logger.warning(f"只能关闭 {closed} 个窗口，有 {-needed - closed} 个窗口正在使用中")
        else:
            logger.info(f"窗口数量正好为 {self.max_windows}，无需调整")
        
        return True


# 全局实例 - 统一窗口管理器（默认2个窗口，与原window_pool保持一致）
autonomous_session_manager = AutonomousSessionManager(max_windows=2)

# 为了兼容性，提供可访问的别名
chrome_pool = autonomous_session_manager