#!/usr/bin/env python3
"""
导出指定时间段的请求到新的数据库文件
==========================================
从大型 requests.db 中提取特定时间段的数据，创建一个小的独立数据库

用法:
    # 按时间范围导出
    python3 export_db_timerange.py source.db output.db \\
        --start-time "2026-08-28 00:00:00" \\
        --end-time "2026-08-28 23:59:59"

    # 只导出有响应的请求
    python3 export_db_timerange.py source.db output.db \\
        --start-time "2026-08-28 00:00:00" \\
        --end-time "2026-08-28 23:59:59" \\
        --only-with-response

    # 导出最近 N 条记录
    python3 export_db_timerange.py source.db output.db --last 1000
"""
import sqlite3
import sys
import os
import argparse
from datetime import datetime


def copy_schema(src_conn, dst_conn):
    """复制源数据库的表结构（自动适配所有字段和索引）"""
    src_cursor = src_conn.cursor()
    dst_cursor = dst_conn.cursor()

    # 1. 复制表结构
    src_cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='requests'")
    result = src_cursor.fetchone()

    if result and result[0]:
        # 使用源表的完整定义
        dst_cursor.execute(result[0])
        print("   ✓ 表结构复制完成")
    else:
        raise RuntimeError("源数据库中没有 requests 表")

    # 2. 复制所有索引（如果存在）
    src_cursor.execute("""
        SELECT sql FROM sqlite_master
        WHERE type='index' AND tbl_name='requests' AND sql IS NOT NULL
    """)
    indexes = src_cursor.fetchall()

    for (index_sql,) in indexes:
        try:
            dst_cursor.execute(index_sql)
            print(f"   ✓ 索引复制完成")
        except sqlite3.OperationalError as e:
            # 索引可能已存在或有冲突，忽略
            print(f"   ⚠️ 索引创建跳过: {e}")

    dst_conn.commit()


def export_by_timerange(source_db, output_db, start_time, end_time, only_with_response=False):
    """按时间范围导出"""
    print(f"\n📦 导出时间范围: {start_time} ~ {end_time}")

    # 连接源数据库
    src_conn = sqlite3.connect(source_db)
    src_cursor = src_conn.cursor()

    # 构建查询
    query = "SELECT * FROM requests WHERE timestamp >= ? AND timestamp <= ?"
    params = [start_time, end_time]

    if only_with_response:
        query += " AND response IS NOT NULL"

    query += " ORDER BY timestamp"

    print("正在查询源数据库...")
    src_cursor.execute(query, params)
    rows = src_cursor.fetchall()

    if not rows:
        print("❌ 未找到匹配的记录")
        src_conn.close()
        return 0

    print(f"✓ 找到 {len(rows):,} 条记录")

    # 获取列名
    columns = [desc[0] for desc in src_cursor.description]

    # 创建输出数据库
    if os.path.exists(output_db):
        print(f"⚠️ 输出文件已存在，将被覆盖: {output_db}")
        os.remove(output_db)

    dst_conn = sqlite3.connect(output_db)
    dst_cursor = dst_conn.cursor()

    print("正在创建表结构...")
    copy_schema(src_conn, dst_conn)

    # 批量插入
    print("正在插入数据...")
    placeholders = ",".join(["?" for _ in columns])
    insert_query = f"INSERT INTO requests ({','.join(columns)}) VALUES ({placeholders})"

    batch_size = 1000
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        dst_cursor.executemany(insert_query, batch)
        dst_conn.commit()
        print(f"  已插入 {min(i+batch_size, len(rows)):,} / {len(rows):,} 条")

    dst_conn.commit()

    # 统计
    dst_cursor.execute("SELECT COUNT(*) FROM requests")
    total = dst_cursor.fetchone()[0]

    dst_cursor.execute("SELECT COUNT(*) FROM requests WHERE response IS NOT NULL")
    with_response = dst_cursor.fetchone()[0]

    # 清理
    src_conn.close()
    dst_conn.close()

    # 文件大小
    file_size = os.path.getsize(output_db) / (1024**2)

    print(f"\n✅ 导出完成")
    print(f"   输出文件: {output_db}")
    print(f"   文件大小: {file_size:.2f} MB")
    print(f"   总记录数: {total:,}")
    print(f"   有响应的: {with_response:,}")

    return total


def export_last_n(source_db, output_db, n, only_with_response=False):
    """导出最近 N 条记录"""
    print(f"\n📦 导出最近 {n:,} 条记录")

    src_conn = sqlite3.connect(source_db)
    src_cursor = src_conn.cursor()

    # 构建查询
    query = "SELECT * FROM requests"
    if only_with_response:
        query += " WHERE response IS NOT NULL"
    query += " ORDER BY timestamp DESC LIMIT ?"

    print("正在查询源数据库...")
    src_cursor.execute(query, (n,))
    rows = src_cursor.fetchall()

    if not rows:
        print("❌ 未找到记录")
        src_conn.close()
        return 0

    print(f"✓ 找到 {len(rows):,} 条记录")

    # 获取列名
    columns = [desc[0] for desc in src_cursor.description]

    # 创建输出数据库
    if os.path.exists(output_db):
        print(f"⚠️ 输出文件已存在，将被覆盖: {output_db}")
        os.remove(output_db)

    dst_conn = sqlite3.connect(output_db)
    dst_cursor = dst_conn.cursor()

    print("正在创建表结构...")
    copy_schema(src_conn, dst_conn)

    # 批量插入（恢复时间顺序）
    print("正在插入数据...")
    rows.reverse()  # 恢复时间正序

    placeholders = ",".join(["?" for _ in columns])
    insert_query = f"INSERT INTO requests ({','.join(columns)}) VALUES ({placeholders})"

    batch_size = 1000
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        dst_cursor.executemany(insert_query, batch)
        dst_conn.commit()
        print(f"  已插入 {min(i+batch_size, len(rows)):,} / {len(rows):,} 条")

    dst_conn.commit()

    # 统计
    dst_cursor.execute("SELECT COUNT(*) FROM requests")
    total = dst_cursor.fetchone()[0]

    dst_cursor.execute("SELECT COUNT(*) FROM requests WHERE response IS NOT NULL")
    with_response = dst_cursor.fetchone()[0]

    # 时间范围
    dst_cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM requests")
    min_ts, max_ts = dst_cursor.fetchone()

    # 清理
    src_conn.close()
    dst_conn.close()

    # 文件大小
    file_size = os.path.getsize(output_db) / (1024**2)

    print(f"\n✅ 导出完成")
    print(f"   输出文件: {output_db}")
    print(f"   文件大小: {file_size:.2f} MB")
    print(f"   总记录数: {total:,}")
    print(f"   有响应的: {with_response:,}")
    print(f"   时间范围: {min_ts} ~ {max_ts}")

    return total


def export_by_conversation(source_db, output_db, conversation_id):
    """导出指定会话的所有请求"""
    print(f"\n📦 导出会话: {conversation_id}")

    src_conn = sqlite3.connect(source_db)
    src_cursor = src_conn.cursor()

    query = "SELECT * FROM requests WHERE conversation_id = ? ORDER BY timestamp"

    print("正在查询源数据库...")
    src_cursor.execute(query, (conversation_id,))
    rows = src_cursor.fetchall()

    if not rows:
        print("❌ 未找到匹配的会话")
        src_conn.close()
        return 0

    print(f"✓ 找到 {len(rows):,} 条记录")

    # 获取列名
    columns = [desc[0] for desc in src_cursor.description]

    # 创建输出数据库
    if os.path.exists(output_db):
        print(f"⚠️ 输出文件已存在，将被覆盖: {output_db}")
        os.remove(output_db)

    dst_conn = sqlite3.connect(output_db)
    dst_cursor = dst_conn.cursor()

    print("正在创建表结构...")
    copy_schema(src_conn, dst_conn)

    # 插入数据
    print("正在插入数据...")
    placeholders = ",".join(["?" for _ in columns])
    insert_query = f"INSERT INTO requests ({','.join(columns)}) VALUES ({placeholders})"
    dst_cursor.executemany(insert_query, rows)
    dst_conn.commit()

    # 清理
    src_conn.close()
    dst_conn.close()

    # 文件大小
    file_size = os.path.getsize(output_db) / (1024**2)

    print(f"\n✅ 导出完成")
    print(f"   输出文件: {output_db}")
    print(f"   文件大小: {file_size:.2f} MB")
    print(f"   记录数: {len(rows):,}")

    return len(rows)


def main():
    parser = argparse.ArgumentParser(
        description="导出指定时间段的请求到新数据库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 导出指定时间范围
  %(prog)s source.db output.db --start-time "2026-08-28 00:00:00" --end-time "2026-08-28 23:59:59"

  # 只导出有响应的请求
  %(prog)s source.db output.db --start-time "2026-08-28 00:00:00" --end-time "2026-08-28 23:59:59" --only-with-response

  # 导出最近 1000 条记录
  %(prog)s source.db output.db --last 1000

  # 导出指定会话
  %(prog)s source.db output.db --conversation-id abc123
        """
    )

    parser.add_argument("source_db", help="源数据库文件路径")
    parser.add_argument("output_db", help="输出数据库文件路径")

    # 时间范围
    parser.add_argument("--start-time", help="开始时间 (YYYY-MM-DD HH:MM:SS)")
    parser.add_argument("--end-time", help="结束时间 (YYYY-MM-DD HH:MM:SS)")

    # 最近 N 条
    parser.add_argument("--last", type=int, metavar="N", help="导出最近 N 条记录")

    # 会话 ID
    parser.add_argument("--conversation-id", help="导出指定会话的所有请求")

    # 过滤
    parser.add_argument("--only-with-response", action="store_true",
                        help="只导出有响应的请求")

    args = parser.parse_args()

    # 检查源数据库
    if not os.path.exists(args.source_db):
        print(f"❌ 源数据库不存在: {args.source_db}")
        sys.exit(1)

    print("=" * 70)
    print("📂 导出请求数据库")
    print("=" * 70)
    print(f"\n源数据库: {args.source_db}")
    print(f"输出文件: {args.output_db}")

    # 根据参数选择导出方式
    if args.conversation_id:
        count = export_by_conversation(args.source_db, args.output_db, args.conversation_id)
    elif args.last:
        count = export_last_n(args.source_db, args.output_db, args.last, args.only_with_response)
    elif args.start_time and args.end_time:
        count = export_by_timerange(args.source_db, args.output_db,
                                     args.start_time, args.end_time,
                                     args.only_with_response)
    else:
        print("\n❌ 必须指定以下参数之一:")
        print("   --start-time + --end-time (时间范围)")
        print("   --last N (最近 N 条)")
        print("   --conversation-id (会话 ID)")
        sys.exit(1)

    if count > 0:
        print("\n" + "=" * 70)
        print("✅ 导出成功！")
        print("=" * 70)
        print(f"\n💡 使用导出的数据库:")
        print(f"   python3 analyze_db_quick.py {args.output_db}")
        print(f"   python3 build_minimal_traces.py {args.output_db} ...")
    else:
        print("\n⚠️ 未导出任何记录")


if __name__ == "__main__":
    main()
