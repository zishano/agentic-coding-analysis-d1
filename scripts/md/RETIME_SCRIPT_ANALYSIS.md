# retime_traces_global.sh 代码解读

## 功能概述

这个脚本的核心功能是：**将多个独立会话的 trace 文件重新标记为统一的全局时间线**

### 问题背景

- **原始问题**：每个 trace 文件的时间都是从 0 开始的相对时间
- **目标**：将所有 trace 文件转换为基于全局起点的绝对时间
- **用途**：方便合并分析多个会话的执行情况

---

## 执行流程

### 第一阶段：Shell 脚本参数处理

#### 1. 配置区域（27-42行）

```bash
# 默认配置
DEFAULT_DB="/home/lmk/claude-code-proxy/requests.db"
DEFAULT_JSONL_ROOT="/mnt/ssd_data/harness-stage1-agent/claude-state/projects/"
DEFAULT_TRACES_DIR="/mnt/sdd/lmk/project/.../traces-20260917_093418_v2"
DEFAULT_DO_MERGE=true
```

**配置项说明：**
- `DB`: 数据库文件路径，包含所有请求的真实时间戳
- `JSONL_ROOT`: 会话记录的根目录
- `TRACES_DIR`: trace 文件所在目录
- `DO_MERGE`: 是否合并输出文件
- `GLOBAL_TIMELINE`: 是否统一时间线（true: 统一到全局时间轴，false: 保持各trace独立时间从0开始）

#### 2. 参数解析（123-184行）

```bash
# 用法示例
./retime_traces_global.sh                           # 使用所有默认配置
./retime_traces_global.sh /path/to/traces           # 指定 traces 目录
./retime_traces_global.sh --db /path/to/db          # 覆盖数据库路径
./retime_traces_global.sh --dry-run                 # 预览模式，不写文件
./retime_traces_global.sh --no-merge                # 不合并输出
./retime_traces_global.sh --merge-only              # 只合并已有文件
```

**支持的选项：**
- `--db PATH`: 指定数据库路径
- `--jsonl-root PATH`: 指定 JSONL 根目录
- `--start-time TIME`: 过滤数据库记录的开始时间
- `--end-time TIME`: 过滤数据库记录的结束时间
- `--dry-run`: 预览模式，不实际写入文件
- `--no-merge`: 不合并输出文件
- `--merge-only`: 只合并，不重新标记时间
- `--global-timeline`: 使用全局时间线，统一所有trace到同一起点（默认）
- `--no-global-timeline`: 保持独立时间线，每条trace从0开始

#### 3. 验证检查（194-209行）

```bash
# 检查必需的路径和文件
if [ ! -d "$TRACES_DIR" ]; then
    echo "❌ 错误: traces 目录不存在"
    exit 1
fi

if [ ! -f "$DB" ]; then
    echo "❌ 错误: 数据库文件不存在"
    exit 1
fi

if [ ! -d "$JSONL_ROOT" ]; then
    echo "❌ 错误: JSONL 根目录不存在"
    exit 1
fi
```

---

### 第二阶段：动态配置注入（228-269行）

这是一个**非常巧妙的设计**！

#### 问题：
- Python 脚本 `retime_traces_global.py` 内部有硬编码的配置
- 但我们希望通过 shell 参数覆盖这些配置

#### 解决方案：动态代码注入

```bash
# 1. 创建临时 Python 包装脚本
TEMP_WRAPPER=$(mktemp)

cat > "$TEMP_WRAPPER" << 'PYTHON_WRAPPER_EOF'
#!/usr/bin/env python3
import sys, os, re

# 从环境变量读取配置
_DB = os.environ.get('RETIME_DB')
_JSONL_ROOT = os.environ.get('RETIME_JSONL_ROOT')
_DB_START_TIME = os.environ.get('RETIME_DB_START_TIME', '')
_DB_END_TIME = os.environ.get('RETIME_DB_END_TIME', '')
_GLOBAL_TIMELINE = os.environ.get('RETIME_GLOBAL_TIMELINE', 'true').lower() == 'true'

# 读取原始 Python 脚本
with open(os.environ.get('PYTHON_SCRIPT'), 'r') as f:
    code = f.read()

# 替换配置行
lines = code.split('\n')
new_lines = []
for line in lines:
    # 找到并替换配置变量
    if re.match(r'^DB\s*=\s*', line.strip()):
        new_lines.append(f'DB = "{_DB}"')
    elif re.match(r'^JSONL_ROOT\s*=\s*', line.strip()):
        new_lines.append(f'JSONL_ROOT = "{_JSONL_ROOT}"')
    # ... 其他配置
    else:
        new_lines.append(line)

# 执行修改后的代码
exec('\n'.join(new_lines))
PYTHON_WRAPPER_EOF
```

**工作原理：**
1. 创建临时 Python 脚本
2. 读取原始 `retime_traces_global.py` 的源代码
3. 使用正则表达式找到配置行（如 `DB = "..."`）
4. 替换为环境变量中的值
5. 执行修改后的代码

**优点：**
- 不修改原始 Python 文件
- 灵活地覆盖任何配置
- 保持配置集中管理

---

### 第三阶段：执行 Python 脚本（271-290行）

```bash
# 1. 设置环境变量
export RETIME_DB="$DB"
export RETIME_JSONL_ROOT="$JSONL_ROOT"
export RETIME_DB_START_TIME="$START_TIME"
export RETIME_DB_END_TIME="$END_TIME"
export RETIME_GLOBAL_TIMELINE="$GLOBAL_TIMELINE"
export PYTHON_SCRIPT="$PYTHON_SCRIPT"

# 2. 构建命令行参数
PYTHON_ARGS="$TRACES_DIR"
if [ "$NO_MERGE" = false ] && [ "$MERGE_ONLY" = false ]; then
    PYTHON_ARGS="$PYTHON_ARGS --merge"
elif [ "$MERGE_ONLY" = true ]; then
    PYTHON_ARGS="$PYTHON_ARGS --merge-only"
fi

# 3. 执行包装脚本
cd "$PROJECT_DIR"
python3 "$TEMP_WRAPPER" $PYTHON_ARGS

# 4. 清理临时文件
rm -f "$TEMP_WRAPPER"
```

---

## Python 脚本的核心功能

虽然 Python 脚本不在这个文件中，但根据参数和输出可以推断它做了什么：

### 1. 时间重标记流程

```python
# 伪代码
def retime_traces(traces_dir, db, jsonl_root):
    # 步骤1：从数据库提取所有会话的真实开始时间
    session_times = {}
    for trace_file in traces_dir:
        trace_id = extract_id(trace_file)
        jsonl_file = find_jsonl(jsonl_root, trace_id)
        real_start_time = query_db_for_start_time(db, jsonl_file)
        session_times[trace_file] = real_start_time
    
    # 步骤2：找到全局最早时间（全局起点）
    global_start = min(session_times.values())
    
    # 步骤3：重新计算每个会话的偏移量
    offsets = {}
    for trace_file, start_time in session_times.items():
        offset = (start_time - global_start).total_seconds()
        offsets[trace_file] = offset
    
    # 步骤4：重写 trace 文件
    for trace_file, offset in offsets.items():
        with open(trace_file) as f:
            data = json.load(f)
        
        # 为所有时间戳加上偏移量
        for record in data['requests']:
            record['t'] += offset  # 原始相对时间 + 会话偏移量
            if record.get('requests'):
                # 子代理内部的时间不变（仍然相对于子代理启动）
                pass
        
        # 保存到新目录
        output_path = f"{traces_dir}_global/{trace_file}"
        with open(output_path, 'w') as f:
            json.dump(data, f)
    
    # 步骤5：合并所有 trace（如果指定了 --merge）
    if merge:
        merge_all_traces(output_dir)
```

### 2. 时间转换示例

#### 2.1 全局时间线模式（GLOBAL_TIMELINE=true，默认）

**原始数据（3个独立会话）：**
```
trace1.json (会话开始于 10:00:00):
  requests: [
    {t: 0.0, type: "main"},
    {t: 5.0, type: "main"},
    {t: 10.0, type: "subagent", agent_id: "a1"}
  ]

trace2.json (会话开始于 10:30:00):
  requests: [
    {t: 0.0, type: "main"},
    {t: 8.0, type: "main"}
  ]

trace3.json (会话开始于 11:00:00):
  requests: [
    {t: 0.0, type: "main"},
    {t: 3.0, type: "subagent", agent_id: "a2"}
  ]
```

**全局时间线计算：**
```
全局起点 = 10:00:00 (trace1 最早)

偏移量计算:
  trace1: 10:00:00 - 10:00:00 = 0秒
  trace2: 10:30:00 - 10:00:00 = 1800秒
  trace3: 11:00:00 - 10:00:00 = 3600秒
```

**重标记后的数据：**
```
trace1_global.json:
  requests: [
    {t: 0.0,   type: "main"},        # 10:00:00
    {t: 5.0,   type: "main"},        # 10:00:05
    {t: 10.0,  type: "subagent"}     # 10:00:10
  ]

trace2_global.json:
  requests: [
    {t: 1800.0, type: "main"},       # 10:30:00
    {t: 1808.0, type: "main"}        # 10:30:08
  ]

trace3_global.json:
  requests: [
    {t: 3600.0, type: "main"},       # 11:00:00
    {t: 3603.0, type: "subagent"}    # 11:00:03
  ]
```

#### 2.2 独立时间线模式（GLOBAL_TIMELINE=false）

当设置 `--no-global-timeline` 时，每条trace保持独立的时间线（从0开始），不进行全局时间偏移。

**重标记后的数据（保持不变）：**
```
trace1_global.json:
  requests: [
    {t: 0.0, type: "main"},
    {t: 5.0, type: "main"},
    {t: 10.0, type: "subagent"}
  ]

trace2_global.json:
  requests: [
    {t: 0.0, type: "main"},
    {t: 8.0, type: "main"}
  ]

trace3_global.json:
  requests: [
    {t: 0.0, type: "main"},
    {t: 3.0, type: "subagent"}
  ]
```

**使用场景：**
- 全局时间线模式：适合分析多个会话的实际时间关系和并发情况
- 独立时间线模式：适合单独分析每个会话的内部执行模式

**合并后（merged.jsonl）：**
```
所有记录按全局时间排序，可以看到：
- 10:00:00 - 10:00:10: trace1 的活动
- 10:30:00 - 10:30:08: trace2 的活动
- 11:00:00 - 11:00:03: trace3 的活动
```

---

## 输出结果

### 目录结构

```
原始目录: traces-20260917_093418_v2/
  ├── 9f148b4f-e71.json
  ├── d8e2bb6b-4cb.json
  └── 6526a359-5e3.json

生成目录: traces-20260917_093418_v2_global/
  ├── 9f148b4f-e71.json      # 时间已重标记
  ├── d8e2bb6b-4cb.json      # 时间已重标记
  ├── 6526a359-5e3.json      # 时间已重标记
  └── merged.jsonl           # 合并的所有记录（可选）
```

### 时间标记差异

**原始文件（相对时间）：**
```json
// 9f148b4f-e71.json
{"requests": [{"t": 0.0}, {"t": 112.5}, ...]}

// d8e2bb6b-4cb.json
{"requests": [{"t": 0.0}, {"t": 45.2}, ...]}
```

**重标记后（全局时间）：**
```json
// 9f148b4f-e71.json (会话1，基准)
{"requests": [{"t": 0.0}, {"t": 112.5}, ...]}

// d8e2bb6b-4cb.json (会话2，晚了1800秒)
{"requests": [{"t": 1800.0}, {"t": 1845.2}, ...]}
```

---

## 关键技术点

### 1. 数据库查询链

```
trace ID → 找到对应的 JSONL 文件 → 从 JSONL 提取 message_id
         → 在数据库中查询 message_id → 获取真实时间戳
```

### 2. 时间过滤

```bash
--start-time "2026-08-28T11:00:00+08:00"
--end-time "2026-08-28T13:00:00+08:00"
```

只处理在指定时间范围内的会话

### 3. 预览模式

```bash
--dry-run
```

只计算和显示，不实际写入文件

### 4. 灵活的合并选项

```bash
# 默认：重标记 + 合并
./retime_traces_global.sh

# 只重标记，不合并
./retime_traces_global.sh --no-merge

# 只合并已有的重标记文件
./retime_traces_global.sh --merge-only
```

### 5. 时间线模式选择

```bash
# 全局时间线模式（默认）- 统一所有trace到同一起点
./retime_traces_global.sh /path/to/traces
./retime_traces_global.sh /path/to/traces --global-timeline

# 独立时间线模式 - 每条trace保持从0开始
./retime_traces_global.sh /path/to/traces --no-global-timeline
```

---

## 使用场景

### 场景1：分析多会话整体行为（全局时间线）
```bash
# 将3个不同时间的会话统一到全局时间线
./retime_traces_global.sh /path/to/traces --merge

# 然后用分析脚本处理合并后的数据
./analyze_traces.sh traces_global/ --sampling 0.5
```

### 场景2：单独分析各会话执行模式（独立时间线）
```bash
# 保持每条trace的独立时间线
./retime_traces_global.sh /path/to/traces --no-global-timeline

# 可以单独查看每个trace的内部时序
./analyze_traces.sh traces_global/ --sampling 1.0
```

### 场景3：调试时间对齐问题
```bash
# 预览模式查看时间映射
./retime_traces_global.sh /path/to/traces --dry-run
```

### 场景4：时间范围过滤
```bash
# 只分析某个时间段的会话
./retime_traces_global.sh /path/to/traces \
  --start-time "2026-09-17T09:00:00+08:00" \
  --end-time "2026-09-17T12:00:00+08:00"
```

---

## 与 analyze_traces.sh 的关系

```
工作流程：

1. retime_traces_global.sh
   ↓
   输出：traces_global/ (统一时间线的 traces)
   ↓
2. analyze_traces.sh traces_global/
   ↓
   输出：可视化图表（所有会话在同一时间轴上）
```

**区别：**
- `retime_traces_global.sh`: 数据预处理，统一时间基准
- `analyze_traces.sh`: 数据分析和可视化

**联系：**
- 重标记后的数据更适合多会话对比分析
- 可以看到不同会话之间的时间关系

---

## 总结

这个脚本实现了一个**智能配置注入系统**，通过：

1. **Shell 参数解析** - 接收用户配置
2. **动态代码注入** - 修改 Python 脚本配置
3. **环境变量传递** - 传递配置到包装脚本
4. **Python 执行** - 实际的时间重标记逻辑

核心价值：
- 🎯 **统一时间基准** - 多会话可比较
- 🔧 **灵活配置** - 不修改源码覆盖配置
- 📊 **便于分析** - 为后续可视化做准备
