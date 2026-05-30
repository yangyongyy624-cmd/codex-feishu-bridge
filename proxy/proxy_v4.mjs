import http from 'node:http';
import https from 'node:https';
import { URL } from 'node:url';
import fs from 'node:fs';
import { exec } from 'node:child_process';
import { promisify } from 'node:util';

const execAsync = promisify(exec);

const LOG = '/tmp/codex-bridge/proxy-access.log';
const log = (msg) => {
  const line = `[${new Date().toISOString()}] ${msg}`;
  console.log(line);
  fs.appendFileSync(LOG, line + '\n');
};

const PORT = Number(process.env.PROXY_PORT || 4000);
const AUTH = process.env.PROXY_AUTH_KEY || 'sk-proxy-7a3b9c2d';
const DS_KEY = process.env.DEEPSEEK_API_KEY || '';
const DS_URL = process.env.DEEPSEEK_BASE_URL || 'https://api.deepseek.com/v1';
const QW_KEY = process.env.QWEN_API_KEY || '';
const QW_URL = process.env.QWEN_BASE_URL || 'https://coding.dashscope.aliyuncs.com/v1';
const WORKDIR = process.env.WORKDIR || '/Users/zujing';

const TOOL_DEFINITIONS = [
  {
    name: 'bash',
    description: 'Execute a bash command. Returns stdout and stderr.',
    parameters: {
      type: 'object',
      properties: {
        command: { type: 'string', description: 'The bash command to execute' }
      },
      required: ['command']
    }
  }
];

function qwenModelsList() {
  return (process.env.QWEN_MODELS || '').split(',').map(s => s.trim()).filter(Boolean);
}

function pickTarget(model) {
  const normalized = model === 'ds-v4-flash' ? 'deepseek-v4-flash' : model;
  return qwenModelsList().includes(normalized)
    ? { url: QW_URL, key: QW_KEY }
    : { url: DS_URL, key: DS_KEY };
}

async function executeToolCall(toolCall) {
  const func = toolCall.function;
  const name = func.name;
  const args = JSON.parse(func.arguments || '{}');
  
  if (name === 'bash') {
    try {
      const { stdout, stderr } = await execAsync(args.command, { cwd: WORKDIR, timeout: 30000 });
      return {
        content: `stdout:\n${stdout}\nstderr:\n${stderr}`,
        isError: false
      };
    } catch (e) {
      return {
        content: `Error: ${e.message}`,
        isError: true
      };
    }
  }
  
  return {
    content: `Unknown tool: ${name}`,
    isError: true
  };
}

async function callDeepSeek(targetUrl, target, body, reqId) {
  const mod = targetUrl.protocol === 'https:' ? https : http;
  
  return new Promise((resolve, reject) => {
    mod.request(targetUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${target.key}` },
      timeout: 300000,
    }, upstream => {
      let buf = '';
      upstream.on('data', c => buf += c);
      upstream.on('end', () => {
        try {
          const c = JSON.parse(buf);
          resolve(c);
        } catch (e) {
          reject(new Error(`Parse error: ${e.message}`));
        }
      });
    }).on('error', e => {
      reject(e);
    }).end(JSON.stringify(body));
  });
}

function forward(path, body, model, res, reqId, isChatCompletions) {
  const normalizedModel = model === 'ds-v4-flash' ? 'deepseek-v4-flash' : model;
  body.model = normalizedModel;

  // Add system prompt to instruct model to provide text summary after tool execution
  if (body.messages && body.messages.length > 0) {
    const firstMsg = body.messages[0];
    if (firstMsg.role === 'system') {
      firstMsg.content += '\n\n**重要**：当你使用工具后，必须用自然语言总结执行结果。不要只调用工具而不提供文字回复。';
    } else {
      body.messages.unshift({
        role: 'system',
        content: '你是一个智能助手。当你使用工具执行命令后，必须用自然语言总结执行结果，告诉用户命令的输出是什么。不要只调用工具而不提供文字回复。'
      });
    }
  }

  // Add tool definitions if not present
  if (!body.tools || body.tools.length === 0) {
    body.tools = TOOL_DEFINITIONS.map(t => ({
      type: 'function',
      function: t
    }));
    body.tool_choice = 'auto';
  }

  const target = pickTarget(normalizedModel);
  const targetUrl = new URL(target.url + path);

  log(`${reqId} → ${targetUrl.origin}${path} (model=${normalizedModel}, chat=${isChatCompletions}, tools=${body.tools?.length || 0})`);

  // Handle chat completions directly
  if (isChatCompletions) {
    const mod = targetUrl.protocol === 'https:' ? https : http;
    mod.request(targetUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${target.key}` },
      timeout: 300000,
    }, upstream => {
      let buf = '';
      upstream.on('data', c => buf += c);
      upstream.on('end', () => {
        log(`${reqId} ← ${upstream.statusCode} (${buf.length} bytes)`);
        if (upstream.statusCode !== 200) {
          res.writeHead(upstream.statusCode || 500, { 'Content-Type': 'application/json' });
          return res.end(buf);
        }
        res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
        res.end(buf);
      });
    }).on('error', e => {
      log(`${reqId} ERROR: ${e.message}`);
      res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: { message: e.message } }));
    }).end(JSON.stringify(body));
    return;
  }

  // Handle Responses API with tool execution loop
  (async () => {
    try {
      let messages = body.messages || [];
      let maxRounds = 3; // Reduced from 5 to 3 to prevent infinite loops
      let round = 0;
      let lastResponse = null;
      let lastToolOutput = '';

      while (round < maxRounds) {
        round++;
        log(`${reqId} Round ${round}`);
        
        const apiBody = {
          model: normalizedModel,
          messages: messages,
          max_tokens: body.max_tokens || body.max_output_tokens,
          tools: body.tools,
          tool_choice: body.tool_choice
        };

        const response = await callDeepSeek(targetUrl, target, apiBody, reqId);
        lastResponse = response;
        
        const msg = response.choices?.[0]?.message || {};
        const toolCalls = msg.tool_calls || [];
        const text = msg.content || '';
        
        log(`${reqId} Round ${round}: tool_calls=${toolCalls.length}, text_len=${text.length}`);
        
        if (toolCalls.length > 0) {
          // Add assistant message with tool calls
          messages.push({
            role: 'assistant',
            content: text || null,
            tool_calls: toolCalls
          });
          
          // Execute tools and add results
          for (const tc of toolCalls) {
            const result = await executeToolCall(tc);
            lastToolOutput = result.content;
            messages.push({
              role: 'tool',
              tool_call_id: tc.id,
              name: tc.function.name,
              content: result.content
            });
            log(`${reqId} Tool ${tc.function.name} executed: ${result.content.substring(0, 100)}`);
          }
          
          // If this is the last round, use the tool output as the final response
          if (round >= maxRounds) {
            log(`${reqId} Max rounds reached, using tool output as final response`);
            break;
          }
          
          // Continue to next round
          continue;
        } else {
          // No more tool calls, we have the final response
          break;
        }
      }

      // Determine final text
      let finalText = '';
      if (lastResponse) {
        const finalMsg = lastResponse.choices?.[0]?.message || {};
        finalText = finalMsg.content || '';
      }
      
      // If no text but we have tool output, use tool output
      if (!finalText && lastToolOutput) {
        finalText = `命令执行结果：\n${lastToolOutput}`;
      }
      
      const respId = lastResponse?.id || `resp_${Date.now()}`;
      
      const usage = {
        input_tokens: lastResponse?.usage?.prompt_tokens || 0,
        output_tokens: lastResponse?.usage?.completion_tokens || 0,
        total_tokens: lastResponse?.usage?.total_tokens || 0,
      };

      const output = [{
        type: 'message',
        role: 'assistant',
        content: [{ type: 'output_text', text: finalText }]
      }];

      log(`${reqId} Final response: text_len=${finalText.length}, rounds=${round}`);

      res.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', 'Connection': 'keep-alive', 'X-Accel-Buffering': 'no', 'Access-Control-Allow-Origin': '*' });
      res.write(`data: ${JSON.stringify({ type: 'response.created', response: { id: respId, object: 'response', status: 'in_progress', model: normalizedModel, output: [] } })}\n\n`);
      res.write(`data: ${JSON.stringify({ type: 'response.in_progress' })}\n\n`);
      res.write(`data: ${JSON.stringify({ type: 'response.output_item.added', item: { type: 'message', role: 'assistant', id: `item_${respId}`, content: [] } })}\n\n`);
      
      if (finalText) {
        res.write(`data: ${JSON.stringify({ type: 'response.output_text.delta', delta: finalText })}\n\n`);
      }
      
      res.write(`data: ${JSON.stringify({ type: 'response.output_text.done', item_index: 0 })}\n\n`);
      res.write(`data: ${JSON.stringify({ type: 'response.output_item.done' })}\n\n`);
      res.write(`data: ${JSON.stringify({ type: 'response.completed', response: { id: respId, object: 'response', status: 'completed', model: normalizedModel, output, usage, created_at: lastResponse?.created || Math.floor(Date.now() / 1000) } })}\n\n`);
      res.end();
    } catch (e) {
      log(`${reqId} Error: ${e.message}`);
      res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: { message: e.message } }));
    }
  })();
}

http.createServer((req, res) => {
  if (req.method === 'OPTIONS') {
    res.writeHead(204, { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type, Authorization' });
    return res.end();
  }

  const auth = req.headers.authorization || '';
  if (AUTH && !auth.includes(AUTH)) {
    res.writeHead(401, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify({ error: { message: 'Unauthorized' } }));
  }

  const reqId = `${req.method} ${req.url}`;
  log(`→ ${reqId}`);

  const url = new URL(req.url, `http://${req.headers.host}`);

  if (url.pathname === '/v1/models' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
    return res.end(JSON.stringify({
      object: 'list',
      data: [...qwenModelsList().map(m => ({ id: m, object: 'model', owned_by: 'qwen' })),
        { id: 'deepseek-v4-flash', object: 'model', owned_by: 'deepseek' },
        { id: 'ds-v4-flash', object: 'model', owned_by: 'deepseek' },
        { id: 'deepseek-v4-pro', object: 'model', owned_by: 'deepseek' },
        { id: 'ds-v4-pro', object: 'model', owned_by: 'deepseek' }],
    }));
  }

  if (url.pathname !== '/v1/chat/completions' && url.pathname !== '/v1/responses') {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify({ error: { message: `not found: ${url.pathname}` } }));
  }

  let buf = '';
  req.on('data', c => buf += c);
  req.on('end', () => {
    let body = {};
    try { body = JSON.parse(buf); } catch { res.writeHead(400); return res.end('bad json'); }

    if (url.pathname === '/v1/chat/completions') {
      return forward('/chat/completions', body, body.model, res, reqId, true);
    }

    // Responses API → translate to chat completions
    const input = body.input;
    const messages = typeof input === 'string'
      ? [{ role: 'user', content: input }]
      : Array.isArray(input)
      ? input.map(m => {
          let role = m.role || 'user';
          if (role === 'developer') role = 'system';
          if (role === 'latest_reminder') role = 'system';
          let content = m.content || '';
          if (Array.isArray(content)) content = content.map(p => typeof p === 'string' ? p : (p.text || '')).join('');
          return { role, content };
        })
      : [{ role: 'user', content: JSON.stringify(input) }];

    if (body.instructions) messages.unshift({ role: 'system', content: body.instructions });

    const chatBody = {
      model: body.model, messages, temperature: body.temperature,
      max_tokens: body.max_output_tokens || body.max_tokens,
    };
    
    if (body.tools?.length) {
      chatBody.tools = body.tools;
      chatBody.tool_choice = body.tool_choice || 'auto';
    }

    forward('/chat/completions', chatBody, body.model, res, reqId, false);
  });
}).listen(PORT, '0.0.0.0', () => {
  console.log(`codex-bridge proxy v4 on :${PORT}`);
  console.log(`  deepseek → ${DS_URL}`);
  console.log(`  qwen     → ${QW_URL}`);
  console.log(`  tools    → bash (auto-added, max 3 rounds, fallback to tool output)`);
});
