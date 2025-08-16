#!/usr/bin/env python3
"""
限流器模块 - 替代窗口池的复杂状态管理
"""
import asyncio
import time
import logging
from typing import Dict, Optional
from enum import Enum

logger = logging.getLogger(__name__)

class LimitType(Enum):
    """限制类型"""
    RATE_LIMIT = "rate_limit"  # 频率限制
    LOGIN_REQUIRED = "login_required"  # 需要登录
    BLOCKED = "blocked"  # 被封锁

class RateLimiter:
    """智能限流器 - 管理窗口访问频率和状态"""
    
    def __init__(self):
        self.window_limits: Dict[int, Dict] = {}  # {window_id: {"type": LimitType, "until": timestamp, "count": int}}
        self.access_history: Dict[int, list] = {}  # {window_id: [timestamp1, timestamp2, ...]}
        self.lock = asyncio.Lock()
        
        # 配置参数
        self.rate_limit_window = 60  # 60秒时间窗口
        self.max_requests_per_window = 10  # 每60秒最多10个请求
        self.rate_limit_penalty = 6 * 60  # 频率限制惩罚时间6分钟
        self.login_check_interval = 30  # 登录状态检查间隔30秒
    
    async def can_access_window(self, window_id: int) -> bool:
        """检查窗口是否可以访问"""
        async with self.lock:
            current_time = time.time()
            
            # 检查是否有活跃限制
            if window_id in self.window_limits:
                limit_info = self.window_limits[window_id]
                if current_time < limit_info["until"]:
                    # 仍在限制期内
                    remaining = limit_info["until"] - current_time
                    logger.debug(f"窗口 {window_id} 仍被限制 ({limit_info['type'].value})，剩余 {remaining:.1f}秒")
                    return False
                else:
                    # 限制期已过，清除限制
                    del self.window_limits[window_id]
                    logger.info(f"窗口 {window_id} 限制已解除")
            
            # 检查访问频率
            if not self._check_rate_limit(window_id, current_time):
                return False
            
            return True
    
    def _check_rate_limit(self, window_id: int, current_time: float) -> bool:
        """检查访问频率是否超限"""
        if window_id not in self.access_history:
            self.access_history[window_id] = []
        
        # 清理过期的访问记录（超过时间窗口的记录）
        cutoff_time = current_time - self.rate_limit_window
        self.access_history[window_id] = [
            t for t in self.access_history[window_id] if t > cutoff_time
        ]
        
        # 检查是否超过限制
        if len(self.access_history[window_id]) >= self.max_requests_per_window:
            # 触发频率限制
            self.apply_rate_limit(window_id, self.rate_limit_penalty)
            logger.warning(f"窗口 {window_id} 触发频率限制，{self.rate_limit_window}秒内请求次数: {len(self.access_history[window_id])}")
            return False
        
        return True
    
    async def record_access(self, window_id: int):
        """记录窗口访问"""
        async with self.lock:
            current_time = time.time()
            if window_id not in self.access_history:
                self.access_history[window_id] = []
            self.access_history[window_id].append(current_time)
            logger.debug(f"记录窗口 {window_id} 访问，当前时间窗口内访问次数: {len(self.access_history[window_id])}")
    
    def apply_rate_limit(self, window_id: int, duration_seconds: int = None):
        """应用频率限制"""
        duration = duration_seconds or self.rate_limit_penalty
        until_time = time.time() + duration
        
        self.window_limits[window_id] = {
            "type": LimitType.RATE_LIMIT,
            "until": until_time,
            "count": self.window_limits.get(window_id, {}).get("count", 0) + 1
        }
        
        until_str = time.strftime("%H:%M:%S", time.localtime(until_time))
        logger.warning(f"窗口 {window_id} 被频率限制，解除时间: {until_str}")
    
    def apply_login_required(self, window_id: int):
        """标记窗口需要登录"""
        # 登录问题比频率限制更严重，设置较长的检查间隔
        until_time = time.time() + self.login_check_interval
        
        self.window_limits[window_id] = {
            "type": LimitType.LOGIN_REQUIRED,
            "until": until_time,
            "count": self.window_limits.get(window_id, {}).get("count", 0) + 1
        }
        
        logger.error(f"窗口 {window_id} 需要登录，{self.login_check_interval}秒后重新检查")
    
    def clear_limit(self, window_id: int):
        """清除窗口限制（手动恢复）"""
        if window_id in self.window_limits:
            limit_type = self.window_limits[window_id]["type"]
            del self.window_limits[window_id]
            logger.info(f"手动清除窗口 {window_id} 的限制 ({limit_type.value})")
    
    def get_limited_windows(self) -> Dict[int, Dict]:
        """获取当前被限制的窗口"""
        current_time = time.time()
        active_limits = {}
        
        for window_id, limit_info in self.window_limits.items():
            if current_time < limit_info["until"]:
                remaining = limit_info["until"] - current_time
                active_limits[window_id] = {
                    "type": limit_info["type"].value,
                    "remaining_seconds": remaining,
                    "until_time": time.strftime("%H:%M:%S", time.localtime(limit_info["until"])),
                    "count": limit_info["count"]
                }
        
        return active_limits
    
    def get_stats(self) -> Dict:
        """获取限流器统计信息"""
        current_time = time.time()
        active_limits = self.get_limited_windows()
        
        # 统计访问频率
        total_recent_requests = 0
        for window_id, history in self.access_history.items():
            cutoff_time = current_time - self.rate_limit_window
            recent_requests = len([t for t in history if t > cutoff_time])
            total_recent_requests += recent_requests
        
        return {
            "total_windows_tracked": len(self.access_history),
            "limited_windows_count": len(active_limits),
            "limited_windows": active_limits,
            "total_recent_requests": total_recent_requests,
            "rate_limit_window": self.rate_limit_window,
            "max_requests_per_window": self.max_requests_per_window
        }

# 全局限流器实例
rate_limiter = RateLimiter()