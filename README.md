# Feed-Push: Telegram RSS Bot
Feed-Push 是一个用于将 RSS 源推送到 Telegram 群组或私人聊天的机器人。通过这个工具，你可以将你关注的网站或博客的最新更新自动通过Bot进行推送，实现信息的即时传递。
运行一键安装脚本
快速安装和配置 Telegram RSS Bot
```
curl -sS -O https://raw.githubusercontent.com/ecouus/Feed-Push/refs/heads/main/bot_deploy.sh && sudo chmod +x bot_deploy.sh && ./bot_deploy.sh
```
**默认抓取间隔时间为300s，时间过短可能会触发反爬机制导致ip被封禁。**
- Bot Token  
在 BotFather 上创建一个新的 Telegram Bot，并获取 Bot Token。
打开 Telegram，搜索并启动 BotFather。
输入 /newbot 并按照提示操作。
创建完毕后，你将收到一个 Token，记下它，用于配置脚本中的 TELEGRAM_BOT_TOKEN。
- 管理员 ID  
管理员 ID 是用于管理机器人的 Telegram 用户 ID。你可以通过以下方法获取你的 ID：
搜索并启动 userinfobot。
发送任何消息后，机器人会回复你的 Telegram 用户 ID。
将该 ID 填入脚本中的 ROOT_ID。
- 目标群组 ID  
目标群组 ID 验证用户是否进入指定群组,进群才能使用,此功能可以通过/whitelist off关闭

### **服务管理命令**
- **启动服务**：
```
sudo systemctl start telegram_rss_bot
```
- **停止服务**：
```
sudo systemctl stop telegram_rss_bot
```
- **重启服务**：
```
sudo systemctl restart telegram_rss_bot
```
- **查看服务状态**：
```
sudo systemctl status telegram_rss_bot
```
- **实时查看服务日志**：
```
journalctl -u telegram_rss_bot -f
```
---

**修改脚本后**
```
sudo systemctl restart telegram_rss_bot && sudo systemctl status telegram_rss_bot
```


若修改了.service文件则需运行
```
sudo systemctl daemon-reload
```

### 基础指令
- **`/start`**：注册并开始使用。
- **`/add_rss <URL>`**：添加 RSS 订阅源。
- **`/list_rss`**：查看已添加的 RSS 源。
- **`/list <编号>`**：查看指定 RSS 源的规则和关键词。
- **`/add <编号> <关键词>`**：为指定 RSS 源添加关键词或规则。
- **`/rm <编号> <关键词编号>`**：删除指定 RSS 源的关键词。
- **`/rm_rss <编号>`**：删除指定的 RSS 源。
- **`/help`**：查看帮助信息。

## 管理员命令
- **`/add_user <用户ID>`**：将用户添加到白名单。
- **`/whitelist <on/off>`**：开启或关闭白名单模式。
