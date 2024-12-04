#!/bin/bash

# 检查是否为 root 用户
if [ "$(id -u)" != "0" ]; then
    echo "请使用 sudo 或 root 权限运行此脚本！"
    exit 1
fi

# 更新系统
echo "更新系统..."
apt update && apt upgrade -y

# 安装 Python 及工具
echo "安装 Python3 和 pip..."
apt install python3 python3-pip python3-venv wget -y

# 创建项目目录
echo "创建项目目录 /home/Python_project/telegram_rss_bot..."
mkdir -p /home/Python_project/telegram_rss_bot && cd /home/Python_project/telegram_rss_bot

# 创建虚拟环境
echo "创建 Python 虚拟环境..."
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "安装所需的 Python 库..."
pip install python-telegram-bot[ext,job-queue] feedparser requests

# 下载 Python 脚本
echo "下载 telegram_rss_bot.py 脚本..."
wget -O telegram_rss_bot.py https://raw.githubusercontent.com/ecouus/Feed-Push/refs/heads/main/telegram_rss_bot.py

# 获取用户输入
echo "请输入 Telegram Bot Token（通过@BotFather创建）:"
read TELEGRAM_BOT_TOKEN
echo "请输入管理员的 Telegram 用户 ID (可通过@userinfobot获取):"
read ROOT_ID
echo "请输入更新间隔时间（秒，默认为 300）："
read INTERVAL
INTERVAL=${INTERVAL:-300}  # 默认值为 300

# 询问是否启用白名单
echo "请输入白名单群组 ID（如果不启用白名单，直接回车）："
read WHITELIST_GROUP_ID

if [ -z "$WHITELIST_GROUP_ID" ]; then
    # 如果没有输入群组ID，关闭白名单
    ENABLE_WHITELIST="False"
else
    # 如果输入了群组ID，开启白名单
    ENABLE_WHITELIST="True"
fi

# 替换 Python 脚本中的占位符
sed -i "s|TELEGRAM_BOT_TOKEN = \"\"|TELEGRAM_BOT_TOKEN = \"$TELEGRAM_BOT_TOKEN\"|g" telegram_rss_bot.py
sed -i "s|ROOT_ID = \"\"|ROOT_ID = \"$ROOT_ID\"|g" telegram_rss_bot.py
sed -i "s|application.job_queue.run_repeating(check_new_posts, interval=300, first=0)|application.job_queue.run_repeating(check_new_posts, interval=$INTERVAL, first=0)|g" telegram_rss_bot.py
sed -i "s|ENABLE_WHITELIST = \"\"|ENABLE_WHITELIST = \"$ENABLE_WHITELIST\"|g" telegram_rss_bot.py
sed -i "s|WHITELIST_GROUP_ID = \"\"|WHITELIST_GROUP_ID = \"$WHITELIST_GROUP_ID\"|g" telegram_rss_bot.py

# 创建 systemd 服务文件
echo "创建 systemd 服务文件..."
cat << EOF > /etc/systemd/system/telegram_rss_bot.service
[Unit]
Description=Telegram RSS Bot
After=network.target

[Service]
User=root
WorkingDirectory=/home/Python_project/telegram_rss_bot
ExecStart=/home/Python_project/telegram_rss_bot/venv/bin/python /home/Python_project/telegram_rss_bot/telegram_rss_bot.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# 重新加载 systemd 配置
systemctl daemon-reload

# 启动服务并设置开机启动
echo "启动 Telegram RSS Bot 服务..."
systemctl start telegram_rss_bot
systemctl enable telegram_rss_bot

# 显示服务状态
systemctl status telegram_rss_bot

echo "部署完成，Bot 应该已启动并运行。"
