#!/bin/bash

# 构建前端React应用脚本
echo "🚀 开始构建SellBook前端应用..."

# 进入前端目录
cd frontend

# 安装依赖（如果需要）
if [ ! -d "node_modules" ]; then
    echo "📦 安装依赖..."
    npm install
fi

# 构建应用
echo "🔨 构建React应用..."
npm run build

# 检查构建结果
if [ $? -eq 0 ]; then
    echo "✅ 前端应用构建成功！"
    echo "📁 构建文件位于: frontend/dist/"
    
    # 显示构建文件信息
    echo "📊 构建文件大小:"
    du -sh dist/
    ls -la dist/
else
    echo "❌ 前端应用构建失败！"
    exit 1
fi

echo "🎉 前端应用已就绪！"