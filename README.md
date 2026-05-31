# Codex Feishu Bridge

Codex APP + 飞书 双链路桥接。两套链路共用同一个本地代理（`127.0.0.1:4000`），同时运行。

## 功能

| 链路 | 能力 |
|------|------|
| **Codex APP** | 代码执行、文件读写、搜索（11个工具） |
| **飞书** | 打开应用、运行命令、查看文件、纯文本对话（bash 工具） |

## 快速开始

### 1. 安装依赖

```bash
cd codex-feishu-bridge
python3 -m venv .venv
.venv/bin/pip install lark-oapi
```

### 2. 配置代理

```bash
cd proxy
cp .env.example .env
# 编辑 .env，填入真实 API 密钥
```

### 3. 配置 Codex APP

```bash
# 编辑 ~/.codex/config.toml
model_provider = "my-proxy"
model = "deepseek-v4-flash"
approval = "never"

[model_providers.my-proxy]
name = "my-proxy"
base_url = "http://127.0.0.1:4000/v1"
wire_api = "responses"
requires_openai_auth = true
```

```bash
# 编辑 ~/.codex/auth.json
{"OPENAI_API_KEY": "sk-proxy-你的代理密钥"}
```

### 4. 启动

```bash
# 代理（推荐用 launchctl 开机自启）
launchctl start com.codex.bridge

# 飞书桥接
export FEISHU_APP_ID=cli_xxx
export FEISHU_APP_SECRET=xxx
.venv/bin/python3 -u bridge_exec.py

# Codex APP
open /Applications/Codex.app
```

## 飞书可执行命令示例

| 用户说 | 执行 | 返回 |
|--------|------|------|
| "打开 Google Chrome" | `open -a "Google Chrome"` | 确认已打开 |
| "执行 ls -la" | `ls -la` | 目录列表总结 |
| "查看系统内存" | `vm_stat` | 内存分析表格 |
| "帮我写个脚本" | 纯文本对话 | 完整代码 |

## 架构

```
用户 ──┬─ Codex APP ──────────────────┐
       │                              ├── codex-bridge proxy (:4000) ──┬─ DeepSeek API
       └─ 飞书 → bridge_exec.py ─────┘                                └─ 百炼 Coding Plan
```

## 代理 v4 特性

1. **工具格式转换** — 自动转换 Responses API → chat completions 格式
2. **模型名映射** — gpt-5.4-mini 等 OpenAI 模型名 → deepseek-v4-flash
3. **无名工具过滤** — 过滤无 name 工具，避免 DeepSeek 反序列化错误
4. **open 命令增强** — GUI 命令无输出时自动补充确认信息
5. **系统提示增强** — 要求模型详细总结工具执行结果

## 安全注意事项

- ⚠️ **永远不要提交 `.env` 文件**
- ⚠️ **不要硬编码 API Key 到代码中**
- ⚠️ **飞书 AppSecret 通过环境变量传入**

## 故障排查

| 现象 | 解决 |
|------|------|
| Codex APP 无回复 | 检查代理是否运行：`lsof -i :4000` |
| 飞书无回复 | 检查 bridge_exec.py 是否运行 |
| 代理报 502 | 确认 proxy_v4.mjs 在运行，不是 v2/v3 |

完整文档见 [docs/SKILL.md](docs/SKILL.md)。

## License

MIT
