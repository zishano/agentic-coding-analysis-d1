#!/usr/bin/env python3
"""
从 trace 的 merged.jsonl 文件生成上下文增长可视化图表

输入格式：
    merged.jsonl - 每行一个 trace（会话），包含：
    {
        "id": "会话ID",
        "requests": [
            {"t": 时间, "type": "s/m", "in": 输入tokens, "out": 输出tokens, ...},
            ...
        ]
    }

输出：
    上下文增长图表（对数坐标），展示所有会话的增长轨迹和压缩事件
"""

import json
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Tuple
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np

# 压缩检测阈值：当前 token 数 < 前一个的 70%
COMPACTION_THRESHOLD = 0.7


def load_traces(jsonl_path: str, verbose: bool = False) -> List[Dict]:
    """从 merged.jsonl 加载所有 trace"""
    traces = []

    if verbose:
        print(f"INFO: 读取文件: {jsonl_path}")

    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                trace = json.loads(line)
                traces.append(trace)

                if verbose:
                    trace_id = trace.get('id', f'line-{line_num}')
                    req_count = len(trace.get('requests', []))
                    print(f"  - Trace {trace_id}: {req_count} requests")

            except json.JSONDecodeError as e:
                if verbose:
                    print(f"WARNING: 跳过第 {line_num} 行 (JSON 解析错误): {e}")
                continue

    if verbose:
        print(f"INFO: 成功加载 {len(traces)} 个 trace\n")

    return traces


def extract_conversation_data(trace: Dict, verbose: bool = False) -> Tuple[List[int], List[int], List[int]]:
    """
    从单个 trace 中提取上下文增长数据

    返回: (turn_numbers, input_tokens, compaction_indices)
    """
    requests = trace.get('requests', [])
    if not requests:
        return [], [], []

    turn_numbers = []
    input_tokens = []
    compaction_indices = []

    prev_tokens = 0

    for turn, req in enumerate(requests, 1):
        # 只处理主请求（type='s'）和可能的子代理请求
        # 提取输入 token 数
        tokens = req.get('in', 0)

        if tokens > 0:
            turn_numbers.append(turn)
            input_tokens.append(tokens)

            # 检测压缩事件：token 数显著下降
            if prev_tokens > 0 and tokens < prev_tokens * COMPACTION_THRESHOLD:
                compaction_indices.append(len(turn_numbers) - 1)

            prev_tokens = tokens

    trace_id = trace.get('id', 'unknown')

    if verbose and compaction_indices:
        print(f"  Trace {trace_id}: {len(compaction_indices)} compaction events detected")

    return turn_numbers, input_tokens, compaction_indices


def plot_context_growth(
    all_data: List[Tuple[str, List[int], List[int], List[int]]],
    output_path: str,
    title: str = "Context growth",
    verbose: bool = False
):
    """
    绘制所有会话的上下文增长图表

    all_data: [(trace_id, turns, tokens, compaction_indices), ...]
    """
    if verbose:
        print("INFO: 生成可视化图表...")

    # 创建图表
    fig, ax = plt.subplots(figsize=(16, 10))

    # 统计信息
    total_conversations = len(all_data)
    total_turns = sum(len(turns) for _, turns, _, _ in all_data)
    total_compactions = sum(len(comp_idx) for _, _, _, comp_idx in all_data)
    max_turns = max((turns[-1] if turns else 0) for _, turns, _, _ in all_data)
    max_tokens = max((max(tokens) if tokens else 0) for _, _, tokens, _ in all_data)

    # 生成颜色：为所有trace分配不同的颜色
    n_conversations = len(all_data)
    colors = []
    for i in range(n_conversations):
        colors.append(plt.cm.tab20(i % 20))  # 使用tab20调色板为所有trace分配颜色

    # 绘制每个会话
    legend_lines = []
    legend_labels = []

    for idx, (trace_id, turns, tokens, compaction_indices) in enumerate(all_data):
        if not turns:
            continue

        color = colors[idx]
        linewidth = 1.5  # 所有trace使用相同的线宽

        # 绘制主线
        line, = ax.plot(turns, tokens, color=color, linewidth=linewidth, alpha=0.7)

        # 为所有trace添加图例
        legend_lines.append(line)
        # 简化trace_id显示：只显示最后8个字符
        short_id = trace_id[-8:] if len(trace_id) > 8 else trace_id
        legend_labels.append(f"Trace {short_id}")

        # 标记压缩事件（垂直线）
        if compaction_indices:
            for comp_idx in compaction_indices:
                if comp_idx > 0 and comp_idx < len(turns):
                    # 画一条从压缩前到压缩后的垂直线
                    ax.plot(
                        [turns[comp_idx-1], turns[comp_idx]],
                        [tokens[comp_idx-1], tokens[comp_idx]],
                        color=color,
                        linewidth=linewidth + 0.5,
                        alpha=0.8
                    )

    # 设置对数坐标
    ax.set_xscale('log')
    ax.set_yscale('log')

    # 自定义纵轴格式化函数
    def format_yaxis(value, pos):
        if value >= 1_000_000:
            return f'{int(value/1_000_000)}M'
        elif value >= 1_000:
            return f'{int(value/1_000)}k'
        else:
            return f'{int(value)}'

    ax.yaxis.set_major_formatter(FuncFormatter(format_yaxis))

    # 添加图例（只为彩色线）
    if legend_lines:
        ax.legend(legend_lines, legend_labels, loc='upper left', fontsize=10,
                 framealpha=0.9, edgecolor='gray')

    # 设置坐标轴
    ax.set_xlabel('main-agent turn count', fontsize=14)
    ax.set_ylabel('context length (input tokens)', fontsize=14)

    # 设置标题
    subtitle = f"— {total_conversations} conversations"
    ax.set_title(f"{title} {subtitle}", fontsize=16, pad=20)

    # 设置网格
    ax.grid(True, which='both', alpha=0.3, linestyle='-', linewidth=0.5)
    ax.grid(True, which='minor', alpha=0.15, linestyle='-', linewidth=0.3)

    # 设置刻度
    ax.tick_params(axis='both', which='major', labelsize=11)
    ax.tick_params(axis='both', which='minor', labelsize=9)

    # 设置坐标范围 - 根据实际数据动态确定纵轴上限
    # 将最大值向上取整到最近的 10^n
    import math
    y_max = 10 ** math.ceil(math.log10(max_tokens))

    ax.set_xlim(0.9, max_turns * 1.5)
    ax.set_ylim(10, y_max)

    # 调整布局
    plt.tight_layout()

    # 保存图表
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    if verbose:
        print(f"INFO: ✅ 图表已保存: {output_path}\n")

    # 打印统计信息
    print("=" * 70)
    print("上下文增长分析统计")
    print("=" * 70)
    print(f"总会话数        : {total_conversations}")
    print(f"总轮次数        : {total_turns}")
    print(f"总压缩事件      : {total_compactions}")
    print(f"平均轮次/会话   : {total_turns / total_conversations:.1f}")
    print(f"平均压缩/会话   : {total_compactions / total_conversations:.1f}")
    print(f"最大轮次数      : {max_turns}")
    print(f"最大token数     : {max_tokens:,}")

    # 长会话统计
    long_convs = sum(1 for _, turns, _, _ in all_data if turns and turns[-1] > 100)
    very_long_convs = sum(1 for _, turns, _, _ in all_data if turns and turns[-1] > 500)
    print(f"长会话(>100轮)  : {long_convs}")
    print(f"超长会话(>500轮): {very_long_convs}")
    print("=" * 70)
    print()
    print(f"✅ 完成！图表已保存到: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='从 trace merged.jsonl 生成上下文增长可视化图表',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本用法
  %(prog)s --input merged.jsonl --output context_growth.png

  # 自定义标题
  %(prog)s --input merged.jsonl --output growth.png --title "My Analysis"

  # 显示详细日志
  %(prog)s --input merged.jsonl --output growth.png --verbose
"""
    )

    parser.add_argument(
        '--input',
        required=True,
        help='输入的 merged.jsonl 文件路径'
    )

    parser.add_argument(
        '--output',
        default='context_growth_traces.png',
        help='输出图片路径 (默认: context_growth_traces.png)'
    )

    parser.add_argument(
        '--title',
        default='Context growth',
        help='图表标题 (默认: Context growth)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='显示详细日志'
    )

    args = parser.parse_args()

    # 检查输入文件
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ 错误: 输入文件不存在: {args.input}")
        sys.exit(1)

    # 加载 traces
    traces = load_traces(args.input, verbose=args.verbose)

    if not traces:
        print("❌ 错误: 没有找到有效的 trace 数据")
        sys.exit(1)

    if args.verbose:
        print("INFO: 提取会话数据...")

    # 提取每个会话的数据
    all_data = []
    for trace in traces:
        trace_id = trace.get('id', 'unknown')
        turns, tokens, compaction_indices = extract_conversation_data(trace, verbose=args.verbose)

        if turns:
            all_data.append((trace_id, turns, tokens, compaction_indices))

    if not all_data:
        print("❌ 错误: 没有提取到有效的会话数据")
        sys.exit(1)

    if args.verbose:
        print(f"INFO: 成功提取 {len(all_data)} 个会话数据\n")

    # 生成图表
    plot_context_growth(all_data, args.output, args.title, verbose=args.verbose)


if __name__ == '__main__':
    main()
