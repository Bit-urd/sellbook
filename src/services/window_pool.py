#!/usr/bin/env python3
"""
Chrome浏览器窗口池管理器 - 支持并发爬取
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any
import aiohttp
from playwright.async_api import async_playwright, Page, Browser
from collections import deque
import time

logger = logging.getLogger(__name__)

class ChromeWindowPool:
    """Chrome窗口池管理器"""
    
    def __init__(self, pool_size: int = 2):
        """
        Args:
            pool_size: 窗口池大小，默认2个窗口
        """
        self.pool_size = pool_size
        
        # 窗口池相关
        self.available_windows = deque()  # 可用窗口队列
        self.busy_windows = {}  # 忙碌窗口字典 {window_id: page}
        self.window_info = {}  # 窗口信息 {window_id: {'created_at': time, 'used_count': int}}
        
        # 连接相关
        self.playwright = None
        self.browser = None
        self.connected = False
        self._lock = asyncio.Lock()
        self._init_lock = asyncio.Lock()
        self._initialized = False
    
    async def initialize(self):
        """初始化窗口池，智能管理窗口数量"""
        async with self._init_lock:
            if self._initialized:
                # 已初始化，检查是否需要调整窗口数量
                current_count = len(self.available_windows) + len(self.busy_windows)
                if current_count == self.pool_size:
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
            needed = self.pool_size - existing_count
            
            if needed > 0:
                logger.info(f"需要创建 {needed} 个新窗口")
                login_urls = []
                for i in range(needed):
                    page = await self._create_window()
                    if page:
                        # 导航到孔夫子网登录页面
                        try:
                            await page.goto("https://www.kongfz.com/", wait_until="domcontentloaded", timeout=10000)
                            login_urls.append(f"新窗口{i+1}: https://www.kongfz.com/")
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
                logger.info(f"当前有 {existing_count} 个窗口，超过设定的 {self.pool_size} 个，将关闭 {-needed} 个窗口")
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
        """调整窗口数量以匹配pool_size"""
        current_count = len(self.available_windows) + len(self.busy_windows)
        needed = self.pool_size - current_count
        
        if needed > 0:
            # 需要创建更多窗口
            logger.info(f"当前有 {current_count} 个窗口，需要创建 {needed} 个新窗口")
            login_urls = []
            for i in range(needed):
                page = await self._create_window()
                if page:
                    try:
                        await page.goto("https://www.kongfz.com/", wait_until="domcontentloaded", timeout=10000)
                        login_urls.append(f"新窗口{i+1}: https://www.kongfz.com/")
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
            logger.info(f"当前有 {current_count} 个窗口，超过设定的 {self.pool_size} 个，将关闭 {-needed} 个窗口")
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
            logger.info(f"窗口数量正好为 {self.pool_size}，无需调整")
        
        return True
    
    async def _connect_browser(self):
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
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.connect_over_cdp(ws_url)
            
            self.connected = True
            logger.info("成功连接到Chrome浏览器")
            
            return True
            
        except Exception as e:
            logger.error(f"Chrome连接失败: {e}")
            self.connected = False
            return False
    
    async def _create_window(self) -> Optional[Page]:
        """创建新的浏览器窗口"""
        try:
            if not self.connected or not self.browser:
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
            return None
    
    async def get_window(self, timeout: float = 30.0) -> Optional[Page]:
        """获取一个可用的窗口
        
        Args:
            timeout: 等待可用窗口的超时时间（秒）
        
        Returns:
            可用的页面对象，如果超时返回None
        """
        # 确保窗口池已初始化
        if not self._initialized:
            if not await self.initialize():
                return None
        
        start_time = time.time()
        
        while True:
            async with self._lock:
                # 从可用窗口池中获取
                if self.available_windows:
                    page = self.available_windows.popleft()
                    window_id = id(page)
                    
                    # 检查窗口是否仍然有效
                    try:
                        await page.evaluate("() => true")  # 简单的检查
                        self.busy_windows[window_id] = page
                        self.window_info[window_id]['used_count'] += 1
                        logger.debug(f"从池中获取窗口: {window_id}")
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
                if total_windows < self.pool_size:
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
                        # 导航到空白页，释放内存
                        try:
                            await page.goto("about:blank", wait_until="domcontentloaded", timeout=5000)
                        except:
                            pass
                        self.available_windows.append(page)
                        logger.debug(f"窗口归还到池(保持存活): {window_id}")
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
    
    async def remove_window(self, page: Page):
        """手动移除指定窗口（用户主动关闭）"""
        async with self._lock:
            await self._remove_window_unsafe(page)
            logger.info(f"手动移除窗口: {id(page)}")
    
    async def close_all_windows(self):
        """关闭所有窗口（用户主动清理）"""
        async with self._lock:
            # 关闭所有窗口
            all_windows = list(self.available_windows)
            for page in list(self.busy_windows.values()):
                all_windows.append(page)
            
            for page in all_windows:
                await self._remove_window_unsafe(page)
            
            # 清空所有集合
            self.available_windows.clear()
            self.busy_windows.clear()
            self.window_info.clear()
            self._initialized = False
            
            logger.info("已关闭所有窗口")
    
    async def disconnect(self):
        """断开连接并清理所有窗口"""
        # 关闭所有窗口
        await self.close_all_windows()
        
        # 断开playwright连接
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
            self.browser = None
        
        self.connected = False
        logger.info("已断开所有浏览器连接")
    
    def get_pool_status(self) -> Dict[str, Any]:
        """获取窗口池状态"""
        window_details = []
        for window_id, info in self.window_info.items():
            status = "busy" if window_id in self.busy_windows else "available"
            window_details.append({
                "window_id": window_id,
                "status": status,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(info['created_at'])),
                "used_count": info['used_count']
            })
        
        return {
            "connected": self.connected,
            "initialized": self._initialized,
            "pool_size": self.pool_size,
            "available_count": len(self.available_windows),
            "busy_count": len(self.busy_windows),
            "total_windows": len(self.available_windows) + len(self.busy_windows),
            "window_details": window_details
        }


# 全局窗口池实例（默认2个窗口）
chrome_pool = ChromeWindowPool(pool_size=2)


class WindowPoolManager:
    """窗口池管理器装饰器 - 自动管理窗口获取和归还"""
    
    def __init__(self, pool: ChromeWindowPool = None, keep_window_alive: bool = True):
        """
        Args:
            pool: 窗口池实例，默认使用全局池
            keep_window_alive: 任务完成后是否保持窗口存活（保持登录状态）
        """
        self.pool = pool or chrome_pool
        self.keep_window_alive = keep_window_alive
    
    def __call__(self, func):
        """装饰器：自动管理窗口生命周期"""
        async def wrapper(*args, **kwargs):
            # 获取窗口
            page = await self.pool.get_window()
            if not page:
                raise Exception("无法获取可用的浏览器窗口，请稍后重试")
            
            try:
                # 将page注入到函数参数中
                kwargs['page'] = page
                result = await func(*args, **kwargs)
                return result
            finally:
                # 归还窗口，默认保持存活状态
                await self.pool.return_window(page, keep_alive=self.keep_window_alive)
        
        return wrapper