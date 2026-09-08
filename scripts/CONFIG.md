# 脚本配置说明

本文档说明如何修改各个脚本的默认配置。

## 📝 配置位置

所有脚本的配置都位于脚本开头的 **配置区域**，用明显的注释标记：

```bash
# ============================================================
# *** 配置区域：根据你的实际路径修改 ***
# ============================================================
```

## 🔧 各脚本配置说明

### 1. count_requests.sh

**配置项：**
```bash
DEFAULT_DB="$PROJECT_DIR/requests_20260828.db"
```

**说明：**
- `DEFAULT_DB`: 默认的 requests.db 路径
- 可以通过 `--db` 参数在运行时覆盖

**修改示例：**
```bash
# 如果你的数据库在不同位置
DEFAULT_DB="$PROJECT_DIR/my_requests.db"
```

---

### 2. extract_hash_ids.sh

**配置项：**
```bash
DEFAULT_INPUT="$PROJECT_DIR/traces-d1/traces-20260908_094608_global/merged.jsonl"
DEFAULT_OUTPUT="$PROJECT_DIR/hash_ids_merged_local"
```

**说明：**
- `DEFAULT_INPUT`: 默认的输入 traces.jsonl 文件路径
- `DEFAULT_OUTPUT`: 默认的输出目录路径
- 可以通过命令行参数覆盖

**修改示例：**
```bash
# 修改为你的实际路径
DEFAULT_INPUT="$PROJECT_DIR/my_traces/merged.jsonl"
DEFAULT_OUTPUT="$PROJECT_DIR/my_output"
```

---

### 3. run_trace_generations.sh

**配置项：**
```bash
DEFAULT_DB="$PROJECT_DIR/requests_20260828.db"
DEFAULT_JSONL_ROOT="$PROJECT_DIR/test_0907/projects"
DEFAULT_OUT_ROOT="$PROJECT_DIR/traces-d1"
DEFAULT_LOG_DIR="$PROJECT_DIR/logs-d1"
DEFAULT_START_TIME=""  # 例: "2026-08-28T11:00:00+08:00"
DEFAULT_END_TIME=""    # 例: "2026-08-28T13:00:00+08:00"
DEFAULT_BLOCK_SIZE=64
DEFAULT_MIN_REQUESTS=1
DEFAULT_INCLUDE_SUBAGENTS="true"
DEFAULT_USE_LOCAL_HASH_IDS="true"
DEFAULT_DO_VALIDATE="true"
```

**说明：**
- `DEFAULT_DB`: requests.db 路径
- `DEFAULT_JSONL_ROOT`: JSONL 目录根路径（包含各个会话目录）
- `DEFAULT_OUT_ROOT`: trace 输出根目录
- `DEFAULT_LOG_DIR`: 日志目录
- `DEFAULT_START_TIME`: 开始时间（留空=不限，格式: YYYY-MM-DDTHH:MM:SS+08:00）
- `DEFAULT_END_TIME`: 结束时间（留空=不限，格式: YYYY-MM-DDTHH:MM:SS+08:00）
- `DEFAULT_BLOCK_SIZE`: prompt 分块大小
- `DEFAULT_MIN_REQUESTS`: 最小请求数
- `DEFAULT_INCLUDE_SUBAGENTS`: 是否包含子代理（"true" 或 "false"）
- `DEFAULT_USE_LOCAL_HASH_IDS`: 使用 local 还是 global hash_ids（"true" = local）
- `DEFAULT_DO_VALIDATE`: 是否执行验证步骤（"true" 或 "false"）

所有配置都可以通过命令行参数覆盖。

**修改示例：**
```bash
# 修改为你的实际路径
DEFAULT_DB="$PROJECT_DIR/my_data/requests.db"
DEFAULT_JSONL_ROOT="$PROJECT_DIR/my_data/sessions"
DEFAULT_OUT_ROOT="$PROJECT_DIR/output/traces"
DEFAULT_LOG_DIR="$PROJECT_DIR/output/logs"

# 设置默认时间范围
DEFAULT_START_TIME="2026-08-28T11:00:00+08:00"
DEFAULT_END_TIME="2026-08-28T13:00:00+08:00"

# 修改生成参数
DEFAULT_BLOCK_SIZE=128
DEFAULT_INCLUDE_SUBAGENTS="false"
DEFAULT_USE_LOCAL_HASH_IDS="false"
```

---

### 4. retime_traces_global.sh

**配置项：**
```bash
DEFAULT_DB="$PROJECT_DIR/requests_20260828.db"
DEFAULT_JSONL_ROOT="$PROJECT_DIR/projects"
DEFAULT_START_TIME=""
DEFAULT_END_TIME=""
DEFAULT_DRY_RUN="False"
DEFAULT_TRACES_DIR=""
DEFAULT_DO_MERGE=true
```

**说明：**
- `DEFAULT_DB`: requests.db 路径
- `DEFAULT_JSONL_ROOT`: 本地 JSONL 根目录
- `DEFAULT_START_TIME`: 数据库时间过滤（开始，留空=不限）
- `DEFAULT_END_TIME`: 数据库时间过滤（结束，留空=不限）
- `DEFAULT_DRY_RUN`: 是否为预览模式（"True" 或 "False"）
- `DEFAULT_TRACES_DIR`: 默认 traces 目录（留空=必须在命令行指定）
- `DEFAULT_DO_MERGE`: 是否默认合并输出（true 或 false）
- 所有配置都可以通过命令行参数覆盖

**修改示例：**
```bash
# 修改为你的实际路径
DEFAULT_DB="$PROJECT_DIR/my_requests.db"
DEFAULT_JSONL_ROOT="$PROJECT_DIR/my_projects"
DEFAULT_START_TIME="2026-08-28T11:00:00+08:00"
DEFAULT_END_TIME="2026-08-28T13:00:00+08:00"

# 设置默认 traces 目录（可选）
DEFAULT_TRACES_DIR="$PROJECT_DIR/traces-d1/traces-20260908_094608"

# 如果设置了 DEFAULT_TRACES_DIR，可以这样运行：
# ./retime_traces_global.sh  # 不需要指定目录
# ./retime_traces_global.sh --db /other/db.db  # 只覆盖特定参数
```

---

## 🎯 快速配置指南

### 场景 1: 更换数据库

如果你有新的数据库文件，只需要修改：

1. **count_requests.sh**:
   ```bash
   DEFAULT_DB="$PROJECT_DIR/新数据库.db"
   ```

2. **run_trace_generations.sh**:
   ```bash
   DEFAULT_DB="$PROJECT_DIR/新数据库.db"
   ```

3. **retime_traces_global.py** (第 40 行):
   ```python
   DB = "/path/to/新数据库.db"
   ```

### 场景 2: 更换 JSONL 目录

修改 **run_trace_generations.sh**:
```bash
DEFAULT_JSONL_ROOT="$PROJECT_DIR/新的会话目录"
```

同时修改 **retime_traces_global.py** (第 42 行):
```python
JSONL_ROOT = "/path/to/新的会话目录"
```

### 场景 3: 更改输出位置

修改 **run_trace_generations.sh**:
```bash
DEFAULT_OUT_ROOT="$PROJECT_DIR/新输出目录"
DEFAULT_LOG_DIR="$PROJECT_DIR/新日志目录"
```

---

## ⚠️ 重要提示

1. **路径格式**：
   - 使用 `$PROJECT_DIR` 作为基础路径，保持脚本的可移植性
   - 或者使用绝对路径，例如：`/mnt/nvme1n1/data/...`

2. **时间格式**（在命令行参数中使用）：
   - 必须使用 ISO 8601 格式：`YYYY-MM-DDTHH:MM:SS+08:00`
   - 详见：`../TIME_FILTER_GUIDE.md`

3. **布尔值**：
   - Shell 脚本中使用字符串：`"true"` 或 `"false"`
   - 注意引号不能省略

4. **修改后无需重启**：
   - 修改配置后立即生效
   - 无需重新编译或重启服务

---

## 📋 配置检查清单

在运行脚本前，确认以下配置：

- [ ] 数据库路径正确且文件存在
- [ ] JSONL 目录路径正确且包含会话文件
- [ ] 输出目录有写入权限
- [ ] 时间过滤参数格式正确（如果使用）

---

## 🔍 验证配置

运行以下命令验证配置是否正确：

```bash
# 1. 检查数据库是否可访问
./count_requests.sh

# 2. 查看 run_trace_generations.sh 的默认配置
./run_trace_generations.sh --help

# 3. 使用 --dry-run 测试（不实际执行）
# （某些脚本支持此选项）
```

---

## 📚 相关文档

- `README.md` - 脚本使用说明
- `TIME_FILTER_GUIDE.md` - 时间过滤详细指南
- 各脚本的 `--help` 选项
