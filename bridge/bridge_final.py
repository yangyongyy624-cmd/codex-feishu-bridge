#!/usr/bin/env python3
"""
Feishu <-> Codex Bridge (Cloud Communication + codex exec mode)

Uses Feishu lark-oapi SDK for WebSocket long connection.
Calls `codex exec` for each message (uses codex-bridge proxy for DeepSeek).

Usage:
  1. Start codex-bridge: cd /tmp/codex-bridge && node --env-file=.env proxy.mjs
  2. In Feishu dev console: set event receiving mode to Long Connection
  3. Run: python3 bridge_exec.py
"""

import asyncio
import json
import os
import subprocess
import threading
import time
import urllib.request
from queue import Queue, Empty

import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

# ===== Configuration =====
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "cli_YOUR_FEISHU_APP_ID")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "YOUR_FEISHU_APP_SECRET")
WORKDIR = os.environ.get("WORKDIR", "/Users/zujing/Developer/feishu-codex-bridge")

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
        print(f"[auth] Feishu token acquired (expires in {data.get('expire', 7200)}s)")
        return _feishu_token

def send_feishu_reply(reply_url, text):
    token = get_feishu_token()
    body = json.dumps({
        "content": json.dumps({"text": text}),
        "msg_type": "text"
    }).encode()
    req = urllib.request.Request(reply_url, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
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

# ===== Message queue =====

msg_queue = Queue()

def on_message(data: P2ImMessageReceiveV1) -> None:
    try:
        evt_data = data.event
        if not evt_data:
            return

        msg = evt_data.message
        if not msg:
            return

        msg_id = msg.message_id or ""
        msg_type = msg.message_type or ""

        if msg_type == "text":
            content = json.loads(msg.content or "{}")
            text = content.get("text", "").strip()
        else:
            text = ""

        if not text:
            return

        sender_id = "unknown"
        if evt_data.sender and evt_data.sender.sender_id:
            sender_id = evt_data.sender.sender_id.open_id or "unknown"
        print(f"[feishu] Message from {sender_id}: {text[:60]}...")

        reply_url = f"https://open.feishu.cn/open-apis/im/v1/messages/{msg_id}/reply"
        msg_queue.put((text, reply_url))
    except Exception as e:
        print(f"[feishu] Callback error: {e}")


SYSTEM_PROMPT = (
    "你是一个智能助手，通过飞书与用户对话。你有 bash 工具可以执行命令。"
    "你的工作目录是 /Users/zujing，桌面路径是 /Users/zujing/Desktop。\n"
    "重要规则：\n"
    "1. 先用 bash 执行用户要求的操作\n"
    "2. 执行后必须用详细的中文文字总结你看到了什么、结果是什么\n"
    "3. 不要连续调用超过2次工具。获取到信息后，直接详细总结回复用户\n"
    "4. 回答要具体详细，描述你看到的具体内容，不要只说'已完成'"
)

TOOLS = [
    {
        "name": "bash",
        "type": "function",
        "description": "Execute a bash command. Returns stdout and stderr.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute"
                }
            },
            "required": ["command"]
        }
    }
]

def call_proxy(text, model="deepseek-v4-flash", max_tokens=4096):
    """Call codex-bridge proxy with tool support and return response text."""
    import http.client

    proxy_url = "http://127.0.0.1:4000/v1/responses"
    auth_key = os.environ.get("PROXY_AUTH_KEY", "sk-proxy-YOUR_PROXY_KEY")

    body = json.dumps({
        "model": model,
        "input": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "max_output_tokens": max_tokens,
        "tools": TOOLS,
    })

    conn = http.client.HTTPConnection("127.0.0.1", 4000, timeout=120)
    conn.request("POST", "/v1/responses", body=body.encode(), headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_key}",
    })
    resp = conn.getresponse()

    if resp.status != 200:
        conn.close()
        return f"[代理错误: {resp.status}]"

    # Read SSE events in chunks (chunked transfer encoding doesn't work with readline)
    text_buf = ""
    while True:
        chunk = resp.read(4096)
        if not chunk:
            break
        for line in chunk.decode('utf-8', errors='replace').split('\n'):
            line = line.strip()
            if line.startswith("data: "):
                evt_json = line[6:]
                if evt_json == "[DONE]":
                    conn.close()
                    return text_buf if text_buf else "[代理无返回]"
                try:
                    evt = json.loads(evt_json)
                    etype = evt.get("type", "")
                    if etype == "response.output_text.delta":
                        text_buf += evt.get("delta", "")
                    elif etype == "response.completed":
                        # Prefer completed response text
                        output = evt.get("response", {}).get("output", [])
                        for item in output:
                            if item.get("type") == "message":
                                for content in item.get("content", []):
                                    if content.get("type") == "output_text":
                                        text_buf = content.get("text", text_buf)
                except json.JSONDecodeError:
                    pass

    conn.close()
    return text_buf if text_buf else "[代理无返回]"

def run_codex_exec(text):
    """Send message to DeepSeek via proxy and return response."""
    return call_proxy(text)


async def process_queue():
    while True:
        try:
            text, reply_url = msg_queue.get_nowait()
            print(f"[bridge] Processing: {text[:60]}...")
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, run_codex_exec, text)
            if response:
                send_feishu_reply(reply_url, response)
            else:
                send_feishu_reply(reply_url, "Codex 未返回任何内容")
        except Empty:
            await asyncio.sleep(0.1)


async def main():
    print("=" * 55)
    print("  Feishu <-> Codex Bridge (codex exec mode)")
    print("=" * 55)
    print(f"  Feishu App ID:  {FEISHU_APP_ID}")
    print(f"  Workdir:        {WORKDIR}")
    print()
    print("  Mode: 飞书云通讯长连接 + codex exec")
    print("  Proxy: codex-bridge on port 4000 (DeepSeek)")
    print("=" * 55)
    print()

    # Start queue processor
    asyncio.create_task(process_queue())

    # Start Feishu WS client in a daemon thread
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
