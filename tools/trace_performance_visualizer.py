#!/usr/bin/env python3
"""
为每个 trace 生成三幅性能特征图表
参考 SemiAnalysis 的可视化风格

三个指标：
1. cached context at turn start (tokens) - 回合开始时的缓存上下文
2. uncached input (tokens, user/tool/agent) - 未缓存输入
3. decode output per turn (tokens) - 每回合解码输出

输入格式：
    merged.jsonl - 每行一个 trace（会话），包含：
    {
        "id": "会话ID",
        "requests": [
            {
                "t": 时间戳,
                "type": "s/m",  # s=system, m=message
                "in": 输入tokens,
                "out": 输出tokens,
                "cached": 缓存tokens (可选),
                "role": "main/subagent" (可选)
            },
            ...
        ]
    }
"""

import json
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Tuple
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# 区分主代理和子代理的颜色
MAIN_COLOR = '#4A90E2'      # 蓝色 - 主代理
SUBAGENT_COLOR = '#F5A623'  # 橙色 - 子代理


def load_traces(jsonl_path: str, verbose: bool = False) -> List[Dict]:
    """从 merged.jsonl 加载所有 trace"""
    traces = []

    if verbose:
        print(f"📖 读取文件: {jsonl_path}")

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
                    print(f"  ✓ Trace {trace_id}: {req_count} requests")

            except json.JSONDecodeError as e:
                if verbose:
                    print(f"⚠️  跳过第 {line_num} 行: {e}")
                continue

    if verbose:
        print(f"✅ 成功加载 {len(traces)} 个 trace\n")

    return traces


def extract_performance_data(trace: Dict) -> Dict:
    """
    从 trace 中提取性能数据

    返回: {
        'busy_times': [累计时间列表],
        'cached_context': [(时间, tokens, is_subagent), ...],
        'uncached_input': [(时间, tokens, is_subagent), ...],
        'decode_output': [(时间, tokens, is_subagent), ...]
    }
    """
    requests = trace.get('requests', [])
    if not requests:
        return None

    # 提取数据
    cached_context = []
    uncached_input = []
    decode_output = []

    # 计算 busy time（累计活跃时间）
    start_time = requests[0].get('t', 0)

    for req in requests:
        t = req.get('t', 0)
        busy_time = t - start_time if t >= start_time else 0

        # 判断是否为子代理
        req_type = req.get('type', 's')
        is_subagent = (req_type == 'm')  # m 表示子代理消息

        # 提取各项指标
        in_tokens = req.get('in', 0)
        out_tokens = req.get('out', 0)
        cached = req.get('cached', 0)

        # 如果没有 cached 字段，估算：假设 20% 的输入是缓存的
        if cached == 0 and in_tokens > 0:
            cached = int(in_tokens * 0.2)

        uncached = in_tokens - cached if in_tokens > cached else in_tokens

        # 只记录有效数据
        if cached > 0:
            cached_context.append((busy_time, cached, is_subagent))
        if uncached > 0:
            uncached_input.append((busy_time, uncached, is_subagent))
        if out_tokens > 0:
            decode_output.append((busy_time, out_tokens, is_subagent))

    return {
        'cached_context': cached_context,
        'uncached_input': uncached_input,
        'decode_output': decode_output
    }


def plot_single_trace(trace: Dict, output_dir: Path, verbose: bool = False):
    """为单个 trace 生成三幅图表"""
    trace_id = trace.get('id', 'unknown')

    if verbose:
        print(f"📊 生成图表: {trace_id}")

    # 提取数据
    data = extract_performance_data(trace)
    if not data:
        if verbose:
            print(f"⚠️  跳过 {trace_id}: 无有效数据")
        return

    # 创建图表：3 行 1 列
    fig, axes = plt.subplots(3, 1, figsize=(12, 10))
    fig.suptitle(f'Performance Metrics - {trace_id}', fontsize=14, fontweight='bold')

    # === 图1: cached context at turn start ===
    ax1 = axes[0]
    plot_scatter_by_role(ax1, data['cached_context'],
                         'cached context at turn start (tokens)',
                         'main', 'subagent')

    # === 图2: uncached input ===
    ax2 = axes[1]
    plot_scatter_by_role(ax2, data['uncached_input'],
                         'uncached input (tokens, user/tool/agent)',
                         'main', 'subagent')

    # === 图3: decode output per turn ===
    ax3 = axes[2]
    plot_scatter_by_role(ax3, data['decode_output'],
                         'decode output per turn (tokens)',
                         'main', 'subagent')

    # 设置最底部的 x 轴标签
    ax3.set_xlabel('busy time (s, active only, ≥1)', fontsize=11)

    # 调整布局
    plt.tight_layout(rect=[0, 0, 1, 0.97])

    # 保存图表
    output_file = output_dir / f'{trace_id}_performance.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()

    if verbose:
        print(f"  ✓ 已保存: {output_file.name}")


def plot_scatter_by_role(ax, data_points, ylabel, main_label, subagent_label):
    """
    绘制散点图，区分主代理和子代理

    data_points: [(busy_time, tokens, is_subagent), ...]
    """
    if not data_points:
        ax.text(0.5, 0.5, 'No data', ha='center', va='center',
                transform=ax.transAxes, fontsize=12, color='gray')
        ax.set_ylabel(ylabel, fontsize=10)
        return

    # 分离主代理和子代理数据
    main_times = []
    main_tokens = []
    sub_times = []
    sub_tokens = []

    for busy_time, tokens, is_subagent in data_points:
        # busy_time 至少为 1（对数坐标要求）
        bt = max(busy_time, 1)

        if is_subagent:
            sub_times.append(bt)
            sub_tokens.append(tokens)
        else:
            main_times.append(bt)
            main_tokens.append(tokens)

    # 绘制散点
    if main_times:
        ax.scatter(main_times, main_tokens, c=MAIN_COLOR, alpha=0.6,
                   s=10, label=main_label, edgecolors='none')

    if sub_times:
        ax.scatter(sub_times, sub_tokens, c=SUBAGENT_COLOR, alpha=0.6,
                   s=10, label=subagent_label, edgecolors='none')

    # 设置对数坐标
    ax.set_xscale('log')
    ax.set_yscale('log')

    # 设置标签
    ax.set_ylabel(ylabel, fontsize=10)

    # 设置网格
    ax.grid(True, which='both', alpha=0.3, linestyle='-', linewidth=0.5)
    ax.grid(True, which='minor', alpha=0.15, linestyle='-', linewidth=0.3)

    # 设置 Y 轴范围（避免显示 <1 的值）
    all_tokens = main_tokens + sub_tokens
    if all_tokens:
        min_token = max(1, min(all_tokens) * 0.8)
        max_token = max(all_tokens) * 1.5
        ax.set_ylim(min_token, max_token)

    # 设置 X 轴范围
    all_times = main_times + sub_times
    if all_times:
        min_time = 1  # 最小为 1 秒
        max_time = max(all_times) * 1.5
        ax.set_xlim(min_time, max_time)

    # 图例
    if main_times or sub_times:
        ax.legend(loc='upper right', fontsize=8, framealpha=0.9)


def main():
    parser = argparse.ArgumentParser(
        description='为每个 trace 生成三幅性能特征图表',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本用法
  %(prog)s --input merged.jsonl

  # 指定输出目录
  %(prog)s --input merged.jsonl --output-dir ./output

  # 显示详细日志
  %(prog)s --input merged.jsonl --verbose
"""
    )

    parser.add_argument(
        '--input',
        required=True,
        help='输入的 merged.jsonl 文件路径'
    )

    parser.add_argument(
        '--output-dir',
        help='输出目录（默认：merged.jsonl 所在目录）'
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

    # 确定输出目录
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = input_path.parent

    output_dir.mkdir(parents=True, exist_ok=True)

    if args.verbose:
        print(f"📁 输出目录: {output_dir}\n")

    # 加载 traces
    traces = load_traces(args.input, verbose=args.verbose)

    if not traces:
        print("❌ 错误: 没有找到有效的 trace 数据")
        sys.exit(1)

    # 为每个 trace 生成图表
    print(f"\n🚀 开始生成图表 ({len(traces)} 个 trace)...\n")

    success_count = 0
    for trace in traces:
        try:
            plot_single_trace(trace, output_dir, verbose=args.verbose)
            success_count += 1
        except Exception as e:
            trace_id = trace.get('id', 'unknown')
            print(f"❌ 生成 {trace_id} 图表时出错: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()

    # 总结
    print(f"\n{'=' * 70}")
    print(f"✅ 完成！成功生成 {success_count}/{len(traces)} 个图表")
    print(f"📁 输出目录: {output_dir}")
    print(f"{'=' * 70}")


if __name__ == '__main__':
    main()
