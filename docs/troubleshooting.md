# 故障排查指南

## 代理问题

### 代理无法启动

**症状：** 运行 `node --env-file=.env proxy_v4.mjs` 报错

**解决方案：**
```bash
# 1. 检查 Node.js 版本
node --version  # 应该 >= 22

# 2. 检查 .env 文件
cat proxy/.env  # 确认格式正确

# 3. 检查端口是否被占用
lsof -i :4000
# 如果被占用，kill 进程或修改 PROXY_PORT
```

### 代理返回 401 Unauthorized

**症状：** 调用代理返回 401 错误

**解决方案：**
```bash
# 1. 检查 PROXY_AUTH_KEY 是否一致
# proxy/.env 中的 PROXY_AUTH_KEY
# ~/.codex/auth.json 中的 OPENAI_API_KEY
# 两者必须相同
```

### 模型名称错误

**症状：** 返回 "unsupported model" 错误

**解决方案：**
```bash
# 1. 检查 ~/.codex/proxy-models.json
# 确保包含 deepseek-v4-flash

# 2. 检查代理代码
# proxy_v4.mjs 中的模型名映射
```

## 飞书桥接问题

### 收不到消息

**症状：** 发送消息后桥接无反应

**解决方案：**
```bash
# 1. 检查飞书应用配置
# - 事件接收模式必须是"长连接"
# - 已订阅 im.message.receive_v1 事件
# - 已发布新版本

# 2. 检查桥接日志
cat /tmp/bridge-final.log

# 3. 测试飞书连接
# 在桥接日志中查找 "connected to wss://"
```

### 命令执行失败

**症状：** 发送命令后返回错误

**解决方案：**
```bash
# 1. 检查应用名称
# macOS 应用使用英文名：
# "Google Chrome" 而不是 "谷歌浏览器"
# "Terminal" 而不是 "终端"

# 2. 检查网址格式
# 使用完整 URL：https://www.google.com
# 或使用关键词：google, baidu 等

# 3. 查看执行日志
cat /tmp/bridge-final.log | grep "execute"
```

## Codex 问题

### Codex 无法连接代理

**症状：** `codex` 命令报错

**解决方案：**
```bash
# 1. 检查配置文件
cat ~/.codex/config.toml
cat ~/.codex/auth.json

# 2. 测试代理连接
curl -s -H "Authorization: Bearer YOUR_KEY" http://127.0.0.1:4000/v1/models

# 3. 检查代理是否在运行
lsof -i :4000
```

### 模型不识别

**症状：** Codex 提示模型不存在

**解决方案：**
```bash
# 1. 检查 proxy-models.json
cat ~/.codex/proxy-models.json

# 2. 确保模型名正确
# deepseek-v4-flash (不是 ds-v4-flash)
```

## 开机自启问题

### launchd 服务不启动

**症状：** 重启后代理未自动启动

**解决方案：**
```bash
# 1. 检查 plist 文件
cat ~/Library/LaunchAgents/com.codex.bridge.plist

# 2. 重新加载
launchctl unload ~/Library/LaunchAgents/com.codex.bridge.plist
launchctl load ~/Library/LaunchAgents/com.codex.bridge.plist

# 3. 检查状态
launchctl list | grep codex
```

## 日志位置

- 代理日志：`/tmp/codex-bridge/proxy.log`
- 代理访问日志：`/tmp/codex-bridge/proxy-access.log`
- 飞书桥接日志：`/tmp/bridge-final.log`

## 获取帮助

如果以上方法无法解决问题：

1. 查看完整日志
2. 检查 GitHub Issues
3. 提交新的 Issue 并提供日志
