# Codex Dual-Bridge (APP + 飞书)

Codex APP 和飞书桥接共用同一个本地代理（`127.0.0.1:4000`），**不冲突，同时运行**。

## 架构

```
Codex APP ─────────────────────────┐
                                   ├── codex-bridge proxy (:4000) ── DeepSeek / 百炼
飞书 → bridge_exec.py ─────────────┘
```

| 链路 | 请求特征 | 代理路由 |
|------|---------|---------|
| Codex APP | 带 tools（11个，Responses API wire format） | 转换工具格式 → DeepSeek/百炼 |
| 飞书 | 带 tools（bash），工具执行 + 纯文本对话 | 工具执行循环 → DeepSeek |

## 关键文件

| 文件 | 作用 |
|------|------|
| `~/Developer/feishu-codex-bridge/proxy/proxy_v4.mjs` | 代理核心（端口 4000） |
| `~/Developer/feishu-codex-bridge/proxy/.env` | 代理配置（API keys） |
| `~/Developer/feishu-codex-bridge/bridge_exec.py` | 飞书桥接服务（带 bash 工具执行） |
| `~/.codex/config.toml` | Codex APP 配置（指向本地代理） |
| `~/.codex/auth.json` | Codex APP 认证（proxy key） |
| `~/Library/LaunchAgents/com.codex.bridge.plist` | 代理自启动服务 |
| `/tmp/codex-bridge/proxy-access.log` | 代理访问日志（调试用） |

## Codex APP 配置（完整）

### config.toml

```toml
model_provider = "my-proxy"
model = "deepseek-v4-flash"
approval = "never"

[model_providers.my-proxy]
name = "my-proxy"
base_url = "http://127.0.0.1:4000/v1"
wire_api = "responses"
requires_openai_auth = true

[projects."/Users/zujing"]
trust_level = "trusted"

[projects."/Users/zujing/Developer/feishu-codex-bridge"]
trust_level = "trusted"

[projects."/"]
trust_level = "trusted"

[desktop]
conversationDetailMode = "STEPS_COMMANDS"
ambient-suggestions-enabled = true
```

### auth.json

```json
{
    "OPENAI_API_KEY": "sk-proxy-你的代理密钥"
}
```

**说明**：
- `base_url` 指向本地代理 `127.0.0.1:4000`，不走 OpenAI 服务器
- `wire_api = "responses"` 使用 Responses API 格式（非旧版 chat）
- `approval = "never"` 命令无需确认直接执行
- `OPENAI_API_KEY` 必须和 `.env` 中的 `PROXY_AUTH_KEY` 一致
- Codex APP 启动时会尝试连接 OpenAI 服务器做插件市场/遥测，这些连接在国内被墙（SYN_SENT），但不影响核心功能

## 飞书能力（工具执行）

飞书现在支持 bash 工具执行。用户发命令，Mac 本地执行：

| 用户说 | 执行 | 返回 |
|--------|------|------|
| "打开 Google Chrome" | `open -a "Google Chrome"` | 确认已打开 |
| "执行 ls -la" | `ls -la` | 目录列表总结 |
| "帮我写个 Python 脚本" | 纯文本对话 | 代码 |
| "查看系统内存" | `vm_stat` / `top` | 内存信息 |

## 启动

### 1. 启动代理（必须先启动）

**方式一：通过 launchctl（推荐，开机自启）**
```bash
launchctl start com.codex.bridge
```

**方式二：手动启动**
```bash
cd ~/Developer/feishu-codex-bridge/proxy
nohup node --env-file=.env proxy_v4.mjs >> /tmp/codex-bridge/proxy.log 2>&1 &
```

### 2. 启动飞书桥接

```bash
cd ~/Developer/feishu-codex-bridge
nohup .venv/bin/python3 -u bridge_exec.py >> /tmp/feishu-bridge.log 2>&1 &
```

### 3. 打开 Codex APP

```bash
open /Applications/Codex.app
```

## 验证

```bash
# 两个服务都在
lsof -i :4000          # 代理监听
ps aux | grep bridge_exec | grep -v grep  # 飞书桥接

# 测试飞书工具执行
cd ~/Developer/feishu-codex-bridge
.venv/bin/python3 -c "from bridge_exec import call_proxy; print(call_proxy('执行 pwd'))"

# 测试 Codex APP 代理连通性
curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:4000/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-proxy-你的代理密钥" \
  -d '{"model":"deepseek-v4-flash","input":"hello","stream":false,"max_output_tokens":10}'

# 代理日志（实时）
tail -f /tmp/codex-bridge/proxy-access.log
```

## 代理 v4 核心修复

### 1. 工具格式转换 (`transformTools`)
- Codex APP 发 `{name, type, description, parameters}`（Responses API 格式）
- DeepSeek 要求 `{type: "function", function: {name, ...}}`（chat completions 格式）
- 代理自动转换，否则 DeepSeek 返回反序列化错误 → 空回复

### 2. 模型名映射 (`normalizeModel`)
- Codex APP 可能发送 `gpt-5.4-mini`、`gpt-4o` 等 OpenAI 模型名
- 代理自动映射到 `deepseek-v4-flash`
- 映射表：
  ```
  gpt-5.4-mini → deepseek-v4-flash
  gpt-5.4      → deepseek-v4-flash
  gpt-4.1      → deepseek-v4-flash
  gpt-4o       → deepseek-v4-flash
  gpt-3.5-turbo→ deepseek-v4-flash
  ds-v4-flash  → deepseek-v4-flash
  ds-v4-pro    → deepseek-v4-pro
  ```

### 3. 无名工具过滤
- Codex APP 偶尔发送没有 `name` 字段的工具（第11个 agent 工具）
- DeepSeek 直接报错 `missing field 'function'`
- 代理过滤掉无 name 的工具

### 4. open 命令输出增强
- macOS `open` 命令执行成功但不产生 stdout/stderr
- 代理检测到 `open` 命令无输出时，自动补充确认信息
- 避免模型因无输出而返回空回复

### 5. 系统提示增强
- 代理自动给每个请求添加中文系统提示
- 要求模型详细总结工具执行结果，不要只说"已完成"

## 飞书桥接已增强的能力

- **bash 工具执行** — 飞书消息带 tools 定义，代理执行 bash 命令并返回结果
- **最大 5 轮工具循环** — 模型可以连续调用多个命令
- **自动添加系统提示** — 代理自动添加中文系统提示，要求模型总结工具结果
- **工作目录已知** — 系统提示包含 `/Users/zujing` 和桌面路径，避免模型浪费时间搜索

## 故障排查

| 现象 | 原因 | 解决 |
|------|------|------|
| Codex APP 回复空 | 工具格式不匹配 | 检查 proxy_v4.mjs transformTools |
| Codex APP 一直 Reconnecting | 代理没启动 | `lsof -i :4000` 确认端口监听 |
| 飞书无回复 | bridge_exec.py 没运行 | 重新启动 |
| 飞书回复空或很短 | proxy 版本不对 | 检查 `lsof -i :4000` 确认运行的是 `proxy_v4.mjs` |
| 代理报 502 | DeepSeek 模型名不支持 | 检查 normalizeModel 映射 |
| 代理不响应 | 端口 4000 未监听 | `lsof -i :4000`，重启 proxy |

## ⚠️ 重要：proxy 版本一致性

launchctl 服务 `com.codex.bridge` 管理 proxy 的自动启动。如果手动改代码但 proxy 不生效：

```bash
# 1. 停止当前服务
launchctl stop com.codex.bridge
sleep 1
launchctl bootout gui/$(id -u)/com.codex.bridge
sleep 1

# 2. 确认端口释放
lsof -i :4000 -P -n  # 应该为空

# 3. 重新启动
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.codex.bridge.plist

# 4. 确认新版本运行
ps aux | grep proxy_v | grep -v grep
```

## Codex APP 配置检查清单

如果 Codex APP 不能工作，依次检查：

1. **config.toml** — `base_url` 是否为 `http://127.0.0.1:4000/v1`
2. **config.toml** — `wire_api` 是否为 `responses`
3. **auth.json** — `OPENAI_API_KEY` 是否与 `.env` 的 `PROXY_AUTH_KEY` 一致
4. **代理** — `lsof -i :4000` 是否有进程监听
5. **代理版本** — `ps aux | grep proxy_v` 确认是 `proxy_v4.mjs`
6. **网络** — Codex APP 连接 OpenAI 服务器会 SYN_SENT（被墙），但不影响功能，忽略即可
