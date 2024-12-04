#!/bin/bash

# 更新系统
echo "Updating system..."
sudo apt update && sudo apt upgrade -y

# 安装 Python 和工具
echo "Installing Python and required packages..."
sudo apt install python3 python3-pip python3-venv curl -y

# 创建项目目录
echo "Creating project directory..."
mkdir -p /home/Python_project/telegram_rss_bot && cd /home/Python_project/telegram_rss_bot

# 创建虚拟环境
echo "Setting up virtual environment..."
python3 -m venv venv

# 激活虚拟环境
echo "Activating virtual environment..."
source venv/bin/activate

# 安装依赖
echo "Installing required Python packages..."
pip install python-telegram-bot[ext,job-queue] feedparser requests

# 下载 Telegram RSS Bot 脚本
echo "Downloading the Telegram RSS bot script..."
curl -o telegram_rss_bot.py https://raw.githubusercontent.com/ecouus/Feed-Push/refs/heads/main/telegram_rss_bot.py

# 提示用户输入配置
echo "Please enter the following information to configure the bot script:"
read -p "Enter your Telegram Bot Token: " TELEGRAM_BOT_TOKEN
read -p "Enter your Telegram user ID (admin_id): " ROOT_ID
read -p "Enter your target Telegram group ID (must be a negative number): " TARGET_GROUP_ID

# 替换脚本中的占位符
echo "Configuring the Telegram bot script..."
sed -i "s|TELEGRAM_BOT_TOKEN = \"Telegram_Bot_Token\"|TELEGRAM_BOT_TOKEN = \"$TELEGRAM_BOT_TOKEN\"|" telegram_rss_bot.py
sed -i "s|ROOT_ID = admin_id|ROOT_ID = $ROOT_ID|" telegram_rss_bot.py
sed -i "s|TARGET_GROUP_ID = group_id|TARGET_GROUP_ID = $TARGET_GROUP_ID|" telegram_rss_bot.py

# 创建 systemd 服务文件
echo "Creating systemd service for the bot..."
sudo bash -c 'cat > /etc/systemd/system/telegram_rss_bot.service <<EOF
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
EOF'

# 重新加载 systemd 配置
echo "Reloading systemd configuration..."
sudo systemctl daemon-reload

# 启动服务
echo "Starting the bot service..."
sudo systemctl start telegram_rss_bot

# 设置开机启动
echo "Enabling the service to start on boot..."
sudo systemctl enable telegram_rss_bot

# 输出服务状态
echo "Checking the service status..."
sudo systemctl status telegram_rss_bot

echo "Installation complete! The Telegram RSS bot should now be running."
