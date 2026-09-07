#!/usr/bin/env python3
"""
retime_traces_global.py —— 把已生成的 trace 文件的 t 重标记为【全局连续时间轴】
=============================================================================
作用：
    原 build_minimal_traces.py 生成的每个 trace 里，t 都从 0 开始（各会话独立）。
    本脚本不改动任何生成逻辑，只对【已经生成好的 trace 文件】做后处理：
    根据 requests.db 和本地 JSONL 会话里的真实时间，把这批 trace 的 t 统一到
    一条连续时间轴上 —— 最早开始的会话 t 从 0 起，后面的会话 t 是相对最早
    会话开始时间的绝对秒数（而非各自从 0 重启）。

用法：
    # 只重标 t(结果写入 <目录>_global/ 新文件夹, 文件名不变, 不覆盖原文件)
    python3 retime_traces_global.py <trace目录>

    # 重标 t 后, 再把 <目录>_global/*.json 合并成一个 merged.jsonl
    # (一行一条 trace, 按每个 trace 起始 t 排序)
    python3 retime_traces_global.py <trace目录> --merge

    # 不重标, 只把已有 <目录>_global/*.json 合并成 merged.jsonl
    python3 retime_traces_global.py <trace目录> --merge-only

    # trace目录 = 存放 *.json trace 的目标目录(必填, 终端传入)
    # 其余参数在下方 CONFIG 区定义(DB / JSONL_ROOT / 时间过滤 / DRY_RUN)
    # 运行时会打印每个会话的启动时间

规则：
    - 每个父 trace 用一个常量 offset = (该父会话 db 最早请求时间 - 全局最早请求时间)
      加到所有顶层请求(含 subagent 条目)的 t 上。
    - 每个 subagent 条目内部 requests 用 offset_sub = (该子代理 db 最早请求时间 - 全局最早)。
    - 全局最早 = 这批 trace 里所有父会话(含子代理) db 请求的最早时间。
"""
import os, sys, sqlite3, json, glob
from pathlib import Path
from datetime import datetime, timezone

# ============================================================
# *** CONFIG: 你要改的参数 ***
# ============================================================
DB          = "/mnt/nvme1n1/data/lmk/PROJECT/agentic-coding-analysis-d1/requests_20260828.db"   # requests.db 路径
# TRACES_DIR 不再写死: 由终端命令行参数传入
JSONL_ROOT  = "/mnt/nvme1n1/data/lmk/PROJECT/agentic-coding-analysis-d1/projects"    # 本地 JSONL 根目录(自动按其下找会话)

# 可选: 与生成 trace 时一致的 db 时间过滤(留空=不过滤)。
#   格式 "YYYY-MM-DD HH:MM:SS" 或带时区 "YYYY-MM-DDTHH:MM:SS+08:00"。
DB_START_TIME = "2026-08-28 11:00:00"        # 例: "2026-08-28 14:25:00"
DB_END_TIME   = ""        # 例: "2026-08-28 14:40:00"

# 运行模式
DRY_RUN  = False     # True=只打印将怎样改, 不写文件; False=真正写入
# 输出: 固定不覆盖原文件夹, 结果写入 "<源文件夹>_global/" 新文件夹, 内部文件名保持不变
# ============================================================


def load_db_map(db_path, start_ts=None, end_ts=None):
    """Build message_id -> (req_id, req_timestamp) from requests.db.
    Optionally restrict to a DB time window (same semantics as build_minimal_traces)."""
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    q = "SELECT id, timestamp, response FROM requests WHERE response IS NOT NULL"
    params = []
    if start_ts is not None or end_ts is not None:
        conds = []
        if start_ts is not None:
            conds.append("timestamp >= ?")
            params.append(start_ts.isoformat())
        if end_ts is not None:
            conds.append("timestamp <= ?")
            params.append(end_ts.isoformat())
        q += " AND " + " AND ".join(conds)
    cur.execute(q, params)
    m = {}
    for req_id, ts, resp_json in cur.fetchall():
        try:
            resp = json.loads(resp_json)
            body = resp.get('body', resp)
            if isinstance(body, str):
                body = json.loads(body)
            mid = body.get('id')
            if mid:
                m[mid] = (req_id, ts)
        except Exception:
            pass
    con.close()
    return m


def parse_ts(s):
    """Parse a db timestamp string (may have +08:00 or trailing Z) to aware datetime."""
    if not s:
        return None
    s = s.strip()
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def extract_message_ids(jsonl_path):
    ids = []
    try:
        with open(jsonl_path) as f:
            for line in f:
                try:
                    m = json.loads(line)
                    if m.get('type') == 'assistant':
                        mid = (m.get('message') or {}).get('id')
                        if mid:
                            ids.append(mid)
                except Exception:
                    pass
    except Exception:
        pass
    return ids


def find_parent_jsonl(jsonl_root, trace_prefix):
    """Locate parent jsonl whose filename starts with the trace id prefix
    (trace id = first 8 chars of session uuid, sometimes with _sN suffix)."""
    base = trace_prefix.split('_')[0]
    matches = []
    for p in Path(jsonl_root).rglob("*.jsonl"):
        if p.name.startswith("agent-"):
            continue
        if p.stem.startswith(base[:12]):
            matches.append(p)
    return matches[0] if matches else None


def find_subagent_jsonl(parent_jsonl, agent_id):
    """Locate subagent jsonl under the parent session's dir.

    On-disk layout is <projects>/<parent-dir>/<uuid>/subagents/agent-<id>.jsonl
    (each conversation gets its own <uuid>/ subdirectory), with a legacy
    fallback of <parent-dir>/agent-<id>.jsonl.
    """
    parent_dir = parent_jsonl.parent if parent_jsonl else None
    if parent_dir is None:
        return None
    session_dir = parent_dir / parent_jsonl.stem
    cands = [
        session_dir / "subagents" / f"agent-{agent_id}.jsonl",
        session_dir / f"agent-{agent_id}.jsonl",
        parent_dir / "subagents" / f"agent-{agent_id}.jsonl",
        parent_dir / f"agent-{agent_id}.jsonl",
    ]
    for c in cands:
        if c.exists():
            return c
    return None


def earliest_db_time(jsonl_path, db_map):
    """Compute the earliest DB request timestamp for a jsonl file's message ids."""
    ids = [db_map[i] for i in extract_message_ids(jsonl_path) if i in db_map]
    if not ids:
        return None
    return min(parse_ts(ts) for _, ts in ids)


def sorted_db_times(jsonl_path, db_map):
    """Return this jsonl file's matching DB request timestamps, in ascending order."""
    ids = [db_map[i] for i in extract_message_ids(jsonl_path) if i in db_map]
    dts = sorted(parse_ts(ts) for _, ts in ids)
    return dts


def retime_trace_file(path, db_map, jsonl_root, global_start, out_dir, dry_run=False):
    """Rewrite one trace file's t onto the global time axis.

    IMPORTANT — idempotent reconstruction: rather than shifting the *current*
    t by an offset (which would double-shift if the script runs twice), this
    rebuilds each request's t directly from the DB timestamp:
        t = (request's absolute DB timestamp) - global_start
    So the result depends only on the DB, never on prior runs — running this
    script any number of times yields the same output.
    """
    with open(path) as f:
        trace = json.load(f)

    prefix = (trace.get('id') or os.path.basename(path))
    parent_jsonl = find_parent_jsonl(jsonl_root, prefix)
    if parent_jsonl is None:
        print(f"  ⚠️ 找不到父会话 jsonl (prefix={prefix}), 跳过 {os.path.basename(path)}")
        return False
    if global_start is None:
        print(f"  ⚠️ 全局起点未算出, 跳过 {os.path.basename(path)}")
        return False

    conv_start = earliest_db_time(parent_jsonl, db_map)
    if conv_start is None:
        print(f"  ⚠️ 父会话匹配不到 db 请求, 跳过 {os.path.basename(path)}")
        return False
    conv_offset = (conv_start - global_start).total_seconds()

    # Absolute timestamps of the parent conversation's requests, in order.
    parent_times = sorted_db_times(parent_jsonl, db_map)
    # If any parent request couldn't be matched, the DB list may be shorter than
    # the trace's non-subagent requests; guard against index error.
    def next_parent_t():
        # Walk parent_times in order; fall back to the conversation offset if
        # we run out (should not happen in normal builds).
        if parent_times:
            return (parent_times.pop(0) - global_start).total_seconds()
        return conv_offset

    # Walk top-level requests. Non-subagent requests map one-to-one onto the
    # parent conversation's DB requests (their relative order matches). Subagent
    # entries keep their spawn position (relative to parent start + conv_offset).
    for req in trace.get('requests', []):
        if not isinstance(req, dict) or 't' not in req:
            continue
        if req.get('type') == 'subagent':
            # Spawn marker: its t is relative to the parent trace start → shift by conv_offset.
            req['t'] = round(req['t'] + conv_offset, 1)
            # Internal sub-agent requests are rebuilt from the sub-agent's own
            # DB timestamps, so they too land on the global axis and stay
            # idempotent.
            if req.get('requests'):
                sub_jsonl = find_subagent_jsonl(parent_jsonl, req.get('agent_id')) if req.get('agent_id') else None
                sub_times = sorted_db_times(sub_jsonl, db_map) if sub_jsonl else []
                for subreq in req['requests']:
                    if isinstance(subreq, dict) and 't' in subreq:
                        if sub_times:
                            subreq['t'] = round((sub_times.pop(0) - global_start).total_seconds(), 1)
                        else:
                            # Fallback: same base as parent.
                            subreq['t'] = round(subreq['t'] + conv_offset, 1)
        else:
            # Regular parent request → rebuild from its DB timestamp.
            req['t'] = round(next_parent_t(), 1)

    # Where to write: NEVER overwrite the original. Write into the given
    # output FOLDER, keeping the original FILE name unchanged.
    out_path = os.path.join(out_dir, os.path.basename(path))

    if dry_run:
        print(f"  [dry-run] {os.path.basename(path)}: conv_offset={conv_offset:.1f}s → {os.path.basename(path)}")
    else:
        # 与原 build_minimal_traces 一致: 保存成单行紧凑格式(无换行/空格)
        with open(out_path, 'w') as f:
            f.write(json.dumps(trace, ensure_ascii=False, separators=(',', ':')))
        print(f"  ✅ {os.path.basename(path)}: conv_offset={conv_offset:.1f}s")
    return True


def parse_cli_time(s):
    if not s:
        return None
    s = s.strip()
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return d


def main():
    # ---- 命令行参数 ----
    # 用法:
    #   python3 retime_traces_global.py <trace目录>            # 只重标 t → <目录>_global/
    #   python3 retime_traces_global.py <trace目录> --merge     # 重标后, 再把 *_global 合并成 merged.jsonl
    #   python3 retime_traces_global.py <trace目录> --merge-only # 不重标, 只把已有 *_global/*.json 合并(适用于已生成过)
    if len(sys.argv) < 2:
        print("❌ 请在命令行传入 trace 目录参数, 例如:")
        print("   python3 retime_traces_global.py /mnt/nvme1n1/data/lmk/PROJECT/traces/traces-20260828_143832 --merge")
        sys.exit(1)
    traces_dir = sys.argv[1]
    do_merge = "--merge" in sys.argv[2:]
    merge_only = "--merge-only" in sys.argv[2:]

    # 输出文件夹 = "<源文件夹>_global", 内部文件名保持不变, 不覆盖原文件夹。
    out_dir = traces_dir.rstrip("/") + "_global"
    merge_out = os.path.join(out_dir, "merged.jsonl")

    # ---- CONFIG 区取值 ----
    db  = DB
    jsonl_root = JSONL_ROOT
    start_dt = parse_cli_time(DB_START_TIME)
    end_dt   = parse_cli_time(DB_END_TIME)
    dry_run  = DRY_RUN

    # --merge-only: 跳过重标, 直接对已有 _global/*.json 合并
    if merge_only:
        merge_global_traces(out_dir, merge_out)
        print(f"完成。已合并已有 _global 目录: {out_dir}")
        return

    trace_files = sorted(glob.glob(os.path.join(traces_dir, "*.json")))
    if not trace_files:
        print(f"❌ 目录下没有 *.json trace 文件: {traces_dir}")
        sys.exit(1)
    if not dry_run:
        os.makedirs(out_dir, exist_ok=True)

    print("=" * 70)
    print("retime_traces_global —— 重标记 trace 到全局时间轴")
    print(f"  DB       : {db}")
    print(f"  TRACES   : {traces_dir}  ({len(trace_files)} 个文件)")
    print(f"  JSONL    : {jsonl_root}")
    print(f"  时间过滤 : {start_dt or '-'} ~ {end_dt or '-'}")
    print(f"  输出目录 : {out_dir if not dry_run else '(dry-run 不写)'}")
    print(f"  模式     : {'dry-run(只打印不写)' if dry_run else '写入新文件夹(原文件夹不动, 文件名不变)'}")
    print("=" * 70)

    print(f"\n加载 db 映射: {db}")
    db_map = load_db_map(db, start_dt, end_dt)
    print(f"  共 {len(db_map)} 个 message id")

    # ---------- Pass 1: 计算全局起点, 并打印每个会话启动时间 ----------
    print("\n=== Pass 1: 逐会话启动时间 & 全局起点 ===")
    conv_starts = {}
    for path in trace_files:
        with open(path) as f:
            trace = json.load(f)
        prefix = trace.get('id') or Path(path).stem
        pj = find_parent_jsonl(jsonl_root, prefix)
        if pj is None:
            print(f"  (跳过) {os.path.basename(path)}: 找不到父会话 jsonl (prefix={prefix})")
            continue
        cs = earliest_db_time(pj, db_map)
        if cs is None:
            print(f"  (跳过) {os.path.basename(path)}: 会话匹配不到 db 请求")
            continue
        conv_starts[path] = (cs, pj)
        print(f"  📅 {os.path.basename(path):<18} 会话启动时间 = {cs.isoformat()}")

    if not conv_starts:
        print("❌ 没有任何 trace 能关联到 db 请求时间")
        sys.exit(1)

    global_start = min((cs for cs, _ in conv_starts.values()))
    print(f"\n  🌐 全局起点 t=0 = {global_start.isoformat()}  (最早启动的会话)")
    print("     各会话相对全局起点的偏移(offset):")
    for path, (cs, pj) in sorted(conv_starts.items(), key=lambda kv: kv[1][0]):
        off = (cs - global_start).total_seconds()
        marker = "  ← t=0 起点" if off == 0 else ""
        print(f"         {os.path.basename(path):<18} offset={off:>8.1f}s  start={cs.isoformat()}{marker}")

    # ---------- Pass 2: 重标记每个 trace ----------
    print("\n=== Pass 2: 重标记 t ===")
    done = 0
    for path in trace_files:
        ok = retime_trace_file(path, db_map, jsonl_root, global_start, out_dir, dry_run=dry_run)
        if ok:
            done += 1

    print(f"\n完成。已处理 {done}/{len(trace_files)} 个 trace 文件。")
    if dry_run:
        print("(DRY_RUN=True, 未写任何文件; 设 DRY_RUN=False 才会真正写入)")
    else:
        print(f"结果已写入: {out_dir}")
        print("原文件夹未改动, 输出文件夹内文件名与原文件夹相同。")

    # ---- 可选: 合并成单文件 jsonl (按每个 trace 起始 t 排序) ----
    if do_merge and not dry_run:
        print()
        merge_global_traces(out_dir, merge_out)


def merge_global_traces(global_dir, merge_out):
    """Merge every <global_dir>/*.json into one jsonl: one trace per line,
    sorted by each trace's first request t (global timeline)."""
    files = sorted(glob.glob(os.path.join(global_dir, "*.json")))
    if not files:
        print(f"⚠️ {global_dir} 下没有 *.json, 无法合并")
        return False
    traces = []
    for f in files:
        try:
            with open(f) as fh:
                d = json.load(fh)
        except Exception as e:
            print(f"  ⚠️ 跳过 {os.path.basename(f)}: {e}")
            continue
        first_t = d['requests'][0]['t'] if d.get('requests') else 0.0
        traces.append((first_t, d))
    traces.sort(key=lambda x: x[0])
    with open(merge_out, 'w', encoding='utf-8') as fh:
        for first_t, d in traces:
            fh.write(json.dumps(d, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(f"✅ 已合并 {len(traces)} 个 trace → {merge_out}")
    print("   按起始 t 排序的行序:")
    for first_t, d in traces:
        print(f"      {d['id']:<18} 起始 t={first_t}")
    return True


if __name__ == "__main__":
    main()
