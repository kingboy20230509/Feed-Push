# Feed-Push: Telegram RSS Bot
Feed-Push 是一个用于将 RSS 源推送到 Telegram 群组或私人聊天的机器人。通过这个工具，你可以将你关注的网站或博客的最新更新自动通过Bot进行推送，实现信息的即时传递。
运行一键安装脚本
快速安装和配置 Telegram RSS Bot
```
curl -sS -O https://raw.githubusercontent.com/ecouus/Feed-Push/refs/heads/main/bot_deploy.sh && sudo chmod +x bot_deploy.sh && ./bot_deploy.sh
```
**输入/help获取指令帮助！**  
**默认抓取间隔时间为300s，时间过短可能会触发反爬机制导致ip被相应源封禁。默认关闭白名单模式和进群验证。**
- **Bot Token**  
    在 Telegram 上通过 BotFather 创建新 Bot，输入 `/newbot` 后按提示操作，获得 Token，并填入脚本中的 `TELEGRAM_BOT_TOKEN`。
- **管理员 ID**  
    使用 @userinfobot 获取你的 Telegram 用户 ID，填入脚本中的 `ROOT_ID`。
- **群组 ID**  
    用于验证用户是否已加入指定群组，开启进群验证功能时，需设置群组 ID 通过 `group_verify` 控制。
  
### 基础指令
- **`/start`**：注册并开始使用。
- **`/help`**：查看帮助信息。
- **`/add_rss <URL>`**：添加 RSS 订阅源。
- **`/list_rss`**：查看已添加的 RSS 源。
- **`/list <编号>`**：查看指定 RSS 源的规则和关键词。
- **`/add <编号> <关键词>`**：为指定 RSS 源添加关键词或规则。
- **`/rm <编号> <关键词编号>`**：删除指定 RSS 源的关键词。
- **`/rm_rss <编号>`**：删除指定的 RSS 源。


## 管理员命令
- **`/add_user <用户ID>`**：将用户添加到白名单。
- **`/whitelist <on/off>`**：开启或关闭白名单模式。
- **`/group_verify <on/off>`**：开启或关闭进群验证。  

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

