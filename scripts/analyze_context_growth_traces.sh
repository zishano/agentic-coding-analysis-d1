#!/bin/bash
# 从 trace 的 merged.jsonl 文件生成上下文增长可视化
#
# 用法:
#   ./scripts/analyze_context_growth_traces.sh <merged.jsonl>                    # 基本用法
#   ./scripts/analyze_context_growth_traces.sh <merged.jsonl> --output out.png  # 指定输出文件
#   ./scripts/analyze_context_growth_traces.sh <merged.jsonl> --verbose         # 显示详细日志
#
# 参数:
#   输入文件          merged.jsonl 文件路径（必需）
#   --output PATH    输出图片路径 (默认: context_growth_traces.png)
#   --title TEXT     图表标题 (默认: Context growth)
#   --verbose        显示详细日志
#   --help           显示帮助

set -e

# 获取脚本所在目录的父目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Python 分析脚本路径
VISUALIZER_SCRIPT="$PROJECT_DIR/context_growth_from_traces.py"

# 显示帮助信息
show_help() {
    cat << EOF
从 trace 的 merged.jsonl 文件生成上下文增长可视化

用法:
  $0 <merged.jsonl> [选项]

参数:
  <merged.jsonl>       输入的 merged.jsonl 文件路径（必需）

选项:
  --output PATH        输出图片路径
                       (默认: context_growth_traces.png)

  --title TEXT         图表标题
                       (默认: Context growth)

  --verbose            显示详细日志（用于调试）

  --help               显示此帮助信息

示例:
  # 基本用法
  $0 traces-xxx_global/merged.jsonl

  # 指定输出文件
  $0 traces-xxx_global/merged.jsonl --output my_growth.png

  # 自定义标题
  $0 traces-xxx_global/merged.jsonl --title "Context Analysis - 2026-09-16"

  # 显示详细日志
  $0 traces-xxx_global/merged.jsonl --verbose

  # 完整路径示例
  $0 /mnt/nvme1n1/data/lmk/PROJECT/agentic-coding-analysis-d1/traces-d1/traces-20260918_093301-2026-09-16T00:00:00+08:00-2026-09-17T19:30:00+08:00_global/merged.jsonl

输出:
  生成的图表展示每个会话的上下文增长轨迹
  - 横轴: 主代理轮次数（对数坐标）
  - 纵轴: 输入 token 数（对数坐标）
  - 垂直下降: 上下文压缩事件

EOF
}

# 检查是否提供了输入文件
if [ $# -eq 0 ] || [ "$1" = "--help" ]; then
    show_help
    exit 0
fi

# 第一个参数是输入文件
INPUT_FILE="$1"
shift

# 解析剩余参数
INPUT_FILE_1="$(dirname "$INPUT_FILE")"
echo $(dirname "$INPUT_FILE_1")
OUTPUT="$INPUT_FILE_1/context_growth_traces.png"
TITLE="Context growth"
VERBOSE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --output)
            OUTPUT="$2"
            shift 2
            ;;
        --title)
            TITLE="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE="--verbose"
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo "❌ 未知参数: $1"
            echo "使用 --help 查看帮助"
            exit 1
            ;;
    esac
done

# 检查分析脚本是否存在
if [ ! -f "$VISUALIZER_SCRIPT" ]; then
    echo "❌ 错误: 找不到分析脚本: $VISUALIZER_SCRIPT"
    exit 1
fi

# 检查输入文件是否存在
if [ ! -f "$INPUT_FILE" ]; then
    echo "❌ 错误: 输入文件不存在: $INPUT_FILE"
    exit 1
fi

# 获取输入文件的绝对路径
INPUT_FILE="$(realpath "$INPUT_FILE")"

# 处理输出路径：如果只是文件名，则保存在项目根目录
if [[ "$OUTPUT" != /* ]]; then
    OUTPUT="$PROJECT_DIR/$OUTPUT"
fi

echo "========================================================================"
echo "上下文增长分析工具 (Trace 版本)"
echo "========================================================================"
echo "输入文件     : $INPUT_FILE"
echo "输出文件     : $OUTPUT"
echo "图表标题     : $TITLE"
[ -n "$VERBOSE" ] && echo "详细日志     : 开启"
echo "========================================================================"
echo ""

# 构建 Python 命令
PYTHON_CMD="python3 \"$VISUALIZER_SCRIPT\" --input \"$INPUT_FILE\" --output \"$OUTPUT\" --title \"$TITLE\""

if [ -n "$VERBOSE" ]; then
    PYTHON_CMD="$PYTHON_CMD --verbose"
fi

# 执行分析
echo "🚀 开始分析 trace 文件..."
echo ""

eval $PYTHON_CMD

if [ $? -eq 0 ]; then
    echo ""
    echo "========================================================================"
    echo "✅ 分析完成！"
    echo "========================================================================"
    echo "生成的图表文件: $OUTPUT"
    echo ""

    # 显示文件信息
    if [ -f "$OUTPUT" ]; then
        ls -lh "$OUTPUT"
    fi
else
    echo ""
    echo "❌ 分析失败"
    exit 1
fi
