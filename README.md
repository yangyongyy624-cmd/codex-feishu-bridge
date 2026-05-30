# Codex Feishu Bridge 🚀

> **手机飞书控制 Mac 执行命令的完整解决方案**

一个让 OpenAI Codex CLI 通过飞书（Lark）机器人接收消息并执行 Mac 终端命令的桥接系统。

## ✨ 特性

-  **飞书消息接收** - 通过飞书长连接接收消息
-  **终端命令执行** - 直接在 Mac 上执行 bash 命令
- 🌐 **网页/应用打开** - 支持打开网页和应用程序
- 📁 **文件操作** - 列出目录、查看文件等
- 🤖 **AI 对话** - 非命令消息转发到 DeepSeek V4 获取 AI 回复
-  **开机自启** - 支持 macOS launchd 自动启动
-  **多模型支持** - DeepSeek V4、Qwen 系列模型

## ️ 架构

```
飞书消息 → bridge_final.py → 直接命令执行 或 → proxy_v4.mjs → DeepSeek API
终端 codex TUI ───────────────────────────→ proxy_v4.mjs → DeepSeek API
```

## 📦 安装

### 前置条件

- macOS 系统
- Node.js 22+ (`nvm install 22 && nvm use 22`)
- Python 3.10+
- OpenAI Codex CLI (`npm install -g @openai/codex`)
- DeepSeek API Key

### 1. 克隆项目

```bash
cd ~/Developer
git clone https://github.com/YOUR_USERNAME/codex-feishu-bridge.git
cd codex-feishu-bridge
```

### 2. 配置代理

```bash
cd proxy
cp .env.example .env
# 编辑 .env 填入你的 API Keys
```

### 3. 配置 Codex

```bash
mkdir -p ~/.codex
cp ../config/codex-config.toml ~/.codex/config.toml
cp ../config/codex-auth.json ~/.codex/auth.json
cp ../config/proxy-models.json ~/.codex/proxy-models.json
# 编辑 ~/.codex/auth.json 填入 PROXY_AUTH_KEY
```

### 4. 安装 Python 依赖

```bash
cd ../bridge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 5. 配置飞书应用

1. 登录 [飞书开放平台](https://open.feishu.cn/app)
2. 创建企业自建应用
3. 启用 **机器人** 能力
4. 添加事件订阅：`im.message.receive_v1`
5. **事件接收模式** 选择 **长连接**（不要选 Webhook）
6. 保存并发布应用版本

## 🚀 使用

### 启动代理

```bash
cd ~/Developer/codex-feishu-bridge/proxy
node --env-file=.env proxy_v4.mjs &
```

### 启动飞书桥接

```bash
cd ~/Developer/codex-feishu-bridge/bridge
source .venv/bin/activate
FEISHU_APP_ID="你的AppID" \
FEISHU_APP_SECRET="你的AppSecret" \
PROXY_AUTH_KEY="你的ProxyKey" \
WORKDIR="/Users/你的用户名" \
python3 -u bridge_final.py
```

### 测试

在飞书中给机器人发送：

```
执行：echo hello
```

应该收到回复：
```
✅ 命令执行成功：
hello
```

##  支持的命令

### 执行命令
- `执行：echo hello`
- `运行：ls -la`

### 打开网页
- `打开 https://www.google.com`
- `打开 google`

### 打开应用
- `打开 Google Chrome`
- `打开 Safari`
- `打开 Terminal`

### 列出文件
- `列出桌面文件`
- `查看 ~/Documents`

## 🔧 开机自启

```bash
cp launchd/com.codex.bridge.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.codex.bridge.plist
```

## 📚 文档

- [安装指南](docs/installation.md)
- [配置说明](docs/configuration.md)
- [故障排查](docs/troubleshooting.md)
- [架构说明](docs/architecture.md)

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)

## 🙏 致谢

- [OpenAI Codex CLI](https://github.com/openai/codex)
- [DeepSeek](https://platform.deepseek.com)
- [lark-oapi](https://github.com/larksuite/oapi-sdk-python)

---

**注意：** 本项目为个人开源项目，仅供学习和交流使用。使用请遵守当地法律法规。
