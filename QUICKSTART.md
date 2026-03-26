# 快速启动指南 🚀

## 本地开发模式

### 1. 启动后端

```bash
# 进入后端目录
cd backend

# 创建虚拟环境（可选但推荐）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动后端服务
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

后端将在 `http://localhost:8000` 启动

### 2. 启动前端（新终端）

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端将在 `http://localhost:3000` 启动

### 3. 访问应用

打开浏览器访问 `http://localhost:3000`

## Docker 部署模式

### 一键启动

```bash
# 在项目根目录执行
docker-compose up -d
```

服务将在后台启动：
- 前端: `http://localhost:8080`
- 后端: `http://localhost:8000`
  +++++++ REPLACE

### 查看日志

```bash
docker-compose logs -f
```

### 停止服务

```bash
docker-compose down
```

## 首次使用

1. **获取 Azure API 密钥**
   - 访问 https://portal.azure.com/
   - 创建"语音服务"资源
   - 获取 API 密钥和区域

2. **配置应用**
   - 在"API 配置"区域填入你的 Azure API 密钥
   - 选择合适的区域（推荐 eastus 或 eastasia）
   - 选择默认语音

3. **开始使用**
   - 选择或编辑 SSML 模板
   - 点击"合成语音"
   - 播放或下载生成的音频

## 常见问题

### 后端启动失败
- 检查 Python 版本（需要 3.8+）
- 确保所有依赖已安装
- 检查端口 8000 是否被占用

### 前端启动失败
- 检查 Node.js 版本（需要 16+）
- 删除 `node_modules` 重新安装依赖
- 检查端口 3000 是否被占用

### Docker 启动失败
- 确保 Docker 和 Docker Compose 已安装
- 检查端口 80 和 8000 是否被占用
- 查看日志: `docker-compose logs`

### 合成失败
- 检查 API 密钥是否正确
- 确认区域和语音名称是否匹配
- 检查网络连接
- 查看 Azure 服务配额

## 开发提示

### 后端热重载
使用 `--reload` 参数启动后端，代码修改会自动重启

### 前端热更新
Vite 开发服务器支持热更新，修改代码会自动刷新

### 调试 API
访问 `http://localhost:8000/docs` 查看 API 文档

## 下一步

- 查看 [README.md](README.md) 了解更多功能
- 修改 SSML 模板创建自定义语音
- 部署到生产环境