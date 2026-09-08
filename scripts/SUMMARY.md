# Scripts 目录 - 完成总结

## 🎉 完成状态

所有 Python 脚本已成功整理为 Shell 脚本，所有脚本都支持通过命令行参数配置。

## 📁 目录结构

```
scripts/
├── 📄 CONFIG.md                 (5.4K) - 脚本配置说明
├── 📄 README.md                 (7.1K) - 完整使用说明
├── 🔧 count_requests.sh         (1.6K) - 统计请求数量
├── 🔧 extract_hash_ids.sh       (2.2K) - 提取 Hash ID 信息
├── 🔧 run_trace_generations.sh  (14K)  - 一键生成 trace（核心）
├── 🔧 retime_traces_global.sh   (7.2K) - 重标记全局时间线
└── 📝 examples.sh               (2.4K) - 使用示例演示
```

## ✨ 核心改进

### 1. **完全参数化** ✅
所有 4 个脚本都支持通过命令行参数配置：

- **count_requests.sh**: `--db`, `--start-time`, `--end-time`, `--hourly`, `--detail`
- **extract_hash_ids.sh**: 输入文件路径、输出目录路径
- **run_trace_generations.sh**: `--db`, `--jsonl-root`, `--out-root`, `--log-dir`, `--start-time`, `--end-time`, 等
- **retime_traces_global.sh**: `--db`, `--jsonl-root`, `--start-time`, `--end-time`, `--dry-run`, `--no-merge`

### 2. **配置集中化** ✅
每个脚本开头都有明确标记的配置区域：

```bash
# ============================================================
# *** 配置区域：根据你的实际路径修改 ***
# ============================================================
DEFAULT_DB="$PROJECT_DIR/requests_20260828.db"
DEFAULT_JSONL_ROOT="$PROJECT_DIR/test_0907/projects"
# ...
# ============================================================
```

### 3. **完整的帮助文档** ✅
每个脚本都支持 `--help` 参数：

```bash
./count_requests.sh --help
./run_trace_generations.sh --help
./extract_hash_ids.sh --help
./retime_traces_global.sh --help
```

## 📝 当前默认配置

### count_requests.sh
```bash
DEFAULT_DB="$PROJECT_DIR/requests_20260828.db"
```

### extract_hash_ids.sh
```bash
DEFAULT_INPUT="$PROJECT_DIR/traces-d1/traces-20260908_094608_global/merged.jsonl"
DEFAULT_OUTPUT="$PROJECT_DIR/hash_ids_merged"
```

### run_trace_generations.sh
```bash
DEFAULT_DB="$PROJECT_DIR/requests_20260828.db"
DEFAULT_JSONL_ROOT="$PROJECT_DIR/test_0907/projects"
DEFAULT_OUT_ROOT="$PROJECT_DIR/traces-d1"
DEFAULT_LOG_DIR="$PROJECT_DIR/logs-d1"
DEFAULT_BLOCK_SIZE=64
DEFAULT_MIN_REQUESTS=1
DEFAULT_INCLUDE_SUBAGENTS="true"
DEFAULT_USE_LOCAL_HASH_IDS="true"
DEFAULT_DO_VALIDATE="true"
```

### retime_traces_global.sh
```bash
DEFAULT_DB="$PROJECT_DIR/requests_20260828.db"
DEFAULT_JSONL_ROOT="$PROJECT_DIR/test_0907/projects"
DEFAULT_START_TIME=""
DEFAULT_END_TIME=""
```

## 🚀 使用示例

### 基础使用

```bash
cd /mnt/nvme1n1/data/lmk/PROJECT/agentic-coding-analysis-d1/scripts

# 1. 查看数据库统计
./count_requests.sh

# 2. 生成 trace（使用默认配置）
./run_trace_generations.sh

# 3. 重标记全局时间线（使用默认配置）
./retime_traces_global.sh /path/to/traces-dir
```

### 高级使用（自定义配置）

```bash
# 1. 查看特定时间段的请求
./count_requests.sh \
    --start "2026-08-28T11:00:00+08:00" \
    --end "2026-08-28T12:00:00+08:00" \
    --hourly --detail

# 2. 生成 trace（完全自定义）
./run_trace_generations.sh \
    --db ../my_requests.db \
    --jsonl-root ../my_projects \
    --start-time "2026-08-28T11:00:00+08:00" \
    --end-time "2026-08-28T13:00:00+08:00" \
    --block-size 128 \
    --global-hash-ids

# 3. 重标记全局时间线（带时间过滤）
./retime_traces_global.sh /path/to/traces-dir \
    --db ../my_requests.db \
    --jsonl-root ../my_projects \
    --start-time "2026-08-28T11:00:00+08:00" \
    --end-time "2026-08-28T13:00:00+08:00"
```

## 📊 完整工作流程

```bash
# Step 1: 查看数据，确定时间范围
./count_requests.sh --hourly

# Step 2: 生成 trace
./run_trace_generations.sh \
    --start-time "2026-08-28T11:00:00+08:00" \
    --end-time "2026-08-28T13:00:00+08:00"

# Step 3: 重标记为全局时间线
./retime_traces_global.sh ../traces-d1/traces-20260908_xxxxxx

# Step 4: 提取 hash_ids
./extract_hash_ids.sh \
    ../traces-d1/traces-20260908_xxxxxx_global/merged.jsonl \
    ../hash_ids_output
```

## 🎯 对应关系

| Shell 脚本 | Python 脚本 | 说明 |
|-----------|-------------|------|
| `count_requests.sh` | `count_requests_by_time.py` | 统计请求数量 |
| `extract_hash_ids.sh` | `extract_hash_ids_expanded.py` | 提取 Hash IDs |
| `run_trace_generations.sh` | `run_trace_generations.py` | 生成 traces（内嵌） |
| `retime_traces_global.sh` | `retime_traces_global.py` | 重标记时间线 |

## ⚠️ 重要提示

### 1. 时间格式
**必须使用 ISO 8601 格式带时区：**

✅ 正确：`2026-08-28T11:00:00+08:00`  
❌ 错误：`2026-08-28 11:00:00`

详见：`../TIME_FILTER_GUIDE.md`

### 2. 配置优先级
命令行参数 > 脚本默认配置

### 3. 路径使用
- `$PROJECT_DIR` 保持可移植性
- 或使用绝对路径确保准确性

## 📚 文档索引

| 文档 | 说明 |
|------|------|
| `README.md` | 完整使用说明、工作流程、示例 |
| `CONFIG.md` | 配置修改指南、场景示例 |
| `../TIME_FILTER_GUIDE.md` | 时间格式详细说明 |
| 各脚本 `--help` | 参数说明、选项列表 |

## ✅ 测试状态

所有脚本已测试通过：

- [x] count_requests.sh - 配置完成，正常工作
- [x] extract_hash_ids.sh - 配置完成，正常工作
- [x] run_trace_generations.sh - 完全参数化，正常工作
- [x] retime_traces_global.sh - 完全参数化，正常工作
- [x] examples.sh - 示例脚本创建
- [x] 文档完整性 - README、CONFIG 已更新

## 🎊 最终总结

### 已完成的工作

1. ✅ 所有 4 个核心脚本都已参数化
2. ✅ 配置集中在脚本开头，易于修改
3. ✅ 支持命令行参数覆盖所有配置
4. ✅ 完整的帮助信息和文档
5. ✅ 时间过滤支持（包括 retime_traces_global.sh）
6. ✅ 示例和使用指南

### 关键特性

- **灵活性**：命令行参数可覆盖所有默认配置
- **易用性**：默认配置适合大多数场景
- **文档化**：每个脚本都有详细的 --help 和文档
- **一致性**：所有脚本使用统一的参数命名和格式

**现在所有脚本都已完全配置化，可以直接投入使用！** 🚀
