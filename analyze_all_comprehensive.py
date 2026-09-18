#!/usr/bin/env python3
"""
Comprehensive subagent analysis: individual traces + combined visualization
Generates separate charts for each trace and one combined chart
"""

import json
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import os
import glob
import argparse
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta, timezone

# ============================================================================
# TIME MAPPING CONFIGURATION
# Configure the actual start time and display color for each trace file
# ============================================================================

TIME_MAPPING={}
def get_base_time(json_file):
    """Get the base time for a JSON file from configuration"""
    filename = os.path.basename(json_file)
    if filename in TIME_MAPPING:
        time_info = TIME_MAPPING[filename]
        start_str = time_info['start']
        if '+' in start_str:
            start_str = start_str.split('+')[0]
        elif 'Z' in start_str:
            start_str = start_str.replace('Z', '')
        return datetime.fromisoformat(start_str)
    return None

def get_color(json_file):
    """Get the color for a JSON file"""
    filename = os.path.basename(json_file)
    if filename in TIME_MAPPING:
        return TIME_MAPPING[filename]['color']
    return '#888888'

def get_label(json_file):
    """Get the label for a JSON file"""
    filename = os.path.basename(json_file)
    if filename in TIME_MAPPING:
        return TIME_MAPPING[filename]['label']
    return Path(json_file).stem

def load_db_map(db_path):
    """Build message_id -> (req_id, req_timestamp) from requests.db."""
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    q = "SELECT id, timestamp, response FROM requests WHERE response IS NOT NULL"
    cur.execute(q)
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
    """Parse a db timestamp string to aware datetime."""
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
    """Extract message IDs from a JSONL file."""
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
    """Locate parent jsonl whose filename starts with the trace id prefix."""
    base = trace_prefix.split('_')[0]
    matches = []
    for p in Path(jsonl_root).rglob("*.jsonl"):
        if p.name.startswith("agent-"):
            continue
        if p.stem.startswith(base[:12]):
            matches.append(p)
    return matches[0] if matches else None

def earliest_db_time(jsonl_path, db_map):
    """Compute the earliest DB request timestamp for a jsonl file's message ids."""
    ids = [db_map[i] for i in extract_message_ids(jsonl_path) if i in db_map]
    if not ids:
        return None
    return min(parse_ts(ts) for _, ts in ids)

def update_time_mapping_from_db(traces_dir, db_path, jsonl_root):
    """
    Extract start times for each trace file from database and JSONL files.

    Args:
        traces_dir: Directory containing trace JSON files
        db_path: Path to requests.db database
        jsonl_root: Root directory containing JSONL conversation files

    Returns:
        Dictionary mapping trace filenames to their configuration
        Format: {filename: {offset, start, color, label}}
    """
    trace_files = sorted(glob.glob(os.path.join(traces_dir, "*.json")))
    if not trace_files:
        raise ValueError(f"No *.json files found in {traces_dir}")

    db_map = load_db_map(db_path)

    # Calculate start times for each trace
    conv_starts = {}
    for path in trace_files:
        with open(path) as f:
            trace = json.load(f)
        prefix = trace.get('id') or Path(path).stem
        pj = find_parent_jsonl(jsonl_root, prefix)
        if pj is None:
            continue
        cs = earliest_db_time(pj, db_map)
        if cs is None:
            continue
        conv_starts[path] = cs

    if not conv_starts:
        raise ValueError("No traces could be matched to DB request times")

    # Find global start
    global_start = min(conv_starts.values())

    # Build TIME_MAPPING dictionary
    colors = ['#FF1744', '#00E676', '#FFEA00', '#2979FF', '#D500F9', '#FF6E40', '#00BCD4']
    time_mapping = {}

    for idx, (path, cs) in enumerate(sorted(conv_starts.items(), key=lambda kv: kv[1])):
        offset = (cs - global_start).total_seconds()
        filename = os.path.basename(path)
        label = Path(path).stem
        color = colors[idx % len(colors)]

        time_mapping[filename] = {
            'offset': offset,
            'start': cs.isoformat(),
            'color': color,
            'label': label
        }

    return time_mapping

def resample_alive_count(subagents, base_time, sampling_interval):
    """
    Resample alive count at regular time intervals

    Args:
        subagents: List of subagent dictionaries with 'start' and 'end' times (in seconds)
        base_time: Base datetime object
        sampling_interval: Sampling interval in seconds (e.g., 1.0 for 1s, 0.1 for 0.1s)

    Returns:
        times: List of time values in seconds
        times_datetime: List of datetime objects
        alive_counts: List of alive count at each time point
    """
    if not subagents:
        return [], [], []

    # Find time range
    min_time = min(s['start'] for s in subagents)
    max_time = max(s['end'] for s in subagents)

    # Generate time points at regular intervals
    time_points = np.arange(min_time, max_time + sampling_interval, sampling_interval)

    # Calculate alive count at each time point
    alive_counts = []
    for t in time_points:
        count = sum(1 for s in subagents if s['start'] <= t < s['end'])
        alive_counts.append(count)

    # Convert to datetime
    times_datetime = [base_time + timedelta(seconds=float(t)) for t in time_points]

    return time_points.tolist(), times_datetime, alive_counts

def analyze_single_file(json_file, sampling_interval=None):
    """
    Analyze a single JSON file and return subagent data
    """
    print(f"\nProcessing: {json_file}")

    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"  Error reading file: {e}")
        return None

    # Count all requests
    all_requests = data.get('requests', [])
    total_requests = len(all_requests)

    # Extract subagent records
    subagent_records = [r for r in all_requests if r.get('type') == 'subagent']

    # Count main requests (non-subagent)
    main_requests = [r for r in all_requests if r.get('type') != 'subagent']
    main_request_count = len(main_requests)

    # Count requests inside subagents
    subagent_internal_requests = 0
    for subagent in subagent_records:
        if subagent.get('requests'):
            subagent_internal_requests += len(subagent['requests'])

    if not subagent_records:
        print(f"  No subagent records found, skipping...")
        return None

    print(f"  Found {len(subagent_records)} subagent records")
    print(f"  Total requests: {total_requests}, Main: {main_request_count}, Subagent internal: {subagent_internal_requests}")

    # Get base time from configuration
    base_time = get_base_time(json_file)
    if base_time:
        print(f"  Using configured start time: {base_time.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print(f"  Warning: No time mapping found")
        return None

    # Parse each subagent's start and end time
    subagents = []
    for record in subagent_records:
        agent_id = record['agent_id']
        start_time = record['t']

        if record.get('requests') and len(record['requests']) > 0:
            last_request_time = max(req['t'] for req in record['requests'])
            end_time = start_time + last_request_time
        else:
            end_time = start_time

        subagents.append({
            'agent_id': agent_id,
            'start': start_time,
            'end': end_time,
            'duration': end_time - start_time,
            'start_datetime': base_time + timedelta(seconds=start_time),
            'end_datetime': base_time + timedelta(seconds=end_time),
        })

    # Sort by start time
    subagents.sort(key=lambda x: x['start'])

    # Calculate alive count time series
    if sampling_interval is not None:
        # Use fixed interval sampling
        print(f"  Using sampling interval: {sampling_interval}s")
        times, times_datetime, alive_counts = resample_alive_count(subagents, base_time, sampling_interval)
    else:
        # Use event-based sampling (original method)
        print(f"  Using event-based sampling")
        time_points = []
        for agent in subagents:
            time_points.append(('start', agent['start']))
            time_points.append(('end', agent['end']))

        time_points.sort(key=lambda x: x[1])

        times = []
        times_datetime = []
        alive_counts = []
        current_alive = 0

        for event_type, time in time_points:
            if event_type == 'start':
                current_alive += 1
            else:
                current_alive -= 1

            times.append(time)
            times_datetime.append(base_time + timedelta(seconds=time))
            alive_counts.append(current_alive)

    # Calculate statistics
    max_alive = max(alive_counts) if alive_counts else 0
    max_time = times[alive_counts.index(max_alive)] if alive_counts else 0

    stats = {
        'total_subagents': len(subagents),
        'max_concurrent': max_alive,
        'peak_time': max_time,
        'peak_datetime': base_time + timedelta(seconds=max_time),
        'avg_duration': np.mean([s['duration'] for s in subagents]) if subagents else 0,
        'median_duration': np.median([s['duration'] for s in subagents]) if subagents else 0,
        'min_duration': min(s['duration'] for s in subagents) if subagents else 0,
        'max_duration': max(s['duration'] for s in subagents) if subagents else 0,
        'time_range': (min(s['start'] for s in subagents), max(s['end'] for s in subagents)),
        'datetime_range': (subagents[0]['start_datetime'], max(s['end_datetime'] for s in subagents)),
        'base_time': base_time,
        # Request counts
        'total_requests': total_requests,
        'main_requests': main_request_count,
        'subagent_count': len(subagent_records),
        'subagent_internal_requests': subagent_internal_requests
    }

    print(f"  Total subagents: {stats['total_subagents']}")
    print(f"  Max concurrent: {stats['max_concurrent']}")
    print(f"  Time range: {stats['datetime_range'][0].strftime('%Y-%m-%d %H:%M:%S')} - {stats['datetime_range'][1].strftime('%H:%M:%S')}")

    return {
        'subagents': subagents,
        'times': times,
        'times_datetime': times_datetime,
        'alive_counts': alive_counts,
        'stats': stats,
        'color': get_color(json_file),
        'label': get_label(json_file),
        'filename': json_file
    }

def plot_individual_trace(data, output_dir, sampling_interval=None):
    """
    Create visualization for a single trace
    """
    subagents = data['subagents']
    times_datetime = data['times_datetime']
    alive_counts = data['alive_counts']
    stats = data['stats']
    color = data['color']
    label = data['label']

    # Create figure
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 12))

    # ===== Chart 1: Lifecycle bar chart =====
    for i, agent in enumerate(subagents):
        ax1.barh(i, agent['end_datetime'] - agent['start_datetime'],
                left=agent['start_datetime'], height=0.8,
                alpha=0.7, edgecolor='black', linewidth=0.3, color=color)

    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
    ax1.set_xlabel('Time (HH:MM:SS)', fontsize=12)
    ax1.set_ylabel('Subagent Index', fontsize=12)

    title_parts = [f'Subagent Lifecycle - {label}']
    title_parts.append(f"Date: {stats['base_time'].strftime('%Y-%m-%d')}")
    title_parts.append(f"(Total: {stats['total_subagents']} subagents)")

    ax1.set_title('\n'.join(title_parts), fontsize=14, fontweight='bold')
    ax1.grid(axis='x', alpha=0.3)
    ax1.set_ylim(-1, len(subagents))

    if len(subagents) > 50:
        ax1.set_yticks(range(0, len(subagents), max(1, len(subagents)//20)))

    # ===== Chart 2: Alive count over time =====
    ax2.plot(times_datetime, alive_counts, linewidth=1.5, color=color, alpha=0.8)
    ax2.fill_between(times_datetime, alive_counts, alpha=0.3, color=color)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    ax2.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
    ax2.set_xlabel('Time (HH:MM:SS)', fontsize=12)

    ax2.set_ylabel('Number of Alive Subagents', fontsize=12)

    # Add sampling info to title
    title = f'Subagent Count Over Time - {label}'
    if sampling_interval is not None:
        title += f' (Sampling: {sampling_interval}s)'
    ax2.set_title(title, fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(bottom=0)

    # Peak marker
    max_alive = stats['max_concurrent']
    max_time_plot = stats['peak_datetime']
    peak_label = f"  Peak: {max_alive}\n  {max_time_plot.strftime('%H:%M:%S')}"

    ax2.axhline(y=max_alive, color='r', linestyle='--', alpha=0.5, linewidth=1)
    ax2.text(max_time_plot, max_alive, peak_label,
             verticalalignment='bottom', fontsize=9, color='red')

    # Add statistics text box
    time_info = f"Start: {stats['datetime_range'][0].strftime('%H:%M:%S')}\nEnd: {stats['datetime_range'][1].strftime('%H:%M:%S')}"

    stats_text = (f"Statistics:\n"
                  f"Total: {stats['total_subagents']}\n"
                  f"Max Concurrent: {stats['max_concurrent']}\n"
                  f"Avg Duration: {stats['avg_duration']:.2f}s\n"
                  f"Median Duration: {stats['median_duration']:.2f}s\n"
                  f"{time_info}")

    ax2.text(0.02, 0.98, stats_text, transform=ax2.transAxes,
             fontsize=9, verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    # Adjust layout
    plt.tight_layout()

    # Save figure
    output_file = os.path.join(output_dir, f"{label}_subagent_analysis.png")
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"  Saved individual chart: {output_file}")
    return output_file

def create_combined_visualization(all_data, output_dir, sampling_interval=None):
    """
    Create a combined visualization with all traces
    """
    print("\n" + "="*80)
    print("Creating combined visualization...")
    print("="*80)

    # Create figure with 3 subplots
    fig = plt.figure(figsize=(20, 16))
    gs = fig.add_gridspec(3, 1, height_ratios=[2, 1.5, 1], hspace=0.3)

    ax1 = fig.add_subplot(gs[0])  # Combined lifecycle
    ax2 = fig.add_subplot(gs[1])  # Individual alive counts
    ax3 = fig.add_subplot(gs[2])  # Total alive count

    # ===== Chart 1: Combined lifecycle bar chart =====
    print("  Drawing combined lifecycle chart...")

    current_y = 0
    legend_handles = []
    y_boundaries = {}

    for file_data in all_data:
        label = file_data['label']
        color = file_data['color']
        subagents = file_data['subagents']

        y_start = current_y

        for i, agent in enumerate(subagents):
            duration = agent['end_datetime'] - agent['start_datetime']
            ax1.barh(current_y, duration, left=agent['start_datetime'],
                    height=0.8, alpha=0.7, edgecolor='black', linewidth=0.3,
                    color=color)
            current_y += 1

        y_end = current_y
        y_boundaries[label] = (y_start, y_end)

        # Create legend entry
        legend_handles.append(plt.Rectangle((0, 0), 1, 1, fc=color, alpha=0.7,
                                           label=f"{label} ({len(subagents)} subagents)"))

    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')

    ax1.set_xlabel('Time (HH:MM)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Subagent Index (All Traces)', fontsize=12, fontweight='bold')
    ax1.set_title('Combined Subagent Lifecycle - All Traces\nDate: 2026-09-16',
                  fontsize=16, fontweight='bold')
    ax1.grid(axis='x', alpha=0.3)
    ax1.set_ylim(-1, current_y)
    ax1.legend(handles=legend_handles, loc='upper right', fontsize=10)

    # Add horizontal separators between traces
    for label, (y_start, y_end) in y_boundaries.items():
        if y_end < current_y:
            ax1.axhline(y=y_end - 0.5, color='black', linestyle='-', linewidth=1, alpha=0.3)

    # ===== Chart 2: Individual alive counts =====
    print("  Drawing individual alive counts...")

    for file_data in all_data:
        ax2.plot(file_data['times_datetime'], file_data['alive_counts'],
                linewidth=2, alpha=0.8, color=file_data['color'],
                label=f"{file_data['label']} (max: {file_data['stats']['max_concurrent']})")

    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax2.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')

    ax2.set_xlabel('Time (HH:MM)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Alive Subagents (per trace)', fontsize=12, fontweight='bold')

    # Add sampling info to title
    title = 'Individual Trace Concurrent Subagents'
    if sampling_interval is not None:
        title += f' (Sampling: {sampling_interval}s)'
    ax2.set_title(title, fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(bottom=0)
    ax2.legend(loc='upper right', fontsize=9)

    # ===== Chart 3: Total alive count across all traces =====
    print("  Calculating total alive count...")

    # Merge all time points from all traces
    all_time_points = []
    for file_data in all_data:
        for dt in file_data['times_datetime']:
            all_time_points.append(dt)

    all_time_points = sorted(set(all_time_points))

    # Calculate total alive at each time point
    total_alive = []
    for tp in all_time_points:
        total = 0
        for file_data in all_data:
            idx = 0
            for i, dt in enumerate(file_data['times_datetime']):
                if dt <= tp:
                    idx = i
                else:
                    break
            if idx < len(file_data['alive_counts']):
                total += file_data['alive_counts'][idx]
        total_alive.append(total)

    ax3.plot(all_time_points, total_alive, linewidth=2.5, color='#2E86AB', alpha=0.9)
    ax3.fill_between(all_time_points, total_alive, alpha=0.3, color='#2E86AB')

    max_total = max(total_alive) if total_alive else 0
    max_time_idx = total_alive.index(max_total) if total_alive else 0
    max_time = all_time_points[max_time_idx] if all_time_points else None

    if max_time:
        ax3.axhline(y=max_total, color='r', linestyle='--', alpha=0.5, linewidth=1.5)
        ax3.text(max_time, max_total, f'  Peak: {max_total} subagents\n  {max_time.strftime("%H:%M:%S")}',
                verticalalignment='bottom', fontsize=11, color='red', fontweight='bold')

    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax3.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right')

    ax3.set_xlabel('Time (HH:MM)', fontsize=12, fontweight='bold')
    ax3.set_ylabel('Total Alive Subagents', fontsize=12, fontweight='bold')

    # Add sampling info to title
    title = 'Total Concurrent Subagents (All Traces Combined)'
    if sampling_interval is not None:
        title += f' (Sampling: {sampling_interval}s)'
    ax3.set_title(title, fontsize=14, fontweight='bold')
    ax3.grid(True, alpha=0.3)
    ax3.set_ylim(bottom=0)

    # Add statistics box
    total_subagents = sum(fd['stats']['total_subagents'] for fd in all_data)
    stats_text = (f"Summary:\n"
                  f"Total subagents: {total_subagents}\n"
                  f"Max concurrent: {max_total}\n"
                  f"Number of traces: {len(all_data)}")

    ax3.text(0.02, 0.98, stats_text, transform=ax3.transAxes,
            fontsize=11, verticalalignment='top', fontweight='bold',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))

    plt.tight_layout()

    # Save figure
    output_file = os.path.join(output_dir, "combined_all_traces.png")
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"  Saved combined chart: {output_file}")

    # Print summary
    print("\n" + "="*80)
    print("COMBINED ANALYSIS SUMMARY")
    print("="*80)
    print(f"Total traces analyzed: {len(all_data)}")
    print(f"Total subagents: {total_subagents}")
    print(f"Peak concurrent (all traces): {max_total}")
    if max_time:
        print(f"Peak time: {max_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nPer-trace breakdown:")
    for fd in all_data:
        print(f"  {fd['label']:<20} {fd['stats']['total_subagents']:>4} subagents, max concurrent: {fd['stats']['max_concurrent']:>3}")
    print("="*80)

def create_summary_comparison(all_data, output_dir):
    """Create a comparison chart across all files"""
    print("\nCreating summary comparison chart...")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    labels = [fd['label'] for fd in all_data]

    # Chart 1: Max concurrent comparison
    max_concurrents = [fd['stats']['max_concurrent'] for fd in all_data]
    total_subagents = [fd['stats']['total_subagents'] for fd in all_data]

    x = np.arange(len(labels))
    width = 0.35

    ax1.bar(x - width/2, total_subagents, width, label='Total Subagents', alpha=0.8, color='#4ECDC4')
    ax1.bar(x + width/2, max_concurrents, width, label='Max Concurrent', alpha=0.8, color='#FF6B6B')

    ax1.set_xlabel('Trace', fontsize=12)
    ax1.set_ylabel('Count', fontsize=12)
    ax1.set_title('Subagent Statistics Comparison', fontsize=14, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=45, ha='right')
    ax1.legend()
    ax1.grid(axis='y', alpha=0.3)

    # Chart 2: Duration statistics
    avg_durations = [fd['stats']['avg_duration'] for fd in all_data]
    median_durations = [fd['stats']['median_duration'] for fd in all_data]

    ax2.bar(x - width/2, avg_durations, width, label='Average Duration', alpha=0.8, color='#95E1D3')
    ax2.bar(x + width/2, median_durations, width, label='Median Duration', alpha=0.8, color='#F38181')

    ax2.set_xlabel('Trace', fontsize=12)
    ax2.set_ylabel('Duration (seconds)', fontsize=12)
    ax2.set_title('Duration Statistics Comparison', fontsize=14, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, rotation=45, ha='right')
    ax2.legend()
    ax2.grid(axis='y', alpha=0.3)

    plt.tight_layout()

    output_file = os.path.join(output_dir, "summary_comparison.png")
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"  Saved: {output_file}")

def create_request_statistics_chart(all_data, output_dir):
    """
    Create a detailed request statistics chart showing breakdown of request types
    """
    print("\nCreating request statistics chart...")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8))

    labels = [fd['label'] for fd in all_data]
    colors = [fd['color'] for fd in all_data]

    # ===== Chart 1: Stacked bar chart of request breakdown =====
    main_requests = [fd['stats']['main_requests'] for fd in all_data]
    subagent_counts = [fd['stats']['subagent_count'] for fd in all_data]
    subagent_internal = [fd['stats']['subagent_internal_requests'] for fd in all_data]

    x = np.arange(len(labels))
    width = 0.6

    # Create stacked bars
    p1 = ax1.bar(x, main_requests, width, label='Main Requests',
                 alpha=0.8, color='#4CAF50')
    p2 = ax1.bar(x, subagent_counts, width, bottom=main_requests,
                 label='Subagent Records', alpha=0.8, color='#FF9800')
    p3 = ax1.bar(x, subagent_internal, width,
                 bottom=np.array(main_requests) + np.array(subagent_counts),
                 label='Requests Inside Subagents', alpha=0.8, color='#2196F3')

    ax1.set_xlabel('Trace', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Request Count', fontsize=12, fontweight='bold')
    ax1.set_title('Request Breakdown by Type', fontsize=14, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=45, ha='right')
    ax1.legend(loc='upper left', fontsize=10)
    ax1.grid(axis='y', alpha=0.3)

    # Add total labels on top of bars
    totals = [fd['stats']['total_requests'] for fd in all_data]
    for i, (pos, total) in enumerate(zip(x, totals)):
        ax1.text(pos, total, f'{total:,}', ha='center', va='bottom',
                fontweight='bold', fontsize=10)

    # ===== Chart 2: Pie charts showing composition for each trace =====
    # Create a grid of pie charts
    num_traces = len(all_data)

    # Use subplot for side-by-side pie charts
    if num_traces <= 3:
        # Clear ax2 and create subplots within it
        ax2.remove()
        gs = fig.add_gridspec(1, num_traces, left=0.55, right=0.98, wspace=0.3)

        for idx, fd in enumerate(all_data):
            ax_pie = fig.add_subplot(gs[0, idx])

            sizes = [
                fd['stats']['main_requests'],
                fd['stats']['subagent_count'],
                fd['stats']['subagent_internal_requests']
            ]
            labels_pie = ['Main', 'Subagent\nRecords', 'Subagent\nInternal']
            colors_pie = ['#4CAF50', '#FF9800', '#2196F3']

            # Filter out zero values
            sizes_filtered = []
            labels_filtered = []
            colors_filtered = []
            for s, l, c in zip(sizes, labels_pie, colors_pie):
                if s > 0:
                    sizes_filtered.append(s)
                    labels_filtered.append(l)
                    colors_filtered.append(c)

            wedges, texts, autotexts = ax_pie.pie(sizes_filtered, labels=labels_filtered,
                                                   colors=colors_filtered, autopct='%1.1f%%',
                                                   startangle=90, textprops={'fontsize': 9})

            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')

            ax_pie.set_title(f'{fd["label"]}\n({fd["stats"]["total_requests"]:,} total)',
                           fontsize=11, fontweight='bold')
    else:
        # For more than 3 traces, just show a summary table
        ax2.axis('off')
        table_data = []
        table_data.append(['Trace', 'Main', 'Subagent\nRecords', 'Subagent\nInternal', 'Total'])

        for fd in all_data:
            table_data.append([
                fd['label'],
                f"{fd['stats']['main_requests']:,}",
                f"{fd['stats']['subagent_count']:,}",
                f"{fd['stats']['subagent_internal_requests']:,}",
                f"{fd['stats']['total_requests']:,}"
            ])

        table = ax2.table(cellText=table_data, cellLoc='center', loc='center',
                         colWidths=[0.25, 0.15, 0.15, 0.2, 0.15])
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 2)

        # Style header row
        for i in range(5):
            table[(0, i)].set_facecolor('#4CAF50')
            table[(0, i)].set_text_props(weight='bold', color='white')

        ax2.set_title('Request Count Details', fontsize=14, fontweight='bold', pad=20)

    plt.tight_layout()

    output_file = os.path.join(output_dir, "request_statistics.png")
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"  Saved: {output_file}")

    # Print detailed statistics
    print("\n" + "="*100)
    print("REQUEST STATISTICS SUMMARY")
    print("="*100)
    print(f"{'Trace':<20} {'Total Req':<12} {'Main Req':<12} {'Subagent Rec':<14} {'Subagent Int':<14}")
    print("-"*100)
    for fd in all_data:
        stats = fd['stats']
        print(f"{fd['label']:<20} {stats['total_requests']:<12,} {stats['main_requests']:<12,} "
              f"{stats['subagent_count']:<14,} {stats['subagent_internal_requests']:<14,}")

    # Grand totals
    print("-"*100)
    total_all = sum(fd['stats']['total_requests'] for fd in all_data)
    total_main = sum(fd['stats']['main_requests'] for fd in all_data)
    total_subagent = sum(fd['stats']['subagent_count'] for fd in all_data)
    total_internal = sum(fd['stats']['subagent_internal_requests'] for fd in all_data)
    print(f"{'TOTAL':<20} {total_all:<12,} {total_main:<12,} {total_subagent:<14,} {total_internal:<14,}")
    print("="*100)

    """Create a comparison chart across all files"""
    print("\nCreating summary comparison chart...")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    labels = [fd['label'] for fd in all_data]
    colors = [fd['color'] for fd in all_data]

    # Chart 1: Max concurrent comparison
    max_concurrents = [fd['stats']['max_concurrent'] for fd in all_data]
    total_subagents = [fd['stats']['total_subagents'] for fd in all_data]

    x = np.arange(len(labels))
    width = 0.35

    ax1.bar(x - width/2, total_subagents, width, label='Total Subagents', alpha=0.8, color='#4ECDC4')
    ax1.bar(x + width/2, max_concurrents, width, label='Max Concurrent', alpha=0.8, color='#FF6B6B')

    ax1.set_xlabel('Trace', fontsize=12)
    ax1.set_ylabel('Count', fontsize=12)
    ax1.set_title('Subagent Statistics Comparison', fontsize=14, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=45, ha='right')
    ax1.legend()
    ax1.grid(axis='y', alpha=0.3)

    # Chart 2: Duration statistics
    avg_durations = [fd['stats']['avg_duration'] for fd in all_data]
    median_durations = [fd['stats']['median_duration'] for fd in all_data]

    ax2.bar(x - width/2, avg_durations, width, label='Average Duration', alpha=0.8, color='#95E1D3')
    ax2.bar(x + width/2, median_durations, width, label='Median Duration', alpha=0.8, color='#F38181')

    ax2.set_xlabel('Trace', fontsize=12)
    ax2.set_ylabel('Duration (seconds)', fontsize=12)
    ax2.set_title('Duration Statistics Comparison', fontsize=14, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, rotation=45, ha='right')
    ax2.legend()
    ax2.grid(axis='y', alpha=0.3)

    plt.tight_layout()

    output_file = os.path.join(output_dir, "summary_comparison.png")
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"  Saved: {output_file}")

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Comprehensive subagent analysis with configurable sampling',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analyze_all_comprehensive.py                              # Use event-based sampling (default)
  python analyze_all_comprehensive.py --sampling 1.0               # Sample every 1 second
  python analyze_all_comprehensive.py --sampling 0.1               # Sample every 0.1 seconds
  python analyze_all_comprehensive.py -s 0.5                       # Sample every 0.5 seconds
  python analyze_all_comprehensive.py --update-time-mapping        # Update TIME_MAPPING from DB first
  python analyze_all_comprehensive.py --db /path/to/db --update-time-mapping  # Specify DB path
        """
    )
    parser.add_argument(
        '--sampling', '-s',
        type=float,
        default=None,
        metavar='INTERVAL',
        help='Sampling interval in seconds (e.g., 1.0, 0.1). If not specified, uses event-based sampling.'
    )
    parser.add_argument(
        '--update-time-mapping',
        action='store_true',
        help='Update TIME_MAPPING configuration from database before analysis'
    )
    parser.add_argument(
        '--db',
        type=str,
        default='/mnt/nvme1n1/data/lmk/PROJECT/agentic-coding-analysis-d1/tmp/tmp_20260917/requests.db',
        help='Path to requests.db database (default: %(default)s)'
    )
    parser.add_argument(
        '--jsonl-root',
        type=str,
        default='/mnt/nvme1n1/data/lmk/PROJECT/agentic-coding-analysis-d1/tmp/tmp_20260917/projects',
        help='Root directory containing JSONL files (default: %(default)s)'
    )
    parser.add_argument(
        '--traces-dir',
        type=str,
        default='.',
        help='Directory containing trace JSON files (default: current directory)'
    )

    args = parser.parse_args()
    sampling_interval = args.sampling

    # Update TIME_MAPPING if requested
    global TIME_MAPPING
    if args.update_time_mapping:
        print("\n" + "="*80)
        print("UPDATING TIME_MAPPING FROM DATABASE")
        print("="*80)
        print(f"Database: {args.db}")
        print(f"JSONL root: {args.jsonl_root}")
        print(f"Traces dir: {args.traces_dir}")
        print()

        try:
            TIME_MAPPING = update_time_mapping_from_db(args.traces_dir, args.db, args.jsonl_root)
            print(f"✅ Successfully updated TIME_MAPPING with {len(TIME_MAPPING)} traces")
            for filename, config in TIME_MAPPING.items():
                print(f"  {filename}: {config['start']} (offset={config['offset']:.1f}s)")
            print()
        except Exception as e:
            print(f"❌ Failed to update TIME_MAPPING: {e}")
            print("Continuing with existing TIME_MAPPING configuration...")
            print()

    # Configuration
    input_pattern = "*.json"
    output_dir = "subagent_analysis_output"

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    print("="*80)
    print("COMPREHENSIVE SUBAGENT ANALYSIS")
    print("Individual Traces + Combined Visualization")
    print("="*80)

    if sampling_interval is not None:
        print(f"\n⏱️  Sampling mode: FIXED INTERVAL ({sampling_interval}s)")
    else:
        print(f"\n⏱️  Sampling mode: EVENT-BASED (at subagent start/end times)")

    print(f"\nOutput directory: {output_dir}")
    print(f"\nConfigured time mappings for {len(TIME_MAPPING)} files:")
    for filename, info in TIME_MAPPING.items():
        print(f"  - {filename}: {info['start']}")

    # Find all JSON files
    json_files = sorted(glob.glob(input_pattern))

    if not json_files:
        print(f"\nNo JSON files found matching pattern: {input_pattern}")
        return

    print(f"\nFound {len(json_files)} JSON files")

    # Process each file
    all_data = []

    for json_file in json_files:
        data = analyze_single_file(json_file, sampling_interval=sampling_interval)

        if data is not None:
            all_data.append(data)

            # Generate individual plot
            plot_individual_trace(data, output_dir, sampling_interval=sampling_interval)

    if not all_data:
        print("\nNo valid data found in any files!")
        return

    # Create combined visualization
    if len(all_data) > 0:
        create_combined_visualization(all_data, output_dir, sampling_interval=sampling_interval)
        create_summary_comparison(all_data, output_dir)
        create_request_statistics_chart(all_data, output_dir)

    # Print final summary table
    print("\n" + "="*110)
    print("FINAL SUMMARY TABLE")
    print("="*110)
    print(f"{'Trace':<20} {'Total':<8} {'Max Conc':<10} {'Avg Dur':<10} {'Med Dur':<10} {'Start Time':<20} {'End Time':<15}")
    print("-"*110)

    for data in all_data:
        stats = data['stats']
        start_str = stats['datetime_range'][0].strftime('%Y-%m-%d %H:%M:%S')
        end_str = stats['datetime_range'][1].strftime('%H:%M:%S')
        print(f"{data['label']:<20} {stats['total_subagents']:<8} {stats['max_concurrent']:<10} "
              f"{stats['avg_duration']:<10.2f} {stats['median_duration']:<10.2f} {start_str:<20} {end_str:<15}")

    print("="*110)
    print(f"\nAll analysis complete! Results saved to: {output_dir}/")
    print(f"  - {len(all_data)} individual trace charts")
    print(f"  - 1 combined visualization")
    print(f"  - 1 summary comparison chart")
    print(f"  - 1 request statistics chart")

if __name__ == "__main__":
    main()
