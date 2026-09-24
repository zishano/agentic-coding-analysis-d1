#!/usr/bin/env python3
"""
Context Growth Visualizer
=========================
分析并可视化 AI 对话会话中的上下文增长模式。

功能：
- 从 JSONL 文件中提取每轮对话的 input_tokens
- 识别上下文压缩 (compaction) 事件
- 生成类似 SemiAnalysis 图表的可视化
- 支持批量处理多个会话

用法:
    python3 context_growth_visualizer.py --jsonl-root /path/to/projects [选项]
"""

import json
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import os
import glob
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class ConversationData:
    """存储单个会话的上下文增长数据"""

    def __init__(self, session_id: str, file_path: str):
        self.session_id = session_id
        self.file_path = file_path
        self.turns = []  # 轮次编号
        self.input_tokens = []  # 输入token数
        self.compactions = []  # 压缩事件位置 (turn_index)
        self.title = ""

    def add_turn(self, turn: int, tokens: int):
        """添加一轮对话数据"""
        # 检测压缩事件：token数显著下降
        if self.input_tokens and tokens < self.input_tokens[-1] * 0.7:
            self.compactions.append(len(self.turns))

        self.turns.append(turn)
        self.input_tokens.append(tokens)

    def get_max_tokens(self) -> int:
        """获取最大token数"""
        return max(self.input_tokens) if self.input_tokens else 0

    def get_turn_count(self) -> int:
        """获取总轮次数"""
        return len(self.turns)


def extract_conversation_data(jsonl_path: str) -> Optional[ConversationData]:
    """
    从 JSONL 文件中提取会话的上下文增长数据

    Args:
        jsonl_path: JSONL 文件路径

    Returns:
        ConversationData 对象，如果无有效数据则返回 None
    """
    if not os.path.exists(jsonl_path):
        logger.warning(f"文件不存在: {jsonl_path}")
        return None

    conv_data = None
    turn_count = 0

    try:
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())

                    # 初始化会话数据
                    if conv_data is None:
                        session_id = data.get('sessionId', Path(jsonl_path).stem)
                        conv_data = ConversationData(session_id, jsonl_path)

                    # 提取标题
                    if data.get('type') == 'custom-title':
                        conv_data.title = data.get('customTitle', '')

                    # 提取 assistant 消息的 usage 数据
                    if data.get('type') == 'assistant':
                        message = data.get('message', {})
                        usage = message.get('usage', {})
                        input_tokens = usage.get('input_tokens', 0)

                        if input_tokens > 0:
                            turn_count += 1
                            conv_data.add_turn(turn_count, input_tokens)

                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    logger.debug(f"处理行时出错: {e}")
                    continue

    except Exception as e:
        logger.error(f"读取文件失败 {jsonl_path}: {e}")
        return None

    # 只返回有数据的会话
    if conv_data and conv_data.get_turn_count() > 0:
        return conv_data

    return None


def find_jsonl_files(jsonl_root: str, recursive: bool = True) -> List[str]:
    """
    查找所有 JSONL 文件（排除 agent- 开头的子代理文件）

    Args:
        jsonl_root: JSONL 文件根目录
        recursive: 是否递归查找

    Returns:
        JSONL 文件路径列表
    """
    if not os.path.exists(jsonl_root):
        logger.error(f"目录不存在: {jsonl_root}")
        return []

    pattern = "**/*.jsonl" if recursive else "*.jsonl"
    all_files = glob.glob(os.path.join(jsonl_root, pattern), recursive=recursive)

    # 过滤掉子代理文件
    main_files = [f for f in all_files if not os.path.basename(f).startswith('agent-')]

    logger.info(f"找到 {len(main_files)} 个主会话 JSONL 文件")
    return sorted(main_files)


def plot_context_growth(conversations: List[ConversationData], output_path: str,
                       title: str = "Context Growth"):
    """
    绘制上下文增长图表

    Args:
        conversations: 会话数据列表
        output_path: 输出图片路径
        title: 图表标题
    """
    if not conversations:
        logger.warning("没有数据可绘制")
        return

    fig, ax = plt.subplots(figsize=(14, 8))

    # 生成颜色（使用半透明以显示重叠）
    colors = plt.cm.tab20(np.linspace(0, 1, min(20, len(conversations))))

    # 绘制每个会话的轨迹
    for i, conv in enumerate(conversations):
        color = colors[i % len(colors)]
        alpha = 0.6 if len(conversations) > 50 else 0.7

        # 绘制主线
        ax.plot(conv.turns, conv.input_tokens,
               color=color, alpha=alpha, linewidth=1.0,
               label=conv.title if i < 10 and conv.title else None)

        # 标记压缩事件（垂直下降的线段）
        for comp_idx in conv.compactions:
            if comp_idx > 0 and comp_idx < len(conv.turns):
                ax.plot([conv.turns[comp_idx-1], conv.turns[comp_idx]],
                       [conv.input_tokens[comp_idx-1], conv.input_tokens[comp_idx]],
                       color=color, alpha=alpha*0.8, linewidth=1.2)

    # 设置对数坐标
    ax.set_yscale('log')
    ax.set_xscale('log')

    # 设置标签和标题
    ax.set_xlabel('main-agent turn count', fontsize=12)
    ax.set_ylabel('context length (input tokens)', fontsize=12)
    ax.set_title(f'{title} — {len(conversations)} conversations', fontsize=14, pad=20)

    # 设置网格
    ax.grid(True, which='both', alpha=0.3, linestyle='-', linewidth=0.5)

    # 设置刻度格式
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda y, _: f'{int(y):,}' if y >= 1000 else f'{int(y)}'))
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f'{int(x)}'))

    # 设置Y轴刻度
    ax.set_yticks([100, 1000, 10000, 100000, 1000000])
    ax.set_yticklabels(['100', '1k', '10k', '100k', '1M'])

    # 图例（只显示前几个）
    if any(conv.title for conv in conversations[:10]):
        ax.legend(loc='upper left', fontsize=8, framealpha=0.9)

    # 调整布局
    plt.tight_layout()

    # 保存图片
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    logger.info(f"✅ 图表已保存: {output_path}")
    plt.close()


def generate_statistics(conversations: List[ConversationData]) -> Dict:
    """
    生成统计数据

    Args:
        conversations: 会话数据列表

    Returns:
        统计数据字典
    """
    if not conversations:
        return {}

    total_convs = len(conversations)
    total_turns = sum(conv.get_turn_count() for conv in conversations)
    total_compactions = sum(len(conv.compactions) for conv in conversations)

    max_turns = max(conv.get_turn_count() for conv in conversations)
    max_tokens = max(conv.get_max_tokens() for conv in conversations)

    avg_turns = total_turns / total_convs
    avg_compactions = total_compactions / total_convs

    # 长会话统计 (>100轮)
    long_convs = [c for c in conversations if c.get_turn_count() > 100]
    very_long_convs = [c for c in conversations if c.get_turn_count() > 500]

    stats = {
        'total_conversations': total_convs,
        'total_turns': total_turns,
        'total_compactions': total_compactions,
        'max_turns': max_turns,
        'max_tokens': max_tokens,
        'avg_turns_per_conv': avg_turns,
        'avg_compactions_per_conv': avg_compactions,
        'long_conversations_100plus': len(long_convs),
        'very_long_conversations_500plus': len(very_long_convs),
    }

    return stats


def print_statistics(stats: Dict):
    """打印统计信息"""
    print("\n" + "=" * 70)
    print("上下文增长分析统计")
    print("=" * 70)
    print(f"总会话数        : {stats['total_conversations']}")
    print(f"总轮次数        : {stats['total_turns']}")
    print(f"总压缩事件      : {stats['total_compactions']}")
    print(f"平均轮次/会话   : {stats['avg_turns_per_conv']:.1f}")
    print(f"平均压缩/会话   : {stats['avg_compactions_per_conv']:.1f}")
    print(f"最大轮次数      : {stats['max_turns']}")
    print(f"最大token数     : {stats['max_tokens']:,}")
    print(f"长会话(>100轮)  : {stats['long_conversations_100plus']}")
    print(f"超长会话(>500轮): {stats['very_long_conversations_500plus']}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description='分析并可视化 AI 对话会话的上下文增长模式',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 分析指定目录下的所有会话
  %(prog)s --jsonl-root /path/to/projects

  # 指定输出路径
  %(prog)s --jsonl-root /path/to/projects --output context_growth.png

  # 限制分析的会话数量
  %(prog)s --jsonl-root /path/to/projects --limit 100

  # 只分析长会话 (>50轮)
  %(prog)s --jsonl-root /path/to/projects --min-turns 50
        """
    )

    parser.add_argument('--jsonl-root', required=True,
                       help='JSONL 文件根目录')
    parser.add_argument('--output', default='context_growth.png',
                       help='输出图片路径 (默认: context_growth.png)')
    parser.add_argument('--title', default='Context growth',
                       help='图表标题 (默认: Context growth)')
    parser.add_argument('--limit', type=int,
                       help='限制分析的会话数量')
    parser.add_argument('--min-turns', type=int, default=1,
                       help='最小轮次数过滤 (默认: 1)')
    parser.add_argument('--max-turns', type=int,
                       help='最大轮次数过滤')
    parser.add_argument('--verbose', action='store_true',
                       help='显示详细日志')

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # 查找 JSONL 文件
    logger.info(f"扫描目录: {args.jsonl_root}")
    jsonl_files = find_jsonl_files(args.jsonl_root)

    if not jsonl_files:
        logger.error("未找到 JSONL 文件")
        return 1

    # 限制文件数量
    if args.limit:
        jsonl_files = jsonl_files[:args.limit]
        logger.info(f"限制为前 {args.limit} 个文件")

    # 提取会话数据
    logger.info("提取会话数据...")
    conversations = []

    for i, jsonl_file in enumerate(jsonl_files, 1):
        if i % 50 == 0:
            logger.info(f"进度: {i}/{len(jsonl_files)}")

        conv_data = extract_conversation_data(jsonl_file)
        if conv_data:
            # 应用过滤条件
            turn_count = conv_data.get_turn_count()
            if turn_count >= args.min_turns:
                if not args.max_turns or turn_count <= args.max_turns:
                    conversations.append(conv_data)

    logger.info(f"成功提取 {len(conversations)} 个会话数据")

    if not conversations:
        logger.error("没有有效的会话数据")
        return 1

    # 生成统计
    stats = generate_statistics(conversations)
    print_statistics(stats)

    # 绘制图表
    logger.info("生成可视化图表...")
    plot_context_growth(conversations, args.output, args.title)

    print(f"\n✅ 完成！图表已保存到: {args.output}")
    return 0


if __name__ == '__main__':
    exit(main())
