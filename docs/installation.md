# 安装指南

## 系统要求

- macOS 12+ (Monterey 或更高版本)
- Node.js 22+ (推荐使用 nvm 管理)
- Python 3.10+
- 稳定的网络连接

## 步骤详解

### 1. 安装 Node.js

```bash
# 使用 nvm 安装 Node.js 22
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.zshrc  # 或 source ~/.bashrc
nvm install 22
nvm use 22
node --version  # 确认版本
```

### 2. 安装 Codex CLI

```bash
npm install -g @openai/codex
codex --version  # 确认安装成功
```

### 3. 获取 API Keys

#### DeepSeek API Key
1. 访问 [DeepSeek 平台](https://platform.deepseek.com)
2. 注册账号并创建 API Key
3. 复制 Key 备用

#### Qwen API Key（可选）
1. 访问 [百炼平台](https://bailian.console.aliyun.com)
2. 创建 API Key
3. 复制 Key 备用

### 4. 配置项目

```bash
cd ~/Developer/codex-feishu-bridge

# 配置代理
cd proxy
cp .env.example .env
# 使用你喜欢的编辑器编辑 .env，填入 API Keys
```

### 5. 配置 Codex

```bash
mkdir -p ~/.codex
cp ../config/codex-config.toml ~/.codex/config.toml
cp ../config/codex-auth.json ~/.codex/auth.json
cp ../config/proxy-models.json ~/.codex/proxy-models.json

# 编辑 auth.json，填入 PROXY_AUTH_KEY
```

### 6. 安装 Python 依赖

```bash
cd ../bridge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 7. 配置飞书应用

详见 [配置说明](configuration.md)

### 8. 启动服务

详见 [快速开始](../README.md#使用)

## 验证安装

运行以下命令验证各组件：

```bash
# 测试代理
curl -s -H "Authorization: Bearer YOUR_PROXY_KEY" http://127.0.0.1:4000/v1/models

# 测试 Codex
codex exec --skip-git-repo-check "say hi"

# 测试桥接（需要在运行 bridge_final.py 后）
# 在飞书中发送：执行：echo hello
```

## 常见问题

### Node.js 版本不匹配
```bash
nvm install 22
nvm use 22
```

### Python 虚拟环境激活失败
```bash
source .venv/bin/activate
# 如果失败，检查 Python 版本
python3 --version
```

### 代理端口被占用
```bash
lsof -i :4000
# 如果端口被占用，修改 .env 中的 PROXY_PORT
```
