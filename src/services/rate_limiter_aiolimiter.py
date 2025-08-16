#!/usr/bin/env python3
"""
使用aiolimiter的窗口限流器
"""
import asyncio
import time
import logging
from typing import Dict, Optional
from aiolimiter import AsyncLimiter

logger = logging.getLogger(__name__)

class WindowRateLimiter:
    """基于aiolimiter的窗口访问限流器"""
    
    def __init__(self):
        # 为每个窗口创建独立的限流器
        self.window_limiters: Dict[int, AsyncLimiter] = {}
        self.window_status: Dict[int, Dict] = {}  # 窗口状态
        self.lock = asyncio.Lock()
        
        # 默认配置：每60秒最多10个请求
        self.max_rate = 10
        self.time_period = 60
        
        # 惩罚配置
        self.penalty_duration = 6 * 60  # 6分钟惩罚
        self.login_check_interval = 30  # 30秒后重试登录
    
    async def get_limiter(self, window_id: int) -> AsyncLimiter:
        """获取窗口对应的限流器"""
        if window_id not in self.window_limiters:
            # 每个窗口独立限流：60秒内最多10个请求
            self.window_limiters[window_id] = AsyncLimiter(
                max_rate=self.max_rate, 
                time_period=self.time_period
            )
            self.window_status[window_id] = {
                "blocked_until": 0,
                "login_required": False,
                "penalty_count": 0
            }
        return self.window_limiters[window_id]
    
    async def can_access(self, window_id: int) -> bool:
        """检查窗口是否可以访问"""
        current_time = time.time()
        
        # 检查是否被手动阻塞
        if window_id in self.window_status:
            status = self.window_status[window_id]
            if current_time < status.get("blocked_until", 0):
                remaining = status["blocked_until"] - current_time
                logger.debug(f"窗口 {window_id} 被阻塞，剩余 {remaining:.1f}秒")
                return False
            
            if status.get("login_required", False):
                if current_time < status.get("login_check_time", 0):
                    remaining = status["login_check_time"] - current_time
                    logger.debug(f"窗口 {window_id} 需要登录，{remaining:.1f}秒后重试")
                    return False
                else:
                    # 登录检查时间已过，清除登录要求状态
                    status["login_required"] = False
        
        # 使用aiolimiter检查频率限制
        limiter = await self.get_limiter(window_id)
        
        # 尝试获取访问许可（非阻塞）
        try:
            await asyncio.wait_for(limiter.acquire(), timeout=0.01)
            return True
        except asyncio.TimeoutError:
            # 触发频率限制
            logger.warning(f"窗口 {window_id} 触发频率限制")
            await self.apply_rate_limit_penalty(window_id)
            return False
    
    async def apply_rate_limit_penalty(self, window_id: int):
        """应用频率限制惩罚"""
        async with self.lock:
            if window_id not in self.window_status:
                self.window_status[window_id] = {"penalty_count": 0}
            
            # 增加惩罚计数和时间
            self.window_status[window_id]["penalty_count"] += 1
            penalty_multiplier = min(self.window_status[window_id]["penalty_count"], 3)
            penalty_duration = self.penalty_duration * penalty_multiplier
            
            self.window_status[window_id]["blocked_until"] = time.time() + penalty_duration
            
            until_str = time.strftime("%H:%M:%S", time.localtime(self.window_status[window_id]["blocked_until"]))
            logger.warning(f"窗口 {window_id} 频率限制惩罚 {penalty_duration}秒，解除时间: {until_str}")
    
    async def mark_login_required(self, window_id: int):
        """标记窗口需要登录"""
        async with self.lock:
            if window_id not in self.window_status:
                self.window_status[window_id] = {}
            
            self.window_status[window_id]["login_required"] = True
            self.window_status[window_id]["login_check_time"] = time.time() + self.login_check_interval
            
            logger.error(f"窗口 {window_id} 需要登录，{self.login_check_interval}秒后重试")
    
    async def clear_restrictions(self, window_id: int):
        """清除窗口所有限制"""
        async with self.lock:
            if window_id in self.window_status:
                self.window_status[window_id] = {"penalty_count": 0}
            logger.info(f"清除窗口 {window_id} 所有限制")
    
    def get_stats(self) -> Dict:
        """获取限流器统计"""
        current_time = time.time()
        blocked_windows = {}
        login_required_windows = {}
        
        for window_id, status in self.window_status.items():
            if current_time < status.get("blocked_until", 0):
                remaining = status["blocked_until"] - current_time
                blocked_windows[window_id] = {
                    "remaining_seconds": remaining,
                    "penalty_count": status.get("penalty_count", 0)
                }
            
            if status.get("login_required", False):
                remaining = max(0, status.get("login_check_time", 0) - current_time)
                login_required_windows[window_id] = {
                    "remaining_seconds": remaining
                }
        
        return {
            "total_windows": len(self.window_limiters),
            "blocked_windows": blocked_windows,
            "login_required_windows": login_required_windows,
            "rate_config": {
                "max_rate": self.max_rate,
                "time_period": self.time_period,
                "penalty_duration": self.penalty_duration
            }
        }

# 全局限流器实例
window_rate_limiter = WindowRateLimiter()