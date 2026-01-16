# 前端Docker镜像构建文件
# 多阶段构建: 构建阶段 + Nginx服务阶段

# 阶段1: 依赖安装和构建
FROM node:20-alpine as builder

# 设置工作目录
WORKDIR /app

# 复制package文件
COPY package*.json ./

# 安装所有依赖(包括devDependencies,构建时需要)
RUN npm ci --ignore-scripts

# 复制源代码
COPY . .

# 构建生产版本
RUN npm run build

# 阶段2: Nginx服务
FROM nginx:1.25-alpine as production

# 复制自定义Nginx配置
COPY nginx.conf /etc/nginx/nginx.conf
COPY nginx-site.conf /etc/nginx/conf.d/default.conf

# 从构建阶段复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 创建日志目录
RUN mkdir -p /var/log/nginx && \
    chown -R nginx:nginx /var/log/nginx

# 暴露端口
EXPOSE 80

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/health || exit 1

# 启动Nginx
CMD ["nginx", "-g", "daemon off;"]

