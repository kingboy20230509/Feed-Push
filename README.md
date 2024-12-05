# Feed-Push: Telegram RSS Bot
Feed-Push可以将你关注的网站或博客的最新更新自动通过Bot进行推送，实现信息的即时传递。  
**本机部署一键脚本：**
```
curl -sS -O https://raw.githubusercontent.com/ecouus/Feed-Push/refs/heads/main/bot_deploy.sh && sudo chmod +x bot_deploy.sh && ./bot_deploy.sh
```
  
**Docker部署：**
```
docker run -d \
  --name telegram-rss-bot \
  --restart always \
  -v $(pwd)/data:/app/data \
  -e TELEGRAM_BOT_TOKEN="bot_token" \
  -e ROOT_ID="admin_id" \
  -e WHITELIST_GROUP_ID="-123456" \
  -e ENABLE_GROUP_VERIFY="false" \
  -e UPDATE_INTERVAL="300" \
  ecouus/telegram-rss-bot:latest
```
**输入/help获取指令帮助！**  
- **TELEGRAM_BOT_TOKEN**: 在 Telegram 上通过 @BotFather 创建 Bot 时获得的 Token，用于与 Telegram API 进行交互。
- **ROOT_ID**: 你的 Telegram 用户 ID，通常用于管理权限。可以通过 @userinfobot 获取。
- **WHITELIST_GROUP_ID**: 群组 ID，用于验证用户是否在指定群组中，进群验证功能启用时需要设置。
- **ENABLE_GROUP_VERIFY**: 是否启用群组验证功能。设置为 `false` 时，不启用群组验证；设置为 `true` 时，启用。
- **UPDATE_INTERVAL**: RSS 源更新的时间间隔，单位为秒，默认为300s。
- 
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
**修改脚本后**
```
sudo systemctl restart telegram_rss_bot && sudo systemctl status telegram_rss_bot
```
若修改了.service文件则需运行
```
sudo systemctl daemon-reload
```
## License
This project is licensed under the GNU General Public License v3.0.  
See the [LICENSE](LICENSE) file for details.
