#!/usr/bin/env python3
"""
完整验证请求分类的脚本
直接从数据库查询，输出清晰的分类树
"""

import sqlite3
import json
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description='验证请求分类')
    parser.add_argument('--db', type=str, default='tmp/exported_requests.db',
                        help='数据库路径 (默认: tmp/exported_requests.db)')
    parser.add_argument('--start', type=str, default=None,
                        help='开始时间 (格式: YYYY-MM-DDTHH:MM:SS+08:00, 默认: 不限)')
    parser.add_argument('--end', type=str, default=None,
                        help='结束时间 (格式: YYYY-MM-DDTHH:MM:SS+08:00, 默认: 不限)')
    return parser.parse_args()

def main():
    args = parse_args()

    DB_PATH = args.db
    START_TIME = args.start
    END_TIME = args.end

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("=" * 70)
    print("请求分类完整验证")
    print("=" * 70)

    # 构建WHERE子句和参数
    if START_TIME and END_TIME:
        where_clause = "WHERE timestamp >= ? AND timestamp <= ?"
        params = (START_TIME, END_TIME)
        print(f"时间范围: {START_TIME} ~ {END_TIME}")
    elif START_TIME:
        where_clause = "WHERE timestamp >= ?"
        params = (START_TIME,)
        print(f"时间范围: {START_TIME} ~ (不限)")
    elif END_TIME:
        where_clause = "WHERE timestamp <= ?"
        params = (END_TIME,)
        print(f"时间范围: (不限) ~ {END_TIME}")
    else:
        where_clause = ""
        params = ()
        print(f"时间范围: 全部数据")
    print()

    # 1. 总请求数
    query_total = f"SELECT COUNT(*) FROM requests {where_clause}"
    cursor.execute(query_total, params)
    total = cursor.fetchone()[0]
    print(f"总请求数: {total:,}")

    # 2. 无响应
    query_no_response = f"""
    SELECT COUNT(*) FROM requests
    {where_clause}
    {'AND' if where_clause else 'WHERE'} (response IS NULL OR response = '' OR response = '{{}}')
    """
    cursor.execute(query_no_response, params)
    no_response = cursor.fetchone()[0]
    print(f"├─ 无响应: {no_response:,} ❌")

    has_response = total - no_response
    print(f"└─ 有响应: {has_response:,} ✅")

    # 3. 流式响应分类
    print(f"\n   ├─ isStreaming = true:")

    query_streaming = f"""
    SELECT
        CASE
            WHEN json_extract(response, '$.body') IS NOT NULL
                 AND json_extract(response, '$.body.id') IS NOT NULL THEN 'has_body_has_id'
            WHEN json_extract(response, '$.body') IS NOT NULL
                 AND json_extract(response, '$.body.id') IS NULL THEN 'has_body_no_id'
            ELSE 'no_body'
        END as category,
        COUNT(*) as count
    FROM requests
    {where_clause}
    {'AND' if where_clause else 'WHERE'} json_extract(response, '$.isStreaming') = 1
    GROUP BY category
    """
    cursor.execute(query_streaming, params)
    streaming_data = {}
    for category, count in cursor.fetchall():
        streaming_data[category] = count

    streaming_total = sum(streaming_data.values())
    print(f"   │  总计: {streaming_total:,}")
    print(f"   │  ├─ 有body+有msg_id: {streaming_data.get('has_body_has_id', 0):,} ✅")
    print(f"   │  ├─ 有body+无msg_id: {streaming_data.get('has_body_no_id', 0):,}")
    print(f"   │  └─ 无body: {streaming_data.get('no_body', 0):,} ❌")

    # 流式无body的错误码
    query_streaming_errors = f"""
    SELECT
        json_extract(response, '$.statusCode') as status_code,
        COUNT(*) as count
    FROM requests
    {where_clause}
    {'AND' if where_clause else 'WHERE'} json_extract(response, '$.isStreaming') = 1
      AND json_extract(response, '$.body') IS NULL
    GROUP BY status_code
    ORDER BY count DESC
    """
    cursor.execute(query_streaming_errors, params)
    print(f"   │      └─ 错误码分布:")
    for status, count in cursor.fetchall():
        print(f"   │         ├─ {status}: {count:,}")

    # 4. 非流式响应分类
    print(f"   │")
    print(f"   └─ isStreaming = false:")

    query_non_streaming = f"""
    SELECT
        CASE
            WHEN json_extract(response, '$.body') IS NOT NULL
                 AND json_extract(response, '$.body.id') IS NOT NULL THEN 'has_body_has_id'
            WHEN json_extract(response, '$.body') IS NOT NULL
                 AND json_extract(response, '$.body.id') IS NULL THEN 'has_body_no_id'
            ELSE 'no_body'
        END as category,
        COUNT(*) as count
    FROM requests
    {where_clause}
    {'AND' if where_clause else 'WHERE'} json_extract(response, '$.isStreaming') = 0
    GROUP BY category
    """
    cursor.execute(query_non_streaming, params)
    non_streaming_data = {}
    for category, count in cursor.fetchall():
        non_streaming_data[category] = count

    non_streaming_total = sum(non_streaming_data.values())
    print(f"      总计: {non_streaming_total:,}")
    print(f"      ├─ 有body+有msg_id: {non_streaming_data.get('has_body_has_id', 0):,} ✅")
    print(f"      ├─ 有body+无msg_id: {non_streaming_data.get('has_body_no_id', 0):,} ⚠️")
    print(f"      └─ 无body: {non_streaming_data.get('no_body', 0):,} ❌")

    # 非流式无body的错误码
    query_non_streaming_errors = f"""
    SELECT
        json_extract(response, '$.statusCode') as status_code,
        COUNT(*) as count
    FROM requests
    {where_clause}
    {'AND' if where_clause else 'WHERE'} json_extract(response, '$.isStreaming') = 0
      AND json_extract(response, '$.body') IS NULL
    GROUP BY status_code
    ORDER BY count DESC
    """
    cursor.execute(query_non_streaming_errors, params)
    print(f"          └─ 错误码分布:")
    for status, count in cursor.fetchall():
        print(f"             ├─ {status}: {count:,}")

    # 5. 输出清晰的树状图


    # 6. 总结统计
    print()
    print("=" * 70)
    print("总结统计")
    print("=" * 70)

    # message_id总数
    query_msg_ids = f"""
    SELECT COUNT(DISTINCT json_extract(response, '$.body.id'))
    FROM requests
    {where_clause}
    {'AND' if where_clause else 'WHERE'} json_extract(response, '$.body.id') IS NOT NULL
    """
    cursor.execute(query_msg_ids, params)
    total_msg_ids = cursor.fetchone()[0]

    streaming_msg_ids = streaming_data.get('has_body_has_id', 0)
    non_streaming_msg_ids = non_streaming_data.get('has_body_has_id', 0)

    print(f"有message_id: {total_msg_ids:,}")
    print(f"  ├─ 流式: {streaming_msg_ids:,}")
    print(f"  └─ 非流式: {non_streaming_msg_ids:,}")

    # 分析有message_id的响应完整性
    query_incomplete = f"""
    SELECT
        CASE
            WHEN json_extract(response, '$.isStreaming') = 1 THEN 'streaming'
            ELSE 'non_streaming'
        END as type,
        CASE
            WHEN json_extract(response, '$.body.stop_reason') IS NULL
                 OR json_extract(response, '$.body.stop_reason') = '' THEN 'incomplete'
            ELSE 'complete'
        END as completeness,
        COUNT(*) as count
    FROM requests
    {where_clause}
    {'AND' if where_clause else 'WHERE'} json_extract(response, '$.body.id') IS NOT NULL
    GROUP BY type, completeness
    """
    cursor.execute(query_incomplete, params)

    completeness_data = {}
    for type_, completeness, count in cursor.fetchall():
        completeness_data[(type_, completeness)] = count

    complete_total = completeness_data.get(('streaming', 'complete'), 0) + completeness_data.get(('non_streaming', 'complete'), 0)
    incomplete_total = completeness_data.get(('streaming', 'incomplete'), 0) + completeness_data.get(('non_streaming', 'incomplete'), 0)

    print(f"\n响应完整性分析:")
    print(f"  ├─ 完整响应 (有stop_reason): {complete_total:,} ({complete_total/total_msg_ids*100:.1f}%) ✅")
    print(f"  │   ├─ 流式: {completeness_data.get(('streaming', 'complete'), 0):,}")
    print(f"  │   └─ 非流式: {completeness_data.get(('non_streaming', 'complete'), 0):,}")
    print(f"  │")
    print(f"  └─ 不完整响应 (stop_reason为空): {incomplete_total:,} ({incomplete_total/total_msg_ids*100:.1f}%) ❌")
    print(f"      ├─ 流式: {completeness_data.get(('streaming', 'incomplete'), 0):,}")
    print(f"      └─ 非流式: {completeness_data.get(('non_streaming', 'incomplete'), 0):,}")

    # 错误总数
    query_all_errors = f"""
    SELECT
        json_extract(response, '$.statusCode') as status_code,
        COUNT(*) as count
    FROM requests
    {where_clause}
    {'AND' if where_clause else 'WHERE'} json_extract(response, '$.statusCode') != 200
    GROUP BY status_code
    ORDER BY count DESC
    """
    cursor.execute(query_all_errors, params)
    errors = cursor.fetchall()
    total_errors = sum(count for _, count in errors)

    print(f"\n错误响应总数: {total_errors:,} ({total_errors/total*100:.1f}%)")
    for status, count in errors:
        print(f"  ├─ {status}: {count:,} ({count/total_errors*100:.1f}%)")

    # 验证总数
    print()
    print("=" * 70)
    print("验证")
    print("=" * 70)
    calculated = no_response + streaming_total + non_streaming_total
    print(f"{no_response:,} + {streaming_total:,} + {non_streaming_total:,} = {calculated:,}")
    print(f"应该等于总数: {total:,}")
    if calculated == total:
        print("✓ 总数一致")
    else:
        print(f"✗ 总数不一致！差异: {total - calculated}")

    conn.close()

if __name__ == "__main__":
    main()
