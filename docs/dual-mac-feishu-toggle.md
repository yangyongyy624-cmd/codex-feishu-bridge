# 双 Mac Mini 飞书防冲突开关指南

> **场景**：两台 Mac Mini（旧机 + 新机），配置相同、飞书 App 相同、launchd 服务相同。
> **问题**：两台同时开机会导致飞书连接冲突、端口抢占。
> **解决**：一台开飞书，另一台关飞书。桌面上一键切换。

---

## 第一性原理

飞书冲突的本质是**两个相同的身份同时在线抢资源**（WebSocket 连接、Webhook 回调、SSH 隧道端口）。

最短的解决方案不是改配置，而是**让不想干活的那台彻底断网**——断掉飞书的消息通道，所有基于飞书的服务自然全部静默。

## 架构概览

```
旧 Mac Mini ────────── 飞书 ON ─── 正常接收消息、处理指令
                           ↑
                      二选一开关（不能同时 ON）
                           ↓
新 Mac Mini ────────── 飞书 OFF ──  本地其他服务正常，飞书静默
```

> 任何时候，只有一台机器的飞书是 ON 状态。

## 飞书开关的实现原理

**不关服务、不删配置、不改端口**——改 `/etc/hosts`。

| 状态 | `/etc/hosts` | 效果 |
|------|-------------|------|
| ON | 无飞书域名 | 飞书消息通道正常，所有桥接服务正常工作 |
| OFF | `127.0.0.1 msg-frontier.feishu.cn`<br>`127.0.0.1 open.feishu.cn` | 飞书域名指向本地，所有连接立即断开 |

为什么选这个方案：
- **零配置差异**：两台机器的 plist 完全相同，切换不需要改任何文件
- **即时生效**：修改 hosts + 刷新 DNS 后立即生效
- **可逆**：切回来只需删掉两行，KeepAlive 会自动重连
- **不影响其他服务**：只断飞书，其他服务（Hermes、OpenClaw、Codex 等）照常运行

## 组件清单

### 1. 切换脚本 `toggle-feishu.sh`

```bash
#!/usr/bin/env bash
# Toggle Feishu — 阻断飞书域名 → 所有飞书连接断开
# 恢复域名 → 所有服务自动重连

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: 需要管理员权限"
    echo "请在弹窗中输入密码，或运行: sudo $0"
    exit 1
fi

HOSTS_FILE="/etc/hosts"

is_blocked() {
    grep -q "msg-frontier.feishu.cn" "$HOSTS_FILE" 2>/dev/null
}

kill_feishu_processes() {
    pkill -9 -f "bridge_exec.py" 2>/dev/null || true
    pkill -9 -f "hermes.*gateway.*run" 2>/dev/null || true
    pkill -9 -f "feishu_webhook.py" 2>/dev/null || true
    pkill -9 -f "cc-connect.*run" 2>/dev/null || true
    pkill -9 -f "openclaw.*feishu" 2>/dev/null || true
}

if is_blocked; then
    # === UNBLOCK ===
    echo "正在恢复飞书..."
    sed -i '' '/msg-frontier.feishu.cn/d' "$HOSTS_FILE"
    sed -i '' '/open.feishu.cn/d' "$HOSTS_FILE"
    dscacheutil -flushcache 2>/dev/null || true
    killall -HUP mDNSResponder 2>/dev/null || true
    kill_feishu_processes
    sleep 3
    echo "飞书已恢复 — STATUS:ON"
else
    # === BLOCK ===
    echo "正在关闭飞书..."
    echo "127.0.0.1	msg-frontier.feishu.cn" >> "$HOSTS_FILE"
    echo "127.0.0.1	open.feishu.cn" >> "$HOSTS_FILE"
    dscacheutil -flushcache 2>/dev/null || true
    killall -HUP mDNSResponder 2>/dev/null || true
    kill_feishu_processes
    sleep 2
    echo "飞书已关闭 — STATUS:OFF"
fi
```

### 2. 桌面 App「飞书开关」

用 macOS Automator 打包成 `.app`，双击即可切换：

```applescript
on run
    set toggleScript to (path to home folder as text) & "Developer:feishu-codex-bridge:toggle-feishu.sh"
    set posixPath to POSIX path of toggleScript

    set scriptResult to do shell script posixPath with administrator privileges

    set isBlocked to false
    try
        set hostsContent to do shell script "cat /etc/hosts"
        if hostsContent contains "msg-frontier.feishu.cn" then
            set isBlocked to true
        end if
    end try

    if isBlocked then
        display notification "飞书已关闭 — 本机不再收飞书消息" with title "飞书开关" subtitle "状态: OFF" sound name "Glass"
    else
        display notification "飞书已恢复 — 本机开始收飞书消息" with title "飞书开关" subtitle "状态: ON" sound name "Submarine"
    end if
end run
```

### 3. LaunchAgent 飞书桥接（两台机器完全相同）

```xml
<!-- ~/Library/LaunchAgents/com.codex.feishu-bridge.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.codex.feishu-bridge</string>
    <key>ProgramArguments</key>
    <array>
        <string>python3</string>
        <string>-u</string>
        <string>bridge_exec.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>~/Developer/feishu-codex-bridge</string>
    <key>EnvironmentVariables</key>
    <dict>
        <!-- 敏感信息：在实际部署时设置，不要提交到版本控制 -->
        <key>FEISHU_APP_ID</key>
        <string><!-- 你的飞书 App ID --></string>
        <key>FEISHU_APP_SECRET</key>
        <string><!-- 你的飞书 App Secret --></string>
        <key>WORKDIR</key>
        <string><!-- 你的工作目录 --></string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/codex-bridge/feishu-bridge.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/codex-bridge/feishu-bridge-error.log</string>
</dict>
</plist>
```

## 安装步骤（在新机器上）

### Step 1：复制完整配置

```bash
# 从旧机器同步所有 LaunchAgent
scp old-mac:~/Library/LaunchAgents/ai.*.plist ~/Library/LaunchAgents/
scp old-mac:~/Library/LaunchAgents/com.*.plist ~/Library/LaunchAgents/

# 同步开发目录
rsync -avz old-mac:~/Developer/feishu-codex-bridge/ ~/Developer/feishu-codex-bridge/
rsync -avz old-mac:~/Developer/openclaw/ ~/Developer/openclaw/
# ... 其他需要同步的目录
```

### Step 2：设置环境变量（敏感信息不复制）

创建 `.env` 文件或直接在 plist 中填入：

```bash
# 在新机器上重新设置敏感信息
cd ~/Developer/feishu-codex-bridge
# 编辑 com.codex.feishu-bridge.plist，填入新的 App ID/Secret
```

### Step 3：加载所有服务

```bash
# 加载所有 LaunchAgent（RunAtLoad=true 会自动启动）
launchctl load ~/Library/LaunchAgents/com.codex.feishu-bridge.plist
launchctl load ~/Library/LaunchAgents/ai.openclaw.gateway.plist
# ... 其他服务

# 验证
launchctl list | grep -E "feishu|openclaw|hermes|codex"
```

### Step 4：在新机器上关闭飞书

```bash
# 方法 1：双击桌面「飞书开关.app」
# 方法 2：命令行
sudo ~/Developer/feishu-codex-bridge/toggle-feishu.sh
```

新机器飞书已关闭，旧机器保持 ON。两台机器互不干扰。

### Step 5：验证

```bash
# 检查飞书是否已关闭
cat /etc/hosts | grep feishu
# 应该看到两行：
# 127.0.0.1  msg-frontier.feishu.cn
# 127.0.0.1  open.feishu.cn

# 检查其他服务是否正常
launchctl list | grep -E "openclaw|hermes|codex"
# 应该显示其他服务都在运行
```

## 日常使用

### 切换飞书到哪台机器

1. **在要关闭的机器上**：双击「飞书开关.app」→ 通知「飞书已关闭」
2. **在要开启的机器上**：双击「飞书开关.app」→ 通知「飞书已恢复」

### 关机/开机场景

| 场景 | 旧机器 | 新机器 |
|------|--------|--------|
| 旧机器用着，新机器备用 | 飞书 ON | 飞书 OFF（hosts 已阻断） |
| 换新机器用 | 关机 或 飞书 OFF | 飞书 ON（hosts 已恢复） |
| 临时切换 | 双击开关.app | 双击开关.app |

### 开机后的自动行为

- 所有 `RunAtLoad=true` 的服务会自动启动
- 如果 hosts 里有飞书域名阻断 → 飞书桥接启动后立刻连不上，静默等待
- 如果 hosts 正常 → 飞书桥接正常连接
- **不需要手动干预**

## 注意事项

1. **两台机器的 plist 完全相同**——差异只在 `/etc/hosts`，这是故意的
2. **切换需要 sudo**——Automator app 会弹出密码框
3. **切换后等 3-5 秒**——DNS 刷新 + 进程重启需要时间
4. **KeepAlive=true 是必须的**——关闭飞书后重新开启时，桥接进程需要自动拉起
5. **旧机器完全关机时**，新机器的飞书可以手动打开（双击开关.app 即可）

## 排查

```bash
# 飞书关不掉？
grep feishu /etc/hosts
# 没看到 127.0.0.1 行 → 手动运行: sudo toggle-feishu.sh

# 飞书开了但没反应？
# 1. 检查 hosts 是否已恢复
grep feishu /etc/hosts
# 应该没有 feishu 相关行

# 2. 检查进程是否活着
launchctl list | grep feishu

# 3. 看日志
tail -f /tmp/codex-bridge/feishu-bridge.log

# SSH 隧道端口被占用？（旧机器也开着的时候）
# 旧机器的 SSH 隧道占着远程端口，新机器连不上
# 解决：关旧机器，等 30 秒，新机器自动连上
```
