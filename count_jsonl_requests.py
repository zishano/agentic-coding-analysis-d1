#!/usr/bin/env python3
"""
统计 JSONL 文件中指定时间段的请求数量

用法:
    python3 count_jsonl_requests.py
    python3 count_jsonl_requests.py --start "2026-09-07 17:00:00" --end "2026-09-08 01:00:00"
    python3 count_jsonl_requests.py --hourly --detail
"""
import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict


def parse_args():
    parser = argparse.ArgumentParser(description='统计 JSONL 文件中指定时间段的请求数量')
    parser.add_argument('--jsonl-root', type=str,
                        default='tmp/projects',
                        help='JSONL 根目录路径')
    parser.add_argument('--start', type=str, default='',
                        help='开始时间，格式: "YYYY-MM-DD HH:MM:SS" 或 "YYYY-MM-DDTHH:MM:SS+08:00"，留空=不限')
    parser.add_argument('--end', type=str, default='',
                        help='结束时间，格式: "YYYY-MM-DD HH:MM:SS" 或 "YYYY-MM-DDTHH:MM:SS+08:00"，留空=不限')
    parser.add_argument('--by-session', action='store_true',
                        help='按会话统计（显示每个会话的请求数）')
    parser.add_argument('--detail', action='store_true',
                        help='显示详细信息（模型、项目分布等）')
    parser.add_argument('--hourly', action='store_true',
                        help='按小时统计请求数量')
    parser.add_argument('--by-project', action='store_true',
                        help='按项目目录统计')
    parser.add_argument('--classify', action='store_true',
                        help='显示详细分类统计（按响应类型等）')
    parser.add_argument('--expand', action='store_true',
                        help='扩展时间范围（前后各扩展 5 分钟以避免边界遗漏）')
    return parser.parse_args()


def parse_timestamp(ts_str):
    """解析时间戳，支持多种格式，统一转换为带时区的 datetime"""
    if not ts_str:
        return None

    # 尝试 fromisoformat（最通用）
    try:
        # 将 Z 替换为 +00:00（UTC）
        dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        # 确保有时区信息
        if dt.tzinfo is None:
            # 如果没有时区，假设是 UTC
            from datetime import timezone
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except:
        pass

    # 尝试多种格式
    formats = [
        '%Y-%m-%dT%H:%M:%S.%fZ',      # 2026-09-07T17:00:00.000Z
        '%Y-%m-%dT%H:%M:%SZ',          # 2026-09-07T17:00:00Z
        '%Y-%m-%dT%H:%M:%S%z',         # 2026-09-07T17:00:00+08:00
        '%Y-%m-%dT%H:%M:%S.%f%z',      # 2026-09-07T17:00:00.000+08:00
        '%Y-%m-%d %H:%M:%S',           # 2026-09-07 17:00:00
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(ts_str, fmt)
            # 如果解析成功但没有时区信息，添加 UTC
            if dt.tzinfo is None:
                from datetime import timezone
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except:
            pass

    return None


def validate_time(time_str):
    """验证并标准化时间格式"""
    if not time_str:
        return None
    try:
        # 尝试解析
        if 'T' not in time_str:
            # 如果没有 T，添加 T 和时区
            time_str = time_str.replace(' ', 'T') + '+08:00'
        elif '+' not in time_str and 'Z' not in time_str:
            # 如果没有时区信息，添加 +08:00
            time_str = time_str + '+08:00'

        dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        return dt
    except ValueError:
        print(f"❌ 时间格式错误: {time_str}")
        print("   正确格式: YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DDTHH:MM:SS+08:00")
        return None


def discover_jsonl_files(jsonl_root):
    """发现所有 JSONL 文件（包括主会话和子代理）"""
    jsonl_root = Path(jsonl_root)
    if not jsonl_root.exists():
        print(f"❌ JSONL 根目录不存在: {jsonl_root}")
        return [], []

    # 递归查找所有 .jsonl 文件，分别统计主会话和子代理
    main_jsonl_files = []
    agent_jsonl_files = []

    for jsonl_file in jsonl_root.rglob("*.jsonl"):
        if jsonl_file.name.startswith("agent-"):
            agent_jsonl_files.append(jsonl_file)
        else:
            main_jsonl_files.append(jsonl_file)

    return sorted(main_jsonl_files), sorted(agent_jsonl_files)


def extract_messages_from_jsonl(jsonl_path, start_time=None, end_time=None):
    """从 JSONL 文件中提取消息"""
    messages = []

    try:
        with open(jsonl_path) as f:
            for line_num, line in enumerate(f, 1):
                try:
                    msg = json.loads(line.strip())

                    # 只统计 assistant 消息（有 message_id 的）
                    if msg.get('type') != 'assistant':
                        continue

                    message_obj = msg.get('message', {})
                    msg_id = message_obj.get('id')

                    # 必须有 message_id
                    if not msg_id or not (msg_id.startswith('msg_') or msg_id.startswith('resp_')):
                        continue

                    # 解析时间戳
                    timestamp = parse_timestamp(msg.get('timestamp', ''))
                    if not timestamp:
                        continue

                    # 时间过滤
                    if start_time and timestamp < start_time:
                        continue
                    if end_time and timestamp > end_time:
                        continue

                    # 提取信息
                    messages.append({
                        'message_id': msg_id,
                        'timestamp': timestamp,
                        'session_id': msg.get('sessionId', ''),
                        'model': message_obj.get('model', 'unknown'),
                        'cwd': msg.get('cwd', ''),
                        'jsonl_file': jsonl_path,
                        'usage': message_obj.get('usage', {}),
                    })

                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    pass
    except Exception as e:
        pass

    return messages


def count_jsonl_requests(jsonl_root, start_time=None, end_time=None,
                        by_session=False, detail=False, hourly=False, by_project=False, classify=False):
    """统计 JSONL 请求数量"""

    jsonl_root = Path(jsonl_root)
    if not jsonl_root.exists():
        print(f"❌ JSONL 根目录不存在: {jsonl_root}")
        return

    print(f"\n📊 JSONL 目录: {jsonl_root}")
    print("=" * 70)

    # 发现 JSONL 文件
    print("🔍 扫描 JSONL 文件...")
    main_jsonl_files, agent_jsonl_files = discover_jsonl_files(jsonl_root)
    total_files = len(main_jsonl_files) + len(agent_jsonl_files)
    print(f"   发现 {total_files} 个 JSONL 文件")
    print(f"     - 主会话: {len(main_jsonl_files)} 个")
    print(f"     - 子代理: {len(agent_jsonl_files)} 个")

    # 提取消息
    print("📖 读取消息...")
    all_messages = []
    main_messages = []
    agent_messages = []
    files_with_messages = 0

    # 处理主会话 JSONL
    for jsonl_file in main_jsonl_files:
        messages = extract_messages_from_jsonl(jsonl_file, start_time, end_time)
        if messages:
            all_messages.extend(messages)
            main_messages.extend(messages)
            files_with_messages += 1

    # 处理子代理 JSONL
    for jsonl_file in agent_jsonl_files:
        messages = extract_messages_from_jsonl(jsonl_file, start_time, end_time)
        if messages:
            all_messages.extend(messages)
            agent_messages.extend(messages)
            files_with_messages += 1

    print(f"   {files_with_messages} 个文件包含符合条件的消息")
    print(f"     - 主会话: {len([m for m in main_messages])} 条")
    print(f"     - 子代理: {len([m for m in agent_messages])} 条")
    print("=" * 70)

    if start_time:
        print(f"⏰ 开始时间: {start_time.isoformat()}")
    if end_time:
        print(f"⏰ 结束时间: {end_time.isoformat()}")

    # 总请求数
    total_count = len(all_messages)
    main_count = len(main_messages)
    agent_count = len(agent_messages)

    print(f"\n✅ 总请求数: {total_count:,}")
    print(f"   主会话: {main_count:,} ({main_count/total_count*100 if total_count > 0 else 0:.1f}%)")
    print(f"   子代理: {agent_count:,} ({agent_count/total_count*100 if total_count > 0 else 0:.1f}%)")

    if total_count == 0:
        print("   (没有找到符合条件的请求)")
        return

    # 唯一 message_id 数量
    unique_msg_ids = len(set(m['message_id'] for m in all_messages))
    print(f"   唯一 message_id: {unique_msg_ids:,}")

    # 唯一会话数
    unique_sessions = len(set(m['session_id'] for m in all_messages if m['session_id']))
    print(f"   唯一会话数: {unique_sessions:,}")

    # 时间范围
    if all_messages:
        timestamps = [m['timestamp'] for m in all_messages]
        min_time = min(timestamps)
        max_time = max(timestamps)
        print(f"\n📅 实际时间范围:")
        print(f"   最早: {min_time.isoformat()}")
        print(f"   最晚: {max_time.isoformat()}")

    # 按小时统计
    if hourly:
        print(f"\n⏰ 按小时统计:")
        hourly_count = defaultdict(int)
        for msg in all_messages:
            # 提取小时（转换为 +08:00 时区以便对比）
            from datetime import timezone, timedelta
            beijing_tz = timezone(timedelta(hours=8))
            local_time = msg['timestamp'].astimezone(beijing_tz)
            hour_key = local_time.strftime('%Y-%m-%dT%H:00:00%z')
            hourly_count[hour_key] += 1

        if hourly_count:
            print(f"   共 {len(hourly_count)} 个小时有请求\n")
            for hour in sorted(hourly_count.keys()):
                count = hourly_count[hour]
                pct = (count / total_count * 100) if total_count > 0 else 0
                bar_length = int(pct / 2)
                bar = '█' * bar_length
                print(f"   {hour} | {count:5,} 请求 ({pct:5.1f}%) {bar}")

    # 按会话统计
    if by_session:
        print(f"\n📋 按会话统计:")
        session_count = defaultdict(list)
        for msg in all_messages:
            session_id = msg['session_id'] or 'unknown'
            session_count[session_id].append(msg)

        print(f"   共 {len(session_count)} 个会话\n")

        # 按请求数排序
        sorted_sessions = sorted(session_count.items(), key=lambda x: len(x[1]), reverse=True)
        for i, (session_id, msgs) in enumerate(sorted_sessions[:20], 1):
            session_short = session_id[:12] if session_id != 'unknown' else 'unknown'
            timestamps = [m['timestamp'] for m in msgs]
            min_t = min(timestamps).isoformat()
            max_t = max(timestamps).isoformat()
            print(f"   {i:2d}. {session_short}: {len(msgs):3d} 请求  ({min_t} ~ {max_t})")

        if len(sorted_sessions) > 20:
            print(f"   ... (还有 {len(sorted_sessions) - 20} 个会话)")

    # 按项目目录统计
    if by_project:
        print(f"\n📁 按项目目录统计:")
        project_count = defaultdict(int)
        for msg in all_messages:
            jsonl_file = msg['jsonl_file']
            project_dir = jsonl_file.parent.name
            project_count[project_dir] += 1

        print(f"   共 {len(project_count)} 个项目目录\n")

        sorted_projects = sorted(project_count.items(), key=lambda x: x[1], reverse=True)
        for i, (project, count) in enumerate(sorted_projects[:15], 1):
            pct = (count / total_count * 100) if total_count > 0 else 0
            project_short = project[:60] + "..." if len(project) > 60 else project
            print(f"   {i:2d}. {project_short}")
            print(f"       {count:4d} 请求 ({pct:5.1f}%)")

        if len(sorted_projects) > 15:
            print(f"   ... (还有 {len(sorted_projects) - 15} 个项目)")

    # 详细信息
    if detail:
        # 按模型统计
        print(f"\n🤖 按模型统计:")
        model_count = defaultdict(int)
        for msg in all_messages:
            model_count[msg['model']] += 1

        for model in sorted(model_count.keys()):
            count = model_count[model]
            pct = (count / total_count * 100) if total_count > 0 else 0
            print(f"   {model}: {count:,} 请求 ({pct:.1f}%)")

        # Token 统计
        print(f"\n💰 Token 统计:")
        total_input = sum(m['usage'].get('input_tokens', 0) for m in all_messages)
        total_output = sum(m['usage'].get('output_tokens', 0) for m in all_messages)

        if total_input > 0:
            avg_input = total_input / total_count
            print(f"   输入 tokens:")
            print(f"      总计: {total_input:,}  平均: {int(avg_input):,}")

        if total_output > 0:
            avg_output = total_output / total_count
            print(f"   输出 tokens:")
            print(f"      总计: {total_output:,}  平均: {int(avg_output):,}")

        if total_input > 0 and total_output > 0:
            print(f"   合计: {total_input + total_output:,}")

    # 详细分类统计
    if classify and all_messages:
        print(f"\n" + "=" * 70)
        print("📊 详细分类统计")
        print("=" * 70)

        # 只统计assistant消息
        assistant_messages = [m for m in all_messages if m.get('type') == 'assistant']

        print(f"\n总消息数: {len(all_messages):,}")
        print(f"├─ assistant消息: {len(assistant_messages):,}")
        print(f"└─ 其他消息: {len(all_messages) - len(assistant_messages):,}")

        if assistant_messages:
            # 统计有无message_id
            with_id = [m for m in assistant_messages if m.get('message', {}).get('id')]
            without_id = [m for m in assistant_messages if not m.get('message', {}).get('id')]

            print(f"\n   assistant消息分类:")
            print(f"   ├─ 有message_id: {len(with_id):,} ({len(with_id)/len(assistant_messages)*100:.1f}%) ✅")
            print(f"   └─ 无message_id: {len(without_id):,} ({len(without_id)/len(assistant_messages)*100:.1f}%) ❌")

            if with_id:
                # 统计完整性（有stop_reason）
                complete = [m for m in with_id if m.get('message', {}).get('stop_reason')]
                incomplete = [m for m in with_id if not m.get('message', {}).get('stop_reason')]

                print(f"\n   有message_id的消息:")
                print(f"   ├─ 完整 (有stop_reason): {len(complete):,} ({len(complete)/len(with_id)*100:.1f}%) ✅")
                print(f"   └─ 不完整 (无stop_reason): {len(incomplete):,} ({len(incomplete)/len(with_id)*100:.1f}%) ❌")

                # 统计stop_reason的分布
                if complete:
                    stop_reasons = {}
                    for m in complete:
                        sr = m.get('message', {}).get('stop_reason', 'unknown')
                        stop_reasons[sr] = stop_reasons.get(sr, 0) + 1

                    print(f"\n   stop_reason分布:")
                    for sr, count in sorted(stop_reasons.items(), key=lambda x: x[1], reverse=True):
                        print(f"       ├─ {sr}: {count:,} ({count/len(complete)*100:.1f}%)")

            # 按文件类型统计
            main_assistant = [m for m in assistant_messages if m.get('_source', '').find('agent-') == -1]
            agent_assistant = [m for m in assistant_messages if m.get('_source', '').find('agent-') != -1]

            if main_assistant or agent_assistant:
                print(f"\n   按来源分类:")
                print(f"   ├─ 主会话: {len(main_assistant):,} ({len(main_assistant)/len(assistant_messages)*100:.1f}%)")
                print(f"   └─ 子代理: {len(agent_assistant):,} ({len(agent_assistant)/len(assistant_messages)*100:.1f}%)")

    print("\n" + "=" * 70)


def main():
    args = parse_args()

    # 验证时间格式并扩展范围
    original_start = args.start
    original_end = args.end

    if args.expand and args.start and args.end:
        # 扩展时间范围 ±5 分钟
        start_time = validate_time(args.start)
        end_time = validate_time(args.end)

        if start_time and end_time:
            # 扩展时间
            start_time = start_time - timedelta(minutes=5)
            end_time = end_time + timedelta(minutes=5)

            print(f"💡 时间范围扩展 ±5 分钟以避免边界遗漏")
            print(f"   原始: {original_start} ~ {original_end}")
            print(f"   扩展: {start_time.isoformat()} ~ {end_time.isoformat()}")
            print()
    else:
        start_time = validate_time(args.start) if args.start else None
        end_time = validate_time(args.end) if args.end else None

    if args.start and start_time is None:
        return
    if args.end and end_time is None:
        return

    # 如果没有指定任何选项，默认显示按小时统计
    hourly = args.hourly
    if not args.hourly and not args.by_session and not args.by_project:
        # 没有指定统计方式，默认使用按小时统计
        hourly = True

    count_jsonl_requests(
        jsonl_root=args.jsonl_root,
        start_time=start_time,
        end_time=end_time,
        by_session=args.by_session,
        detail=args.detail,
        hourly=hourly,
        by_project=args.by_project,
        classify=args.classify
    )


if __name__ == "__main__":
    main()
