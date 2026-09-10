#!/usr/bin/env python3
"""
统计 JSONL 文件中的消息数据
显示详细的分类树和统计信息
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

def parse_args():
    parser = argparse.ArgumentParser(description='统计 JSONL 文件数据')
    parser.add_argument('--jsonl-root', type=str, default='tmp/projects',
                        help='JSONL 根目录 (默认: tmp/projects)')
    parser.add_argument('--start', type=str, default=None,
                        help='开始时间 (格式: YYYY-MM-DDTHH:MM:SS+08:00, 默认: 不限)')
    parser.add_argument('--end', type=str, default=None,
                        help='结束时间 (格式: YYYY-MM-DDTHH:MM:SS+08:00, 默认: 不限)')
    return parser.parse_args()

def parse_timestamp(ts_str):
    """解析时间戳"""
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
    except:
        return None

def main():
    args = parse_args()

    JSONL_ROOT = Path(args.jsonl_root)
    START_TIME = args.start
    END_TIME = args.end

    if not JSONL_ROOT.exists():
        print(f"❌ 错误: JSONL 根目录不存在: {JSONL_ROOT}")
        return 1

    # 解析时间范围
    start_dt = parse_timestamp(START_TIME) if START_TIME else None
    end_dt = parse_timestamp(END_TIME) if END_TIME else None

    print("=" * 70)
    print("JSONL 文件数据统计")
    print("=" * 70)

    # 显示时间范围
    if start_dt and end_dt:
        print(f"时间范围: {START_TIME} ~ {END_TIME}")
    elif start_dt:
        print(f"时间范围: {START_TIME} ~ (不限)")
    elif end_dt:
        print(f"时间范围: (不限) ~ {END_TIME}")
    else:
        print(f"时间范围: 全部数据")
    print()

    # 统计变量
    total_files = 0
    main_session_files = 0
    agent_files = 0

    total_messages = 0
    messages_with_id = 0
    messages_without_id = 0

    # Stop reason 分布
    stop_reason_dist = defaultdict(int)

    # Message type 分布
    message_type_dist = defaultdict(int)

    # 唯一会话
    unique_sessions = set()

    # Content 统计
    messages_with_content = 0
    messages_without_content = 0

    # 扫描所有 JSONL 文件
    for jsonl_file in JSONL_ROOT.rglob('*.jsonl'):
        is_agent = 'agent-' in jsonl_file.name
        file_has_messages = False

        try:
            with open(jsonl_file) as f:
                for line in f:
                    try:
                        msg = json.loads(line.strip())

                        # 只统计 assistant 消息
                        if msg.get('type') != 'assistant':
                            continue

                        # 检查时间范围
                        ts_str = msg.get('timestamp', '')
                        if ts_str:
                            ts = parse_timestamp(ts_str)
                            if ts:
                                if start_dt and ts < start_dt:
                                    continue
                                if end_dt and ts > end_dt:
                                    continue
                            else:
                                continue  # 无法解析时间戳
                        else:
                            continue  # 没有时间戳

                        # 统计消息
                        total_messages += 1
                        file_has_messages = True

                        message_obj = msg.get('message', {})

                        # Session ID
                        session_id = msg.get('sessionId') or jsonl_file.stem
                        unique_sessions.add(session_id)

                        # Message ID
                        msg_id = message_obj.get('id')
                        if msg_id and (msg_id.startswith('msg_') or msg_id.startswith('resp_')):
                            messages_with_id += 1
                        else:
                            messages_without_id += 1

                        # Stop Reason
                        stop_reason = message_obj.get('stop_reason')
                        if stop_reason:
                            stop_reason_dist[stop_reason] += 1
                        else:
                            stop_reason_dist['空/NULL'] += 1

                        # Message Type
                        msg_type = message_obj.get('type', 'unknown')
                        message_type_dist[msg_type] += 1

                        # Content
                        content = message_obj.get('content', [])
                        if content:
                            messages_with_content += 1
                        else:
                            messages_without_content += 1

                    except json.JSONDecodeError:
                        pass
                    except Exception:
                        pass

            if file_has_messages:
                total_files += 1
                if is_agent:
                    agent_files += 1
                else:
                    main_session_files += 1

        except Exception:
            pass

    # 输出统计结果
    print(f"扫描的文件: {total_files:,}")
    print(f"├─ 主会话文件: {main_session_files:,}")
    print(f"└─ 子代理文件: {agent_files:,}")
    print()

    # 1. 总消息数
    print(f"总 assistant 消息数: {total_messages:,}")

    if total_messages == 0:
        print("\n❌ 没有找到任何消息")
        return 0

    # 2. Message ID 统计
    print(f"├─ 有 message_id: {messages_with_id:,} ({messages_with_id/total_messages*100:.1f}%)")
    print(f"└─ 无 message_id: {messages_without_id:,} ({messages_without_id/total_messages*100:.1f}%)")

    # 3. 唯一会话数
    print(f"\n唯一会话数: {len(unique_sessions):,}")

    # 4. Content 统计
    print(f"\nContent 统计:")
    print(f"├─ 有 content: {messages_with_content:,} ({messages_with_content/total_messages*100:.1f}%)")
    print(f"└─ 无 content: {messages_without_content:,} ({messages_without_content/total_messages*100:.1f}%)")

    # 5. Message Type 分布
    print(f"\nMessage Type 分布:")
    for msg_type, count in sorted(message_type_dist.items(), key=lambda x: -x[1]):
        pct = count / total_messages * 100
        print(f"├─ {msg_type}: {count:,} ({pct:.1f}%)")

    # 6. Stop Reason 分布
    print(f"\nStop Reason 分布:")
    for sr, count in sorted(stop_reason_dist.items(), key=lambda x: -x[1]):
        pct = count / total_messages * 100
        if sr == '空/NULL':
            print(f"├─ 空/NULL: {count:,} ({pct:.1f}%) ❌")
        else:
            print(f"├─ '{sr}': {count:,} ({pct:.1f}%)")

    # 统计有/无 stop_reason
    has_stop_reason = sum(count for sr, count in stop_reason_dist.items() if sr != '空/NULL')
    no_stop_reason = stop_reason_dist.get('空/NULL', 0)

    print(f"\n总结:")
    print(f"├─ 有 stop_reason: {has_stop_reason:,} ({has_stop_reason/total_messages*100:.1f}%)")
    print(f"└─ 无 stop_reason: {no_stop_reason:,} ({no_stop_reason/total_messages*100:.1f}%)")

    # 7. 验证
    print(f"\n" + "=" * 70)
    print("验证")
    print("=" * 70)
    verify_total = messages_with_id + messages_without_id
    print(f"{messages_with_id:,} + {messages_without_id:,} = {verify_total:,}")
    print(f"应该等于总数: {total_messages:,}")
    if verify_total == total_messages:
        print("✓ 总数一致")
    else:
        print("✗ 总数不一致")

    return 0

if __name__ == "__main__":
    exit(main())
