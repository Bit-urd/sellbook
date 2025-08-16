#!/usr/bin/env python3
"""
AutonomousSessionManager核心逻辑单元测试
重点测试会话管理、网站状态管理等核心功能，避免测试外部依赖
"""
import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from dataclasses import asdict

from src.services.autonomous_session_manager import (
    AutonomousSessionManager,
    SiteStatus,
    SiteState, 
    WindowSession,
    TaskRequest,
    TaskStatus
)


class TestSiteState:
    """SiteState单元测试"""
    
    def test_site_state_initialization(self):
        """测试网站状态初始化"""
        site_state = SiteState("kongfuzi")
        
        assert site_state.site_name == "kongfuzi"
        assert site_state.status == SiteStatus.AVAILABLE
        assert site_state.blocked_until == 0
        assert site_state.error_count == 0
        assert site_state.last_success_time == 0
        assert site_state.last_error_message == ""
    
    def test_is_available_when_available(self):
        """测试可用状态检查"""
        site_state = SiteState("kongfuzi")
        assert site_state.is_available() is True
    
    def test_is_available_when_rate_limited_not_expired(self):
        """测试频率限制未过期时不可用"""
        site_state = SiteState("kongfuzi")
        site_state.mark_rate_limited(6)  # 6分钟后解封
        
        assert site_state.is_available() is False
        assert site_state.status == SiteStatus.RATE_LIMITED
    
    def test_is_available_when_rate_limited_expired(self):
        """测试频率限制过期后自动恢复可用"""
        site_state = SiteState("kongfuzi")
        
        # 模拟已过期的限制
        site_state.status = SiteStatus.RATE_LIMITED
        site_state.blocked_until = time.time() - 10  # 10秒前就该解封了
        
        assert site_state.is_available() is True
        assert site_state.status == SiteStatus.AVAILABLE
        assert site_state.blocked_until == 0
    
    def test_mark_rate_limited(self):
        """测试标记频率限制"""
        site_state = SiteState("kongfuzi")
        
        before_time = time.time()
        site_state.mark_rate_limited(6)
        after_time = time.time()
        
        assert site_state.status == SiteStatus.RATE_LIMITED
        assert site_state.error_count == 1
        # 验证解封时间在合理范围内（6分钟后）
        assert before_time + 6*60 <= site_state.blocked_until <= after_time + 6*60
    
    def test_mark_login_required(self):
        """测试标记需要登录"""
        site_state = SiteState("kongfuzi")
        site_state.mark_login_required()
        
        assert site_state.status == SiteStatus.LOGIN_REQUIRED
        assert site_state.error_count == 1
    
    def test_mark_success(self):
        """测试标记成功访问"""
        site_state = SiteState("kongfuzi")
        # 先设置一些错误状态
        site_state.status = SiteStatus.ERROR
        site_state.error_count = 3
        site_state.blocked_until = time.time() + 100
        site_state.last_error_message = "测试错误"
        
        before_time = time.time()
        site_state.mark_success()
        after_time = time.time()
        
        assert site_state.status == SiteStatus.AVAILABLE
        assert site_state.blocked_until == 0
        assert site_state.error_count == 0
        assert site_state.last_error_message == ""
        assert before_time <= site_state.last_success_time <= after_time
    
    def test_mark_error(self):
        """测试标记错误"""
        site_state = SiteState("kongfuzi")
        error_message = "网络连接错误"
        
        site_state.mark_error(error_message)
        
        assert site_state.status == SiteStatus.ERROR
        assert site_state.error_count == 1
        assert site_state.last_error_message == error_message


class TestWindowSession:
    """WindowSession单元测试"""
    
    def test_window_session_initialization(self):
        """测试窗口会话初始化"""
        mock_page = Mock()
        mock_context = Mock()
        
        session = WindowSession(
            window_id="test_window_1",
            page=mock_page,
            context=mock_context,
            account_name="test_account"
        )
        
        assert session.window_id == "test_window_1"
        assert session.page == mock_page
        assert session.context == mock_context
        assert session.account_name == "test_account"
        assert session.is_busy is False
        assert isinstance(session.created_at, float)
        assert len(session.sites) == 0
    
    def test_get_site_state_new_site(self):
        """测试获取新网站状态"""
        mock_page = Mock()
        mock_context = Mock()
        session = WindowSession("test_window", mock_page, mock_context)
        
        site_state = session.get_site_state("kongfuzi")
        
        assert isinstance(site_state, SiteState)
        assert site_state.site_name == "kongfuzi"
        assert site_state.status == SiteStatus.AVAILABLE
        assert "kongfuzi" in session.sites
    
    def test_get_site_state_existing_site(self):
        """测试获取已存在网站状态"""
        mock_page = Mock()
        mock_context = Mock()
        session = WindowSession("test_window", mock_page, mock_context)
        
        # 先创建一个网站状态并修改
        site_state1 = session.get_site_state("kongfuzi")
        site_state1.error_count = 5
        
        # 再次获取应该是同一个对象
        site_state2 = session.get_site_state("kongfuzi")
        
        assert site_state1 is site_state2
        assert site_state2.error_count == 5
    
    def test_is_site_available(self):
        """测试检查网站是否可用"""
        mock_page = Mock()
        mock_context = Mock()
        session = WindowSession("test_window", mock_page, mock_context)
        
        # 新网站应该可用
        assert session.is_site_available("kongfuzi") is True
        
        # 标记为频率限制后不可用
        site_state = session.get_site_state("kongfuzi")
        site_state.mark_rate_limited(6)
        assert session.is_site_available("kongfuzi") is False
    
    def test_get_available_sites(self):
        """测试获取可用网站列表"""
        mock_page = Mock()
        mock_context = Mock()
        session = WindowSession("test_window", mock_page, mock_context)
        
        # 添加多个网站，设置不同状态
        session.get_site_state("kongfuzi")  # 默认可用
        session.get_site_state("duozhuayu")  # 默认可用
        session.get_site_state("taobao")     # 将设为不可用
        
        # 设置taobao为不可用
        session.get_site_state("taobao").mark_rate_limited(6)
        
        available_sites = session.get_available_sites()
        
        assert len(available_sites) == 2
        assert "kongfuzi" in available_sites
        assert "duozhuayu" in available_sites
        assert "taobao" not in available_sites


class TestTaskRequest:
    """TaskRequest单元测试"""
    
    def test_task_request_initialization(self):
        """测试任务请求初始化"""
        task = TaskRequest(
            task_id=123,
            task_type="book_sales_crawl",
            target_platform="kongfuzi",
            params={"isbn": "9787544291200"}
        )
        
        assert task.task_id == 123
        assert task.task_type == "book_sales_crawl"
        assert task.target_platform == "kongfuzi"
        assert task.params == {"isbn": "9787544291200"}
        assert task.priority == 5  # 默认值
        assert task.status == TaskStatus.QUEUED
        assert isinstance(task.created_at, float)


class TestAutonomousSessionManager:
    """AutonomousSessionManager核心逻辑测试（不涉及外部依赖）"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        # 创建管理器但不自动启动
        with patch.object(AutonomousSessionManager, '_auto_start'):
            self.manager = AutonomousSessionManager(max_windows=2)
    
    def test_initialization(self):
        """测试管理器初始化"""
        assert self.manager.max_windows == 2
        assert len(self.manager.sessions) == 0
        assert len(self.manager.available_sessions) == 0
        assert len(self.manager.busy_sessions) == 0
        assert self.manager.connected is False
        assert self.manager._running is False
        assert self.manager._initialized is False
    
    def test_identify_site_from_task_by_function_name(self):
        """测试通过函数名识别网站类型"""
        # 模拟函数对象
        def kongfuzi_crawl_function():
            pass
        
        def duozhuayu_price_function():
            pass
        
        def unknown_function():
            pass
        
        # 测试识别
        site1 = self.manager.identify_site_from_task(kongfuzi_crawl_function, {})
        site2 = self.manager.identify_site_from_task(duozhuayu_price_function, {})
        site3 = self.manager.identify_site_from_task(unknown_function, {})
        
        assert site1 == 'kongfuzi'
        assert site2 == 'duozhuayu'
        assert site3 == 'unknown'
    
    def test_identify_site_from_task_by_params(self):
        """测试通过参数识别网站类型"""
        def dummy_function():
            pass
        
        # 测试URL参数识别
        params1 = {'target_url': 'https://www.kongfz.com/book/123'}
        params2 = {'url': 'https://www.duozhuayu.com/book/456'}
        params3 = {'link': 'https://www.taobao.com/item/789'}
        params4 = {'data': 'some other data'}
        
        site1 = self.manager.identify_site_from_task(dummy_function, params1)
        site2 = self.manager.identify_site_from_task(dummy_function, params2)
        site3 = self.manager.identify_site_from_task(dummy_function, params3)
        site4 = self.manager.identify_site_from_task(dummy_function, params4)
        
        assert site1 == 'kongfuzi'
        assert site2 == 'duozhuayu'
        assert site3 == 'taobao'
        assert site4 == 'unknown'
    
    def test_can_handle_task_no_sessions(self):
        """测试没有会话时无法处理任务"""
        task = TaskRequest(
            task_id=1,
            task_type="book_sales_crawl",
            target_platform="kongfuzi",
            params={}
        )
        
        assert self.manager._can_handle_task(task) is False
    
    def test_can_handle_task_with_available_session(self):
        """测试有可用会话时可以处理任务"""
        # 创建模拟会话
        mock_page = Mock()
        mock_context = Mock()
        session = WindowSession("test_window", mock_page, mock_context)
        
        # 添加到管理器
        self.manager.sessions["test_window"] = session
        self.manager.available_sessions.add("test_window")
        
        task = TaskRequest(
            task_id=1,
            task_type="book_sales_crawl", 
            target_platform="kongfuzi",
            params={}
        )
        
        assert self.manager._can_handle_task(task) is True
    
    def test_can_handle_task_with_unavailable_session(self):
        """测试会话不可用时无法处理任务"""
        # 创建模拟会话并设置网站为不可用
        mock_page = Mock()
        mock_context = Mock()
        session = WindowSession("test_window", mock_page, mock_context)
        session.get_site_state("kongfuzi").mark_rate_limited(6)
        
        # 添加到管理器
        self.manager.sessions["test_window"] = session
        self.manager.available_sessions.add("test_window")
        
        task = TaskRequest(
            task_id=1,
            task_type="book_sales_crawl",
            target_platform="kongfuzi", 
            params={}
        )
        
        assert self.manager._can_handle_task(task) is False
    
    @pytest.mark.asyncio
    async def test_get_session_for_platform_success(self):
        """测试成功获取平台会话"""
        # 创建模拟会话
        mock_page = Mock()
        mock_context = Mock()
        session = WindowSession("test_window", mock_page, mock_context)
        
        # 添加到管理器
        self.manager.sessions["test_window"] = session
        self.manager.available_sessions.add("test_window")
        
        # 获取会话
        result_session = await self.manager._get_session_for_platform("kongfuzi")
        
        assert result_session is session
        assert session.is_busy is True
        assert "test_window" in self.manager.busy_sessions
        assert "test_window" not in self.manager.available_sessions
    
    @pytest.mark.asyncio
    async def test_get_session_for_platform_no_available(self):
        """测试没有可用会话时返回None"""
        result_session = await self.manager._get_session_for_platform("kongfuzi")
        assert result_session is None
    
    @pytest.mark.asyncio
    async def test_return_session(self):
        """测试归还会话"""
        # 创建模拟会话
        mock_page = Mock()
        mock_context = Mock()
        session = WindowSession("test_window", mock_page, mock_context)
        session.is_busy = True
        
        # 添加到忙碌会话集合
        self.manager.sessions["test_window"] = session
        self.manager.busy_sessions.add("test_window")
        
        # 归还会话
        await self.manager._return_session(session)
        
        assert session.is_busy is False
        assert "test_window" in self.manager.available_sessions
        assert "test_window" not in self.manager.busy_sessions
    
    def test_handle_task_error_rate_limited(self):
        """测试处理频率限制错误"""
        mock_page = Mock()
        mock_context = Mock()
        session = WindowSession("test_window", mock_page, mock_context)
        
        # 模拟调用 - 使用同步方法测试
        error_msg = "rate limited by server"
        
        # 直接调用私有方法测试逻辑
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                self.manager._handle_task_error(session, "kongfuzi", error_msg)
            )
        finally:
            loop.close()
        
        site_state = session.get_site_state("kongfuzi")
        assert site_state.status == SiteStatus.RATE_LIMITED
    
    def test_handle_task_error_login_required(self):
        """测试处理登录错误"""
        mock_page = Mock()
        mock_context = Mock()
        session = WindowSession("test_window", mock_page, mock_context)
        
        error_msg = "login required to access"
        
        # 直接调用逻辑测试
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                self.manager._handle_task_error(session, "kongfuzi", error_msg)
            )
        finally:
            loop.close()
        
        site_state = session.get_site_state("kongfuzi")
        assert site_state.status == SiteStatus.LOGIN_REQUIRED
    
    def test_handle_task_error_general(self):
        """测试处理一般错误"""
        mock_page = Mock()
        mock_context = Mock()
        session = WindowSession("test_window", mock_page, mock_context)
        
        error_msg = "network connection failed"
        
        # 直接调用逻辑测试
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                self.manager._handle_task_error(session, "kongfuzi", error_msg)
            )
        finally:
            loop.close()
        
        site_state = session.get_site_state("kongfuzi")
        assert site_state.status == SiteStatus.ERROR
        assert site_state.last_error_message == error_msg
    
    @pytest.mark.asyncio
    async def test_get_status_basic(self):
        """测试获取基本状态（不触发启动）"""
        # 绕过自动启动逻辑，直接测试状态生成
        self.manager._initialized = True
        
        # 添加一些模拟会话
        mock_page1 = Mock()
        mock_context1 = Mock()
        session1 = WindowSession("window1", mock_page1, mock_context1)
        session1.get_site_state("kongfuzi")
        
        mock_page2 = Mock()
        mock_context2 = Mock()
        session2 = WindowSession("window2", mock_page2, mock_context2)
        session2.get_site_state("duozhuayu")
        session2.is_busy = True
        
        self.manager.sessions["window1"] = session1
        self.manager.sessions["window2"] = session2
        self.manager.available_sessions.add("window1")
        self.manager.busy_sessions.add("window2")
        
        # 模拟一些统计数据
        self.manager.stats = {
            "tasks_processed": 10,
            "tasks_completed": 8,
            "tasks_failed": 2,
            "tasks_rejected": 0,
            "last_activity": time.time()
        }
        
        # 获取状态
        with patch.object(self.manager, '_ensure_started', new_callable=AsyncMock) as mock_ensure:
            mock_ensure.return_value = True
            
            status = await self.manager.get_status()
        
        # 验证基本状态
        assert status["running"] is False
        assert status["connected"] is False
        assert status["total_windows"] == 2
        assert status["available_windows"] == 1
        assert status["busy_windows"] == 1
        assert status["queue_size"] == 0
        assert status["processing_tasks"] == 0
        
        # 验证平台可用性
        assert status["available_by_platform"]["kongfuzi"] == 1
        assert status["available_by_platform"]["duozhuayu"] == 0
        
        # 验证统计信息
        assert status["statistics"]["tasks_processed"] == 10
        assert status["statistics"]["tasks_completed"] == 8
        
        # 验证会话详情
        assert len(status["sessions"]) == 2
        session_details = {s["window_id"]: s for s in status["sessions"]}
        assert session_details["window1"]["is_busy"] is False
        assert session_details["window2"]["is_busy"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])