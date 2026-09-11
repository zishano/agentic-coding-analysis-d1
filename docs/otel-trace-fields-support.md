# OTel 数据对 Trace 核心字段的支持情况

## 问题

你需要的 trace 核心字段：`t`, `input`, `output`, `hash_ids`

OTel 数据能满足这些需求吗？

## 答案

**❌ 不能满足**

只有 **1/4** 的字段有支持，缺失的 3 个字段是 trace 生成的核心依赖。

---

## 详细分析

### ✅ t (timestamp) - 完全支持

**需求**: 请求的时间戳，用于排序和时间线分析

**OTel 支持**: ✅ **完全支持**

**OTel 字段**:
- `startTimeUnixNano`: 请求开始时间（纳秒）
- `endTimeUnixNano`: 请求结束时间（纳秒）

**示例**:
```json
{
  "startTimeUnixNano": "1789031053418133000",
  "endTimeUnixNano": "1789031058043107000"
}
```

**转换**:
```python
# 纳秒 → 秒
timestamp = int(span['startTimeUnixNano']) / 1e9  # 1789031053.418133

# 纳秒 → ISO8601
from datetime import datetime
dt = datetime.fromtimestamp(timestamp)
iso_time = dt.isoformat()  # "2026-09-10T17:04:13.418133"
```

**结论**: 时间戳字段完全可用，只需要格式转换。

---

### ❌ input (输入内容) - 完全不支持

**需求**: LLM 请求的完整输入，包括：
- `messages` 数组 (用户输入 + 历史对话)
- `system` prompt
- `tools` 定义
- `max_tokens`, `temperature` 等参数

**OTel 支持**: ❌ **完全不支持**

**OTel 中的实际情况**:

经过完整扫描 2,223 个 spans，发现的所有 attribute 键（共 86 个）中：
- ❌ 没有 `messages`
- ❌ 没有 `system`
- ❌ 没有 `prompt`
- ❌ 没有 `input`
- ❌ 没有任何包含请求内容的字段

**OTel 只记录了**:
```json
{
  "name": "run_sampling_request",
  "attributes": [
    {"key": "model", "value": "gpt-6-astra"},
    {"key": "turn_id", "value": "01a08a8f-5f8a-7710-a9bd-91ad36538d14"},
    {"key": "cwd", "value": "/path/to/workload"}
  ]
}
```

**对比 requests.db**:
```json
{
  "body": {
    "model": "gpt-6-astra",
    "messages": [
      {"role": "user", "content": "帮我分析这段代码..."},
      {"role": "assistant", "content": "..."}
    ],
    "system": "你是一个代码分析专家...",
    "tools": [...],
    "max_tokens": 4096
  }
}
```

**为什么 OTel 不记录？**

1. **数据量考虑**: `messages` 可能包含数万 tokens，OTel 不适合存储大文本
2. **隐私考虑**: 请求内容可能包含敏感信息（API key、用户数据、代码片段）
3. **用途不同**: OTel 专注于**性能追踪**，不是**数据重放工具**

**替代方案**: 必须从 `requests.db` 的 `body` 字段获取

---

### ❌ output (输出内容) - 完全不支持

**需求**: LLM 响应的完整输出，包括：
- `content` (assistant 回复文本)
- `tool_calls` (工具调用)
- `stop_reason`
- `usage` (token 统计)

**OTel 支持**: ❌ **完全不支持**

**OTel 中的实际情况**:

经过扫描，没有任何字段包含响应内容。

**OTel 只记录了 token 统计**:
```json
{
  "name": "handle_responses",
  "attributes": [
    {"key": "gen_ai.usage.input_tokens", "value": "20634"},
    {"key": "gen_ai.usage.output_tokens", "value": "58"},
    {"key": "gen_ai.usage.cache_read.input_tokens", "value": "0"},
    {"key": "codex.usage.total_tokens", "value": "20692"}
  ]
}
```

**但没有**:
- ❌ assistant 回复的文本内容
- ❌ 工具调用的具体参数
- ❌ stop_reason 的值

**对比 requests.db**:
```json
{
  "response": {
    "content": [
      {
        "type": "text",
        "text": "我来帮你分析这段代码..."
      },
      {
        "type": "tool_use",
        "id": "toolu_xxx",
        "name": "read_file",
        "input": {"path": "main.py"}
      }
    ],
    "stop_reason": "tool_use",
    "usage": {
      "input_tokens": 20634,
      "output_tokens": 58
    }
  }
}
```

**为什么 OTel 不记录？**

同样的原因：数据量、隐私、用途定位。

**替代方案**: 必须从 `requests.db` 的 `response` 字段获取

---

### ❌ hash_ids (内容哈希) - 无法计算

**需求**: 基于 input/output 内容计算的哈希值，用于：
- 内容去重（相同 input → 相同 hash_id）
- 建立引用关系（某个 output 引用了哪个 input）
- 缓存查询（是否见过相同的 input）

**OTel 支持**: ❌ **无法计算**

**原因**: `hash_id` 的计算依赖完整的 `input`/`output` 内容

**典型的 hash_id 计算逻辑**:
```python
import hashlib
import json

def calculate_hash_id(content):
    """基于内容计算 hash_id"""
    # 将内容序列化为规范化的字符串
    normalized = json.dumps(content, sort_keys=True, ensure_ascii=False)
    # 计算 SHA256 哈希
    hash_obj = hashlib.sha256(normalized.encode('utf-8'))
    # 取前 8 字节转为 16 进制
    return hash_obj.hexdigest()[:16]

# 示例
input_content = {
    "messages": [...],
    "system": "...",
    "tools": [...]
}
hash_id = calculate_hash_id(input_content)  # "a1b2c3d4e5f6g7h8"
```

**OTel 的困境**:

没有 `input`/`output` → 无法计算 `hash_id` → 无法去重和建立引用

**替代方案**: 必须基于 `requests.db` 的 `body`/`response` 计算

---

## 实际验证：OTel 中所有 86 个 attribute 键

经过完整扫描 `otel-traces.segment-000001.jsonl`，发现的所有 attribute 键：

```
✅ 有价值的元数据 (与 trace 相关):
  - model                    # 模型名称
  - turn_id                  # 对话轮次 ID
  - gen_ai.usage.input_tokens       # 输入 token 数
  - gen_ai.usage.output_tokens      # 输出 token 数
  - gen_ai.usage.cache_read.input_tokens
  - gen_ai.usage.cache_write.input_tokens
  - codex.usage.total_tokens
  - codex.usage.reasoning_output_tokens

⚠️ 有限价值 (代码执行相关):
  - code.file.path           # 代码文件路径
  - code.line.number         # 代码行号
  - code.module.name         # 模块名
  - cwd                      # 工作目录
  - thread.id / thread.name  # 线程信息
  - busy_ns / idle_ns        # 繁忙/空闲时间

❌ 无价值 (内部实现细节):
  - app_server.connection_id
  - rpc.request_id
  - target
  - 其他 60+ 个字段...

🔍 关键缺失:
  - messages       (输入内容)
  - system         (系统提示词)
  - tools          (工具定义)
  - content        (输出内容)
  - tool_calls     (工具调用)
  - prompt         (提示词)
  - input          (输入)
  - output         (输出)
  - request_body   (请求体)
  - response_body  (响应体)
```

**完整列表** (86 个键):
```
aborted, allow_provider_model_fallback, api.path, app_server.api_version,
app_server.client_name, app_server.client_version, app_server.connection_id,
apps_enabled, busy_ns, call_id, catalog_entry_count, cell.id, code.file.path,
code.line.number, code.module.name, codex.op, codex.request.reasoning_effort,
codex.turn.reasoning_effort, codex.turn.token_usage.*, codex.usage.*,
configuration_pending, connector_count, cwd, dynamic_tool_count,
environment_count, environment_id, from, gen_ai.usage.*, hook.*, http.method,
http.request.method, http.response.status_code, idle_ns, input_count,
item_count, key, model, model.provided, name, non_blocking, plugins_enabled,
provider, refresh_strategy, remote, remote_plugin_enabled, root_count,
rpc.method, rpc.request_id, rpc.system, rpc.transport, runtime_tool_call_id,
search_info_count, selected_skill_count, server.address, server.port,
server_name, session_init.*, submission.id, target, thread.*, thread_id,
thread_start.*, tool_name, tool_spec_count, transport, turn.*, turn_id,
user_input_count, websocket.warmup, wire_api
```

---

## 对比：OTel vs requests.db

| 字段 | OTel | requests.db | 满足需求？ |
|-----|------|-------------|----------|
| **t** | ✅ startTimeUnixNano | ✅ timestamp | ✅ 都可用 |
| **input** | ❌ 无 | ✅ body (完整) | ❌ 必须用 DB |
| **output** | ❌ 无 | ✅ response (完整) | ❌ 必须用 DB |
| **hash_ids** | ❌ 无法计算 | ✅ 可基于 body/response 计算 | ❌ 必须用 DB |
| **model** | ✅ attributes.model | ✅ model | ✅ 都可用 |
| **token usage** | ✅ gen_ai.usage.* | ✅ response.usage.* | ✅ 都可用 |
| **stream 标记** | ❌ 无 | ✅ body.stream | ❌ 必须用 DB |
| **turn_id** | ✅ attributes.turn_id | ❌ 无 | ⚠️ OTel 独有 |
| **trace 上下文** | ✅ traceId/spanId | ❌ 无 | ⚠️ OTel 独有 |
| **代码位置** | ✅ code.file.path | ❌ 无 | ⚠️ OTel 独有 |

---

## 结论

### 能满足你的需求吗？

**❌ 不能**

你需要的 4 个字段：
- ✅ `t` (timestamp): OTel 支持，requests.db 也支持
- ❌ `input`: OTel **完全不支持**，必须用 requests.db
- ❌ `output`: OTel **完全不支持**，必须用 requests.db
- ❌ `hash_ids`: 依赖 input/output，OTel **无法计算**，必须用 requests.db

**支持率**: 1/4 (25%)

### 为什么不能用 OTel？

**核心原因**: OTel 只记录"发生了什么"（元数据），不记录"具体内容是什么"（数据本身）。

```
OTel 告诉你:
  ✅ 在 2026-09-10 17:04:13 发生了一次 LLM 请求
  ✅ 使用的模型是 gpt-6-astra
  ✅ 消耗了 20634 input tokens + 58 output tokens
  ✅ 耗时 4625 毫秒
  ✅ 在 core/src/session/turn.rs:1374 发起
  ✅ turn_id 是 01a08a8f-5f8a-7710-a9bd-91ad36538d14

但 OTel 不告诉你:
  ❌ 用户问了什么 (messages)
  ❌ 系统提示词是什么 (system)
  ❌ 定义了哪些工具 (tools)
  ❌ LLM 回复了什么 (content)
  ❌ 调用了哪些工具 (tool_calls)
```

而 **trace 生成的核心逻辑** 依赖：
1. 解析 `messages` → 计算 prompt 分块
2. 分析 `tools` → 识别工具定义和调用
3. 提取 `content` → 获取 LLM 回复
4. 计算 `hash_ids` → 建立内容去重和引用关系

**没有 input/output 内容 = 无法生成 trace**

### 必须使用 requests.db 的原因

```python
# requests.db 的 body 字段包含 trace 生成所需的一切
{
  "body": {
    "model": "claude-opus-4-8",
    "messages": [
      {"role": "user", "content": "帮我分析这段代码"},
      {"role": "assistant", "content": "..."}
    ],
    "system": "你是一个代码分析专家...",
    "tools": [
      {"name": "read_file", "description": "...", "input_schema": {...}}
    ],
    "max_tokens": 4096,
    "stream": true  # ← trace 生成需要区分流式/非流式
  },
  
  "response": {
    "content": [
      {"type": "text", "text": "我来帮你分析..."},
      {"type": "tool_use", "name": "read_file", "input": {...}}
    ],
    "stop_reason": "tool_use",
    "usage": {"input_tokens": 20634, "output_tokens": 58}
  }
}
```

### 推荐方案

**继续使用 requests.db**，因为它是唯一包含完整 input/output 内容的数据源。

**可选增强**: 如果需要代码级追踪，可以将 OTel 作为补充数据源：
```python
# 1. 从 requests.db 生成基础 trace
trace = generate_trace_from_db(requests_db)

# 2. (可选) 从 OTel 补充调用链和代码位置
if otel_available:
    span = find_span_by_timestamp_and_model(trace.timestamp, trace.model)
    trace.enrich({
        'traceId': span.traceId,
        'turn_id': span.turn_id,
        'code_location': span.code_file_path,
        'execution_breakdown': span.children_timings
    })
```

但 **trace 生成的核心流程** 必须基于 requests.db。
