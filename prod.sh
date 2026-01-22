#!/bin/bash
# 从本地自动部署生产环境到阿里云服务器
# 使用自定义端口8001(前端) / 8002(后端)

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 加载部署配置
if [ ! -f "deploy-config" ]; then
    echo -e "${RED}错误: deploy-config文件不存在${NC}"
    echo "请先创建配置文件:"
    echo "  cp deploy-config.example deploy-config"
    echo "  vim deploy-config  # 填入服务器信息"
    exit 1
fi

source deploy-config

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# 检查sshpass
check_sshpass() {
    if ! command -v sshpass &> /dev/null; then
        log_error "sshpass未安装"
        log_info "MacOS安装: brew install sshpass"
        log_info "Ubuntu安装: sudo apt-get install sshpass"
        exit 1
    fi
}

# 执行远程命令（远端强制使用 bash 且启用严格模式，避免“失败但脚本仍然显示成功”）
remote_exec() {
    sshpass -p "$SERVER_PASSWORD" ssh -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" "bash -seuo pipefail" <<EOF
$1
EOF
}

# 上传文件
upload_file() {
    sshpass -p "$SERVER_PASSWORD" scp -o StrictHostKeyChecking=no "$1" "$SERVER_USER@$SERVER_IP:$2"
}

# 上传目录
upload_dir() {
    sshpass -p "$SERVER_PASSWORD" scp -r -o StrictHostKeyChecking=no "$1" "$SERVER_USER@$SERVER_IP:$2"
}

echo "================================================================"
echo "   阿里云服务器自动部署脚本 - 生产环境"
echo "   服务器: $SERVER_IP"
echo "   端口: 8001(前端) / 8002(后端)"
echo "================================================================"
echo ""

# 步骤1: 检查本地环境
log_step "步骤1: 检查本地环境"
check_sshpass

# 检查必要文件
if [ ! -f .env ]; then
    log_error ".env文件不存在"
    log_info "请先运行: ./setup-env.sh"
    exit 1
fi

if [ ! -f docker-compose.prod.yml ]; then
    log_error "docker-compose.prod.yml不存在"
    exit 1
fi

log_info "本地环境检查通过 ✓"
echo ""

# 步骤2: 检查.env配置
log_step "步骤2: 检查环境变量配置"
log_info "检查关键配置项..."

# 检查是否有未配置的占位符
if grep -q "CHANGE_ME\|your-.*-here" .env; then
    log_warn ".env中存在未配置的占位符"
    log_warn "请确保已正确配置所有API密钥"
    read -p "继续部署? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_warn "部署已取消"
        exit 0
    fi
fi

log_info "环境变量配置检查通过 ✓"
echo ""

# 步骤3: 安装Docker到服务器
log_step "步骤3: 检查并安装Docker环境"
log_info "正在检查服务器Docker安装情况..."

remote_exec "
    # 检查Docker
    if command -v docker &> /dev/null; then
        echo 'Docker已安装,版本:'
        docker --version
    else
        echo '正在安装Docker...'
        curl -fsSL https://get.docker.com -o get-docker.sh
        sh get-docker.sh
        systemctl start docker
        systemctl enable docker
        echo 'Docker安装完成'
    fi
    
    # 检查Docker Compose
    if command -v docker-compose &> /dev/null; then
        echo 'Docker Compose已安装,版本:'
        docker-compose --version
    else
        echo '正在安装Docker Compose...'
        curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)\" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
        echo 'Docker Compose安装完成'
    fi
"

log_info "Docker环境准备完成 ✓"
echo ""

# 步骤4: 创建部署目录
log_step "步骤4: 创建部署目录"
remote_exec "
    mkdir -p $DEPLOY_PATH
    echo '部署目录: $DEPLOY_PATH'
"
log_info "部署目录已创建 ✓"
echo ""

# 步骤4.5: 部署前备份数据库
log_step "步骤4.5: 部署前备份数据库"
log_info "正在备份生产数据库..."

remote_exec "
    # 检查数据库容器是否运行
    if docker ps --format '{{.Names}}' | grep -q 'content-creation-postgres-prod'; then
        # 执行备份
        /root/backup_db.sh
        echo '数据库备份完成'
    else
        echo '数据库容器未运行，跳过备份'
    fi
"

log_info "数据库备份完成 ✓"
echo ""

# 步骤5: 上传项目文件
log_step "步骤5: 上传项目文件到服务器"

log_info "正在上传后端代码..."
# 使用rsync排除Python缓存和不需要的文件
sshpass -p "$SERVER_PASSWORD" rsync -avz --progress \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='*.db' \
    --exclude='*.sqlite' \
    --exclude='*.log' \
    --exclude='venv' \
    --exclude='.pytest_cache' \
    --exclude='test-results' \
    -e "ssh -o StrictHostKeyChecking=no" \
    content-creation-backend/ "$SERVER_USER@$SERVER_IP:$DEPLOY_PATH/content-creation-backend/"

log_info "正在上传前端代码..."
# 使用rsync排除node_modules和其他不需要的文件
log_info "使用rsync上传(自动排除node_modules)..."
sshpass -p "$SERVER_PASSWORD" rsync -avz --progress \
    --exclude='node_modules' \
    --exclude='dist' \
    --exclude='.git' \
    --exclude='test-results' \
    --exclude='playwright-report' \
    --exclude='*.log' \
    -e "ssh -o StrictHostKeyChecking=no" \
    content-creation-frontend/ "$SERVER_USER@$SERVER_IP:$DEPLOY_PATH/content-creation-frontend/"

log_info "正在上传配置文件..."
upload_file "docker-compose.prod.yml" "$DEPLOY_PATH/"
upload_file "nginx-custom.conf" "$DEPLOY_PATH/"
upload_file ".env" "$DEPLOY_PATH/"

log_info "项目文件上传完成 ✓"
echo ""

# 步骤6: 配置防火墙
log_step "步骤6: 配置防火墙"
log_info "正在配置防火墙规则..."

remote_exec "
    # 检查firewalld是否运行
    if systemctl is-active --quiet firewalld; then
        echo '配置firewalld规则...'
        firewall-cmd --permanent --add-port=8001/tcp 2>/dev/null || true
        firewall-cmd --permanent --add-port=8002/tcp 2>/dev/null || true
        firewall-cmd --reload 2>/dev/null || true
        echo 'firewalld配置完成'
    else
        echo 'firewalld未运行,跳过配置'
    fi
"

log_info "防火墙配置完成 ✓"
echo ""

# 步骤7: 部署应用
log_step "步骤7: 部署应用"
log_info "正在构建和启动Docker容器..."
log_warn "这可能需要几分钟,请耐心等待..."
echo ""

remote_exec "
    cd $DEPLOY_PATH
    
    # 停止旧容器
    docker-compose -f docker-compose.prod.yml down 2>/dev/null || true
    
    # 构建镜像
    echo '正在构建Docker镜像...'
    if [ \"\${NO_CACHE:-0}\" = '1' ]; then
        echo '使用 NO_CACHE=1，禁用构建缓存（可能会触发 apt/npm/pip 网络下载）'
        docker-compose -f docker-compose.prod.yml build --no-cache
    else
        echo '使用构建缓存（推荐：避免服务器无外网导致构建失败）'
        docker-compose -f docker-compose.prod.yml build
    fi

    # 先启动依赖（数据库/Redis），再跑迁移，最后再启动业务容器
    # 原因：如果先启动 backend 再迁移，可能出现“后端已接流量但表结构未升级”导致 500（例如 projects.reference_image_urls 缺失）
    echo '启动基础依赖服务（postgres/redis）...'
    docker-compose -f docker-compose.prod.yml up -d postgres redis

    # 校验：确认镜像内已包含最新迁移文件（避免“本地已改但镜像未更新/旧镜像”）
    echo '校验迁移文件是否为最新版本...'
    docker-compose -f docker-compose.prod.yml run --rm --no-deps backend bash -lc 'test -f /app/alembic/versions/3a1c9d7f0b12_add_reference_image_urls_to_projects.py'

    # 运行数据库迁移（强制）
    # 说明：create_all 只会创建缺失表，不会为已有表补充新字段；
    # 生产环境迭代升级必须执行迁移以避免 500（例如 projects.reference_image_urls 缺失）。
    echo '执行数据库迁移（alembic upgrade head）...'
    docker-compose -f docker-compose.prod.yml run --rm --no-deps backend bash -lc 'cd /app && alembic upgrade head'
    echo '数据库迁移完成'

    # 迁移后做一次硬校验：确认关键字段已存在（否则直接失败，避免线上继续 500）
    echo '校验 projects.reference_image_urls 字段是否存在...'
    if [ \"$(docker-compose -f docker-compose.prod.yml exec -T postgres sh -lc \"psql -U \\\"${POSTGRES_USER:-postgres}\\\" -d \\\"${POSTGRES_DB:-content_creation}\\\" -tAc \\\"select 1 from information_schema.columns where table_name='projects' and column_name='reference_image_urls'\\\"\" | tr -d '[:space:]')\" != \"1\" ]; then
        echo 'ERROR: 数据库迁移后仍未检测到 projects.reference_image_urls 字段。请检查 alembic 版本链与执行日志。'
        exit 1
    fi
    echo '字段校验通过'

    # 启动服务
    echo '正在启动服务...'
    docker-compose -f docker-compose.prod.yml up -d
    
    # 等待服务启动
    echo '等待服务启动...'
    sleep 30
    
    # 显示容器状态
    echo '容器状态:'
    docker-compose -f docker-compose.prod.yml ps
"

log_info "应用部署完成 ✓"
echo ""

# 步骤8: 验证部署
log_step "步骤8: 验证部署"
log_info "正在进行健康检查..."

sleep 5

# 测试前端
if remote_exec "curl -f http://localhost:8001/health 2>/dev/null" &> /dev/null; then
    log_info "前端健康检查: ✓"
else
    log_warn "前端健康检查: ✗ (可能需要更多时间启动)"
fi

# 测试后端
if remote_exec "curl -f http://localhost:8002/health 2>/dev/null" &> /dev/null; then
    log_info "后端健康检查: ✓"
else
    log_warn "后端健康检查: ✗ (可能需要更多时间启动)"
fi

echo ""

# 完成
echo "================================================================"
log_info "部署完成! 🎉"
echo "================================================================"
echo ""
echo "服务地址:"
echo "  前端: http://$SERVER_IP:8001"
echo "  后端API: http://$SERVER_IP:8002"
echo "  API文档: http://$SERVER_IP:8002/docs"
echo ""
echo "管理命令(SSH到服务器后执行):"
echo "  cd $DEPLOY_PATH"
echo "  docker-compose -f docker-compose.prod.yml ps        # 查看状态"
echo "  docker-compose -f docker-compose.prod.yml logs -f   # 查看日志"
echo "  docker-compose -f docker-compose.prod.yml restart   # 重启服务"
echo ""
echo "远程查看日志:"
echo "  ssh root@$SERVER_IP \"cd $DEPLOY_PATH && docker-compose -f docker-compose.prod.yml logs -f\""
echo ""
log_info "提示: 如果服务未正常启动,请SSH到服务器查看详细日志"
log_info "      ssh root@$SERVER_IP"
echo ""
log_warn "重要: 请在阿里云控制台的安全组中开放8001和8002端口"

