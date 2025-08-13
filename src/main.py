#!/usr/bin/env python3
"""
主应用入口
"""
import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .routes.api_routes import api_router, crawler_router
from .models.database import db

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="卖书网站价差数据分析系统",
    description="孔夫子和多抓鱼价差分析系统",
    version="2.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router)
app.include_router(crawler_router)

# 静态文件目录
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info("应用启动中...")
    # 数据库已在模块导入时初始化
    logger.info("数据库连接就绪")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("应用关闭中...")

@app.get("/", response_class=HTMLResponse)
async def root():
    """主页 - 数据展示页面"""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    else:
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>卖书网站价差数据分析系统</title>
            <meta charset="utf-8">
        </head>
        <body>
            <h1>系统正在初始化...</h1>
            <p>请稍后刷新页面</p>
        </body>
        </html>
        """)

@app.get("/crawler-admin", response_class=HTMLResponse)
async def crawler_admin():
    """爬虫控制页面 - 隐藏入口"""
    admin_file = static_dir / "crawler_admin.html"
    if admin_file.exists():
        return FileResponse(admin_file)
    else:
        # 如果文件不存在，创建一个简单的控制页面
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>爬虫控制面板</title>
            <meta charset="utf-8">
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .container { max-width: 1200px; margin: 0 auto; }
                .section { margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }
                button { padding: 10px 20px; margin: 5px; cursor: pointer; }
                .success { color: green; }
                .error { color: red; }
                #log { background: #f5f5f5; padding: 10px; height: 200px; overflow-y: auto; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>爬虫控制面板</h1>
                
                <div class="section">
                    <h2>店铺管理</h2>
                    <div>
                        <input type="text" id="shopIds" placeholder="输入店铺ID，多个用逗号分隔" style="width: 300px;">
                        <button onclick="addShops()">添加店铺</button>
                    </div>
                    <div>
                        <button onclick="updateAllShops()">更新所有店铺数据</button>
                        <button onclick="updateDuozhuayuPrices()">更新多抓鱼价格</button>
                    </div>
                </div>
                
                <div class="section">
                    <h2>任务状态</h2>
                    <div>
                        <button onclick="getTaskStatus('pending')">待执行任务</button>
                        <button onclick="getTaskStatus('running')">运行中任务</button>
                        <button onclick="getTaskStatus()">所有任务</button>
                        <button onclick="runPendingTasks()">执行待处理任务</button>
                    </div>
                    <div id="taskList" style="margin-top: 10px;"></div>
                </div>
                
                <div class="section">
                    <h2>操作日志</h2>
                    <div id="log"></div>
                </div>
            </div>
            
            <script>
                function log(message, isError = false) {
                    const logDiv = document.getElementById('log');
                    const time = new Date().toLocaleTimeString();
                    const className = isError ? 'error' : 'success';
                    logDiv.innerHTML = `<div class="${className}">[${time}] ${message}</div>` + logDiv.innerHTML;
                }
                
                async function addShops() {
                    const shopIds = document.getElementById('shopIds').value.split(',').map(s => s.trim()).filter(s => s);
                    if (shopIds.length === 0) {
                        log('请输入店铺ID', true);
                        return;
                    }
                    
                    try {
                        const response = await fetch('/crawler/shop/add', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify(shopIds)
                        });
                        const data = await response.json();
                        log(data.message);
                        document.getElementById('shopIds').value = '';
                    } catch (error) {
                        log('添加店铺失败: ' + error.message, true);
                    }
                }
                
                async function updateAllShops() {
                    try {
                        const response = await fetch('/crawler/update/all-shops', {method: 'POST'});
                        const data = await response.json();
                        log(data.message);
                    } catch (error) {
                        log('更新失败: ' + error.message, true);
                    }
                }
                
                async function updateDuozhuayuPrices() {
                    try {
                        const response = await fetch('/crawler/update/duozhuayu-prices', {method: 'POST'});
                        const data = await response.json();
                        log(data.message);
                    } catch (error) {
                        log('更新价格失败: ' + error.message, true);
                    }
                }
                
                async function getTaskStatus(status) {
                    try {
                        const url = status ? `/crawler/tasks/status?status=${status}` : '/crawler/tasks/status';
                        const response = await fetch(url);
                        const data = await response.json();
                        displayTasks(data.data);
                    } catch (error) {
                        log('获取任务状态失败: ' + error.message, true);
                    }
                }
                
                async function runPendingTasks() {
                    try {
                        const response = await fetch('/crawler/tasks/run-pending', {method: 'POST'});
                        const data = await response.json();
                        log(data.message);
                    } catch (error) {
                        log('执行任务失败: ' + error.message, true);
                    }
                }
                
                function displayTasks(tasks) {
                    const taskList = document.getElementById('taskList');
                    if (tasks.length === 0) {
                        taskList.innerHTML = '<p>没有任务</p>';
                        return;
                    }
                    
                    let html = '<table border="1" style="width: 100%; border-collapse: collapse;">';
                    html += '<tr><th>ID</th><th>任务名称</th><th>类型</th><th>状态</th><th>进度</th><th>创建时间</th></tr>';
                    
                    tasks.forEach(task => {
                        html += `<tr>
                            <td>${task.id}</td>
                            <td>${task.task_name}</td>
                            <td>${task.task_type}</td>
                            <td>${task.status}</td>
                            <td>${task.progress_percentage}%</td>
                            <td>${new Date(task.created_at).toLocaleString()}</td>
                        </tr>`;
                    });
                    
                    html += '</table>';
                    taskList.innerHTML = html;
                }
                
                // 页面加载时获取任务状态
                window.onload = () => {
                    getTaskStatus();
                };
            </script>
        </body>
        </html>
        """)

@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "healthy", "database": "connected"}

def run_server(host: str = "127.0.0.1", port: int = 8000):
    """运行服务器"""
    uvicorn.run(app, host=host, port=port, reload=True)

if __name__ == "__main__":
    run_server()