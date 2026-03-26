# SSML 语音合成平台 🎤

一个基于 Vue 3 和 FastAPI 的现代化 SSML 语音合成平台，集成 Azure TTS 服务，提供实时语音合成、在线播放和下载功能。

## ✨ 功能特性

- 🎨 **现代化界面** - 基于 Vue 3 的响应式设计，支持亮色/暗色主题
- ✍️ **SSML 编辑器** - 内置 SSML 编辑器，支持语法高亮、代码补全和实时验证
- 🎵 **音频播放器** - 功能完善的音频播放器，支持播放控制、进度调节、速度控制
- 🔊 **多语音支持** - 支持多种语言和语音风格
- 🌐 **REST API** - 完整的 RESTful API 接口
- 🐳 **Docker 部署** - 一键 Docker 部署，简化环境配置
- 📱 **移动端适配** - 完美支持移动端设备
- 💾 **配置持久化** - 本地保存用户配置和主题设置

## 🛠️ 技术栈

### 前端
- **Vue 3** - 渐进式 JavaScript 框架
- **Vite** - 下一代前端构建工具
- **Axios** - HTTP 客户端

### 后端
- **FastAPI** - 现代化的 Python Web 框架
- **Azure TTS** - 微软语音合成服务
- **Uvicorn** - ASGI 服务器

### 部署
- **Docker** - 容器化部署
- **Docker Compose** - 多容器编排
- **Nginx** - 反向代理和静态文件服务

## 📦 项目结构

```
ssml-tts-webapp/
├── backend/                 # 后端服务
│   ├── main.py             # FastAPI 主程序
│   ├── azure_tts.py       # Azure TTS 封装
│   ├── models.py           # 数据模型
│   └── requirements.txt    # Python 依赖
├── frontend/              # 前端应用
│   ├── src/
│   │   ├── components/    # Vue 组件
│   │   │   ├── SSMLEditor.vue      # SSML 编辑器
│   │   │   └── AudioPlayer.vue     # 音频播放器
│   │   ├── App.vue        # 主应用组件
│   │   ├── main.js        # 入口文件
│   │   ├── api.js         # API 封装
│   │   └── style.css      # 全局样式
│   ├── package.json
│   ├── vite.config.js
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml      # Docker Compose 配置
├── Dockerfile             # 后端 Docker 配置
└── README.md             # 项目文档
```

## 🚀 快速开始

### 方式一：Docker 部署（推荐）

1. **克隆项目**
```bash
git clone <repository-url>
cd ssml-tts-webapp
```

2. **启动服务**
```bash
docker-compose up -d
```

3. **访问应用**
打开浏览器访问 `http://localhost:8080`
  +++++++ REPLACE

### 方式二：本地开发

#### 后端

1. **安装 Python 依赖**
```bash
cd backend
pip install -r requirements.txt
```

2. **启动后端服务**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

#### 前端

1. **安装 Node 依赖**
```bash
cd frontend
npm install
```

2. **启动开发服务器**
```bash
npm run dev
```

3. **访问应用**
打开浏览器访问 `http://localhost:3000`

## 📝 使用说明

### 1. 配置 Azure API

1. 访问 [Azure Portal](https://portal.azure.com/)
2. 创建语音服务资源
3. 获取 API 密钥和区域
4. 在应用中填入 API 密钥和区域

### 2. 编写 SSML

SSML (Speech Synthesis Markup Language) 是用于控制语音合成的 XML 标记语言。

**基础示例：**
```xml
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="zh-CN">
    <voice name="zh-CN-XiaoxiaoNeural">
        你好，欢迎使用 SSML 语音合成平台。
    </voice>
</speak>
```

**情感语音：**
```xml
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="zh-CN">
    <voice name="zh-CN-XiaoxiaoNeural">
        <mstts:express-as style="cheerful" styledegree="2">
            今天天气真好！
        </mstts:express-as>
    </voice>
</speak>
```

### 3. 合成语音

1. 在编辑器中编写或选择 SSML 模板
2. 点击"合成语音"按钮
3. 等待合成完成
4. 在播放器中播放或下载音频

## 🔧 API 接口

### 合成语音
```
POST /api/synthesize
Content-Type: application/json

{
  "ssml": "<speak>...</speak>",
  "api_key": "your_key",
  "region": "eastus",
  "voice": "zh-CN-XiaoxiaoNeural",
  "output_format": "audio-16khz-32kbitrate-mono-mp3"
}
```

### 获取语音列表
```
GET /api/voices?region=eastus&locale=zh-CN
```

### 验证 SSML
```
POST /api/validate
Content-Type: application/json

{
  "ssml": "<speak>测试</speak>"
}
```

## 🎨 主题切换

点击右上角的主题按钮可以在亮色和暗色模式之间切换。主题设置会自动保存到本地存储。

## 📱 移动端适配

应用完全响应式，支持在手机、平板等移动设备上使用。

## 🔐 安全说明

- API 密钥仅在客户端使用，不会存储在服务器
- SSML 输入经过验证，防止注入攻击
- 音频文件定期清理，避免磁盘空间占用

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 🙏 致谢

- [Azure TTS](https://azure.microsoft.com/zh-cn/services/cognitive-services/text-to-speech/) - 微软语音合成服务
- [Vue 3](https://vuejs.org/) - 渐进式 JavaScript 框架
- [FastAPI](https://fastapi.tiangolo.com/) - 现代化的 Python Web 框架

## 📧 联系方式

如有问题或建议，欢迎通过以下方式联系：

- 提交 Issue
- 发送邮件

---

⭐ 如果这个项目对你有帮助，请给个 Star！