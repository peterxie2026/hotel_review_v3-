#!/bin/bash
# ============================================
# 酒店点评管家V3 - 腾讯云CVM部署脚本
# 支持 Ubuntu 22.04 / CentOS 7+
# 用法: chmod +x deploy.sh && sudo ./deploy.sh
# ============================================
set -e

PROJECT_DIR="/opt/hotel_review_v3"
DOMAIN="${1:-_}"  # 第一个参数为域名，默认用IP访问
PYTHON="python3.11"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ===== 检测系统 =====
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    err "无法检测操作系统"
fi
log "检测到系统: $OS"

# ===== 1. 安装系统依赖 =====
log "安装系统依赖..."
if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
    apt-get update -qq
    apt-get install -y -qq nginx postgresql postgresql-client \
        $PYTHON $PYTHON-venv $PYTHON-dev \
        nodejs npm \
        libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
        libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
        libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
        libgbm1 libpango-1.0-0 libcairo2 libasound2 \
        certbot python3-certbot-nginx \
        git curl unzip
elif [ "$OS" = "centos" ] || [ "$OS" = "rhel" ]; then
    yum install -y epel-release
    yum install -y nginx postgresql postgresql-server \
        $PYTHON $PYTHON-devel \
        nodejs npm \
        nss nspr atk at-spi2-atk cups-libs libdrm \
        libXcomposite libXdamage libXrandr mesa-libgbm \
        pango cairo alsa-lib \
        git curl unzip
    # 初始化PostgreSQL
    postgresql-setup --initdb
    systemctl enable postgresql
    systemctl start postgresql
else
    warn "未识别的系统，跳过包安装，请手动安装依赖"
fi

# ===== 2. 创建项目目录 =====
log "创建项目目录..."
mkdir -p $PROJECT_DIR

# ===== 3. 克隆/更新代码 =====
if [ -d "$PROJECT_DIR/.git" ]; then
    log "更新现有代码..."
    cd $PROJECT_DIR
    git pull origin main
else
    log "克隆项目代码..."
    # 请替换为你的Git仓库地址
    git clone https://github.com/your-username/hotel_review_v3.git $PROJECT_DIR
    cd $PROJECT_DIR
fi

# ===== 4. 配置环境变量 =====
cd $PROJECT_DIR/backend
if [ ! -f .env ]; then
    log "创建 .env 配置文件..."
    cp .env.example .env
    # 生成随机密钥
    JWT_SECRET=$(openssl rand -hex 32)
    ENCRYPTION_KEY=$(openssl rand -base64 32)
    sed -i "s/JWT_SECRET=.*/JWT_SECRET=$JWT_SECRET/" .env
    sed -i "s/ENCRYPTION_KEY=.*/ENCRYPTION_KEY=$ENCRYPTION_KEY/" .env
    warn "请编辑 $PROJECT_DIR/backend/.env 填入AI_API_KEY等必要配置"
fi

# ===== 5. 设置Python虚拟环境 =====
log "设置Python虚拟环境..."
if [ ! -d ".venv" ]; then
    $PYTHON -m venv .venv
fi
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q

# ===== 6. 安装Playwright浏览器 =====
log "安装Playwright Chromium浏览器（用于OTA自动化）..."
.venv/bin/playwright install --with-deps chromium 2>&1 | tail -3

# ===== 7. 构建前端 =====
log "构建前端..."
cd $PROJECT_DIR/frontend
npm install --silent
npm run build
log "前端构建完成: $PROJECT_DIR/frontend/dist"

# ===== 8. 配置Nginx =====
log "配置Nginx..."
cp $PROJECT_DIR/deploy/nginx.conf /etc/nginx/sites-available/hotel-review
sed -i "s/server_name _;/server_name $DOMAIN;/" /etc/nginx/sites-available/hotel-review

# 启用站点
if [ -d /etc/nginx/sites-enabled ]; then
    ln -sf /etc/nginx/sites-available/hotel-review /etc/nginx/sites-enabled/
    # 删除默认站点
    rm -f /etc/nginx/sites-enabled/default
else
    # CentOS 风格
    cp /etc/nginx/sites-available/hotel-review /etc/nginx/conf.d/hotel-review.conf
fi

# 设置前端目录权限
chown -R www-data:www-data $PROJECT_DIR/frontend/dist 2>/dev/null || true

nginx -t && systemctl reload nginx || err "Nginx配置检查失败"
log "Nginx配置完成"

# ===== 9. 配置Systemd服务 =====
log "配置后端服务..."
cp $PROJECT_DIR/deploy/hotel-review.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable hotel-review
systemctl restart hotel-review

# ===== 10. 检查状态 =====
sleep 2
if systemctl is-active --quiet hotel-review; then
    log "后端服务运行正常"
else
    warn "后端服务未成功启动，查看日志: journalctl -u hotel-review -n 30"
fi

if systemctl is-active --quiet nginx; then
    log "Nginx运行正常"
else
    warn "Nginx未成功启动"
fi

# ===== 完成 =====
echo ""
echo "============================================"
echo -e "${GREEN}  部署完成！${NC}"
echo "============================================"
echo "  项目目录: $PROJECT_DIR"
echo "  后端日志: journalctl -u hotel-review -f"
echo "  Nginx日志: /var/log/nginx/access.log"
echo ""
echo -e "${YELLOW}  请完成以下配置:${NC}"
echo "  1. 编辑 .env: vim $PROJECT_DIR/backend/.env"
echo "  2. 填入 AI_API_KEY"
echo "  3. 如需HTTPS: sudo certbot --nginx"
echo "  4. 访问: http://$(curl -s ifconfig.me 2>/dev/null || echo 'YOUR_IP')"
echo "============================================"
