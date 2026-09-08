#!/usr/bin/env python3
"""
统计 requests.db 中指定时间段的请求数量
用法:
    python3 count_requests_by_time.py
    python3 count_requests_by_time.py --start "2026-08-27 00:00:00" --end "2026-08-27 23:59:59"
"""
import sqlite3
import argparse
from datetime import datetime
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description='统计指定时间段的请求数量')
    parser.add_argument('--db', type=str,
                        default='/mnt/nvme1n1/data/lmk/PROJECT/agentic-coding-analysis-d1/requests_20260828.db',
                        help='requests.db 的路径')
    parser.add_argument('--start', type=str, default='',
                        help='开始时间，格式: "YYYY-MM-DD HH:MM:SS"，留空=不限')
    parser.add_argument('--end', type=str, default='',
                        help='结束时间，格式: "YYYY-MM-DD HH:MM:SS"，留空=不限')
    parser.add_argument('--by-session', action='store_true',
                        help='按会话统计（显示每个会话的请求数）')
    parser.add_argument('--detail', action='store_true',
                        help='显示详细信息（时间范围、模型等）')
    parser.add_argument('--hourly', action='store_true',
                        help='按小时统计请求数量')
    return parser.parse_args()


def validate_time(time_str):
    """验证时间格式"""
    if not time_str:
        return None
    try:
        # 尝试解析，如果没有时区信息，自动添加 +08:00
        dt = datetime.fromisoformat(time_str.strip())
        # 如果没有时区信息，添加 +08:00
        if dt.tzinfo is None:
            time_str = time_str.strip() + "+08:00"
            dt = datetime.fromisoformat(time_str)
        return dt.isoformat()
    except ValueError:
        print(f"❌ 时间格式错误: {time_str}")
        print("   正确格式: YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DDTHH:MM:SS+08:00")
        return None


def get_db_info(cursor):
    """获取数据库基本信息"""
    # 检查表结构
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    # 获取请求表的列
    if 'requests' in tables:
        cursor.execute("PRAGMA table_info(requests)")
        columns = [row[1] for row in cursor.fetchall()]
        return tables, columns
    return tables, []


def count_requests(db_path, start_time=None, end_time=None, by_session=False, detail=False, hourly=False):
    """统计请求数量"""
    if not Path(db_path).exists():
        print(f"❌ 数据库文件不存在: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 获取数据库信息
    tables, columns = get_db_info(cursor)

    if 'requests' not in tables:
        print(f"❌ 数据库中没有 'requests' 表")
        print(f"   可用的表: {', '.join(tables)}")
        conn.close()
        return

    print(f"\n📊 数据库: {db_path}")
    print(f"   表: {', '.join(tables)}")
    print(f"   requests 表字段: {', '.join(columns)}")
    print("=" * 70)

    # 构建查询条件
    where_clauses = []
    params = []

    if start_time:
        where_clauses.append("timestamp >= ?")
        params.append(start_time)
        print(f"⏰ 开始时间: {start_time}")

    if end_time:
        where_clauses.append("timestamp <= ?")
        params.append(end_time)
        print(f"⏰ 结束时间: {end_time}")

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    # 总请求数
    query = f"SELECT COUNT(*) FROM requests {where_sql}"
    cursor.execute(query, params)
    total_count = cursor.fetchone()[0]

    print(f"\n✅ 总请求数: {total_count:,}")

    if total_count == 0:
        print("   (没有找到匹配的请求)")
        conn.close()
        return

    # 时间范围统计
    if detail or (not start_time and not end_time):
        query = f"SELECT MIN(timestamp), MAX(timestamp) FROM requests {where_sql}"
        cursor.execute(query, params)
        min_time, max_time = cursor.fetchone()
        if min_time and max_time:
            print(f"\n📅 实际时间范围:")
            print(f"   最早: {min_time}")
            print(f"   最晚: {max_time}")

    # 按小时统计
    if hourly:
        print(f"\n⏰ 按小时统计:")
        # 直接用 substr 提取小时部分（保留时区信息）
        query = f"""
            SELECT
                substr(timestamp, 1, 13) || ':00:00' || substr(timestamp, 20) as hour,
                COUNT(*) as count
            FROM requests {where_sql}
            GROUP BY substr(timestamp, 1, 13)
            ORDER BY hour
        """
        cursor.execute(query, params)
        rows = cursor.fetchall()

        if rows:
            print(f"   共 {len(rows)} 个小时有请求\n")
            total_in_hours = 0
            for hour, count in rows:
                total_in_hours += count
                # 计算每小时的占比
                pct = (count / total_count * 100) if total_count > 0 else 0
                bar_length = int(pct / 2)  # 每2%一个字符
                bar = '█' * bar_length
                print(f"   {hour} | {count:5,} 请求 ({pct:5.1f}%) {bar}")
        else:
            print("   (无数据)")

    # 按会话统计
    if by_session:
        print(f"\n📋 按会话统计:")
        if 'conversation_id' in columns:
            query = f"""
                SELECT conversation_id, COUNT(*) as count, MIN(timestamp), MAX(timestamp)
                FROM requests {where_sql}
                GROUP BY conversation_id
                ORDER BY count DESC
            """
            cursor.execute(query, params)
            rows = cursor.fetchall()
            print(f"   共 {len(rows)} 个会话\n")
            for i, (conv_id, count, min_t, max_t) in enumerate(rows, 1):
                conv_short = conv_id[:12] if conv_id else 'NULL'
                print(f"   {i:2d}. {conv_short}: {count:3d} 请求  ({min_t} ~ {max_t})")
        else:
            print("   ⚠️ 表中没有 conversation_id 字段")

    # 详细信息
    if detail:
        # 按模型统计
        if 'model' in columns:
            print(f"\n🤖 按模型统计:")
            query = f"""
                SELECT model, COUNT(*) as count
                FROM requests {where_sql}
                GROUP BY model
                ORDER BY count DESC
            """
            cursor.execute(query, params)
            for model, count in cursor.fetchall():
                print(f"   {model or 'NULL'}: {count:,} 请求")

        # 按流式/非流式统计
        if 'stream' in columns:
            print(f"\n📡 按请求类型统计:")
            query = f"""
                SELECT stream, COUNT(*) as count
                FROM requests {where_sql}
                GROUP BY stream
            """
            cursor.execute(query, params)
            for stream, count in cursor.fetchall():
                type_name = "流式" if stream else "非流式"
                print(f"   {type_name}: {count:,} 请求")

        # Token 统计
        token_cols = [c for c in columns if 'token' in c.lower()]
        if token_cols:
            print(f"\n💰 Token 统计:")
            for col in token_cols:
                query = f"SELECT SUM({col}), AVG({col}), MAX({col}) FROM requests {where_sql}"
                cursor.execute(query, params)
                total, avg, max_val = cursor.fetchone()
                if total is not None:
                    print(f"   {col}:")
                    print(f"      总计: {int(total):,}  平均: {int(avg):,}  最大: {int(max_val):,}")

    conn.close()
    print("\n" + "=" * 70)


def main():
    args = parse_args()

    # 验证时间格式
    start_time = validate_time(args.start) if args.start else None
    end_time = validate_time(args.end) if args.end else None

    if args.start and start_time is None:
        return
    if args.end and end_time is None:
        return

    # 如果没有指定任何选项，默认显示按小时统计
    hourly = args.hourly
    if not args.hourly and not args.by_session and not args.detail and not args.start and not args.end:
        hourly = True

    count_requests(
        db_path=args.db,
        start_time=start_time,
        end_time=end_time,
        by_session=args.by_session,
        detail=args.detail,
        hourly=hourly
    )


if __name__ == "__main__":
    main()
