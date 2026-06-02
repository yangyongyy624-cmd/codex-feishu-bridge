# 飞书双电脑控制 Skill

> 通过飞书（Feishu/Lark）实现手机/另一台电脑远程 Mac 执行命令、运行代码、控制应用、文件管理。

## 一句话说明

在你的 Mac 上运行一个飞书桥接服务，手机飞书发消息 → Mac 本地执行命令 → 结果回传飞书。两台电脑之间通过飞书云端消息通道通信，无需公网 IP 或端口映射。

## 架构

```
手机/另一台电脑                    你的 Mac
┌──────────────┐              ┌──────────────────────────┐
│   飞书 APP    │ ──云端──→    │  bridge_exec.py (飞书长连接) │
│   (发消息)    │              │         ↓                  │
│              │ ←─回复───    │  proxy_v4.mjs (:4000)      │
└──────────────┘              │         ↓                  │
                              │  DeepSeek / 百炼 / MiniMax │
                              │         ↓                  │
                              │  bash 工具 → 本地命令执行    │
                              └──────────────────────────┘
```

**核心思路**：飞书开放平台 WebSocket 长连接作为"控制通道"，Mac 本地 Python 服务接收消息，通过代理调用 LLM 解析意图，LLM 输出 bash 命令后在本地执行，结果回传飞书。

## 能力矩阵

| 类别 | 示例命令 | 实际执行 |
|------|---------|---------|
| 应用控制 | "打开 Chrome" | `open -a "Google Chrome"` |
| 终端命令 | "执行 ls -la" | `ls -la` |
| 文件操作 | "查看 README.md" | `cat README.md` |
| 系统信息 | "查看内存使用" | `vm_stat` / `top -l1` |
| 代码执行 | "运行这个 Python 脚本" | `python3 script.py` |
| 纯文本对话 | "帮我写个脚本" | LLM 直接生成代码 |

## 快速部署

### 前置条件

- Mac 上已安装 Node.js (v22+) 和 Python 3
- 飞书开放平台应用（需要消息事件权限）
- DeepSeek / 百炼 / MiniMax API Key（至少一个）

### 步骤 1：创建飞书开放平台应用

1. 访问 [飞书开放平台](https://open.feishu.cn/) → 创建企业自建应用
2. 记录 **App ID** 和 **App Secret**
3. 权限配置：添加 `im:message`、`im:message:send_as_bot` 权限
4. 事件订阅：模式选择 **长连接 (WebSocket)**（不需要公网回调地址）
5. 发布应用（需要管理员审批）

### 步骤 2：克隆仓库并安装依赖

```bash
cd ~/Developer
git clone https://github.com/YOUR_GITHUB_USERNAME/codex-feishu-bridge.git
cd codex-feishu-bridge

# Python 依赖
python3 -m venv .venv
.venv/bin/pip install lark-oapi
```

### 步骤 3：配置代理

```bash
cd proxy
cp .env.example .env
```

编辑 `.env`：

```bash
PROXY_AUTH_KEY=生成一个随机字符串
DEEPSEEK_API_KEY=你的DeepSeek Key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
QWEN_API_KEY=你的百炼 Key
QWEN_BASE_URL=https://coding.dashscope.aliyuncs.com/v1
QWEN_MODELS=qwen3-coder-plus,qwen3.6-plus
PROXY_PORT=4000
WORKDIR=/Users/你的用户名
```

### 步骤 4：启动飞书桥接

```bash
cd ~/Developer/codex-feishu-bridge

# 设置环境变量
export FEISHU_APP_ID=你的AppID
export FEISHU_APP_SECRET=你的AppSecret
export PROXY_AUTH_KEY=与.env一致
export WORKDIR=/Users/你的用户名

# 启动
.venv/bin/python3 -u bridge_exec.py
```

看到以下输出即表示成功：

```
=======================================================
  Feishu <-> Codex Bridge (codex exec mode)
=======================================================
  Feishu App ID:  cli_xxxxxxxx
  Workdir:        /Users/xxx

  Mode: 飞书云通讯长连接 + codex exec
  Proxy: codex-bridge on port 4000 (DeepSeek)
=======================================================

[feishu] Cloud communication WebSocket started
```

### 步骤 5：测试

在手机飞书里给机器人发消息："执行 pwd"，应该返回工作目录路径。

## 开机自启（推荐）

### 代理自启

```bash
# 复制并编辑 launchd plist
cp launchd/com.codex.bridge.plist ~/Library/LaunchAgents/
# 编辑 ~/Library/LaunchAgents/com.codex.bridge.plist，替换 YOUR_USERNAME

# 加载服务
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.codex.bridge.plist
```

### 飞书桥接自启

创建 `~/Library/LaunchAgents/com.feishu.bridge.plist`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.feishu.bridge</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/YOUR_USERNAME/Developer/codex-feishu-bridge/.venv/bin/python3</string>
        <string>-u</string>
        <string>/Users/YOUR_USERNAME/Developer/codex-feishu-bridge/bridge_exec.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/YOUR_USERNAME/Developer/codex-feishu-bridge</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>FEISHU_APP_ID</key>
        <string>你的AppID</string>
        <key>FEISHU_APP_SECRET</key>
        <string>你的AppSecret</string>
        <key>PROXY_AUTH_KEY</key>
        <string>与.env一致</string>
        <key>WORKDIR</key>
        <string>/Users/YOUR_USERNAME</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/feishu-bridge.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/feishu-bridge.log</string>
</dict>
</plist>
```

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.feishu.bridge.plist
```

## ToggleFeishu — 一键开关

Mac 菜单栏一键切换飞书连接开关，保护隐私或专注工作。

### 原理

通过 `/etc/hosts` 将飞书 WebSocket 域名 `msg-frontier.feishu.cn` 指向 `127.0.0.1`，断开长连接。移除后立即恢复。

- **关闭飞书**：添加 hosts 规则 → 飞书 WS 断开 → 服务重启后连不上
- **打开飞书**：移除 hosts 规则 → 服务重启后自动重连
- Web UI 不受影响

### 安装

```bash
# 1. 确保 toggle-feishu.sh 可执行
chmod +x ~/Developer/codex-feishu-bridge/toggle-feishu.sh

# 2. 将 ToggleFeishu.applescript 导出为 Application
# 打开 AppleScript 编辑器 → 打开脚本 → 导出为 Application
# 或者命令行：
osacompile -o ~/Applications/ToggleFeishu.app ~/Developer/codex-feishu-bridge/ToggleFeishu.applescript
```

### 使用

双击 `ToggleFeishu.app` → 输入 Mac 密码 → 切换状态。

### 脚本逻辑

```
关闭时：
  1. echo "127.0.0.1  msg-frontier.feishu.cn" >> /etc/hosts
  2. 重启所有飞书相关服务 (hermes, bridge, openclaw)
  3. 通知"飞书已关闭"

打开时：
  1. 从 /etc/hosts 移除飞书规则
  2. 重启所有飞书相关服务
  3. 通知"飞书已恢复"
```

## 代理核心：proxy_v4.mjs

### 功能

1. **Responses API → Chat Completions 转换**
   - Codex APP 发 Responses API 格式，代理自动转为 DeepSeek 兼容的 chat completions 格式
   - 工具定义自动包装 `{name, ...}` → `{type: "function", function: {name, ...}}`

2. **模型名映射**
   - OpenAI 风格模型名 → 实际后端模型
   - `gpt-4o` → `deepseek-v4-flash`，`gpt-3.5-turbo` → `deepseek-v4-flash`

3. **工具执行循环**
   - 代理内置 bash 工具执行器
   - 支持最多 5 轮连续工具调用
   - `open` 命令特殊处理（GUI 命令无输出时自动补充确认）

4. **系统提示增强**
   - 自动注入中文系统提示，要求模型详细总结执行结果
   - 限制工具调用次数，避免无限循环

5. **多后端路由**
   - 根据模型名自动路由到 DeepSeek / 百炼 / MiniMax

### 端口和接口

```
端口: 4000 (PROXY_PORT 环境变量)

接口:
  GET  /v1/models          — 列出可用模型
  POST /v1/responses       — Responses API（Codex APP 主用）
  POST /v1/chat/completions — Chat Completions API
```

## 安全注意事项

- **永远不要**提交 `.env` 文件或任何包含真实 API Key 的文件
- 飞书 AppSecret 通过环境变量传入，不要硬编码
- `PROXY_AUTH_KEY` 是本地代理认证密钥，只在 localhost 使用
- `/etc/hosts` 操作需要 sudo 权限，toggle-feishu.sh 通过 AppleScript 弹窗获取

## 故障排查

| 现象 | 检查 | 解决 |
|------|------|------|
| 飞书无回复 | `ps aux | grep bridge_exec` | 重启 bridge_exec.py |
| 代理不响应 | `lsof -i :4000` | 确认 proxy_v4.mjs 在运行 |
| 回复为空或很短 | `ps aux | grep proxy_v` | 确认是 v4 版本，不是旧版 |
| ToggleFeishu 不生效 | `grep feishu /etc/hosts` | 确认 hosts 规则是否正确 |
| 飞书连不上 | 飞书开放平台事件配置 | 确认长连接模式已开启 |
| 代理报 502 | 代理日志 | `tail -f /tmp/codex-bridge/proxy-access.log` |

## 完整文件清单

```
codex-feishu-bridge/
├── bridge_exec.py          # 飞书桥接主服务（WebSocket 长连接 + bash 工具）
├── toggle-feishu.sh        # /etc/hosts 方式飞书开关（需 sudo）
├── ToggleFeishu.applescript # macOS 应用封装（双击运行）
├── proxy/
│   ├── proxy_v4.mjs        # 代理核心（端口 4000，工具转换，多后端路由）
│   └── .env.example        # 环境变量模板
├── launchd/
│   └── com.codex.bridge.plist  # macOS 开机自启配置
├── config/
│   ├── codex-config.toml.example  # Codex APP 配置模板
│   ├── codex-auth.json.example    # Codex APP 认证模板
│   └── proxy-models.json.example  # 代理支持的后端模型
└── README.md               # 项目说明
```
