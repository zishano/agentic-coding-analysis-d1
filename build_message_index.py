#!/usr/bin/env python3
"""
Build Message ID Index

Creates a fast-lookup index mapping Anthropic message IDs to database request IDs.
This enables accurate conversation-to-request mapping.
"""

import sqlite3
import json
import sys
import argparse

def build_message_id_index(db_path='./requests.db', start_time=None, end_time=None):
    """Build index of message IDs from database"""

    print("Building message ID index...")
    print(f"Database: {db_path}")
    if start_time:
        print(f"Start time: {start_time}")
    if end_time:
        print(f"End time: {end_time}")
    print()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Build query with optional time filters
    where_clauses = ["response IS NOT NULL"]
    params = []

    if start_time:
        where_clauses.append("timestamp >= ?")
        params.append(start_time)
    if end_time:
        where_clauses.append("timestamp <= ?")
        params.append(end_time)

    where_sql = " AND ".join(where_clauses)

    # Get total count
    cursor.execute(f"SELECT COUNT(*) FROM requests WHERE {where_sql}", params)
    total = cursor.fetchone()[0]
    print(f"Total requests with responses: {total:,}")
    print()

    # Extract message IDs
    cursor.execute(f"SELECT id, response FROM requests WHERE {where_sql}", params)

    message_id_index = {}  # message_id -> db_request_id
    count = 0

    for req_id, response_json in cursor.fetchall():
        count += 1
        if count % 5000 == 0:
            print(f"  Progress: {count:,}/{total:,} ({count/total*100:.1f}%)")

        try:
            response = json.loads(response_json)

            if 'body' in response:
                resp_body = response['body']
                if isinstance(resp_body, str):
                    resp_body = json.loads(resp_body)

                msg_id = resp_body.get('id')
                # Accept both 'msg_' (message IDs) and 'resp_' (response IDs)
                if msg_id and (msg_id.startswith('msg_') or msg_id.startswith('resp_')):
                    message_id_index[msg_id] = req_id
        except:
            pass

    conn.close()

    print(f"  Complete!")
    print()
    print(f"Extracted {len(message_id_index):,} unique message IDs")

    # Save to file
    output_file = 'message_id_index.json'
    with open(output_file, 'w') as f:
        json.dump(message_id_index, f)

    print(f"Saved to: {output_file}")
    print()
    print(f"Coverage: {len(message_id_index)/total*100:.1f}% of requests have message IDs")

    return message_id_index

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Build message ID index from database')
    parser.add_argument('db_path', nargs='?', default='./requests.db',
                        help='Path to the requests database')
    parser.add_argument('--start-time', type=str, default=None,
                        help='Start time filter (e.g., "2026-09-07T17:00:00+08:00")')
    parser.add_argument('--end-time', type=str, default=None,
                        help='End time filter (e.g., "2026-09-07T18:00:00+08:00")')

    args = parser.parse_args()
    build_message_id_index(args.db_path, args.start_time, args.end_time)
