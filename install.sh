#!/bin/bash

# Exit on error
set -e

# Display Banner
cat << "EOF"
 _______   __    __  __         ______    ______  
|       \ |  \  |  \|  \       /      \  /      \ 
| $$$$$$$\| $$  | $$| $$      |  $$$$$$\|  $$$$$$\
| $$__/ $$| $$  | $$| $$      | $$__| $$| $$  | $$
| $$    $$| $$  | $$| $$      | $$    $$| $$  | $$
| $$$$$$$ | $$  | $$| $$      | $$$$$$$$| $$  | $$
| $$      | $$__/ $$| $$_____ | $$  | $$| $$__/ $$
| $$       \$$    $$| $$     \| $$  | $$ \$$    $$
 \$$        \$$$$$$  \$$$$$$$$ \$$   \$$  \$$$$$$ 
          AI-Powered DevOps Assistant
EOF

APP_NAME="pulao"
INSTALL_DIR="/opt/$APP_NAME"
BIN_NAME="pulao"
REPO_URL="https://github.com/lotusTanglei/pulao/archive/refs/heads/main.zip"

# --- Language Selection ---
echo "Please select language / 请选择语言:"
echo "1. English"
echo "2. 中文"

# Try to read from tty if available (to support curl | bash)
if [ -c /dev/tty ]; then
    read -p "Enter number (1/2): " LANG_CHOICE < /dev/tty
else
    LANG_CHOICE="1"
fi

if [ "$LANG_CHOICE" == "2" ]; then
    LANG="zh"
    MSG_START="🚀 开始安装 $APP_NAME..."
    MSG_ROOT="请以 root 身份运行 (sudo ./install.sh)"
    MSG_UPDATE="📦 正在更新系统软件源..."
    MSG_DOWNLOADING="⬇️ 正在下载源码..."
    MSG_UNZIP_INSTALL="📦 正在安装 unzip..."
    MSG_DOCKER_INSTALL="🐳 未找到 Docker。正在安装 Docker..."
    MSG_DOCKER_DONE="✅ Docker 安装完成。"
    MSG_DOCKER_EXIST="✅ Docker 已安装。"
    MSG_DIR="📂 正在设置安装目录 $INSTALL_DIR..."
    MSG_VENV="🐍 正在配置 Python 虚拟环境..."
    MSG_DEPS="⬇️ 正在安装 Python 依赖..."
    MSG_CMD="🔗 正在创建系统命令 '$BIN_NAME'..."
    MSG_DONE="🎉 安装完成!"
    MSG_USAGE="👉 现在可以使用命令: $BIN_NAME"
    MSG_HELP="   尝试运行: $BIN_NAME --help"
else
    LANG="en"
    MSG_START="🚀 Starting installation of $APP_NAME..."
    MSG_ROOT="Please run as root (sudo ./install.sh)"
    MSG_UPDATE="📦 Updating system repositories..."
    MSG_DOWNLOADING="⬇️ Downloading source code..."
    MSG_UNZIP_INSTALL="📦 Installing unzip..."
    MSG_DOCKER_INSTALL="🐳 Docker not found. Installing Docker..."
    MSG_DOCKER_DONE="✅ Docker installed."
    MSG_DOCKER_EXIST="✅ Docker is already installed."
    MSG_DIR="📂 Setting up installation directory at $INSTALL_DIR..."
    MSG_VENV="🐍 Setting up Python virtual environment..."
    MSG_DEPS="⬇️ Installing Python dependencies..."
    MSG_CMD="🔗 Creating system command '$BIN_NAME'..."
    MSG_DONE="🎉 Installation Complete!"
    MSG_USAGE="👉 You can now use the command: $BIN_NAME"
    MSG_HELP="   Try: $BIN_NAME --help"
fi

echo "$MSG_START"

# Check for root
if [ "$EUID" -ne 0 ]; then
  echo "$MSG_ROOT"
  exit 1
fi

# 1. System Updates & Dependencies
echo "$MSG_UPDATE"
apt-get update
# Install libreadline-dev for better python input handling
apt-get install -y python3 python3-pip python3-venv git curl libreadline-dev

# 2. Check source availability (Download if running via curl pipe)
if [ ! -f "requirements.txt" ] || [ ! -d "src" ]; then
    echo "$MSG_DOWNLOADING"
    
    # Install unzip if needed
    if ! command -v unzip &> /dev/null; then
        echo "$MSG_UNZIP_INSTALL"
        apt-get install -y unzip
    fi

    # Create temp dir
    TMP_DIR=$(mktemp -d)
    echo "⬇️ Downloading from: $REPO_URL"
    if ! curl -f -L -o "$TMP_DIR/source.zip" "$REPO_URL"; then
        echo "❌ Download failed! Please check your network or URL."
        exit 1
    fi
    
    # Unzip and move to current dir (which might be a temp execution dir)
    # We unzip to a specific location to avoid cluttering /root or wherever
    if ! unzip -q "$TMP_DIR/source.zip" -d "$TMP_DIR"; then
        echo "❌ Unzip failed! The downloaded file might be corrupted or not a zip file."
        echo "File content (first 10 lines):"
        head -n 10 "$TMP_DIR/source.zip"
        exit 1
    fi
    
    # The zip usually contains a folder like pulao-main
    SOURCE_ROOT=$(find "$TMP_DIR" -maxdepth 1 -type d -name "pulao-*" | head -n 1)
    
    if [ -z "$SOURCE_ROOT" ]; then
        echo "Error: Could not find source directory in zip."
        exit 1
    fi
    
    # Change context to the downloaded source
    cd "$SOURCE_ROOT"
fi

# 3. Check/Install Docker
if ! command -v docker &> /dev/null; then
    echo "$MSG_DOCKER_INSTALL"
    # Try using Aliyun mirror for China users or standard get.docker.com
    if [ "$INSTALL_LANG" == "zh" ]; then
        curl -fsSL https://get.docker.com | bash -s docker --mirror Aliyun
    else
        curl -fsSL https://get.docker.com -o get-docker.sh
        sh get-docker.sh
        rm get-docker.sh
    fi
    echo "$MSG_DOCKER_DONE"
else
    echo "$MSG_DOCKER_EXIST"
fi

# 4. Configure Docker Registry Mirrors (Always run for ZH users)
if [ "$INSTALL_LANG" == "zh" ]; then
    echo "🔧 Configuring Docker Registry Mirrors..."
    mkdir -p /etc/docker
    cat > /etc/docker/daemon.json <<EOF
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.1panel.live",
    "https://docker.m.daocloud.io",
    "https://huecker.io",
    "https://dockerhub.timeweb.cloud",
    "https://noohub.ru",
    "https://dockerproxy.com",
    "https://docker.mirrors.ustc.edu.cn",
    "https://docker.nju.edu.cn",
    "https://registry.docker-cn.com",
    "http://hub-mirror.c.163.com"
  ]
}
EOF
    systemctl daemon-reload
    systemctl restart docker
fi

# Ensure Docker service is running
systemctl start docker
systemctl enable docker

# 4. Setup Application Directory
echo "$MSG_DIR"
mkdir -p "$INSTALL_DIR"
cp -r ./* "$INSTALL_DIR/"

# 5. Save Global Language Config
echo "language: $INSTALL_LANG" > "$INSTALL_DIR/global_config.yaml"

# 6. Setup Python Virtual Environment
echo "$MSG_VENV"
python3 -m venv "$INSTALL_DIR/venv"
source "$INSTALL_DIR/venv/bin/activate"

# 7. Install Python Dependencies
echo "$MSG_DEPS"
pip install --upgrade pip
# Ensure sqlite3 is available for ChromaDB (some minimal systems might miss it)
if ! python3 -c "import sqlite3" &> /dev/null; then
    echo "⚠️  sqlite3 module missing. Installing libsqlite3-dev..."
    apt-get install -y libsqlite3-dev
fi
pip install -r "$INSTALL_DIR/requirements.txt"

# 8. Create executable wrapper
echo "$MSG_CMD"
cat <<EOF > "/usr/local/bin/$BIN_NAME"
#!/bin/bash
source "$INSTALL_DIR/venv/bin/activate"
export PYTHONPATH="$INSTALL_DIR"
python3 -m src.main "\$@"
EOF

chmod +x "/usr/local/bin/$BIN_NAME"

# 9. Initialize Template Library
if [ "$INSTALL_LANG" == "zh" ]; then
    echo "📚 正在初始化模板库..."
else
    echo "📚 Initializing template library..."
fi

# Run update-library command using the venv python
# We ignore errors here so installation can finish even if network fails
"$INSTALL_DIR/venv/bin/python3" -m src.main update-library || true

echo "$MSG_DONE"
echo "$MSG_USAGE"
echo "$MSG_HELP"
