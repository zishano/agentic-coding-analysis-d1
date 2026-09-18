# count_jsonl.sh 使用说明

统计 JSONL 文件中的消息数据，类似于 `count_classification.sh` 但针对本地 JSONL 文件。

---

## 📋 功能

- 统计 JSONL 文件中的 assistant 消息
- 按时间范围过滤
- 显示详细的分类统计
- 验证数据完整性

---

## 🚀 使用方法

### 1. 基本用法（统计所有数据）

```bash
./scripts/count_jsonl.sh
```

**输出示例**：
```
======================================================================
JSONL 文件数据统计
======================================================================
时间范围: 全部数据

扫描的文件: 17,076
├─ 主会话文件: 9,612
└─ 子代理文件: 7,464

总 assistant 消息数: 284,956
├─ 有 message_id: 278,528 (97.7%)
└─ 无 message_id: 6,428 (2.3%)

唯一会话数: 9,612
...
```

---

### 2. 指定时间范围

```bash
./scripts/count_jsonl.sh \
  --start "2026-09-07T17:00:00+08:00" \
  --end "2026-09-07T18:00:00+08:00"
```

**输出示例**：
```
======================================================================
JSONL 文件数据统计
======================================================================
时间范围: 2026-09-07T17:00:00+08:00 ~ 2026-09-07T18:00:00+08:00

扫描的文件: 151
├─ 主会话文件: 98
└─ 子代理文件: 53

总 assistant 消息数: 1,133
├─ 有 message_id: 1,120 (98.9%)
└─ 无 message_id: 13 (1.1%)
...
```

---

### 3. 指定 JSONL 根目录

```bash
./scripts/count_jsonl.sh --jsonl-root /path/to/projects
```

---

### 4. 组合使用

```bash
./scripts/count_jsonl.sh \
  --jsonl-root tmp/projects \
  --start "2026-09-07T17:00:00+08:00" \
  --end "2026-09-07T18:00:00+08:00"
```

---

## 📊 输出说明

### 文件统计

```
扫描的文件: 151
├─ 主会话文件: 98      ← 不含 "agent-" 的文件
└─ 子代理文件: 53       ← 含 "agent-" 的文件
```

### 消息统计

```
总 assistant 消息数: 1,133
├─ 有 message_id: 1,120 (98.9%)   ← msg_* 或 resp_* 开头
└─ 无 message_id: 13 (1.1%)        ← 无效或缺失的 ID
```

### 会话统计

```
唯一会话数: 98          ← 基于 sessionId 或文件名
```

### Content 统计

```
Content 统计:
├─ 有 content: 1,133 (100.0%)     ← content 字段非空
└─ 无 content: 0 (0.0%)            ← content 字段为空
```

**说明**：
- JSONL 中应该所有消息都有 content
- 如果有消息没有 content，说明数据异常

### Message Type 分布

```
Message Type 分布:
├─ message: 1,133 (100.0%)         ← message.type 字段
```

**常见类型**：
- `message`: 标准消息
- `stream`: 流式消息（理论上不应出现在 JSONL 中）

### Stop Reason 分布

```
Stop Reason 分布:
├─ 'tool_use': 1,056 (93.2%)      ← 调用工具结束
├─ 'end_turn': 64 (5.6%)           ← 正常结束
├─ 'stop_sequence': 13 (1.1%)      ← 遇到停止序列
```

**常见 stop_reason**：
- `tool_use`: 模型调用了工具
- `end_turn`: 正常完成回复
- `stop_sequence`: 遇到预定义的停止序列
- `max_tokens`: 达到最大 token 限制
- `空/NULL`: 没有 stop_reason（异常）

### 验证

```
验证
======================================================================
1,120 + 13 = 1,133
应该等于总数: 1,133
✓ 总数一致
```

---

## 🆚 与 count_classification.sh 对比

| 特性 | count_classification.sh | count_jsonl.sh |
|------|------------------------|----------------|
| **数据源** | 数据库 (requests.db) | JSONL 文件 |
| **统计对象** | 请求和响应 | Assistant 消息 |
| **分类维度** | isStreaming, body, 错误码 | message_id, stop_reason, content |
| **时间过滤** | ✅ 支持 | ✅ 支持 |
| **默认行为** | 统计所有数据 | 统计所有数据 |

---

## 💡 常见使用场景

### 场景 1: 快速查看全部数据概览

```bash
./scripts/count_jsonl.sh
```

**用途**：
- 了解 JSONL 文件总体情况
- 查看数据量级
- 检查数据质量

---

### 场景 2: 统计特定时间段

```bash
# 统计一小时
./scripts/count_jsonl.sh \
  --start "2026-09-07T17:00:00+08:00" \
  --end "2026-09-07T18:00:00+08:00"

# 统计一天
./scripts/count_jsonl.sh \
  --start "2026-09-07T00:00:00+08:00" \
  --end "2026-09-07T23:59:59+08:00"
```

**用途**：
- 按时间段分析数据
- 对比不同时间段的数据质量
- 定位问题发生的时间

---

### 场景 3: 对比数据库和 JSONL

```bash
# 1. 统计数据库
./scripts/count_classification.sh \
  --start "2026-09-07T17:00:00+08:00" \
  --end "2026-09-07T18:00:00+08:00"

# 2. 统计 JSONL
./scripts/count_jsonl.sh \
  --start "2026-09-07T17:00:00+08:00" \
  --end "2026-09-07T18:00:00+08:00"

# 3. 对比结果
```

**对比指标**：
- 有 message_id 的数量
- stop_reason 分布
- 数据覆盖率

---

### 场景 4: 检查数据异常

```bash
./scripts/count_jsonl.sh | grep "无 content\|空/NULL"
```

**检查项**：
- 是否有消息没有 content
- 是否有消息没有 stop_reason
- message_id 缺失率

---

## 📈 实际数据示例

### 一小时数据（2026-09-07 17:00-18:00）

```
扫描的文件: 151
  - 主会话: 98 个
  - 子代理: 53 个

总消息: 1,133
  - 有 message_id: 1,120 (98.9%)
  - 无 message_id: 13 (1.1%)

唯一会话: 98

Content: 100.0% 有内容
Message Type: 100.0% 是 "message"
Stop Reason:
  - tool_use: 93.2%
  - end_turn: 5.6%
  - stop_sequence: 1.1%
```

### 全量数据

```
扫描的文件: 17,076
  - 主会话: 9,612 个
  - 子代理: 7,464 个

总消息: 284,956
  - 有 message_id: 278,528 (97.7%)
  - 无 message_id: 6,428 (2.3%)

唯一会话: 9,612

Content: 100.0% 有内容
Message Type: 100.0% 是 "message"
Stop Reason:
  - tool_use: 88.5%
  - end_turn: 9.2%
  - stop_sequence: 2.3%
  - 空/NULL: 0.0%
```

---

## 🔍 数据质量指标

### 健康的数据特征

✅ **好的指标**：
- `有 message_id` > 95%
- `有 content` = 100%
- `有 stop_reason` > 99%
- `message type` = "message" (100%)

❌ **问题指标**：
- `无 content` > 0%
- `空/NULL stop_reason` > 1%
- `无 message_id` > 5%

---

## 🛠️ 故障排除

### 问题 1: 找不到 Python 脚本

```
❌ 错误: 找不到 Python 脚本: /path/to/count_jsonl.py
```

**解决**：
```bash
# 确保在项目根目录运行
cd /mnt/nvme1n1/data/lmk/PROJECT/agentic-coding-analysis-d1

# 或使用绝对路径
/path/to/scripts/count_jsonl.sh
```

---

### 问题 2: JSONL 根目录不存在

```
❌ 错误: JSONL 根目录不存在: tmp/projects
```

**解决**：
```bash
# 指定正确的目录
./scripts/count_jsonl.sh --jsonl-root /path/to/jsonl
```

---

### 问题 3: 没有找到任何消息

```
❌ 没有找到任何消息
```

**可能原因**：
1. 时间范围内没有数据
2. JSONL 文件格式错误
3. 时间戳字段缺失

**检查**：
```bash
# 查看 JSONL 文件
ls -lh tmp/projects/*/*.jsonl | head

# 检查文件内容
head tmp/projects/*/[文件名].jsonl
```

---

## 📝 参数说明

| 参数 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `--jsonl-root` | ❌ | `tmp/projects` | JSONL 根目录 |
| `--start` | ❌ | 无（不限） | 开始时间 |
| `--end` | ❌ | 无（不限） | 结束时间 |
| `--help` | ❌ | - | 显示帮助 |

### 时间格式

支持的格式：
```
YYYY-MM-DDTHH:MM:SS+08:00
YYYY-MM-DDTHH:MM:SSZ
```

示例：
```
2026-09-07T17:00:00+08:00
2026-09-07T09:00:00Z (UTC)
```

---

## 🎯 最佳实践

### 1. 定期统计

```bash
# 每天统计一次
./scripts/count_jsonl.sh > logs/jsonl_stats_$(date +%Y%m%d).log
```

### 2. 对比分析

```bash
# 统计数据库
./scripts/count_classification.sh --start "$START" --end "$END" > db.log

# 统计 JSONL
./scripts/count_jsonl.sh --start "$START" --end "$END" > jsonl.log

# 对比
diff db.log jsonl.log
```

### 3. 监控数据质量

```bash
# 检查异常
./scripts/count_jsonl.sh | grep -E "无 content|空/NULL|无 message_id"

# 如果有异常输出，说明数据有问题
```

---

## 📚 相关文档

- [count_classification.sh](count_classification.sh) - 数据库统计脚本
- [数据库_vs_JSONL_对比分析.md](../数据库_vs_JSONL_对比分析.md) - 数据对比分析
- [一小时数据分析报告.md](../一小时数据分析报告.md) - 实际数据分析

---

**最后更新**: 2026-09-09  
**版本**: 1.0
