# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
分析 requests.db 的时间分布
============================
帮助确定合适的时间窗口过滤参数

用法:
    python3 analyze_db_timeline.py /path/to/requests.db
    python3 analyze_db_timeline.py /path/to/requests.db --detailed
    python3 analyze_db_timeline.py /path/to/requests.db --by-hour
"""
import sqlite3
import sys
import argparse
from datetime import datetime, timedelta
from collections import defaultdict


def parse_timestamp(ts_str):
    """解析时间戳（兼容多种格式）"""
    if not ts_str:
        return None
    try:
        # ISO 格式，可能带时区
        return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
    except:
        try:
            # 简单格式
            return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        except:
            return None


def format_dt(dt):
    """格式化时间"""
    if dt.tzinfo:
        return dt.strftime("%Y-%m-%d %H:%M:%S %z")
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def analyze_basic(db_path):
    """基础分析：总体统计"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("=" * 70)
    print("📊 数据库基础统计")
    print("=" * 70)

    # 文件大小
    import os
    file_size = os.path.getsize(db_path) / (1024**3)
    print(f"\n数据库大小: {file_size:.2f} GB")

    # 总请求数
    cursor.execute("SELECT COUNT(*) FROM requests")
    total = cursor.fetchone()[0]
    print(f"总请求数: {total:,}")

    # 有响应的请求数
    cursor.execute("SELECT COUNT(*) FROM requests WHERE response IS NOT NULL")
    with_response = cursor.fetchone()[0]
    print(f"有响应的: {with_response:,} ({with_response/total*100:.1f}%)")

    # 时间范围
    cursor.execute("""
        SELECT MIN(timestamp), MAX(timestamp)
        FROM requests
        WHERE timestamp IS NOT NULL
    """)
    min_ts, max_ts = cursor.fetchone()

    if min_ts and max_ts:
        min_dt = parse_timestamp(min_ts)
        max_dt = parse_timestamp(max_ts)
        if min_dt and max_dt:
            duration = max_dt - min_dt
            print(f"\n时间范围:")
            print(f"  最早: {format_dt(min_dt)}")
            print(f"  最晚: {format_dt(max_dt)}")
            print(f"  跨度: {duration.days} 天 {duration.seconds//3600} 小时 {(duration.seconds%3600)//60} 分钟")

    conn.close()


def analyze_by_day(db_path):
    """按天统计"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("\n" + "=" * 70)
    print("📅 按天统计")
    print("=" * 70)

    cursor.execute("""
        SELECT timestamp
        FROM requests
        WHERE timestamp IS NOT NULL
        ORDER BY timestamp
    """)

    day_counts = defaultdict(int)
    day_with_response = defaultdict(int)

    for (ts_str,) in cursor.fetchall():
        dt = parse_timestamp(ts_str)
        if dt:
            day = dt.strftime("%Y-%m-%d")
            day_counts[day] += 1

    # 有响应的按天
    cursor.execute("""
        SELECT timestamp
        FROM requests
        WHERE timestamp IS NOT NULL AND response IS NOT NULL
        ORDER BY timestamp
    """)

    for (ts_str,) in cursor.fetchall():
        dt = parse_timestamp(ts_str)
        if dt:
            day = dt.strftime("%Y-%m-%d")
            day_with_response[day] += 1

    print(f"\n{'日期':<12} {'总请求':>10} {'有响应':>10} {'响应率':>8}")
    print("-" * 45)

    for day in sorted(day_counts.keys()):
        total = day_counts[day]
        with_resp = day_with_response.get(day, 0)
        rate = with_resp / total * 100 if total > 0 else 0
        print(f"{day:<12} {total:>10,} {with_resp:>10,} {rate:>7.1f}%")

    conn.close()


def analyze_by_hour(db_path):
    """按小时统计"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("\n" + "=" * 70)
    print("🕐 按小时统计（最近 7 天）")
    print("=" * 70)

    cursor.execute("""
        SELECT timestamp
        FROM requests
        WHERE timestamp IS NOT NULL AND response IS NOT NULL
        ORDER BY timestamp DESC
    """)

    hour_counts = defaultdict(int)
    rows = cursor.fetchall()

    if not rows:
        print("没有数据")
        conn.close()
        return

    # 只分析最近 7 天
    latest_dt = parse_timestamp(rows[0][0])
    if not latest_dt:
        print("无法解析时间戳")
        conn.close()
        return

    cutoff = latest_dt - timedelta(days=7)

    for (ts_str,) in rows:
        dt = parse_timestamp(ts_str)
        if dt and dt >= cutoff:
            hour_key = dt.strftime("%Y-%m-%d %H:00")
            hour_counts[hour_key] += 1

    print(f"\n{'时间（小时）':<20} {'请求数':>10} {'柱状图'}")
    print("-" * 60)

    for hour in sorted(hour_counts.keys()):
        count = hour_counts[hour]
        bar = "█" * min(count, 50)  # 最多显示 50 个字符
        print(f"{hour:<20} {count:>10,} {bar}")

    conn.close()


def analyze_detailed(db_path):
    """详细分析：找出集中的时间段"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("\n" + "=" * 70)
    print("🔍 时间段分析（有响应的请求）")
    print("=" * 70)

    cursor.execute("""
        SELECT timestamp
        FROM requests
        WHERE timestamp IS NOT NULL AND response IS NOT NULL
        ORDER BY timestamp
    """)

    timestamps = []
    for (ts_str,) in cursor.fetchall():
        dt = parse_timestamp(ts_str)
        if dt:
            timestamps.append(dt)

    if not timestamps:
        print("没有数据")
        conn.close()
        return

    # 找出间隔超过 1 小时的断点
    print("\n找到的会话时间段（间隔 > 1 小时）：\n")

    segments = []
    current_start = timestamps[0]
    current_end = timestamps[0]
    current_count = 1

    for i in range(1, len(timestamps)):
        gap = (timestamps[i] - timestamps[i-1]).total_seconds()

        if gap > 3600:  # 1 小时
            # 记录当前段
            segments.append((current_start, current_end, current_count))

            # 开始新段
            current_start = timestamps[i]
            current_end = timestamps[i]
            current_count = 1
        else:
            current_end = timestamps[i]
            current_count += 1

    # 最后一段
    segments.append((current_start, current_end, current_count))

    print(f"{'#':<4} {'开始时间':<25} {'结束时间':<25} {'请求数':>8} {'时长'}")
    print("-" * 85)

    for idx, (start, end, count) in enumerate(segments, 1):
        duration = end - start
        hours = duration.total_seconds() / 3600
        print(f"{idx:<4} {format_dt(start):<25} {format_dt(end):<25} {count:>8,} {hours:>6.1f}h")

    # 推荐时间窗口
    print("\n💡 推荐时间窗口（覆盖最多请求的段）：")
    print("-" * 70)

    # 按请求数排序
    sorted_segments = sorted(segments, key=lambda x: x[2], reverse=True)

    for idx, (start, end, count) in enumerate(sorted_segments[:5], 1):
        # 加 30 分钟余量
        start_with_margin = start - timedelta(minutes=30)
        end_with_margin = end + timedelta(minutes=30)

        print(f"\n段 {idx}（{count:,} 个请求）:")
        print(f'  --start-time "{start_with_margin.strftime("%Y-%m-%d %H:%M:%S")}"')
        print(f'  --end-time   "{end_with_margin.strftime("%Y-%m-%d %H:%M:%S")}"')

    conn.close()


def main():
    parser = argparse.ArgumentParser(description="分析 requests.db 的时间分布")
    parser.add_argument("db", help="requests.db 路径")
    parser.add_argument("--detailed", action="store_true", help="详细分析（找出时间段）")
    parser.add_argument("--by-hour", action="store_true", help="按小时统计")
    parser.add_argument("--by-day", action="store_true", help="按天统计")
    args = parser.parse_args()

    if not args.db:
        print("用法: python3 analyze_db_timeline.py <requests.db>")
        sys.exit(1)

    # 基础分析（总是执行）
    analyze_basic(args.db)

    # 按天统计
    if args.by_day or not (args.detailed or args.by_hour):
        analyze_by_day(args.db)

    # 按小时统计
    if args.by_hour:
        analyze_by_hour(args.db)

    # 详细分析
    if args.detailed:
        analyze_detailed(args.db)

    print("\n" + "=" * 70)
    print("✅ 分析完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
