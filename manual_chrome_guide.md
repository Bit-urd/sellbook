# 🌟 使用真实Chrome浏览器进行爬取

## 🚀 启动步骤

### 1. 手动启动Chrome（推荐）

**macOS:**
```bash
# 方法1 - 推荐
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chrome-debug-session

# 方法2 - 如果方法1不行
open -a "Google Chrome" --args --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug-session
```

**Linux:**
```bash
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug-session
```

**Windows:**
```cmd
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir=c:\temp\chrome-debug-session
```

### 2. 验证启动成功

打开浏览器访问: http://localhost:9222/json/version

应该看到类似这样的JSON响应：
```json
{
   "Browser": "Chrome/120.0.6099.109",
   "Protocol-Version": "1.3",
   "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...",
   "V8-Version": "12.0.267.8",
   "WebKit-Version": "537.36 (@cfede9db1a9b28c6bbd0d8ee3a0bc32c4d2d2e7f)",
   "webSocketDebuggerUrl": "ws://localhost:9222/devtools/browser/..."
}
```

### 3. 运行爬虫

Chrome启动后，执行：
```bash
uv run python real_browser_scraper.py
```

## ✅ 优势

1. **完全真实环境** - 使用真实Chrome，无任何自动化特征
2. **登录状态保持** - 可以手动登录，保持会话
3. **插件支持** - 支持所有Chrome插件和扩展
4. **完美伪装** - 网站无法检测到自动化

## 🔧 故障排除

### Chrome启动失败？
- 确保Chrome已安装且路径正确
- 检查端口9222是否被占用
- 尝试不同的用户数据目录

### 连接失败？
- 访问 http://localhost:9222 确认Chrome调试服务运行
- 检查防火墙设置
- 确保Chrome进程仍在运行

### 爬取过程中出错？
- 手动在Chrome中登录网站
- 确保网络连接正常
- 检查网站是否有变化