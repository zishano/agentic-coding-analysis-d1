#!/usr/bin/env python3
"""
提取 traces.jsonl 所有行的 Hash ID 分配
直接从数据中读取每个请求的实际 hash_ids 范围
对于不连续的hash_ids，在一行中横向展示多个范围
对于subagent，展开其内部的每个request
"""

import json
import csv
from pathlib import Path


def find_continuous_ranges(hash_ids):
    """
    找出hash_ids中的连续区间

    Args:
        hash_ids: sorted list of hash_ids

    Returns:
        list of tuples: [(start1, end1), (start2, end2), ...]
    """
    if not hash_ids:
        return []

    sorted_ids = sorted(hash_ids)
    ranges = []
    start = sorted_ids[0]
    end = sorted_ids[0]

    for i in range(1, len(sorted_ids)):
        if sorted_ids[i] == end + 1:
            end = sorted_ids[i]
        else:
            ranges.append((start, end))
            start = sorted_ids[i]
            end = sorted_ids[i]

    ranges.append((start, end))
    return ranges


def format_ranges(ranges):
    """
    将多个范围格式化为字符串

    Args:
        ranges: list of (start, end) tuples

    Returns:
        str: 格式化的范围字符串，如 "[1...30], [1048...1388]"
    """
    if not ranges:
        return ""

    range_strs = [f"[{start}...{end}]" for start, end in ranges]
    return ", ".join(range_strs)


def extract_hash_ids_from_trace(trace, trace_index):
    """
    提取单个trace中每个请求的实际hash_ids

    Args:
        trace: trace数据（JSON对象）
        trace_index: trace索引（从1开始）

    Returns:
        list: 每个请求的hash_ids信息
    """

    results = []

    # 首先收集所有主会话的hash_ids，用于推断没有嵌套requests的subagent
    all_main_hids = set()
    for req in trace['requests']:
        req_type = req.get('type', 'unknown')
        if req_type != 'subagent':
            all_main_hids.update(req.get('hash_ids', []))

    # 用于跟踪已记录的subagent范围，避免重复
    recorded_subagent_ranges = set()

    # 处理每个请求
    for req_idx, req in enumerate(trace['requests']):
        req_type = req.get('type', 'unknown')
        hash_ids = req.get('hash_ids', [])

        if req_type == 'subagent':
            # Subagent请求，首先检查是否有嵌套的requests
            nested_requests = req.get('requests', [])

            if nested_requests:
                # 展开subagent内部的每个request，单独一行
                for nested_idx, nested_req in enumerate(nested_requests):
                    nested_type = nested_req.get('type', 'unknown')
                    nested_hids = nested_req.get('hash_ids', [])

                    if nested_hids:
                        ranges = find_continuous_ranges(nested_hids)

                        results.append({
                            'trace_index': trace_index,
                            'trace_id': trace.get('id', 'unknown'),
                            'request_index': f"{req_idx}.{nested_idx}",  # 使用 主索引.子索引
                            'request_type': f"subagent.{nested_type}",
                            'ranges': ranges,
                            'ranges_str': format_ranges(ranges),
                            'num_segments': len(ranges),
                            'count': len(nested_hids)
                        })
                    else:
                        results.append({
                            'trace_index': trace_index,
                            'trace_id': trace.get('id', 'unknown'),
                            'request_index': f"{req_idx}.{nested_idx}",
                            'request_type': f"subagent.{nested_type}",
                            'ranges': [],
                            'ranges_str': '',
                            'num_segments': 0,
                            'count': 0
                        })
            else:
                # 没有嵌套requests，通过主会话的间隙推断
                before_idx = req_idx - 1
                while before_idx >= 0 and trace['requests'][before_idx].get('type') == 'subagent':
                    before_idx -= 1

                after_idx = req_idx + 1
                while after_idx < len(trace['requests']) and trace['requests'][after_idx].get('type') == 'subagent':
                    after_idx += 1

                if before_idx >= 0 and after_idx < len(trace['requests']):
                    before_hids = trace['requests'][before_idx].get('hash_ids', [])
                    after_hids = trace['requests'][after_idx].get('hash_ids', [])

                    if before_hids and after_hids:
                        before_max = max(before_hids)
                        before_set = set(before_hids)
                        after_set = set(after_hids)
                        new_in_after = sorted([h for h in after_hids if h not in before_set])

                        if new_in_after:
                            sub_start = before_max + 1
                            sub_end = new_in_after[0] - 1

                            range_key = (sub_start, sub_end)
                            if range_key not in recorded_subagent_ranges:
                                recorded_subagent_ranges.add(range_key)

                                if sub_start <= sub_end:
                                    subagent_indices = [j for j in range(before_idx + 1, after_idx)
                                                      if trace['requests'][j].get('type') == 'subagent']

                                    req_idx_str = f"Requests {subagent_indices}" if len(subagent_indices) > 1 else f"Request {subagent_indices[0]}" if subagent_indices else req_idx

                                    results.append({
                                        'trace_index': trace_index,
                                        'trace_id': trace.get('id', 'unknown'),
                                        'request_index': req_idx_str,
                                        'request_type': 'subagent',
                                        'ranges': [(sub_start, sub_end)],
                                        'ranges_str': format_ranges([(sub_start, sub_end)]),
                                        'num_segments': 1,
                                        'count': sub_end - sub_start + 1
                                    })
                                else:
                                    results.append({
                                        'trace_index': trace_index,
                                        'trace_id': trace.get('id', 'unknown'),
                                        'request_index': req_idx,
                                        'request_type': 'subagent',
                                        'ranges': [],
                                        'ranges_str': '',
                                        'num_segments': 0,
                                        'count': 0
                                    })
                        else:
                            results.append({
                                'trace_index': trace_index,
                                'trace_id': trace.get('id', 'unknown'),
                                'request_index': req_idx,
                                'request_type': 'subagent',
                                'ranges': [],
                                'ranges_str': '',
                                'num_segments': 0,
                                'count': 0
                            })
                    else:
                        results.append({
                            'trace_index': trace_index,
                            'trace_id': trace.get('id', 'unknown'),
                            'request_index': req_idx,
                            'request_type': 'subagent',
                            'ranges': [],
                            'ranges_str': '',
                            'num_segments': 0,
                            'count': 0
                        })
                else:
                    results.append({
                        'trace_index': trace_index,
                        'trace_id': trace.get('id', 'unknown'),
                        'request_index': req_idx,
                        'request_type': 'subagent',
                        'ranges': [],
                        'ranges_str': '',
                        'num_segments': 0,
                        'count': 0
                    })
        elif hash_ids:
            # 普通请求（有hash_ids），保持原始request_type
            ranges = find_continuous_ranges(hash_ids)

            results.append({
                'trace_index': trace_index,
                'trace_id': trace.get('id', 'unknown'),
                'request_index': req_idx,
                'request_type': req_type,  # 保持原始类型
                'ranges': ranges,
                'ranges_str': format_ranges(ranges),
                'num_segments': len(ranges),
                'count': len(hash_ids)
            })
        else:
            # 其他没有hash_ids的请求
            results.append({
                'trace_index': trace_index,
                'trace_id': trace.get('id', 'unknown'),
                'request_index': req_idx,
                'request_type': req_type,
                'ranges': [],
                'ranges_str': '',
                'num_segments': 0,
                'count': 0
            })

    return results


def process_all_traces(jsonl_path, output_dir):
    """
    处理所有traces并生成CSV文件

    Args:
        jsonl_path: traces.jsonl 文件路径
        output_dir: 输出目录
    """

    # 创建输出目录
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 为每个trace创建子目录
    traces_dir = output_path / 'traces'
    traces_dir.mkdir(exist_ok=True)

    all_results = []
    trace_stats = []

    print(f"Processing traces from: {jsonl_path}")
    print(f"Output directory: {output_dir}")
    print()

    # 读取并处理每一行
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for trace_index, line in enumerate(f, start=1):
            if not line.strip():
                continue

            try:
                trace = json.loads(line)
                trace_id = trace.get('id', 'unknown')

                # 提取hash_ids
                results = extract_hash_ids_from_trace(trace, trace_index)

                if not results:
                    print(f"Trace {trace_index} ({trace_id[:16]}...): No data")
                    continue

                all_results.extend(results)

                # 统计信息
                total_entries = len(results)
                entries_with_hash_ids = sum(1 for r in results if r['count'] > 0)
                entries_without_hash_ids = total_entries - entries_with_hash_ids
                total_hash_ids = sum(r['count'] for r in results)
                max_hash_id = max((max(r['ranges'])[1] for r in results if r['ranges']), default=0)
                multi_segment_requests = sum(1 for r in results if r['num_segments'] > 1)

                trace_stats.append({
                    'trace_index': trace_index,
                    'trace_id': trace_id,
                    'total_entries': total_entries,
                    'entries_with_hash_ids': entries_with_hash_ids,
                    'entries_without_hash_ids': entries_without_hash_ids,
                    'multi_segment_requests': multi_segment_requests,
                    'max_hash_id': max_hash_id,
                    'total_hash_ids': total_hash_ids
                })

                # 为每个trace保存单独的CSV
                trace_csv_path = traces_dir / f'trace_{trace_index:04d}.csv'
                with open(trace_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['request_index', 'request_type', 'hash_id_ranges', 'num_segments', 'count']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()

                    for item in results:
                        writer.writerow({
                            'request_index': item['request_index'],
                            'request_type': item['request_type'],
                            'hash_id_ranges': item['ranges_str'],
                            'num_segments': item['num_segments'] if item['num_segments'] > 0 else '',
                            'count': item['count']
                        })

                seg_info = f", {multi_segment_requests} multi-segment" if multi_segment_requests > 0 else ""
                print(f"Trace {trace_index} ({trace_id[:16]}...): {total_entries} entries, max hash_id={max_hash_id}{seg_info}")

            except Exception as e:
                print(f"Error processing trace {trace_index}: {e}")
                import traceback
                traceback.print_exc()
                continue

    print()
    print(f"Processed {len(trace_stats)} traces")
    print()

    # 保存汇总CSV
    summary_csv_path = output_path / 'all_traces_hash_ids.csv'
    with open(summary_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['trace_index', 'trace_id', 'request_index', 'request_type',
                     'hash_id_ranges', 'num_segments', 'count']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for item in all_results:
            writer.writerow({
                'trace_index': item['trace_index'],
                'trace_id': item['trace_id'],
                'request_index': item['request_index'],
                'request_type': item['request_type'],
                'hash_id_ranges': item['ranges_str'],
                'num_segments': item['num_segments'] if item['num_segments'] > 0 else '',
                'count': item['count']
            })

    print(f"All traces data saved to: {summary_csv_path}")
    print(f"Total entries: {len(all_results)}")

    # 保存统计信息CSV
    stats_csv_path = output_path / 'traces_statistics.csv'
    with open(stats_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['trace_index', 'trace_id', 'total_entries', 'entries_with_hash_ids',
                     'entries_without_hash_ids', 'multi_segment_requests', 'max_hash_id', 'total_hash_ids']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for stat in trace_stats:
            writer.writerow(stat)

    print(f"Traces statistics saved to: {stats_csv_path}")
    print()

    # 打印汇总统计
    total_entries = sum(s['total_entries'] for s in trace_stats)
    total_with_hash_ids = sum(s['entries_with_hash_ids'] for s in trace_stats)
    total_without_hash_ids = sum(s['entries_without_hash_ids'] for s in trace_stats)
    total_multi_segment = sum(s['multi_segment_requests'] for s in trace_stats)

    print("="*80)
    print("Summary Statistics")
    print("="*80)
    print(f"Total traces: {len(trace_stats)}")
    print(f"Total entries: {total_entries}")
    print(f"  Entries with hash_ids: {total_with_hash_ids}")
    print(f"  Entries without hash_ids: {total_without_hash_ids}")
    print(f"  Multi-segment requests: {total_multi_segment}")
    print()


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        jsonl_path = sys.argv[1]
    else:
        jsonl_path = '/mnt/nvme1n1/data/lmk/PROJECT/agentic-coding-analysis-d1/traces-d1/traces-20260907_194305_global/merged.jsonl'

    if len(sys.argv) > 2:
        output_dir = sys.argv[2]
    else:
        output_dir = '/mnt/nvme1n1/data/lmk/PROJECT/agentic-coding-analysis-d1/hash_ids_merged'

    process_all_traces(jsonl_path, output_dir)
    print("Done!")
