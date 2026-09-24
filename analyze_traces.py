#!/usr/bin/env python3
"""
分析 Claude Code traces 数据并生成与 InferenceX 网站一致的可视化图表
生成7个指标的分布图:
1. Input tokens per request (每个请求的输入 token 数 - 主会话)
2. Output tokens per request (每个请求的输出 token 数 - 主会话)
3. Uncached input tokens per request (每个请求的未缓存输入 token 数)
4. Requests per conversation (每个对话的请求数)
5. Subagent request ISL (子代理请求的输入序列长度)
6. Subagent request OSL (子代理请求的输出序列长度)
7. Cached fraction per request (每个请求的缓存比例)

注意：只区分主会话（顶层请求）vs 子代理（subagent 内部请求），不区分请求类型 s/n
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from typing import List, Dict, Any
import argparse


def load_jsonl(filepath: str) -> List[Dict[str, Any]]:
    """加载 JSONL 文件"""
    data = []
    with open(filepath, 'r') as f:
        for line in f:
            data.append(json.loads(line))
    return data


def extract_metrics(conversations: List[Dict[str, Any]]) -> Dict[str, List[float]]:
    """从对话数据中提取所有需要的指标"""

    metrics = {
        'input_tokens_per_turn': [],          # 主会话的输入 token（所有顶层非 subagent 请求）
        'output_tokens_per_turn': [],         # 主会话的输出 token
        'uncached_input_per_turn': [],        # 未缓存输入（主会话 + 子代理）
        'turns_per_conversation': [],         # 每个对话的请求数
        'subagent_isl': [],                   # 子代理输入序列长度
        'subagent_osl': [],                   # 子代理输出序列长度
        'cached_fraction_per_turn': []     # 缓存比例（主会话 + 子代理）
    }

    for conv in conversations:
        requests = conv.get('requests', [])
        block_size = conv.get('block_size', 64)

        # 统计主会话请求数（非 subagent 的顶层请求）
        main_request_count = sum(1 for req in requests if req.get('type') != 'subagent')
        metrics['turns_per_conversation'].append(main_request_count)

        # 跟踪上一个主会话请求的 hash_ids
        prev_main_hash_ids = set()

        # 遍历所有顶层请求
        for req in requests:
            req_type = req.get('type', '')

            if req_type == 'subagent':
                # 处理子代理请求
                sub_requests = req.get('requests', [])
                prev_sub_hash_ids = set()

                for sub_req in sub_requests:
                    # 不区分类型，所有子请求都统计
                    in_tokens = sub_req.get('in', 0)
                    out_tokens = sub_req.get('out', 0)

                    # Subagent ISL and OSL
                    if in_tokens > 0:
                        metrics['subagent_isl'].append(in_tokens)
                    if out_tokens > 0:
                        metrics['subagent_osl'].append(out_tokens)

                    # 子代理的缓存计算
                    hash_ids = sub_req.get('hash_ids', [])
                    if hash_ids:
                        curr_hash_ids = set(hash_ids)

                        if prev_sub_hash_ids:
                            cached_blocks = len(prev_sub_hash_ids & curr_hash_ids)
                            total_blocks = len(hash_ids)
                            cached_fraction = cached_blocks / total_blocks if total_blocks > 0 else 0.0
                            uncached_blocks = total_blocks - cached_blocks
                            uncached_tokens = uncached_blocks * block_size
                        else:
                            cached_fraction = 0.0
                            uncached_tokens = len(hash_ids) * block_size

                        metrics['uncached_input_per_turn'].append(uncached_tokens)
                        metrics['cached_fraction_per_turn'].append(cached_fraction)

                        prev_sub_hash_ids = curr_hash_ids
                    else:
                        if in_tokens > 0:
                            metrics['uncached_input_per_turn'].append(in_tokens)
                            metrics['cached_fraction_per_turn'].append(0.0)

            else:
                # 主会话请求 - 不区分类型，只要不是 subagent 就统计
                in_tokens = req.get('in', 0)
                out_tokens = req.get('out', 0)

                if in_tokens > 0:
                    metrics['input_tokens_per_turn'].append(in_tokens)
                if out_tokens > 0:
                    metrics['output_tokens_per_turn'].append(out_tokens)

                # 主会话的缓存计算
                hash_ids = req.get('hash_ids', [])
                if hash_ids:
                    curr_hash_ids = set(hash_ids)

                    if prev_main_hash_ids:
                        cached_blocks = len(prev_main_hash_ids & curr_hash_ids)
                        total_blocks = len(hash_ids)
                        cached_fraction = cached_blocks / total_blocks if total_blocks > 0 else 0.0
                        uncached_blocks = total_blocks - cached_blocks
                        uncached_tokens = uncached_blocks * block_size
                    else:
                        cached_fraction = 0.0
                        uncached_tokens = len(hash_ids) * block_size

                    metrics['uncached_input_per_turn'].append(uncached_tokens)
                    metrics['cached_fraction_per_turn'].append(cached_fraction)

                    prev_main_hash_ids = curr_hash_ids
                else:
                    if in_tokens > 0:
                        metrics['uncached_input_per_turn'].append(in_tokens)
                        metrics['cached_fraction_per_turn'].append(0.0)

    return metrics


def calculate_percentiles(data: List[float]) -> Dict[str, float]:
    """计算百分位数"""
    if not data:
        return {}

    arr = np.array(data)
    return {
        'n': len(data),
        'p50': np.percentile(arr, 50),
        'p75': np.percentile(arr, 75),
        'p90': np.percentile(arr, 90),
        'p95': np.percentile(arr, 95),
        'max': np.max(arr)
    }


def format_number(num: float, unit: str = '', is_percentage: bool = False) -> str:
    """格式化数字显示（k表示千）"""
    if is_percentage:
        return f"{num*100:.0f}%"
    if num >= 1000:
        return f"{num/1000:.1f}k"
    return f"{num:.0f}"


def create_histogram_plot(data: List[float], title: str, xlabel: str,
                         output_path: str, use_log_scale: bool = True, is_percentage: bool = False):
    """创建直方图，样式匹配 InferenceX 网站"""

    if not data:
        print(f"Warning: No data for {title}")
        return

    # 设置样式
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor('#1a1a1a')
    ax.set_facecolor('#1a1a1a')

    # 计算统计信息
    stats = calculate_percentiles(data)

    # 创建直方图
    arr = np.array(data)

    # 动态确定 bin 数量和范围
    if use_log_scale:
        # 过滤掉 0 值，避免 log(0) 问题
        arr_positive = arr[arr > 0]
        if len(arr_positive) == 0:
            print(f"Warning: No positive values for {title}")
            return

        # 使用实际的最小正值和最大值
        min_val = arr_positive.min()
        max_val = arr_positive.max()
        bins = np.logspace(np.log10(min_val), np.log10(max_val), 50)

        # 只绘制正值数据
        arr = arr_positive
    else:
        bins = 50

    # 绘制直方图
    n, bins, patches = ax.hist(arr, bins=bins, color='#c89250',
                               edgecolor='none', linewidth=0, alpha=0.95)

    # 设置对数刻度
    if use_log_scale:
        ax.set_xscale('log')

    # 添加百分位线
    percentile_colors = {
        'p50': '#4a9eff',
        'p75': '#00ff00',
        'p90': '#ffff00',
        'p95': '#ff6b6b'
    }

    legend_lines = []
    legend_labels = []

    for pct, color in percentile_colors.items():
        value = stats[pct]
        line = ax.axvline(value, color=color, linestyle='--', linewidth=1.5, alpha=0.8)
        legend_lines.append(line)
        legend_labels.append(f"{pct} {format_number(value, is_percentage=is_percentage)}")

    # 添加图例
    ax.legend(legend_lines, legend_labels, loc='upper left',
             framealpha=0.9, facecolor='#1a1a1a', edgecolor='none',
             fontsize=9, labelcolor='white')

    # 设置标题和标签
    if is_percentage:
        max_display = format_number(stats['max'], is_percentage=True)
    else:
        max_display = f"{format_number(stats['max'])} {xlabel}"

    stats_text = (f"n={stats['n']:,} · p50 {format_number(stats['p50'], is_percentage=is_percentage)} · "
                 f"p75 {format_number(stats['p75'], is_percentage=is_percentage)} · "
                 f"p90 {format_number(stats['p90'], is_percentage=is_percentage)} · "
                 f"p95 {format_number(stats['p95'], is_percentage=is_percentage)} · "
                 f"max {max_display}")

    ax.set_title(f"{title}\n{stats_text}", fontsize=12, color='white',
                loc='left', pad=20, fontweight='normal')
    ax.set_xlabel(xlabel, fontsize=10, color='#888888')
    ax.set_ylabel('', fontsize=10, color='#888888')

    # 添加 "LOG SCALE" 标签
    if use_log_scale:
        ax.text(0.98, 0.98, 'LOG SCALE', transform=ax.transAxes,
               fontsize=9, color='#888888', ha='right', va='top',
               bbox=dict(boxstyle='round,pad=0.4', facecolor='#1a1a1a',
                        edgecolor='#333333', alpha=0.8))

    # 设置网格
    ax.grid(True, alpha=0.15, color='#333333', linewidth=0.5)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#333333')
    ax.spines['bottom'].set_color('#333333')
    ax.tick_params(colors='#888888', length=4)

    # 调整布局并保存
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, facecolor='#1a1a1a', bbox_inches='tight')
    plt.close()

    print(f"Saved: {output_path}")
    print(f"  Stats: {stats}")


def main():
    parser = argparse.ArgumentParser(description='Analyze Claude Code traces')
    parser.add_argument('--input', default='/mnt/nvme1n1/data/lmk/Github/tair-kvcache/kv_cache_manager/optimizer/tools/kimi_k3_test/trace_0918/merged_20260918.jsonl',
                       help='Input JSONL file path')
    parser.add_argument('--output-dir', default='/mnt/nvme1n1/data/lmk/PROJECT/InferenceX/tmp/plots_0924_test',
                       help='Output directory for plots')
    args = parser.parse_args()

    # 创建输出目录
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading data from {args.input}...")
    conversations = load_jsonl(args.input)
    print(f"Loaded {len(conversations)} conversations")

    print("\nExtracting metrics...")
    metrics = extract_metrics(conversations)

    # 打印统计信息
    print("\nMetrics summary:")
    for name, data in metrics.items():
        print(f"  {name}: {len(data)} data points")

    # 生成所有图表
    print("\nGenerating plots...")

    plots = [
        ('input_tokens_per_turn', 'Input tokens per turn\nMain session only', 'tokens', True, False),
        ('output_tokens_per_turn', 'Output tokens per turn\nMain session only', 'tokens', True, False),
        ('uncached_input_per_turn', 'Uncached input tokens per turn\nMain + Subagent', 'tokens', True, False),
        ('turns_per_conversation', 'Turns per conversation', 'turns', True, False),
        ('subagent_isl', 'Subagent request ISL\nInner subagent requests only', 'tokens', True, False),
        ('subagent_osl', 'Subagent request OSL\nInner subagent requests only', 'tokens', True, False),
        ('cached_fraction_per_turn', 'Cached fraction per turn\nMain + Subagent', 'fraction', False, True),
    ]

    for metric_key, title, xlabel, use_log, is_pct in plots:
        data = metrics[metric_key]
        if data:
            output_path = output_dir / f"{metric_key}.png"
            create_histogram_plot(data, title, xlabel, str(output_path), use_log, is_pct)
        else:
            print(f"Skipping {title} - no data")

    print(f"\nAll plots saved to {output_dir}")
    print("\nTo view the plots, open the PNG files in the output directory.")


if __name__ == '__main__':
    main()
