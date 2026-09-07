#!/usr/bin/env python3
"""
数据库时间戳格式诊断工具
帮助调试时间范围查询问题
"""
import sqlite3
import sys

def diagnose_timestamps(db_path):
    """诊断数据库中的时间戳格式"""
    print("=" * 70)
    print("🔍 时间戳格式诊断")
    print("=" * 70)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. 采样时间戳
    print("\n1️⃣ 时间戳格式采样（前 10 条）:")
    cursor.execute("SELECT timestamp FROM requests WHERE timestamp IS NOT NULL LIMIT 10")
    for idx, (ts,) in enumerate(cursor.fetchall(), 1):
        print(f"   {idx:2d}. {ts!r}")

    # 2. 检查是否有时区
    cursor.execute("SELECT timestamp FROM requests WHERE timestamp IS NOT NULL LIMIT 1")
    sample_ts = cursor.fetchone()[0]
    has_timezone = '+' in sample_ts or 'Z' in sample_ts

    print(f"\n2️⃣ 时区检测:")
    print(f"   样本: {sample_ts!r}")
    print(f"   是否带时区: {'✓ 是' if has_timezone else '✗ 否'}")

    # 3. 测试不同的查询方式
    test_time = "2026-09-03 16:30:00"

    print(f"\n3️⃣ 查询测试（查找 {test_time} 附近的记录）:")

    # 方法1: 精确匹配
    cursor.execute("""
        SELECT COUNT(*) FROM requests
        WHERE timestamp >= ? AND timestamp <= ?
    """, (test_time, "2026-09-03 17:00:00"))
    count1 = cursor.fetchone()[0]
    print(f"   方法1（精确匹配）: {count1:,} 条")

    # 方法2: LIKE 模糊匹配
    cursor.execute("""
        SELECT COUNT(*) FROM requests
        WHERE timestamp LIKE '2026-09-03 16:%'
    """)
    count2 = cursor.fetchone()[0]
    print(f"   方法2（LIKE 模糊）: {count2:,} 条")

    # 方法3: 带时区
    if has_timezone:
        cursor.execute("""
            SELECT COUNT(*) FROM requests
            WHERE timestamp >= ? AND timestamp <= ?
        """, (test_time + " +0800", "2026-09-03 17:00:00 +0800"))
        count3 = cursor.fetchone()[0]
        print(f"   方法3（带时区）: {count3:,} 条")

    # 4. 给出建议
    print(f"\n4️⃣ 导出建议:")

    if has_timezone:
        print("   ✓ 数据库时间戳带时区")
        print("   ✓ 建议导出时也带上时区:")
        print(f'     --start-time "2026-09-03 16:00:00 +0800"')
        print(f'     --end-time   "2026-09-03 18:00:00 +0800"')
    else:
        print("   ✓ 数据库时间戳不带时区")
        print("   ✓ 建议直接使用无时区格式:")
        print(f'     --start-time "2026-09-03 16:00:00"')
        print(f'     --end-time   "2026-09-03 18:00:00"')

    # 5. 推荐具体的导出命令
    cursor.execute("""
        SELECT MIN(timestamp), MAX(timestamp)
        FROM requests
        WHERE timestamp LIKE '2026-09-03%'
    """)
    min_ts, max_ts = cursor.fetchone()

    if min_ts and max_ts:
        print(f"\n5️⃣ 2026-09-03 当天的数据:")
        print(f"   最早: {min_ts}")
        print(f"   最晚: {max_ts}")

        cursor.execute("""
            SELECT COUNT(*) FROM requests
            WHERE timestamp LIKE '2026-09-03%'
        """)
        count_day = cursor.fetchone()[0]
        print(f"   总数: {count_day:,} 条")

        print(f"\n   💡 推荐导出命令:")
        print(f'   python3 export_db_timerange.py \\')
        print(f'     {db_path} \\')
        print(f'     output.db \\')
        print(f'     --start-time "{min_ts}" \\')
        print(f'     --end-time "{max_ts}"')

    conn.close()

    print("\n" + "=" * 70)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 diagnose_timestamps.py <requests.db>")
        sys.exit(1)

    diagnose_timestamps(sys.argv[1])
