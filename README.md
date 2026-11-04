# Feed-Push: Telegram RSS Bot
## 🧐 Features
Feed-Push可以将你关注的网站或博客的最新更新自动通过Bot进行推送，实现信息的即时传递。  
[常用源地址](https://github.com/weekend-project-space/top-rss-list)
## 🛠️ Installation Steps
### 本机部署一键脚本：
```
curl -sS -O https://raw.githubusercontent.com/kingboy20230509/Feed-Push/refs/heads/main/bot_deploy.sh && sudo chmod +x bot_deploy.sh && ./bot_deploy.sh
```
  
### Docker部署（构建本仓库代码）：
```bash
git clone https://github.com/kingboy20230509/Feed-Push.git
cd Feed-Push
cp .env.example .env
# 编辑 .env，填写 Token、管理员 ID 等配置
nano .env
docker compose up -d --build
docker compose logs --tail=100 -f
```

镜像由本仓库的 `telegram_rss_bot.py` 构建，数据保存在宿主机 `./data/`。
不需要开放入站端口，服务器需要能够访问 Telegram 和所订阅的 RSS 网站。

**原 systemd 部署迁移请先阅读 [Docker 迁移说明](DOCKER_MIGRATION.md)**，
先准备镜像，再停止旧服务，最后复制数据并启动容器，避免同一 Bot 同时运行两份。

### 同一台服务器运行多个独立 Bot

每个实例使用不同的 BotFather Token，拥有独立配置、容器、订阅、用户、白名单和推送缓存。
无需复制项目或修改 Python 代码；更新代码后各实例仍读取各自的配置和数据。

```bash
bash bot-instance.sh init bot1
nano instances/bot1/.env  # 填写第一个 Token、ROOT_ID 等
bash bot-instance.sh up bot1

bash bot-instance.sh init bot2
nano instances/bot2/.env  # 填写另一个 Token、ROOT_ID 等
bash bot-instance.sh up bot2
```

`init` 不覆盖已有配置。配置保存在 `instances/<实例名>/.env`，数据保存在
`instances/<实例名>/data/`，整个 `instances/` 已排除在 Git 和镜像构建上下文之外。
新实例默认使用空数据目录，互不复制订阅或缓存。各实例的 `BOT_DATA_DIR` 必须保持不同。
不要把同一个 Token 同时用于两个运行实例。

```bash
bash bot-instance.sh status bot1
bash bot-instance.sh logs bot2
bash bot-instance.sh stop bot2  # 只停止 bot2
bash bot-instance.sh restart bot2  # 应用该实例修改后的配置
git pull
bash bot-instance.sh up bot1  # 更新代码后，逐个重新构建并部署所需实例
bash bot-instance.sh up bot2
```

从旧 Docker 单实例迁移时，先停止旧容器，再把四个数据文件复制到
`instances/bot1/data/`，把原配置填入 `instances/bot1/.env`，然后启动 bot1。
镜像升级不会覆盖这些宿主机文件。旧版固定容器名已取消，容器名由各实例的 Compose 项目名生成。

**输入/help获取指令帮助！**  
- **TELEGRAM_BOT_TOKEN**: 在 Telegram 上通过 @BotFather 创建 Bot 时获得的 Token，用于与 Telegram API 进行交互。
- **ROOT_ID**: 你的 Telegram 用户 ID，通常用于管理权限。可以通过 @userinfobot 获取。
- **WHITELIST_GROUP_ID**: 群组 ID，用于验证用户是否在指定群组中，进群验证功能启用时需要设置。
- **ENABLE_GROUP_VERIFY**: 是否启用群组验证功能。设置为 `false` 时，不启用群组验证；设置为 `true` 时，启用。
- **UPDATE_INTERVAL**: RSS 源更新的时间间隔，单位为秒，默认为300s。
Docker 修改参数：编辑 `.env` 后执行 `docker compose up -d`；仅执行 `restart` 不会应用新的环境变量。
### 基础指令
- **`/start`**：注册并开始使用。
- **`/help`**：查看帮助信息。
- **`/add_rss <URL>`**：添加 RSS 订阅源。
- **`/list_rss`**：查看已添加的 RSS 源。
- **`/list <编号>`**：查看指定 RSS 源的规则和关键词。
- **`/add <编号> <关键词>`**：为指定 RSS 源添加关键词或规则。
- **`/rm <编号> <关键词编号>`**：删除指定 RSS 源的关键词。
- **`/rm_rss <编号>`**：删除指定的 RSS 源。


### 管理员命令
- **`/add_user <用户ID>`**：将用户添加到白名单。
- **`/whitelist <on/off>`**：开启或关闭白名单模式。
- **`/group_verify <on/off>`**：开启或关闭进群验证。  

### 本地部署管理命令
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
## 💻 Built with
- [Python](https://www.python.org/)
- [Docker](https://www.docker.com/)
## 🙇 Sponsors  
Null  
![ecouus's GitHub stats](https://github-readme-stats.vercel.app/api?username=ecouus&show_icons=true)  
## License
This project is licensed under the GNU General Public License v3.0.  
See the [LICENSE](LICENSE) file for details.
