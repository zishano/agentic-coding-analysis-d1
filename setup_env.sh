#!/bin/bash
# 一键安装脚本

set -e

PROJECT_DIR="/mnt/nvme1n1/data/lmk/PROJECT/agentic-coding-analysis-d1"
cd "$PROJECT_DIR"

echo "🔧 创建虚拟环境..."
python3 -m venv .venv

echo "✅ 激活虚拟环境..."
source .venv/bin/activate

echo "📦 升级 pip..."
pip install --upgrade pip

echo "📥 安装依赖..."
pip install -r requirements.txt

echo "🧪 验证安装..."
python3 -c "import tiktoken; print('✓ tiktoken:', tiktoken.__version__)"
python3 -c "import plotly; print('✓ plotly:', plotly.__version__)"
python3 -c "import numpy; print('✓ numpy:', numpy.__version__)"

echo ""
echo "✅ 环境安装完成！"
echo ""
echo "💡 激活虚拟环境："
echo "   source .venv/bin/activate"
echo ""
echo "💡 运行脚本："
echo "   python3 analyze_db_quick.py /path/to/requests.db"
echo "   python3 run_trace_generation_fast_v2.py --create-index"
