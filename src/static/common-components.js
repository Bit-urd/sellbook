/**
 * 公共组件 - 封控状态显示
 */

class RateLimitStatusComponent {
    constructor(containerId = 'rateLimitStatusContainer') {
        this.containerId = containerId;
        this.updateInterval = null;
        this.isVisible = false;
    }

    /**
     * 初始化组件
     */
    init() {
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

        // 设置容器样式
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            padding: 12px 16px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            font-size: 14px;
            min-width: 200px;
            transition: all 0.3s ease;
            display: none;
        `;

        this.container = container;
    }

    /**
     * 更新状态显示
     */
    async updateStatus() {
        try {
            const response = await fetch('/sales-data/crawler/rate-limit-status');
            const data = await response.json();

            if (data.success) {
                this.displayStatus(data.data);
            }
        } catch (error) {
            console.warn('获取封控状态失败:', error);
            // 网络错误时隐藏状态组件
            this.hideStatus();
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
            this.container.style.cssText += `
                background: linear-gradient(135deg, #ff6b6b, #ee5a24);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.2);
                display: block;
            `;

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
                            当前等待: ${currentTimeText}
                        </div>
                        <div style="font-size: 11px; opacity: 0.8; margin-top: 2px;">
                            下次等待: ${nextTimeText}
                        </div>
                    </div>
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
            // 显示正常状态（短暂显示后隐藏）
            if (this.isVisible) {
                this.container.style.cssText += `
                    background: linear-gradient(135deg, #00b894, #00a085);
                    color: white;
                    border: 1px solid rgba(255, 255, 255, 0.2);
                    display: block;
                `;

                this.container.innerHTML = `
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <div style="
                            width: 10px; 
                            height: 10px; 
                            background: white; 
                            border-radius: 50%;
                        "></div>
                        <div>
                            <div style="font-weight: 600; margin-bottom: 4px; font-size: 14px;">
                                ✅ 系统正常
                            </div>
                            <div style="font-size: 12px; opacity: 0.9;">
                                爬虫服务运行正常
                            </div>
                        </div>
                    </div>
                `;

                // 3秒后隐藏正常状态
                setTimeout(() => {
                    this.hideStatus();
                }, 3000);
            }
        }
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

