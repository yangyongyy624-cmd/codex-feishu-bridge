#!/usr/bin/env python3
"""
Final Feishu Bridge — 可靠的消息处理

使用 http.client 读取 SSE 流，避免 urllib 的阻塞问题
"""
import asyncio, json, os, time, threading, http.client, urllib.request, re, subprocess
from asyncio import QueueEmpty
import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "YOUR_FEISHU_APP_ID")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "YOUR_FEISHU_APP_SECRET")
PROXY_AUTH = os.environ.get("PROXY_AUTH_KEY", "YOUR_PROXY_AUTH_KEY")
WORKDIR = os.environ.get("WORKDIR", "/path/to/your/workdir")

# 命令关键词
CMD_KEYWORDS = ['执行', '运行', '打开', '启动', '关闭', '停止', '重启', '列出', '查看', '创建', '删除', '移动', '复制', '下载', '安装', '卸载', '更新', '搜索', '查找', '计算', '转换', '压缩', '解压', '备份', '恢复']

# ===== Feishu REST =====
_feishu_token = None
_feishu_token_expires = 0

def get_feishu_token():
    global _feishu_token, _feishu_token_expires
    now = time.time()
    if _feishu_token and now < _feishu_token_expires - 60:
        return _feishu_token
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    body = json.dumps({"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
        if data.get("code") != 0:
            raise Exception(f"Feishu auth failed: {data}")
        _feishu_token = data["tenant_access_token"]
        _feishu_token_expires = now + data.get("expire", 7200)
        return _feishu_token

def send_feishu_reply(reply_url, text):
    token = get_feishu_token()
    if len(text) > 1900:
        text = text[:1900] + "\n...（内容过长已截断）"
    body = json.dumps({"content": json.dumps({"text": text}), "msg_type": "text"}).encode()
    req = urllib.request.Request(reply_url, data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {token}"
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            if result.get("code") != 0:
                print(f"[feishu] Reply failed: {result}")
            else:
                print(f"[feishu] Reply sent ({len(text)} chars)")
    except Exception as e:
        print(f"[feishu] Reply error: {e}")

def call_proxy(text):
    """使用 http.client 调用代理 API，避免 SSE 流阻塞"""
    body = json.dumps({
        "model": "deepseek-v4-flash",
        "input": [{"type": "text", "text": text}],
        "max_output_tokens": 4096,
    })
    
    conn = http.client.HTTPConnection("127.0.0.1", 4000, timeout=120)
    try:
        conn.request("POST", "/v1/responses", body=body.encode(), headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {PROXY_AUTH}",
        })
        
        resp = conn.getresponse()
        if resp.status != 200:
            return f"[代理错误: {resp.status}]"
        
        text_buf = ""
        while True:
            line = resp.readline().decode('utf-8', errors='replace').strip()
            if not line:
                break
            if line.startswith("data: "):
                evt_json = line[6:]
                if evt_json == "[DONE]":
                    break
                try:
                    evt = json.loads(evt_json)
                    if evt.get("type") == "response.output_text.delta":
                        text_buf += evt.get("delta", "")
                    elif evt.get("type") == "response.completed":
                        output = evt.get("response", {}).get("output", [])
                        for item in output:
                            if item.get("type") == "message":
                                for content in item.get("content", []):
                                    if content.get("type") == "output_text":
                                        text_buf = content.get("text", text_buf)
                except:
                    pass
        return text_buf
    except Exception as e:
        return f"[代理调用失败: {e}]"
    finally:
        conn.close()

def is_command_intent(text):
    """检测用户消息是否包含命令意图"""
    for keyword in CMD_KEYWORDS:
        if keyword in text:
            return True
    return False

def execute_command(text):
    """执行命令"""
    # 清理命令文本
    cmd = text.strip()
    cmd = cmd.rstrip('。，,;；')
    
    # 如果是打开网页
    if '打开' in cmd and ('http' in cmd or 'www' in cmd or '.com' in cmd or '.cn' in cmd or 'google' in cmd.lower() or 'chrome' in cmd.lower()):
        url_match = re.search(r'(https?://[^\s]+)', cmd)
        if url_match:
            url = url_match.group(1)
        else:
            # 检查是否是常见的网站名称
            site_map = {
                'google': 'https://www.google.com',
                '百度': 'https://www.baidu.com',
                'baidu': 'https://www.baidu.com',
                'bing': 'https://www.bing.com',
                'github': 'https://github.com',
                'youtube': 'https://www.youtube.com',
                'twitter': 'https://twitter.com',
                'facebook': 'https://www.facebook.com',
            }
            
            url = None
            for name, site_url in site_map.items():
                if name in cmd.lower():
                    url = site_url
                    break
            
            if not url:
                url_match = re.search(r'([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', cmd)
                if url_match:
                    url = 'http://' + url_match.group(1)
                else:
                    # 默认打开 Google
                    url = 'https://www.google.com'
        
        try:
            subprocess.run(['open', url], check=True)
            return f"✅ 已打开网页：{url}"
        except Exception as e:
            return f"❌ 打开网页失败：{str(e)}"
    
    # 如果是打开应用
    if '打开' in cmd:
        app_name = cmd.replace('打开', '').strip()
        
        # 映射常见应用名称
        app_map = {
            '浏览器': 'Google Chrome',
            'chrome': 'Google Chrome',
            '谷歌浏览器': 'Google Chrome',
            'google 浏览器': 'Google Chrome',
            'safari': 'Safari',
            '终端': 'Terminal',
            'terminal': 'Terminal',
            'finder': 'Finder',
            '访达': 'Finder',
            '邮件': 'Mail',
            'mail': 'Mail',
            '日历': 'Calendar',
            'calendar': 'Calendar',
            '备忘录': 'Notes',
            'notes': 'Notes',
            '照片': 'Photos',
            'photos': 'Photos',
            '音乐': 'Music',
            'music': 'Music',
            '视频': 'QuickTime Player',
            'quicktime': 'QuickTime Player',
            'xcode': 'Xcode',
            'vscode': 'Visual Studio Code',
            'visual studio code': 'Visual Studio Code',
            'pycharm': 'PyCharm',
            'intellij': 'IntelliJ IDEA',
            'webstorm': 'WebStorm',
            'docker': 'Docker',
            'iterm': 'iTerm2',
            'iterm2': 'iTerm2',
        }
        
        # 尝试映射应用名称
        mapped_app = app_map.get(app_name.lower(), app_name)
        
        try:
            # 先尝试使用映射后的名称
            subprocess.run(['open', '-a', mapped_app], check=True)
            return f"✅ 已打开应用：{mapped_app}"
        except Exception as e:
            # 如果失败，尝试使用原始名称
            try:
                subprocess.run(['open', '-a', app_name], check=True)
                return f"✅ 已打开应用：{app_name}"
            except Exception as e2:
                # 最后尝试直接打开
                try:
                    subprocess.run(['open', app_name], check=True)
                    return f"✅ 已尝试打开：{app_name}"
                except Exception as e3:
                    return f"❌ 打开失败：{str(e3)}\n提示：请检查应用名称是否正确"
    
    # 如果是列出文件
    if '列出' in cmd or '查看' in cmd:
        dir_path = cmd.replace('列出', '').replace('查看', '').strip()
        if not dir_path or dir_path in ['文件', '目录', '文件夹']:
            dir_path = WORKDIR
        
        # 展开 ~ 路径
        dir_path = os.path.expanduser(dir_path)
        
        try:
            result = subprocess.run(['ls', '-la', dir_path], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                output = result.stdout.strip()
                if len(output) > 1500:
                    output = output[:1500] + "\n...（内容过长已截断）"
                return f"✅ {dir_path} 目录内容：\n```\n{output}\n```"
            else:
                return f"❌ 列出目录失败：{result.stderr.strip()}"
        except Exception as e:
            return f"❌ 列出目录失败：{str(e)}"
    
    # 默认尝试作为 shell 命令执行
    if '执行' in cmd or '运行' in cmd:
        shell_cmd = cmd.replace('执行', '').replace('运行', '').strip()
        shell_cmd = shell_cmd.lstrip('命令').strip()
    else:
        # 默认尝试作为 shell 命令执行
        shell_cmd = cmd
    
    try:
        result = subprocess.run(shell_cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=WORKDIR)
        output = result.stdout.strip()
        error = result.stderr.strip()
        
        if result.returncode == 0:
            if output:
                if len(output) > 1500:
                    output = output[:1500] + "\n...（内容过长已截断）"
                return f"✅ 命令执行成功：\n```\n{output}\n```"
            else:
                return f"✅ 命令执行成功（无输出）"
        else:
            if error:
                return f"⚠️ 命令执行有错误：\n```\n{error}\n```"
            else:
                return f"❌ 命令执行返回非零退出码：{result.returncode}"
    except subprocess.TimeoutExpired:
        return f"❌ 命令执行超时（30秒限制）：`{shell_cmd}`"
    except Exception as e:
        return f"❌ 命令执行失败：`{shell_cmd}`\n错误：{str(e)}"

msg_queue = asyncio.Queue()

def on_message(data: P2ImMessageReceiveV1) -> None:
    try:
        evt_data = data.event
        if not evt_data: return
        msg = evt_data.message
        if not msg: return
        msg_id = msg.message_id or ""
        msg_type = msg.message_type or ""
        if msg_type == "text":
            content = json.loads(msg.content or "{}")
            text = content.get("text", "").strip()
        else:
            text = ""
        if not text: return
        sender_id = "unknown"
        if evt_data.sender and evt_data.sender.sender_id:
            sender_id = evt_data.sender.sender_id.open_id or "unknown"
        print(f"[feishu] Message from {sender_id}: {text[:60]}...")
        reply_url = f"https://open.feishu.cn/open-apis/im/v1/messages/{msg_id}/reply"
        msg_queue.put_nowait((text, reply_url))
    except Exception as e:
        print(f"[feishu] Callback error: {e}")

async def process_queue():
    while True:
        try:
            text, reply_url = msg_queue.get_nowait()
            print(f"[bridge] Processing: {text[:60]}...")
            
            if is_command_intent(text):
                print(f"[bridge] Detected command intent")
                response = execute_command(text)
            else:
                print(f"[bridge] Calling proxy API")
                response = call_proxy(text)
            
            print(f"[bridge] Response ({len(response)} chars): {response[:100]}...")
            send_feishu_reply(reply_url, response)
        except QueueEmpty:
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"[bridge] Error: {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(1)

async def main():
    print("=" * 55)
    print("  Final Feishu Bridge")
    print("=" * 55)
    print(f"  Feishu App ID:  {FEISHU_APP_ID}")
    print(f"  Proxy URL:      http://127.0.0.1:4000/v1/responses")
    print(f"  Workdir:        {WORKDIR}")
    print(f"  Mode:           Direct command execution")
    print("=" * 55)
    print()

    asyncio.create_task(process_queue())

    def run_feishu_ws():
        ws_client = lark.ws.Client(
            app_id=FEISHU_APP_ID,
            app_secret=FEISHU_APP_SECRET,
            log_level=lark.LogLevel.INFO,
            event_handler=lark.EventDispatcherHandler.builder("", "")
                .register_p2_im_message_receive_v1(on_message)
                .build()
        )
        ws_client.start()

    feishu_thread = threading.Thread(target=run_feishu_ws, daemon=True)
    feishu_thread.start()
    print("[feishu] Cloud communication WebSocket started")
    print()

    try:
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        print("\n[bridge] Shutting down")

if __name__ == "__main__":
    asyncio.run(main())
