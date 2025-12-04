# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Leaflow 自动签到控制面板 - 基于 Python Flask 的 Web 应用，用于自动化 Leaflow 网站每日签到任务。支持多账户管理、定时签到、多平台通知（Telegram、企业微信、WxPusher、钉钉）。

## 开发命令

```bash
# 安装依赖
pip install -r requirements.txt

# 运行应用（默认端口 8181）
python app.py

# 带环境变量运行
PORT=8181 ADMIN_USERNAME=admin ADMIN_PASSWORD=yourpass python app.py
```

## Docker 部署

```bash
# 构建镜像
docker build -t leaflow-auto .

# 运行容器
docker run -d -p 8181:8181 \
  -e ADMIN_USERNAME=admin \
  -e ADMIN_PASSWORD=your_password \
  -v /path/to/data:/app/data \
  leaflow-auto
```

## 代码架构

### 目录结构

```
leaflow-hub/
├── app.py                 # Flask 主入口
├── config.py              # 配置管理、环境变量解析
├── database/
│   ├── cache.py          # AccountCache(5min), DataCache(1min)
│   └── db.py             # Database 单例（SQLite/MySQL 双支持）
├── services/
│   ├── notification_service.py  # 多渠道通知服务
│   ├── checkin_service.py       # 签到核心逻辑
│   └── scheduler_service.py     # 后台调度器（scheduler 单例）
├── routes/
│   ├── auth.py           # 登录、验证、仪表盘
│   ├── accounts.py       # 账户 CRUD
│   ├── checkin.py        # 签到操作
│   └── notification.py   # 通知设置
├── utils/
│   ├── auth.py           # JWT 认证装饰器 @token_required
│   └── cookie_parser.py  # Cookie 解析（支持 JSON/分号分隔格式）
└── static/               # 前端静态文件
```

### 关键设计模式

- **单例模式**: `db`、`scheduler`、`account_cache`、`data_cache` 在模块级初始化
- **Blueprint 注册**: `routes/__init__.py` 的 `register_blueprints()` 统一注册路由
- **指数退避重试**: MySQL 连接失败时使用 3s→6s→12s→24s 重试策略
- **智能 Keepalive**: MySQL 连接保活（5 分钟检查，30 分钟实际 ping）
- **时区**: 硬编码为 `Asia/Shanghai`（北京时间）

### 核心模块职责

| 模块 | 职责 |
|------|------|
| `database/db.py` | 数据库连接、指数退避重试、表初始化、SQL 执行、MySQL 保活线程 |
| `database/cache.py` | 线程安全缓存：AccountCache(5min) + DataCache(1min) |
| `services/scheduler_service.py` | 后台线程调度器，在配置的时间窗口内执行签到 |
| `services/checkin_service.py` | HTTP 请求签到、认证验证、CSRF 处理 |
| `services/notification_service.py` | Telegram/企业微信/WxPusher/钉钉通知 |

### 数据库表

- `accounts`: 账户凭证、签到时间窗口配置、重试次数
- `checkin_history`: 签到结果日志（含重试次数）
- `notification_settings`: 各通知渠道配置（含自定义 API 地址）

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PORT` | 8181 | 服务端口 |
| `ADMIN_USERNAME` | admin | 登录用户名 |
| `ADMIN_PASSWORD` | admin123 | 登录密码 |
| `JWT_SECRET_KEY` | 自动生成 | JWT 签名密钥 |
| `MYSQL_DSN` | - | MySQL 连接字符串（格式: `mysql://user:pass@host:port/db`） |
| `MAX_MYSQL_RETRIES` | 12 | MySQL 重连次数 |
| `DATA_DIR` | ./data 或 /app/data | 数据目录（Docker 中为 /app/data） |

### API 接口

需要 `Authorization: Bearer <token>` 请求头：

- `POST /api/login` - 登录获取 JWT
- `GET /api/verify` - 验证 token
- `GET /api/dashboard` - 仪表盘统计
- `GET/POST /api/accounts` - 账户列表/添加
- `PUT/DELETE /api/accounts/:id` - 更新/删除账户
- `POST /api/checkin/manual/:id` - 手动触发签到
- `POST /api/checkin/clear` - 清空签到记录
- `GET/PUT /api/notification` - 通知设置
- `POST /api/test/notification` - 测试通知

### 模块依赖关系

```
app.py
├── config.py (环境变量、日志、时区)
├── routes/ ──────► utils/auth.py (@token_required)
│                 └► database/db.py (db 单例)
│                 └► services/*
└── services/
    ├── scheduler_service.py ─► checkin_service.py
    │                        └► database/{db.py, cache.py}
    ├── checkin_service.py ───► notification_service.py
    └── notification_service.py ► database/db.py
```

## CI/CD

GitHub Actions (`.github/workflows/docker-image.yml`):
- 触发: main/master 分支推送、tag 推送、PR
- 构建: 多平台 Docker 镜像（linux/amd64, linux/arm64）
- 推送: GHCR（带时间戳标签 + latest）
