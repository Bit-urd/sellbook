/**
 * 公共组件 - 封控状态显示
 */

class RateLimitStatusComponent {
    constructor(containerId = 'rateLimitStatusContainer') {
        this.containerId = containerId;
        this.updateInterval = null;
        this.isVisible = false;
        this.isDragging = false;
        this.dragOffset = { x: 0, y: 0 };
        this.position = { x: 20, y: 20 }; // 默认位置 (right: 20px, top: 20px)
    }

    /**
     * 初始化组件
     */
    init() {
        // 加载保存的位置
        this.loadPosition();
        this.createStatusContainer();
        this.startPeriodicUpdate();
        
        // 页面卸载时清理
        window.addEventListener('beforeunload', () => {
            this.destroy();
        });
    }

    /**
     * 创建状态显示容器
     */
    createStatusContainer() {
        // 检查容器是否已存在
        let container = document.getElementById(this.containerId);
        if (!container) {
            container = document.createElement('div');
            container.id = this.containerId;
            document.body.appendChild(container);
        }

        // 设置容器样式 - 常驻浮动可拖拽
        container.style.cssText = `
            position: fixed;
            top: ${this.position.y}px;
            right: ${this.position.x}px;
            z-index: 9999;
            padding: 12px 16px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            font-size: 14px;
            min-width: 200px;
            transition: box-shadow 0.3s ease, transform 0.3s ease;
            display: block;
            cursor: move;
            user-select: none;
            opacity: 0.9;
        `;

        // 添加拖拽功能
        this.addDragFunctionality(container);

        this.container = container;
    }

    /**
     * 添加拖拽功能
     */
    addDragFunctionality(container) {
        let startX, startY, initialLeft, initialTop;
        let isDragging = false;

        const startDrag = (e) => {
            isDragging = true;
            
            // 支持鼠标和触摸事件
            const clientX = e.clientX || (e.touches && e.touches[0].clientX);
            const clientY = e.clientY || (e.touches && e.touches[0].clientY);
            
            startX = clientX;
            startY = clientY;
            
            // 获取当前位置 - 改用left和top，更直观
            const rect = container.getBoundingClientRect();
            initialLeft = rect.left;
            initialTop = rect.top;
            
            // 改变样式表示正在拖拽
            container.style.opacity = '1';
            container.style.boxShadow = '0 8px 25px rgba(0, 0, 0, 0.3)';
            container.style.transform = 'scale(1.05)';
            container.style.zIndex = '10000';
            
            e.preventDefault();
        };

        const doDrag = (e) => {
            if (!isDragging) return;
            
            const clientX = e.clientX || (e.touches && e.touches[0].clientX);
            const clientY = e.clientY || (e.touches && e.touches[0].clientY);
            
            const deltaX = clientX - startX;
            const deltaY = clientY - startY;
            
            let newLeft = initialLeft + deltaX;
            let newTop = initialTop + deltaY;
            
            // 边界限制
            const maxLeft = window.innerWidth - container.offsetWidth - 10;
            const maxTop = window.innerHeight - container.offsetHeight - 10;
            
            newLeft = Math.max(10, Math.min(newLeft, maxLeft));
            newTop = Math.max(10, Math.min(newTop, maxTop));
            
            // 使用left和top定位，清除right定位
            container.style.left = newLeft + 'px';
            container.style.top = newTop + 'px';
            container.style.right = 'auto';
            
            e.preventDefault();
        };

        const endDrag = () => {
            if (isDragging) {
                isDragging = false;
                
                // 恢复样式
                container.style.opacity = '0.9';
                container.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.15)';
                container.style.transform = 'scale(1)';
                container.style.zIndex = '9999';
                
                // 保存位置
                this.position.x = parseInt(container.style.left);
                this.position.y = parseInt(container.style.top);
                this.savePosition();
            }
        };

        // 鼠标事件
        container.addEventListener('mousedown', startDrag);
        document.addEventListener('mousemove', doDrag);
        document.addEventListener('mouseup', endDrag);
        
        // 触摸事件（移动端支持）
        container.addEventListener('touchstart', startDrag, { passive: false });
        document.addEventListener('touchmove', doDrag, { passive: false });
        document.addEventListener('touchend', endDrag);
        
        // 鼠标悬停效果
        container.addEventListener('mouseenter', () => {
            if (!isDragging) {
                container.style.opacity = '1';
                container.style.transform = 'scale(1.02)';
            }
        });
        
        container.addEventListener('mouseleave', () => {
            if (!isDragging) {
                container.style.opacity = '0.9';
                container.style.transform = 'scale(1)';
            }
        });
    }

    /**
     * 保存位置到本地存储
     */
    savePosition() {
        localStorage.setItem('crawlerStatusPosition', JSON.stringify(this.position));
    }

    /**
     * 从本地存储加载位置
     */
    loadPosition() {
        const saved = localStorage.getItem('crawlerStatusPosition');
        if (saved) {
            try {
                this.position = JSON.parse(saved);
            } catch (e) {
                console.warn('加载位置信息失败:', e);
            }
        }
    }

    /**
     * 更新状态显示
     */
    async updateStatus() {
        try {
            const response = await fetch('/sales-data/crawler/rate-limit-status');
            const data = await response.json();

            if (data.success) {
                // 先检查窗口池状态
                await this.checkWindowPoolStatus(data.data);
            }
        } catch (error) {
            console.warn('获取封控状态失败:', error);
            // 网络错误时显示离线状态而不是隐藏组件
            this.showOfflineStatus();
        }
    }

    /**
     * 检查窗口池状态
     */
    async checkWindowPoolStatus(rateLimitStatus) {
        try {
            const poolResponse = await fetch('/window-pool/status');
            const poolData = await poolResponse.json();

            if (poolData.success && poolData.data) {
                const { connected, initialized, total_windows } = poolData.data;
                
                // 如果窗口池未就绪，显示初始化状态
                if (!connected || !initialized || total_windows === 0) {
                    this.showInitializationStatus(connected, initialized, total_windows);
                    return;
                }
            }
            
            // 窗口池正常，显示封控状态
            this.displayStatus(rateLimitStatus);
        } catch (error) {
            console.warn('获取窗口池状态失败:', error);
            // 如果无法获取窗口池状态，仍然显示封控状态
            this.displayStatus(rateLimitStatus);
        }
    }

    /**
     * 显示状态信息
     */
    displayStatus(status) {
        if (!this.container) return;

        const { is_rate_limited, current_wait_time, next_wait_time } = status;
        // 向后兼容旧格式
        const currentTimeText = current_wait_time?.display_text || `${status.current_wait_time_minutes}分钟`;
        const nextTimeText = next_wait_time?.display_text || `${status.next_wait_time_minutes}分钟`;

        if (is_rate_limited) {
            // 显示封控状态
            this.container.style.background = 'linear-gradient(135deg, #ff6b6b, #ee5a24)';
            this.container.style.color = 'white';
            this.container.style.border = '1px solid rgba(255, 255, 255, 0.2)';
            this.container.style.display = 'block';

            this.container.innerHTML = `
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div style="
                        width: 10px; 
                        height: 10px; 
                        background: white; 
                        border-radius: 50%;
                        animation: pulse 2s infinite;
                    "></div>
                    <div>
                        <div style="font-weight: 600; margin-bottom: 4px; font-size: 14px;">
                            🚫 系统封控中
                        </div>
                        <div style="font-size: 12px; opacity: 0.9;">
                            剩余等待时间: ${currentTimeText}
                        </div>
                    </div>
                    <div style="
                        position: absolute; 
                        top: -2px; 
                        right: -2px; 
                        width: 8px; 
                        height: 8px; 
                        background: #ff4444; 
                        border-radius: 50%; 
                        border: 2px solid white;
                        animation: blink 1s infinite;
                    "></div>
                </div>
                <style>
                    @keyframes pulse {
                        0%, 100% { opacity: 1; }
                        50% { opacity: 0.4; }
                    }
                    @keyframes blink {
                        0%, 50% { opacity: 1; }
                        51%, 100% { opacity: 0; }
                    }
                </style>
            `;

            this.isVisible = true;
        } else {
            // 检查是否有等待时间
            const nextWaitMinutes = next_wait_time?.minutes || status.next_wait_time_minutes || 0;
            
            // 显示正常状态
            this.container.style.background = 'linear-gradient(135deg, #00b894, #00a085)';
            this.container.style.color = 'white';
            this.container.style.border = '1px solid rgba(255, 255, 255, 0.2)';
            this.container.style.display = 'block';

            if (nextWaitMinutes > 0) {
                // 有策略等待时间的正常状态
                this.container.innerHTML = `
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <div style="
                            width: 10px; 
                            height: 10px; 
                            background: white; 
                            border-radius: 50%;
                            animation: pulse 2s infinite;
                        "></div>
                        <div>
                            <div style="font-weight: 600; margin-bottom: 4px; font-size: 14px;">
                                ✅ 爬虫正常运行
                            </div>
                            <div style="font-size: 12px; opacity: 0.9;">
                                异常等待时间: ${nextTimeText}
                            </div>
                        </div>
                        <div style="
                            position: absolute; 
                            top: -2px; 
                            right: -2px; 
                            width: 8px; 
                            height: 8px; 
                            background: #00d2ff; 
                            border-radius: 50%; 
                            border: 2px solid white;
                            animation: pulse 2s infinite;
                        "></div>
                    </div>
                    <style>
                        @keyframes pulse {
                            0%, 100% { opacity: 1; }
                            50% { opacity: 0.4; }
                        }
                    </style>
                `;
                this.isVisible = true;
            } else {
                // 完全正常状态（常驻显示）
                this.container.innerHTML = `
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <div style="
                            width: 10px; 
                            height: 10px; 
                            background: white; 
                            border-radius: 50%;
                            animation: pulse 2s infinite;
                        "></div>
                        <div>
                            <div style="font-weight: 600; margin-bottom: 4px; font-size: 14px;">
                                ✅ 爬虫正常运行
                            </div>
                            <div style="font-size: 12px; opacity: 0.9;">
                                系统运行正常
                            </div>
                        </div>
                        <div style="
                            position: absolute; 
                            top: -2px; 
                            right: -2px; 
                            width: 8px; 
                            height: 8px; 
                            background: #00ff88; 
                            border-radius: 50%; 
                            border: 2px solid white;
                            animation: pulse 2s infinite;
                        "></div>
                    </div>
                    <style>
                        @keyframes pulse {
                            0%, 100% { opacity: 1; }
                            50% { opacity: 0.4; }
                        }
                    </style>
                `;
                this.isVisible = true;
            }
        }
    }

    /**
     * 显示初始化状态
     */
    showInitializationStatus(connected, initialized, totalWindows) {
        if (!this.container) return;
        
        this.container.style.background = 'linear-gradient(135deg, #f39c12, #e67e22)';
        this.container.style.color = 'white';
        this.container.style.border = '1px solid rgba(255, 255, 255, 0.2)';
        this.container.style.display = 'block';
        
        let statusText = '系统未就绪';
        let detailText = '';
        
        if (!connected) {
            detailText = '窗口池未连接';
        } else if (!initialized) {
            detailText = '窗口池未初始化';
        } else if (totalWindows === 0) {
            detailText = '没有可用窗口';
        }
        
        this.container.innerHTML = `
            <div style="display: flex; align-items: center; gap: 12px;">
                <div style="
                    width: 10px; 
                    height: 10px; 
                    background: white; 
                    border-radius: 50%;
                    animation: blink 1.5s infinite;
                "></div>
                <div>
                    <div style="font-weight: 600; margin-bottom: 4px; font-size: 14px;">
                        ⚠️ ${statusText}
                    </div>
                    <div style="font-size: 12px; opacity: 0.9;">
                        ${detailText}
                    </div>
                </div>
            </div>
            <style>
                @keyframes blink {
                    0%, 50% { opacity: 1; }
                    51%, 100% { opacity: 0.3; }
                }
            </style>
        `;
        this.isVisible = true;
    }

    /**
     * 显示离线状态
     */
    showOfflineStatus() {
        if (!this.container) return;
        
        this.container.style.background = '#6c757d';
        this.container.style.color = 'white';
        this.container.style.border = '1px solid rgba(255, 255, 255, 0.2)';
        this.container.style.display = 'block';
        
        this.container.innerHTML = `
            <div style="display: flex; align-items: center; gap: 12px;">
                <div style="
                    width: 10px; 
                    height: 10px; 
                    background: white; 
                    border-radius: 50%;
                    opacity: 0.7;
                    animation: pulse 3s infinite;
                "></div>
                <div>
                    <div style="font-weight: 600; margin-bottom: 4px; font-size: 14px;">
                        🔌 连接中断
                    </div>
                    <div style="font-size: 12px; opacity: 0.9;">
                        无法获取封控状态
                    </div>
                </div>
                <div style="
                    position: absolute; 
                    top: -2px; 
                    right: -2px; 
                    width: 8px; 
                    height: 8px; 
                    background: #ffa500; 
                    border-radius: 50%; 
                    border: 2px solid white;
                    animation: blink 2s infinite;
                "></div>
            </div>
            <style>
                @keyframes pulse {
                    0%, 100% { opacity: 0.7; }
                    50% { opacity: 0.3; }
                }
                @keyframes blink {
                    0%, 50% { opacity: 1; }
                    51%, 100% { opacity: 0; }
                }
            </style>
        `;
        
        this.isVisible = true;
    }

    /**
     * 隐藏状态显示
     */
    hideStatus() {
        if (this.container) {
            this.container.style.display = 'none';
            this.isVisible = false;
        }
    }

    /**
     * 开始定期更新
     */
    startPeriodicUpdate() {
        // 立即更新一次
        this.updateStatus();
        
        // 每30秒更新一次
        this.updateInterval = setInterval(() => {
            this.updateStatus();
        }, 30000);
    }

    /**
     * 停止定期更新
     */
    stopPeriodicUpdate() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }

    /**
     * 销毁组件
     */
    destroy() {
        this.stopPeriodicUpdate();
        if (this.container) {
            this.container.remove();
        }
    }

    /**
     * 手动触发更新（用于爬取操作后立即检查状态）
     */
    async refreshStatus() {
        await this.updateStatus();
    }

}

// 全局实例
window.rateLimitStatus = new RateLimitStatusComponent();

// 页面加载完成后自动初始化
document.addEventListener('DOMContentLoaded', () => {
    console.log('初始化封控状态组件...');
    window.rateLimitStatus.init();
});

// 确保刷新函数存在
window.refreshRateLimitStatus = window.refreshRateLimitStatus || (() => {
    console.log('刷新封控状态...');
    if (window.rateLimitStatus) {
        window.rateLimitStatus.refreshStatus();
    } else {
        console.warn('封控状态组件未初始化');
    }
});

