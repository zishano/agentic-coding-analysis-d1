# agentic-coding-analysis 环境安装步骤

## 📋 环境要求

- Python 3.8+
- pip

## 🚀 快速安装

### 1. 创建虚拟环境

```bash
cd /mnt/nvme1n1/data/lmk/PROJECT/agentic-coding-analysis-d1

# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境
source .venv/bin/activate
```

### 2. 安装依赖

```bash
# 升级 pip
pip install --upgrade pip

# 安装项目依赖
pip install -r requirements.txt
```

### 3. 验证安装

```bash
python3 -c "import tiktoken; print('tiktoken:', tiktoken.__version__)"
python3 -c "import plotly; print('plotly:', plotly.__version__)"
python3 -c "import numpy; print('numpy:', numpy.__version__)"
```

## 📦 依赖包说明

| 包名 | 版本要求 | 用途 |
|------|----------|------|
| **tiktoken** | ≥0.5.0 | OpenAI 的分词器，用于计算 token 数 |
| **plotly** | ≥5.0.0 | 交互式可视化，生成 trace 分析图表 |
| **numpy** | ≥1.20.0 | 数值计算，支持 trace 数据分析 |

## 🔧 故障排查

### 问题 1：tiktoken 安装失败（网络问题）

**症状**：
```
ERROR: Could not install packages due to an EnvironmentError
```

**解决方案**：设置离线缓存目录
```bash
export TIKTOKEN_CACHE_DIR=/tmp/tiktoken-cache
mkdir -p $TIKTOKEN_CACHE_DIR
```

### 问题 2：ImportError: No module named 'tiktoken'

**症状**：
```
ModuleNotFoundError: No module named 'tiktoken'
```

**解决方案**：确认虚拟环境已激活
```bash
# 检查当前 Python 路径
which python3

# 应该显示：
# /mnt/nvme1n1/data/lmk/PROJECT/agentic-coding-analysis-d1/.venv/bin/python3

# 如果不是，重新激活
source .venv/bin/activate
```

### 问题 3：pip 版本过旧

**症状**：
```
WARNING: You are using pip version 21.x; however, version 23.x is available.
```

**解决方案**：
```bash
pip install --upgrade pip
```

## 📝 完整安装脚本

创建一个一键安装脚本：

```bash
#!/bin/bash
# setup_env.sh

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
echo "   python3 build_minimal_traces.py --help"
```

保存为 `setup_env.sh`，然后运行：

```bash
chmod +x setup_env.sh
./setup_env.sh
```

## 🎯 使用示例

激活环境后运行脚本：

```bash
# 激活虚拟环境
source .venv/bin/activate

# 快速分析数据库
python3 analyze_db_quick.py /path/to/requests.db

# 生成 trace
python3 run_trace_generation_fast_v2.py --create-index

# 退出虚拟环境
deactivate
```

## 📌 注意事项

1. **每次使用前激活虚拟环境**
   ```bash
   source .venv/bin/activate
   ```

2. **tiktoken 缓存**
   - 首次运行会下载编码文件（~1MB）
   - 设置 `TIKTOKEN_CACHE_DIR` 避免重复下载

3. **Python 版本**
   - 推荐 Python 3.10+
   - 最低要求 Python 3.8

4. **磁盘空间**
   - 虚拟环境约占 100-200 MB
   - 确保有足够空间存储 trace 输出
