#!/usr/bin/env python3
"""
为每个 trace 生成三幅性能特征图，区分主代理和子代理

基于 SemiAnalysis 风格，为每个 trace 生成包含三个子图的 PNG：
1. cached context at turn start (缓存上下文)
2. uncached input (未缓存输入)
3. decode output per turn (解码输出)

横轴: busy time (s, active only, ≥1) - 从第一个请求开始的累计时间
纵轴: token 数（对数坐标）

输入格式：
    merged.jsonl - 每行一个 trace，包含：
    {
        "id": "会话ID",
        "requests": [
            {"type": "s", "t": 时间戳, "in": X, "out": Y, ...},  # 主代理请求
            {"type": "subagent", "t": 时间戳, "agent_id": "...", "requests": [...]},  # 子代理
            ...
        ]
    }

输出：
    在 merged.jsonl 同级目录生成 <trace_id>_performance.png
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

def load_traces(jsonl_path: str, verbose: bool = False) -> List[Dict]:
    """从 merged.jsonl 加载所有 trace"""
    traces = []

    if verbose:
        print(f"读取文件: {jsonl_path}")

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
                    print(f"  - Trace {trace_id}: {req_count} 个请求")

            except json.JSONDecodeError as e:
                if verbose:
                    print(f"WARNING: 跳过第 {line_num} 行 (JSON 解析错误): {e}")
                continue

    if verbose:
        print(f"成功加载 {len(traces)} 个 trace\n")

    return traces


def extract_performance_data(trace: Dict) -> Tuple[Dict, Dict]:
    """
    从单个 trace 中提取主代理和子代理的性能数据

    返回: (main_data, subagent_data)
    每个 dict 包含:
        {
            'busy_time': [时间列表],
            'cached': [缓存token数, ...],
            'uncached': [未缓存token数, ...],
            'output': [输出token数, ...]
        }
    """
    requests = trace.get('requests', [])
    if not requests:
        return None, None

    # 找到全局起始时间
    start_time = None
    for req in requests:
        t = req.get('t', 0)
        if start_time is None or t < start_time:
            start_time = t

    if start_time is None:
        start_time = 0

    # 主代理数据
    main_data = {
        'busy_time': [],
        'cached': [],
        'uncached': [],
        'output': []
    }

    # 子代理数据
    sub_data = {
        'busy_time': [],
        'cached': [],
        'uncached': [],
        'output': []
    }

    prev_main_in = 0

    for req in requests:
        req_type = req.get('type')
        t = req.get('t', 0)
        busy_time = max(1, t - start_time)  # 至少为 1（对数坐标要求）

        if req_type == 's':
            # 主代理请求
            in_tokens = req.get('in', 0)
            out_tokens = req.get('out', 0)

            if in_tokens > 0:
                # 计算缓存和未缓存
                if prev_main_in == 0:
                    cached = 0
                    uncached = in_tokens
                else:
                    if in_tokens >= prev_main_in:
                        cached = prev_main_in
                        uncached = in_tokens - prev_main_in
                    else:
                        # 压缩事件
                        cached = 0
                        uncached = in_tokens

                main_data['busy_time'].append(busy_time)
                main_data['cached'].append(cached)
                main_data['uncached'].append(uncached)
                main_data['output'].append(out_tokens)

                prev_main_in = in_tokens

        elif req_type == 'subagent':
            # 子代理请求
            sub_requests = req.get('requests', [])
            prev_sub_in = 0

            for sub_req in sub_requests:
                if sub_req.get('type') == 's':
                    sub_t = sub_req.get('t', 0)
                    # 子代理的 t 是相对于子代理启动时间的
                    # 需要加上父请求的 t 来得到全局时间
                    sub_busy_time = max(1, t + sub_t - start_time)

                    in_tokens = sub_req.get('in', 0)
                    out_tokens = sub_req.get('out', 0)

                    if in_tokens > 0:
                        # 子代理的缓存计算
                        if prev_sub_in == 0:
                            cached = 0
                            uncached = in_tokens
                        else:
                            if in_tokens >= prev_sub_in:
                                cached = prev_sub_in
                                uncached = in_tokens - prev_sub_in
                            else:
                                cached = 0
                                uncached = in_tokens

                        sub_data['busy_time'].append(sub_busy_time)
                        sub_data['cached'].append(cached)
                        sub_data['uncached'].append(uncached)
                        sub_data['output'].append(out_tokens)

                        prev_sub_in = in_tokens

    return main_data, sub_data


def plot_trace_performance(trace: Dict, output_path: str, verbose: bool = False):
    """为单个 trace 生成三幅性能图"""
    trace_id = trace.get('id', 'unknown')

    if verbose:
        print(f"\n生成图表: {trace_id}")

    main_data, sub_data = extract_performance_data(trace)

    if not main_data or len(main_data['busy_time']) == 0:
        if verbose:
            print(f"  ⚠ 跳过 {trace_id}: 无有效数据")
        return False

    # 创建图表：3 行 1 列
    fig, axes = plt.subplots(3, 1, figsize=(12, 10))
    fig.suptitle(f'Trace: {trace_id}', fontsize=14, fontweight='bold')

    # 颜色：主代理=蓝色，子代理=橙色
    main_color = '#1f77b4'
    sub_color = '#ff7f0e'

    # === 子图 1: cached context at turn start ===
    ax1 = axes[0]
    if len(main_data['busy_time']) > 0:
        ax1.scatter(main_data['busy_time'], main_data['cached'],
                   c=main_color, s=20, alpha=0.6, label='main')
    if len(sub_data['busy_time']) > 0:
        ax1.scatter(sub_data['busy_time'], sub_data['cached'],
                   c=sub_color, s=20, alpha=0.6, label='subagent')

    ax1.set_xscale('log')
    ax1.set_yscale('log')
    ax1.set_ylabel('cached context at turn start (tokens)', fontsize=10)
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.legend(loc='upper left', fontsize=9)

    # === 子图 2: uncached input ===
    ax2 = axes[1]
    if len(main_data['busy_time']) > 0:
        ax2.scatter(main_data['busy_time'], main_data['uncached'],
                   c=main_color, s=20, alpha=0.6, label='main')
    if len(sub_data['busy_time']) > 0:
        ax2.scatter(sub_data['busy_time'], sub_data['uncached'],
                   c=sub_color, s=20, alpha=0.6, label='subagent')

    ax2.set_xscale('log')
    ax2.set_yscale('log')
    ax2.set_ylabel('uncached input (tokens, user/tool/agent)', fontsize=10)
    ax2.grid(True, alpha=0.3, linestyle='--')
    ax2.legend(loc='upper left', fontsize=9)

    # === 子图 3: decode output per turn ===
    ax3 = axes[2]
    if len(main_data['busy_time']) > 0:
        ax3.scatter(main_data['busy_time'], main_data['output'],
                   c=main_color, s=20, alpha=0.6, label='main')
    if len(sub_data['busy_time']) > 0:
        ax3.scatter(sub_data['busy_time'], sub_data['output'],
                   c=sub_color, s=20, alpha=0.6, label='subagent')

    ax3.set_xscale('log')
    ax3.set_yscale('log')
    ax3.set_xlabel('busy time (s, active only, ≥1)', fontsize=10)
    ax3.set_ylabel('decode output per turn (tokens)', fontsize=10)
    ax3.grid(True, alpha=0.3, linestyle='--')
    ax3.legend(loc='upper left', fontsize=9)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    if verbose:
        main_count = len(main_data['busy_time'])
        sub_count = len(sub_data['busy_time'])
        file_size = Path(output_path).stat().st_size
        print(f"  ✓ 生成成功: {output_path}")
        print(f"    主代理: {main_count} 请求, 子代理: {sub_count} 请求")
        print(f"    文件大小: {file_size / 1024:.1f} KB")

    return True


def main():
    parser = argparse.ArgumentParser(
        description='为每个 trace 生成三幅性能特征图',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  %(prog)s traces/merged.jsonl
  %(prog)s traces/merged.jsonl --verbose
        """
    )

    parser.add_argument('jsonl_file', help='输入的 merged.jsonl 文件路径')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='显示详细处理信息')

    args = parser.parse_args()

    # 验证输入文件
    jsonl_path = Path(args.jsonl_file)
    if not jsonl_path.exists():
        print(f"ERROR: 文件不存在: {jsonl_path}", file=sys.stderr)
        sys.exit(1)

    # 输出目录 = 输入文件同级目录
    output_dir = jsonl_path.parent

    # 加载 traces
    traces = load_traces(str(jsonl_path), args.verbose)

    if not traces:
        print("ERROR: 没有找到有效的 trace", file=sys.stderr)
        sys.exit(1)

    # 为每个 trace 生成图表
    success_count = 0
    total_count = len(traces)

    for trace in traces:
        trace_id = trace.get('id', 'unknown')
        # 清理 trace_id，移除可能的特殊字符
        safe_id = trace_id.replace('/', '_').replace('\\', '_')
        output_filename = f"{safe_id}_performance.png"
        output_path = output_dir / output_filename

        if plot_trace_performance(trace, str(output_path), args.verbose):
            success_count += 1

    # 总结
    print(f"\n{'='*60}")
    print(f"✓ 完成！成功生成: {success_count}/{total_count} 个图表")
    print(f"📁 输出目录: {output_dir}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
