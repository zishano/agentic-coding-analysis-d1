# OTel 数据 vs requests.db 对比分析

## 概述

本文档对比分析 **OpenTelemetry (OTel) traces 数据**和 **requests.db 代理数据库**两种数据源，评估是否可以用 OTel 替代 requests.db 来生成 agentic coding trace。

## 数据源特征

### OTel Traces (`otel-traces.segment-*.jsonl`)

**数据来源**: Codex Desktop 内置的 OpenTelemetry 采集器，记录代码执行过程中的 span 调用树。

**格式**: JSONL，每行一个完整的 `resourceSpans` 对象。

**典型 span 结构**:
```json
{
  "traceId": "e8142e0b1851522161bea9e5c810e8c9",
  "spanId": "bcc72d5ecea9713f",
  "parentSpanId": "f9bc37bc6313fb6c",
  "name": "run_sampling_request",
  "startTimeUnixNano": "1789031053418133000",
  "endTimeUnixNano": "1789031058043107000",
  "attributes": [
    {"key": "model", "value": {"stringValue": "gpt-6-astra"}},
    {"key": "turn_id", "value": {"stringValue": "01a08a8f-5f8a-7710-a9bd-91ad36538d14"}},
    {"key": "gen_ai.usage.input_tokens", "value": {"intValue": "20634"}},
    {"key": "gen_ai.usage.output_tokens", "value": {"intValue": "58"}}
  ]
}
```

**数据规模** (macmini-otel-20260910-v1 示例):
- 总 spans: **2,223 个**
- 覆盖时间: 约 35.5 秒的单次任务
- 带 model 字段的 spans: 23 个
- HTTP 请求相关: 15 个

### requests.db (代理数据库)

**数据来源**: claude-code-proxy 拦截的所有 Anthropic API HTTP 请求/响应。

**格式**: SQLite 数据库。

**表结构**:
```sql
CREATE TABLE requests (
    id TEXT PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    method TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    headers TEXT NOT NULL,
    body TEXT NOT NULL,              -- 完整请求 JSON
    user_agent TEXT,
    content_type TEXT,
    prompt_grade TEXT,
    response TEXT,                    -- 完整响应 JSON
    model TEXT,
    original_model TEXT,
    routed_model TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

**典型数据**:
- `body`: 包含 `model`, `stream`, `messages`, `system`, `tools`, `max_tokens` 等完整请求
- `response`: 包含 `content`, `usage.input_tokens`, `usage.output_tokens`, `stop_reason` 等完整响应

**数据规模** (示例):
- 总请求数: 80-90 条
- 流式请求 (`stream=true`): 约 50%
- 非流式请求: 约 50%

## 字段映射关系

### ✅ 可完全对应的字段

| 字段用途 | OTel | requests.db | 转换说明 |
|---------|------|-------------|---------|
| **时间戳** | `startTimeUnixNano` / `endTimeUnixNano` | `timestamp` | 纳秒→ISO8601 |
| **模型** | `attributes.model` | `model` / `original_model` | 完全匹配 |
| **Token 使用** | `gen_ai.usage.input_tokens` / `output_tokens` | `response.usage.input_tokens` / `output_tokens` | 完全匹配 |
| **HTTP 方法** | `http.request.method` | `method` | 完全匹配 |

### ⚠️ 部分对应的字段

| 字段用途 | OTel | requests.db | 说明 |
|---------|------|-------------|------|
| **会话 ID** | `turn_id` (部分 span 有) | 无 | OTel 有，DB 缺失 |
| **Trace 上下文** | `traceId` / `spanId` / `parentSpanId` | 无 | OTel 有树状结构，DB 平面 |
| **请求内容** | 无 | `body` (完整 JSON) | **OTel 缺失关键数据** |
| **响应内容** | 无 | `response` (完整 JSON) | **OTel 缺失关键数据** |
| **HTTP 状态** | `http.response.status_code` | 需从 `response` 解析 | 部分可对应 |

### ❌ 无法对应的字段

| 字段 | OTel | requests.db |
|-----|------|-------------|
| **流式标记** | ❌ 无 | ✅ `body.stream` |
| **请求 ID** | ❌ 无 | ✅ `id` |
| **用户代理** | ❌ 无 | ✅ `user_agent` |
| **代码位置** | ✅ `code.file.path` / `code.module.name` | ❌ 无 |
| **Span 层级** | ✅ `parentSpanId` 树状结构 | ❌ 平面单请求 |

## 关键差异分析

### 1. 数据完整性

#### OTel 的优势
- ✅ **完整的调用链**: 通过 `traceId` + `parentSpanId` 构建完整的调用树
- ✅ **代码执行路径**: 记录了哪个模块 (code.module.name)、哪个文件 (code.file.path)、哪一行 (code.line.number) 发起的调用
- ✅ **精确的性能数据**: 纳秒级的 `startTimeUnixNano` / `endTimeUnixNano`，可计算每个 span 的精确耗时
- ✅ **Turn ID**: 可以关联到具体的对话轮次

#### OTel 的缺失
- ❌ **无完整请求内容**: 没有 `messages`、`system prompt`、`tools` 定义
- ❌ **无完整响应内容**: 没有 assistant 的回复文本
- ❌ **无流式标记**: 无法区分是流式还是非流式请求
- ❌ **无请求 ID**: 无法直接与 requests.db 主键对应

#### requests.db 的优势
- ✅ **完整的 API 调用记录**: `body` 包含所有请求参数
- ✅ **完整的响应**: `response` 包含所有返回内容
- ✅ **流式标记**: `body.stream` 明确标识请求类型
- ✅ **唯一 ID**: `id` 可作为主键关联

#### requests.db 的缺失
- ❌ **无调用链上下文**: 只有平面的单个请求记录
- ❌ **无代码位置**: 不知道哪段代码发起的请求
- ❌ **无 Turn ID**: 无法直接关联到会话轮次
- ❌ **无 span 层级**: 缺少内部执行细节

### 2. 对 trace 生成的影响

**当前 trace 生成流程依赖的关键数据**:

1. ✅ **sessionId** → OTel 无直接字段，但可从 `turn_id` 推断
2. ❌ **messages 内容** → **OTel 完全没有，这是致命缺失**
3. ✅ **timestamp** → OTel 有 (需转换)
4. ❌ **stream 标记** → **OTel 没有**
5. ✅ **model** → OTel 有
6. ✅ **token usage** → OTel 有

**结论**: OTel **无法独立生成 trace**，因为缺少 `messages` 这个核心字段。

### 3. 数据粒度差异

| 维度 | OTel | requests.db |
|-----|------|-------------|
| **记录粒度** | 代码执行层面的 span | HTTP 请求层面的记录 |
| **一个 API 请求** | 可能对应多个 span (准备、发送、接收、处理) | 仅一条记录 |
| **子代理调用** | 通过 `parentSpanId` 自然形成树 | 需手动关联 (通过 timestamp) |
| **流式请求** | 无法区分 | 明确标记 `stream=true/false` |

**示例**: 一次 LLM 请求在两种数据源中的体现

**OTel** (多个 span):
```
run_sampling_request (4625ms, model=gpt-6-astra)
├── built_tools (31ms)
├── try_run_sampling_request (4625ms)
│   ├── model_client.stream_responses_websocket (1603ms)
│   └── handle_responses (含 token 统计)
└── ...
```

**requests.db** (单条记录):
```json
{
  "id": "abc123",
  "timestamp": "2026-09-10T17:04:05+08:00",
  "body": {"model": "gpt-6-astra", "stream": true, "messages": [...]},
  "response": {"content": [...], "usage": {...}}
}
```

## 能否用 OTel 替代 requests.db？

### 直接回答: ❌ **不能完全替代**

### 原因

1. **缺少完整的请求/响应内容**
   - Trace 生成需要 `messages` 字段来计算 prompt 分块、识别工具调用等
   - OTel 只记录了"发生了一次 LLM 请求"，但不记录"请求的具体内容是什么"

2. **缺少流式标记**
   - 当前代码中 `INCLUDE_STREAMING` 参数依赖 `body.stream` 字段
   - OTel 无法区分流式和非流式请求

3. **数据用途不同**
   - OTel: 用于**性能分析、调用链追踪、问题诊断**
   - requests.db: 用于**重放请求、生成 trace、数据分析**

### 但可以作为补充数据源

**组合使用方案**:

```python
# 1. 从 requests.db 获取完整的请求/响应
request = db.get_request_by_id(request_id)
messages = request.body['messages']
response_content = request.response['content']

# 2. 从 OTel 获取性能和调用链数据
span = otel.find_span_by_time_and_model(
    timestamp=request.timestamp,
    model=request.model
)
trace_context = {
    'traceId': span.traceId,
    'parentSpanId': span.parentSpanId,
    'turn_id': span.attributes.turn_id,
    'duration_ms': (span.endTimeUnixNano - span.startTimeUnixNano) / 1e6,
    'code_location': span.attributes.code_file_path
}

# 3. 合并生成增强的 trace
enhanced_trace = {
    **trace_from_db(request),      # 基础 trace (messages, tokens, 等)
    **trace_context                 # 补充上下文 (调用链, 性能, 代码位置)
}
```

## 实际示例对比

### OTel 中的 token 统计

```
Span: handle_responses
  input_tokens: 20634
  output_tokens: 58
  cache_read: 0
  total: 20692
```

### requests.db 中的相同信息

```json
{
  "response": {
    "usage": {
      "input_tokens": 20634,
      "output_tokens": 58,
      "cache_read_input_tokens": 0
    }
  }
}
```

**结论**: Token 统计完全一致，可互相验证。

## 数据质量对比

### OTel 数据质量

**优点**:
- ✅ 时间戳精度高 (纳秒级)
- ✅ 有数据完整性校验 (SHA256SUMS)
- ✅ 有接收/写出对账 (接收数 = 写出数 = 落盘数)

**局限**:
- ⚠️ 存在源端截断标记 (2 条)
- ⚠️ 仅覆盖单次任务，非历史全量

### requests.db 数据质量

**优点**:
- ✅ 完整记录所有代理经手的请求
- ✅ 流式/非流式都完整保存
- ✅ 可长期累积历史数据

**局限**:
- ⚠️ 依赖代理正确运行
- ⚠️ 时间戳精度较低 (秒级)
- ⚠️ 无数据完整性自校验

## 推荐方案

### 方案一: 保持现状 (仅用 requests.db)

**适用场景**: 只需要生成基础 trace，不需要代码执行路径和调用链分析。

**优点**:
- 实现简单，已有完整工具链
- 数据完整，满足当前需求

**缺点**:
- 缺少代码级别的追踪能力
- 无法分析性能瓶颈

### 方案二: 两者结合 (推荐)

**适用场景**: 需要同时分析 API 调用和代码执行路径。

**实现方式**:
1. 继续用 requests.db 生成基础 trace
2. 新增 OTel 数据解析模块
3. 通过 `timestamp` + `model` 关联两种数据源
4. 在 trace 中补充 `traceId`、`turn_id`、`code_location` 等字段

**优点**:
- 保留现有能力
- 增加深度分析能力
- 可追溯到代码具体执行路径

**缺点**:
- 需要额外开发
- 需要同时维护两种数据源

### 方案三: 仅用 OTel (不推荐)

**不可行原因**:
- ❌ 无法获取 `messages` 内容
- ❌ 无法区分流式/非流式
- ❌ 需要大幅修改现有 trace 生成逻辑

## 总结

| 维度 | OTel | requests.db | 组合使用 |
|-----|------|-------------|---------|
| **生成基础 trace** | ❌ 不可行 | ✅ 可行 | ✅ 可行 |
| **代码执行追踪** | ✅ 优秀 | ❌ 无 | ✅ 优秀 |
| **性能分析** | ✅ 优秀 | ⚠️ 基础 | ✅ 优秀 |
| **调用链分析** | ✅ 完整树状 | ❌ 平面 | ✅ 完整树状 |
| **请求内容分析** | ❌ 无 | ✅ 完整 | ✅ 完整 |
| **实现复杂度** | 高 | 低 | 中等 |

**最终建议**: 
- **短期**: 继续使用 requests.db，满足当前 trace 生成需求
- **中长期**: 开发 OTel + requests.db 组合分析工具，提供更深入的代码级追踪能力
