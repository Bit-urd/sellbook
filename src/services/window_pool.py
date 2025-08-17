#!/usr/bin/env python3
"""
Chrome浏览器窗口池管理器 - 支持并发爬取（集成aiolimiter）
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any
import aiohttp
from patchright.async_api import async_playwright, Page, Browser
from collections import deque
import time
from aiolimiter import AsyncLimiter

logger = logging.getLogger(__name__)

class ChromeWindowPool:
    """Chrome窗口池管理器（集成aiolimiter）"""
    
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
        
        # 基于aiolimiter的限流管理
        self.window_limiters = {}  # {window_id: AsyncLimiter}
        self.window_penalties = {}  # {window_id: {'blocked_until': time, 'login_required_until': time}}
        
        # 限流配置
        self.max_requests_per_minute = 10  # 每分钟最多10个请求
        self.rate_limit_penalty = 6 * 60  # 频率限制惩罚6分钟
        self.login_penalty = 30  # 登录问题惩罚30秒
        
        # 连接相关
        self.patchright = None
        self.browser = None
        self.connected = False
        self._lock = asyncio.Lock()
        self._init_lock = asyncio.Lock()
        self._initialized = False
    
    def _get_limiter(self, window_id: int) -> AsyncLimiter:
        """获取窗口的限流器"""
        if window_id not in self.window_limiters:
            # 每个窗口每分钟最多10个请求
            self.window_limiters[window_id] = AsyncLimiter(
                max_rate=self.max_requests_per_minute, 
                time_period=60
            )
        return self.window_limiters[window_id]
    
    async def _can_access_window(self, window_id: int) -> bool:
        """检查窗口是否可以访问（基于aiolimiter）"""
        current_time = time.time()
        
        # 检查手动惩罚状态
        if window_id in self.window_penalties:
            penalties = self.window_penalties[window_id]
            
            # 检查是否被阻塞
            if current_time < penalties.get('blocked_until', 0):
                remaining = penalties['blocked_until'] - current_time
                logger.debug(f"窗口 {window_id} 被阻塞，剩余 {remaining:.1f}秒")
                return False
            
            # 检查是否需要登录
            if current_time < penalties.get('login_required_until', 0):
                remaining = penalties['login_required_until'] - current_time
                logger.debug(f"窗口 {window_id} 需要登录，剩余 {remaining:.1f}秒")
                return False
            
            # 清理过期的惩罚
            if current_time >= penalties.get('blocked_until', 0) and current_time >= penalties.get('login_required_until', 0):
                del self.window_penalties[window_id]
        
        # 使用aiolimiter检查频率限制
        limiter = self._get_limiter(window_id)
        try:
            # 非阻塞获取访问许可
            await asyncio.wait_for(limiter.acquire(), timeout=0.01)
            return True
        except asyncio.TimeoutError:
            # 触发频率限制，应用惩罚
            logger.warning(f"窗口 {window_id} 触发频率限制")
            self._apply_rate_limit_penalty(window_id)
            return False
    
    def _apply_rate_limit_penalty(self, window_id: int):
        """应用频率限制惩罚"""
        if window_id not in self.window_penalties:
            self.window_penalties[window_id] = {}
        
        self.window_penalties[window_id]['blocked_until'] = time.time() + self.rate_limit_penalty
        
        until_str = time.strftime("%H:%M:%S", time.localtime(self.window_penalties[window_id]['blocked_until']))
        logger.warning(f"窗口 {window_id} 频率限制惩罚 {self.rate_limit_penalty}秒，解除时间: {until_str}")
    
    def mark_window_rate_limited(self, page: Page, duration_minutes: int = 6):
        """标记窗口为被频率限制状态（兼容旧接口）"""
        window_id = id(page)
        self._apply_rate_limit_penalty(window_id)
    
    def mark_window_login_required(self, page: Page):
        """标记窗口为需要登录状态"""
        window_id = id(page)
        if window_id not in self.window_penalties:
            self.window_penalties[window_id] = {}
        
        self.window_penalties[window_id]['login_required_until'] = time.time() + self.login_penalty
        logger.error(f"窗口 {window_id} 需要登录，{self.login_penalty}秒后重试")
    
    def mark_window_success(self, page: Page):
        """标记窗口成功访问，清除所有错误状态"""
        window_id = id(page)
        if window_id in self.window_penalties:
            del self.window_penalties[window_id]
        logger.debug(f"窗口 {window_id} 成功访问，清除所有限制")
    
    def _is_all_windows_limited(self) -> bool:
        """检查是否所有窗口都被限制"""
        total_windows = len(self.available_windows) + len(self.busy_windows)
        if total_windows == 0:
            return False
        
        current_time = time.time()
        limited_count = 0
        
        # 检查所有窗口状态
        all_window_ids = set()
        for page in self.available_windows:
            all_window_ids.add(id(page))
        for window_id in self.busy_windows.keys():
            all_window_ids.add(window_id)
        
        for window_id in all_window_ids:
            if window_id in self.window_penalties:
                penalties = self.window_penalties[window_id]
                # 检查是否仍在惩罚期内
                if (current_time < penalties.get('blocked_until', 0) or 
                    current_time < penalties.get('login_required_until', 0)):
                    limited_count += 1
        
        # 如果大部分窗口都被限制，认为全部受限
        return limited_count >= total_windows * 0.8
    
    def get_earliest_unblock_time(self) -> Optional[float]:
        """获取最早的窗口解禁时间
        
        Returns:
            float: 最早解禁的时间戳，如果没有被限制的窗口则返回None
        """
        if not self.window_penalties:
            return None
        
        current_time = time.time()
        earliest_time = None
        
        for window_id, penalties in self.window_penalties.items():
            blocked_until = penalties.get('blocked_until', 0)
            login_until = penalties.get('login_required_until', 0)
            
            # 取两个惩罚时间的最大值
            window_unblock_time = max(blocked_until, login_until)
            
            # 只考虑未来的时间
            if window_unblock_time > current_time:
                if earliest_time is None or window_unblock_time < earliest_time:
                    earliest_time = window_unblock_time
        
        return earliest_time
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """获取窗口状态详情（兼容旧接口）"""
        total_windows = len(self.available_windows) + len(self.busy_windows)
        current_time = time.time()
        
        blocked_count = 0
        login_required_count = 0
        
        for window_id, penalties in self.window_penalties.items():
            if current_time < penalties.get('blocked_until', 0):
                blocked_count += 1
            if current_time < penalties.get('login_required_until', 0):
                login_required_count += 1
        
        return {
            "total_windows": total_windows,
            "available_windows": total_windows - len(self.window_penalties),
            "rate_limited_count": blocked_count,
            "login_required_count": login_required_count,
            "all_rate_limited": self._is_all_windows_limited(),
            "all_login_required": login_required_count >= total_windows * 0.8,
            "percentage_limited": (blocked_count / total_windows * 100) if total_windows > 0 else 0,
            "percentage_login_required": (login_required_count / total_windows * 100) if total_windows > 0 else 0
        }

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
            self.patchright = await async_playwright().start()
            self.browser = await self.patchright.chromium.connect_over_cdp(ws_url)
            
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
        logger.debug(f"开始获取窗口，超时时间: {timeout}秒")
        
        # 确保窗口池已初始化
        if not self._initialized:
            logger.debug("窗口池未初始化，开始初始化")
            if not await self.initialize():
                logger.error("窗口池初始化失败")
                return None
            logger.debug("窗口池初始化完成")
        
        start_time = time.time()
        attempt = 0
        
        while True:
            attempt += 1
            logger.debug(f"第{attempt}次尝试获取窗口，已等待{time.time() - start_time:.2f}秒")
            
            async with self._lock:
                logger.debug(f"已获取窗口池锁，可用窗口数: {len(self.available_windows)}, 忙碌窗口数: {len(self.busy_windows)}")
                
                # 尝试获取可用窗口，使用aiolimiter检查限制
                checked_windows = []
                found_page = None
                
                while self.available_windows and not found_page:
                    page = self.available_windows.popleft()
                    window_id = id(page)

                    # 使用新的限流检查
                    if not await self._can_access_window(window_id):
                        # 窗口被限制，记录并继续查找
                        checked_windows.append(page)
                        logger.debug(f"窗口 {window_id} 被限制，跳过")
                        continue
                    
                    # 检查窗口是否仍然有效
                    try:
                        await page.evaluate("() => true")  # 简单的检查
                        # 检查URL，如果是about:blank或错误页面，导航到主页
                        current_url = page.url
                        if "about:blank" in current_url:
                            logger.info(f"窗口 {window_id} 处于空白页，导航到孔夫子网主页")
                            await page.goto("https://www.kongfz.com/", wait_until="domcontentloaded", timeout=10000)
                        
                        # 找到可用窗口
                        found_page = page
                        break
                    except:
                        # 窗口已失效，移除并创建新的
                        await self._remove_window_unsafe(page)
                        new_page = await self._create_window()
                        if new_page:
                            found_page = new_page
                            break
                
                # 将检查过但不可用的窗口放回队列
                for page in checked_windows:
                    self.available_windows.append(page)
                
                # 如果找到可用窗口，标记为忙碌并返回
                if found_page:
                    window_id = id(found_page)
                    self.busy_windows[window_id] = found_page
                    self.window_info[window_id]['used_count'] += 1
                    logger.debug(f"从池中获取窗口: {window_id}")
                    return found_page
                
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
                logger.warning(f"获取窗口超时（{timeout}秒），所有窗口都在使用中或被限制")
                return None
            
            # 检查是否所有窗口都被限制，如果是则提前返回
            if self._is_all_windows_limited():
                logger.warning("所有窗口都被限制，无法获取可用窗口")
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
                                await page.goto("https://www.kongfz.com/", wait_until="domcontentloaded", timeout=5000)
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
        
        # 断开patchright连接
        if self.patchright:
            await self.patchright.stop()
            self.patchright = None
            self.browser = None
        
        self.connected = False
        logger.info("已断开所有浏览器连接")
    
    def clear_window_login_required(self, page: Page):
        """清除窗口的登录错误状态（手动登录后调用）"""
        window_id = id(page)
        if window_id in self.window_penalties:
            penalties = self.window_penalties[window_id]
            penalties.pop('login_required_until', None)
            if not penalties:  # 如果没有其他惩罚，删除整个记录
                del self.window_penalties[window_id]
        logger.info(f"窗口 {window_id} 登录错误状态已清除")
    
    def get_available_window_count(self) -> int:
        """获取真正可用的窗口数量（排除被限制或需要登录的窗口）"""
        available_count = 0
        current_time = time.time()
        
        for page in self.available_windows:
            window_id = id(page)
            # 检查是否被惩罚
            if window_id in self.window_penalties:
                penalties = self.window_penalties[window_id]
                if (current_time < penalties.get('blocked_until', 0) or 
                    current_time < penalties.get('login_required_until', 0)):
                    continue
            available_count += 1
        
        return available_count
    
    def get_pool_status(self) -> Dict[str, Any]:
        """获取窗口池状态"""
        current_time = time.time()
        window_details = []
        
        for window_id, info in self.window_info.items():
            status = "busy" if window_id in self.busy_windows else "available"
            
            # 检查惩罚状态
            penalties = self.window_penalties.get(window_id, {})
            is_rate_limited = current_time < penalties.get('blocked_until', 0)
            is_login_required = current_time < penalties.get('login_required_until', 0)
            
            # 判断窗口实际状态
            if is_login_required:
                actual_status = "需要登录"
            elif is_rate_limited:
                actual_status = "频率限制"
            elif status == "busy":
                actual_status = "使用中"
            else:
                actual_status = "可用"
            
            window_details.append({
                "window_id": window_id,
                "status": status,
                "actual_status": actual_status,
                "is_rate_limited": is_rate_limited,
                "is_login_required": is_login_required,
                "blocked_until": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(penalties.get('blocked_until', 0))) if penalties.get('blocked_until', 0) > 0 else None,
                "login_required_until": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(penalties.get('login_required_until', 0))) if penalties.get('login_required_until', 0) > 0 else None,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(info['created_at'])),
                "used_count": info['used_count']
            })
        
        # 获取封控状态
        rate_limit_status = self.get_rate_limit_status()
        
        return {
            "connected": self.connected,
            "initialized": self._initialized,
            "pool_size": self.pool_size,
            "available_count": len(self.available_windows),
            "busy_count": len(self.busy_windows),
            "total_windows": len(self.available_windows) + len(self.busy_windows),
            "rate_limit_status": rate_limit_status,
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
            logger.debug(f"开始执行窗口管理器装饰的函数: {func.__name__}")
            
            # 获取窗口
            logger.debug("开始获取窗口")
            page = await self.pool.get_window()
            if not page:
                logger.error("无法获取可用的浏览器窗口")
                raise Exception("无法获取可用的浏览器窗口，请稍后重试")
            
            window_id = id(page)
            logger.debug(f"获取到窗口 {window_id}，开始执行函数")
            
            try:
                # 将page注入到函数参数中
                kwargs['page'] = page
                logger.debug(f"开始执行函数 {func.__name__}")
                result = await func(*args, **kwargs)
                logger.debug(f"函数 {func.__name__} 执行成功")
                
                # 成功完成，标记窗口为成功状态
                self.pool.mark_window_success(page)
                return result
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"函数 {func.__name__} 执行出错: {error_msg}")
                
                # 区分处理不同类型的错误
                if "LOGIN_REQUIRED:" in error_msg:
                    logger.warning(f"窗口 {window_id} 需要登录")
                    # 登录错误：标记窗口为需要登录状态
                    self.pool.mark_window_login_required(page)
                    
                    # 检查是否所有窗口都需要登录
                    if self.pool.is_all_windows_login_required():
                        logger.error("所有窗口都需要登录，爬虫服务停止运行")
                        raise Exception("ALL_WINDOWS_LOGIN_REQUIRED:所有窗口都需要登录，请在浏览器中登录后重试")
                
                elif "RATE_LIMITED:" in error_msg:
                    logger.warning(f"窗口 {window_id} 被频率限制")
                    # 频率限制错误：标记窗口为频率限制状态
                    self.pool.mark_window_rate_limited(page, duration_minutes=6)
                    
                    # 检查是否所有窗口都被频率限制
                    if self.pool._is_all_windows_limited():
                        logger.warning("所有窗口都被频率限制，等待6分钟后重试")
                        # 不要阻塞主线程，直接重新抛出原始异常
                        pass
                
                raise  # 重新抛出异常
                
            finally:
                logger.debug(f"开始归还窗口 {window_id}")
                # 归还窗口，默认保持存活状态
                await self.pool.return_window(page, keep_alive=self.keep_window_alive)
                logger.debug(f"窗口 {window_id} 已归还")
        
        return wrapper