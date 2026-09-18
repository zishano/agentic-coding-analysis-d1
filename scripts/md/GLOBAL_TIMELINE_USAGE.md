# GLOBAL_TIMELINE 参数使用指南

## 概述

`GLOBAL_TIMELINE` 参数控制 `retime_traces_global.sh` 如何处理多个trace文件的时间线：

- **`true` (默认)**: 统一全局时间线 - 所有trace基于真实时间对齐到同一起点
- **`false`**: 独立时间线 - 每条trace保持从0开始的相对时间

## 使用方法

### 1. 全局时间线模式（默认）

```bash
# 使用默认配置（全局时间线）
./retime_traces_global.sh /path/to/traces

# 显式指定全局时间线
./retime_traces_global.sh /path/to/traces --global-timeline
```

**效果：**
- trace1 (实际开始于 10:00:00) → t=0
- trace2 (实际开始于 10:30:00) → t=1800 (偏移30分钟)
- trace3 (实际开始于 11:00:00) → t=3600 (偏移60分钟)

**适用场景：**
- 分析多个会话之间的实际时间关系
- 查看不同会话的并发执行情况
- 合并多个trace进行整体分析

### 2. 独立时间线模式

```bash
# 保持独立时间线
./retime_traces_global.sh /path/to/traces --no-global-timeline
```

**效果：**
- trace1 → t=0 开始
- trace2 → t=0 开始
- trace3 → t=0 开始

每条trace保持自己的相对时间，互不影响。

**适用场景：**
- 单独分析每个会话的内部执行模式
- 比较不同会话的相对执行效率
- 不关心会话之间的实际时间关系

## 配置文件

在 `retime_traces_global.sh` 中可以设置默认值：

```bash
# 默认是否使用全局时间线
DEFAULT_GLOBAL_TIMELINE=true   # 或 false
```

在 `retime_traces_global.py` 中：

```python
# 运行模式
GLOBAL_TIMELINE = True  # True=统一全局时间线; False=每个trace保持独立时间(从0开始)
```

## 实际示例

### 示例1：分析多会话并发（全局时间线）

```bash
# 步骤1：重标记为全局时间线并合并
./retime_traces_global.sh ~/traces/traces-20260917 --global-timeline --merge

# 步骤2：分析并发情况
cd ~/traces/traces-20260917_global
python3 ../analyze_all_comprehensive.py --traces-dir . --sampling 1.0
```

生成的图表会显示：
- 各trace在真实时间轴上的分布
- 不同会话的并发执行情况
- 整体系统负载变化

### 示例2：比较单会话执行效率（独立时间线）

```bash
# 步骤1：保持独立时间线
./retime_traces_global.sh ~/traces/traces-20260917 --no-global-timeline

# 步骤2：分析各trace
cd ~/traces/traces-20260917_global
python3 ../analyze_all_comprehensive.py --traces-dir . --sampling 0.5
```

生成的图表会显示：
- 每个会话从启动到结束的执行模式
- 各会话内部的subagent生命周期
- 便于横向比较各会话的执行效率

### 示例3：结合其他参数

```bash
# 全局时间线 + 时间过滤 + 预览
./retime_traces_global.sh ~/traces/traces-20260917 \
  --global-timeline \
  --start-time "2026-09-17T09:00:00+08:00" \
  --end-time "2026-09-17T12:00:00+08:00" \
  --dry-run

# 独立时间线 + 不合并
./retime_traces_global.sh ~/traces/traces-20260917 \
  --no-global-timeline \
  --no-merge
```

## 技术实现

### 全局时间线模式

```python
# 计算全局起点
global_start = min(all_conversation_starts)

# 为每个trace计算偏移
for trace_file in trace_files:
    conv_start = get_conversation_start(trace_file)
    offset = (conv_start - global_start).total_seconds()
    
    # 应用偏移到所有时间戳
    for record in trace['requests']:
        record['t'] += offset
```

### 独立时间线模式

```python
# 不计算偏移，保持原始相对时间
for trace_file in trace_files:
    # 直接复制，不修改时间戳
    for record in trace['requests']:
        # record['t'] 保持不变
        pass
```

## 注意事项

1. **合并文件**：使用独立时间线模式时，合并后的 `merged.jsonl` 中的记录会按原始trace顺序排列，而不是按时间排序

2. **可视化差异**：
   - 全局时间线：X轴显示真实时间，trace之间可能有间隔
   - 独立时间线：X轴从0开始，trace之间无时间关系

3. **默认行为**：如果不指定参数，默认使用全局时间线模式

## 常见问题

**Q: 什么时候应该使用全局时间线？**
A: 当你需要分析多个会话的实际时间关系、并发情况或合并数据时。

**Q: 什么时候应该使用独立时间线？**
A: 当你只关心每个会话内部的执行模式，或想比较不同会话的相对执行效率时。

**Q: 两种模式可以互相转换吗？**
A: 可以，但需要重新运行 `retime_traces_global.sh`，因为时间戳已经被修改。

**Q: 独立时间线模式下还需要数据库吗？**
A: 技术上不需要，但脚本仍会尝试访问数据库。可以考虑添加 `--skip-db` 选项来跳过数据库访问。

