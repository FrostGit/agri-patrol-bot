#!/bin/bash
# 农业巡检智能服务应用 - 快速启动脚本

echo "=========================================="
echo "农业巡检智能服务应用 - 启动中..."
echo "=========================================="

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查Python3
echo -e "\n${YELLOW}[1/5]${NC} 检查Python3..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}✓${NC} Python3已安装: $PYTHON_VERSION"
else
    echo -e "${RED}✗${NC} Python3未安装，请先安装Python3"
    exit 1
fi

# 检查摄像头
echo -e "\n${YELLOW}[2/5]${NC} 检查USB摄像头..."
if [ -e "/dev/video0" ]; then
    echo -e "${GREEN}✓${NC} 检测到USB摄像头: /dev/video0"
else
    echo -e "${RED}✗${NC} 未检测到USB摄像头，请检查连接"
    echo "提示: 使用 'ls /dev/video*' 查看可用设备"
fi

# 检查依赖
echo -e "\n${YELLOW}[3/5]${NC} 检查Python依赖..."
MISSING_DEPS=0

python3 -c "import flask" 2>/dev/null || { echo -e "${RED}✗${NC} Flask未安装"; MISSING_DEPS=1; }
python3 -c "import cv2" 2>/dev/null || { echo -e "${RED}✗${NC} OpenCV未安装"; MISSING_DEPS=1; }
python3 -c "import numpy" 2>/dev/null || { echo -e "${RED}✗${NC} NumPy未安装"; MISSING_DEPS=1; }

if [ $MISSING_DEPS -eq 1 ]; then
    echo -e "\n${YELLOW}是否立即安装缺失的依赖? (y/n)${NC}"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        echo "正在安装依赖..."
        pip3 install -r requirements.txt
    else
        echo -e "${RED}依赖缺失，程序可能无法正常运行${NC}"
    fi
else
    echo -e "${GREEN}✓${NC} 所有依赖已安装"
fi

# 检查static目录
echo -e "\n${YELLOW}[4/5]${NC} 检查前端文件..."
if [ -f "static/index.html" ]; then
    echo -e "${GREEN}✓${NC} 前端文件存在"
else
    echo -e "${RED}✗${NC} static/index.html 不存在"
    echo "请确保前端HTML文件位于 static/index.html"
    exit 1
fi

# 获取IP地址
echo -e "\n${YELLOW}[5/5]${NC} 获取网络信息..."
IP_ADDRESS=$(hostname -I | awk '{print $1}')
if [ -n "$IP_ADDRESS" ]; then
    echo -e "${GREEN}✓${NC} IP地址: $IP_ADDRESS"
    echo -e "访问地址: ${GREEN}http://$IP_ADDRESS:5000${NC}"
else
    echo -e "${YELLOW}⚠${NC} 无法获取IP地址"
fi

# 启动服务器
echo -e "\n=========================================="
echo -e "${GREEN}准备启动服务器...${NC}"
echo "按 Ctrl+C 停止服务器"
echo "=========================================="
echo ""

# 运行Python后端
python3 app.py