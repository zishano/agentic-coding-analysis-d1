# Scripts 使用说明

这个目录包含了 agentic-coding-analysis 项目的常用脚本，用于分析和处理 Claude Code 的请求数据。

## 📋 脚本列表

### 1. count_requests.sh
统计 requests.db 中指定时间段的请求数量

**功能：**
- 按小时统计请求分布
- 按会话统计请求数
- 显示详细的 token 和模型信息
- 支持时间范围过滤

**用法：**
```bash
# 默认显示按小时统计
./count_requests.sh

# 指定时间范围
./count_requests.sh --start "2026-08-28T11:00:00+08:00" --end "2026-08-28T12:00:00+08:00"

# 显示详细信息
./count_requests.sh --hourly --detail

# 按会话统计
./count_requests.sh --by-session

# 查看帮助
./count_requests.sh --help
```

**对应 Python 脚本：** `../count_requests_by_time.py`

---

### 2. run_trace_generations.sh
一键生成 trace 文件的完整流程

**功能：**
- Step 1: 从 requests.db 提取 message IDs
- Step 2: 建立会话关联索引
- Step 3: 生成 trace 文件（包含 hash_ids）
- Step 4: 验证 trace 缓存

**用法：**
```bash
# 使用默认配置运行
./run_trace_generations.sh

# 指定数据库和时间范围
./run_trace_generations.sh \
    --db /path/to/requests.db \
    --start-time "2026-08-28T11:00:00+08:00" \
    --end-time "2026-08-28T13:00:00+08:00"

# 完整配置示例
./run_trace_generations.sh \
    --db /path/to/requests.db \
    --jsonl-root /path/to/projects \
    --out-root /path/to/traces-d1 \
    --log-dir /path/to/logs-d1 \
    --start-time "2026-08-28T11:00:00+08:00" \
    --end-time "2026-08-28T13:00:00+08:00" \
    --block-size 64 \
    --include-subagents \
    --local-hash-ids

# 查看帮助和所有选项
./run_trace_generations.sh --help
```

**可用选项：**
- `--db PATH` - requests.db 路径
- `--jsonl-root PATH` - JSONL 目录根路径
- `--out-root PATH` - 输出根目录
- `--log-dir PATH` - 日志目录
- `--start-time TIME` - 开始时间（格式：`YYYY-MM-DDTHH:MM:SS+08:00`）
- `--end-time TIME` - 结束时间（格式：`YYYY-MM-DDTHH:MM:SS+08:00`）
- `--block-size N` - prompt 分块大小（默认：64）
- `--min-requests N` - 最小请求数（默认：1）
- `--include-subagents` - 包含子代理（默认）
- `--no-subagents` - 不包含子代理
- `--local-hash-ids` - 使用 local hash_ids（默认）
- `--global-hash-ids` - 使用 global hash_ids
- `--no-validate` - 跳过验证步骤

**输出：**
- traces: `OUT_ROOT/traces-<时间戳>/`
- 日志: `LOG_DIR/run_<时间戳>.log`

**对应 Python 脚本：** `../run_trace_generations.py`

---

### 3. extract_hash_ids.sh
从 traces.jsonl 提取所有 Hash ID 分配信息

**功能：**
- 提取每个请求的实际 hash_ids 范围
- 对于不连续的 hash_ids，横向展示多个范围
- 对于 subagent，展开其内部的每个 request
- 生成 CSV 统计报告

**用法：**
```bash
# 使用默认路径
./extract_hash_ids.sh

# 指定输入文件
./extract_hash_ids.sh /path/to/traces.jsonl

# 指定输入和输出目录
./extract_hash_ids.sh /path/to/traces.jsonl /path/to/output
```

**输出文件：**
- `traces_all_data.csv` - 所有请求的详细信息
- `traces_statistics.csv` - 统计摘要

**对应 Python 脚本：** `../extract_hash_ids_expanded.py`

---

### 4. retime_traces_global.sh
将多个会话的 traces 重标记为全局时间线

**功能：**
- 将每个 trace 的时间戳重标记为相对于全局起点的时间
- 全局起点 = 所有会话中最早的请求时间
- 自动合并所有 traces 到一个文件

**用法：**
```bash
# 基本使用（使用默认配置）
./retime_traces_global.sh /path/to/traces-dir

# 指定数据库和 JSONL 路径
./retime_traces_global.sh /path/to/traces-dir \
    --db /path/to/requests.db \
    --jsonl-root /path/to/projects

# 带时间过滤
./retime_traces_global.sh /path/to/traces-dir \
    --start-time "2026-08-28T11:00:00+08:00" \
    --end-time "2026-08-28T13:00:00+08:00"

# 预览模式（不实际写入）
./retime_traces_global.sh /path/to/traces-dir --dry-run

# 不合并输出
./retime_traces_global.sh /path/to/traces-dir --no-merge

# 查看帮助
./retime_traces_global.sh --help
```

**可用选项：**
- `--db PATH` - requests.db 路径
- `--jsonl-root PATH` - JSONL 根目录路径
- `--start-time TIME` - 数据库时间过滤（开始）
- `--end-time TIME` - 数据库时间过滤（结束）
- `--dry-run` - 预览模式，不实际写入文件
- `--no-merge` - 不合并输出文件
- `--merge-only` - 只合并，不重标记

**输出：**
- 输出目录: `<源文件夹>_global/`
- 合并文件: `<源文件夹>_global/merged.jsonl`

**对应 Python 脚本：** `../retime_traces_global.py`

---

### 5. export_db.sh
导出指定时间段的请求到新数据库

**功能：**
- 从大型数据库中提取特定时间段的数据
- 创建一个小的独立数据库便于分析
- 支持按时间范围、最近 N 条、会话 ID 导出
- 可选择只导出有响应的请求

**用法：**
```bash
# 使用默认数据库，导出指定时间范围
./export_db.sh --start-time "2026-08-28T00:00:00+08:00" \
    --end-time "2026-08-28T23:59:59+08:00"

# 指定数据库路径
./export_db.sh source.db output.db \
    --start-time "2026-08-28T00:00:00+08:00" \
    --end-time "2026-08-28T23:59:59+08:00"

# 只导出有响应的请求
./export_db.sh source.db output.db \
    --start-time "2026-08-28T00:00:00+08:00" \
    --end-time "2026-08-28T23:59:59+08:00" \
    --only-with-response

# 导出最近 1000 条记录
./export_db.sh source.db output.db --last 1000

# 导出指定会话
./export_db.sh source.db output.db --conversation-id abc123

# 查看帮助
./export_db.sh --help
```

**可用选项：**
- `--start-time TIME` - 开始时间（格式：`YYYY-MM-DDTHH:MM:SS+08:00`）
- `--end-time TIME` - 结束时间（格式：`YYYY-MM-DDTHH:MM:SS+08:00`）
- `--last N` - 导出最近 N 条记录
- `--conversation-id ID` - 导出指定会话的所有请求
- `--only-with-response` - 只导出有响应的请求

**输出：**
- 新的 SQLite 数据库文件
- 包含指定条件的所有请求记录

**对应 Python 脚本：** `../tools/analyze_db_quick.py`

---

## 🔄 典型工作流程

### 完整的分析流程：

```bash
# 1. 先查看数据库中有多少请求
./count_requests.sh --hourly --detail

# 2. 根据需要的时间范围，编辑 run_trace_generations.py 中的配置
#    设置 DB_START_TIME 和 DB_END_TIME

# 3. 生成 trace 文件
./run_trace_generations.sh

# 4. 将 traces 重标记为全局时间线
./retime_traces_global.sh /path/to/traces-20260908_094608

# 5. 提取 hash_ids 信息
./extract_hash_ids.sh /path/to/traces-20260908_094608_global/merged.jsonl
```

---

## ⚠️ 重要注意事项

### 时间格式
所有涉及时间过滤的参数**必须使用带时区的 ISO 8601 格式**：

✅ **正确：** `2026-08-28T11:00:00+08:00`  
❌ **错误：** `2026-08-28 11:00:00`（会查询不到数据）

**原因：** SQLite 使用字符串比较，格式必须与数据库中的时间戳格式完全一致。

详细说明请参考：`../TIME_FILTER_GUIDE.md`

### 数据库路径
确保各个脚本中的数据库路径正确指向你的 `requests.db` 文件。

### JSONL 目录
确保 JSONL 目录结构正确，每个会话目录包含 `*.jsonl` 文件。

---

## 📊 输出示例

### count_requests.sh 输出：
```
📊 数据库: requests_20260828.db
======================================================================

✅ 总请求数: 12,121

📅 实际时间范围:
   最早: 2026-08-28T11:00:13+08:00
   最晚: 2026-08-28T13:00:00+08:00

⏰ 按小时统计:
   共 3 个小时有请求

   2026-08-28T11:00:00+08:00 | 5,927 请求 ( 48.9%) ████████████████████████
   2026-08-28T12:00:00+08:00 | 6,193 请求 ( 51.1%) █████████████████████████
   2026-08-28T13:00:00+08:00 |     1 请求 (  0.0%)
```

---

## 🛠️ 故障排除

### 问题：查询不到任何请求
**解决方案：** 检查时间格式是否正确，必须使用 `YYYY-MM-DDTHH:MM:SS+08:00` 格式

### 问题：找不到 Python 脚本
**解决方案：** 确保从 `scripts/` 目录运行脚本，或使用绝对路径

### 问题：权限被拒绝
**解决方案：** 运行 `chmod +x *.sh` 给脚本添加执行权限

---

## 📚 相关文档

- `../TIME_FILTER_GUIDE.md` - 时间过滤详细指南
- `../run_trace_generations.py` - trace 生成主脚本
- `../AGENTS.md` - 项目总体说明

---

## 📝 维护信息

这些脚本是 Python 脚本的 Shell 封装，提供更友好的命令行接口。

如需修改核心逻辑，请编辑对应的 Python 脚本。
