# 从 systemd 迁移 Telegram Bot 到 Docker

适用于通过 `bot_deploy.sh` 安装的 Telegram 版。迁移保留 JSON/TXT 格式，
订阅、关键词、正则匹配、白名单、推送和去重函数不变。
配置改为支持环境变量，Docker 数据目录为 `/app/data`，本机默认仍为当前目录。

## 1. 核对旧部署

在原 Linux 服务器执行：

```bash
sudo systemctl cat telegram_rss_bot
```

确认 `WorkingDirectory` 和 `ExecStart`。下面假设未修改默认目录。
安装好 Docker Engine 和 Compose 插件后，进入 root shell，在同一个终端执行后续命令：

```bash
sudo -i
OLD_DIR=/home/Python_project/telegram_rss_bot
NEW_DIR=/opt/feed-push-docker
"$OLD_DIR/venv/bin/python" --version
docker version
docker compose version
```

此阶段保持旧服务运行。不要使用旧安装脚本的“卸载”选项：它会删除项目和数据。

## 2. 准备自己的镜像

`NEW_DIR` 应是全新的目录，不覆盖已有部署：

```bash
umask 077
git clone https://github.com/kingboy20230509/Feed-Push.git "$NEW_DIR"
cd "$NEW_DIR"
cp .env.example .env
"$OLD_DIR/venv/bin/python" -m pip freeze > requirements.lock.txt
nano .env
```

将旧脚本中的实际配置填入 `.env`：

| 旧脚本中的配置 | `.env` 配置 |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | `TELEGRAM_BOT_TOKEN` |
| `ROOT_ID` | `ROOT_ID` |
| `WHITELIST_GROUP_ID` | `WHITELIST_GROUP_ID` |
| `ENABLE_GROUP_VERIFY` | `ENABLE_GROUP_VERIFY`，填 `true` 或 `false` |
| `run_repeating(..., interval=数值, ...)` | `UPDATE_INTERVAL`，单位秒 |

同时设置 `REQUIREMENTS_FILE=requirements.lock.txt`，并将 `PYTHON_IMAGE` 改为与旧环境
一致的 Python 版本，例如旧环境为 Python 3.11.x 时使用 `python:3.11-slim`。
需要精确补丁版本时，可选择存在的对应镜像标签。不要在本次迁移中顺便升级 Python 或依赖。

仓库原先没有依赖锁定文件，`requirements.txt` 沿用原安装脚本的依赖声明。
迁移时使用服务器导出的锁定文件；若包含本地路径或私有依赖，须先保证构建环境能够获取它们。
Docker 的系统库和网络与宿主机仍可能不同，需完成后续验证。

`.env` 和旧脚本可能包含 Token，请仅在服务器本地查看和编辑。
若旧脚本还有未提交的业务修改，先将这些修改合入本次代码，再构建镜像；仓库无法自动包含服务器独有的改动。

```bash
chmod 600 .env
docker compose config --quiet
docker compose build
```

只构建镜像，不启动 Bot。构建失败时保持旧服务运行，先处理错误。

## 3. 停旧服务，备份并复制数据

```bash
systemctl disable --now telegram_rss_bot
systemctl is-active telegram_rss_bot
```

应显示 `inactive`，确认旧进程退出后继续。保留服务文件和旧目录以便回滚。

```bash
cd "$NEW_DIR"
mkdir -p backups data
chmod 700 backups data
tar -czf "backups/legacy-$(date +%Y%m%d-%H%M%S).tar.gz" -C "$OLD_DIR" .
```

备份成功后复制以下四个文件：

```bash
for name in user_data.json allowed_users.json whitelist_status.json rss_cache3.txt; do
  if [ -f "$OLD_DIR/$name" ]; then
    cp -p "$OLD_DIR/$name" "$NEW_DIR/data/$name"
    cmp "$OLD_DIR/$name" "$NEW_DIR/data/$name"
  else
    printf '旧目录中不存在：%s，请核对是否符合实际使用情况\n' "$name"
  fi
done
```

`user_data.json` 保存用户、订阅和规则；`allowed_users.json` 保存白名单；
`whitelist_status.json` 保存白名单开关；`rss_cache3.txt` 保存去重记录。
有些功能未使用时对应文件可能不存在。如果已有订阅却没有 `user_data.json`，先核对目录。
不要重置去重文件，否则可能重复推送历史内容。

## 4. 启动与验证

```bash
cd "$NEW_DIR"
docker compose up -d
docker compose ps
docker compose logs --tail=100 -f
```

按 Ctrl+C 退出日志查看，Bot 会继续运行。
在 Telegram 中用 `/list_rss` 和 `/list 1` 检查订阅、关键词和规则，验证管理员及白名单权限，
再等待至少一个抓取周期确认推送正常。不要同时启动旧服务。

`/group_verify on/off` 原本只修改内存状态，重启后恢复配置值；迁移时应将当前期望的值填入
`.env` 的 `ENABLE_GROUP_VERIFY`。`/whitelist on/off` 则通过 JSON 文件持久化，迁移原文件即可。

宿主机的 `data/` 挂载到容器 `/app/data`，重建容器会继续使用这些文件。
备份应包含 `data/`、`.env` 和依赖锁定文件，复制数据前先停止 Bot，避免复制到正在写入的文件。

## 5. 管理和回滚

在新项目目录执行：

```bash
docker compose stop                 # 停止
docker compose up -d                # 启动，或应用修改后的 .env
docker compose restart             # 用原配置重启
docker compose up -d --build        # 更新源码后重新构建并启动
docker compose logs --tail=100 -f   # 查看日志
```

如需恢复 systemd，先停止容器：

```bash
cd "$NEW_DIR"
docker compose stop
```

容器运行期间可能新增订阅或去重记录，回滚前将最新文件复制回旧目录。
复制前可将旧目录再备份一份；不要在旧进程运行时覆盖数据。

```bash
for name in user_data.json allowed_users.json whitelist_status.json rss_cache3.txt; do
  if [ -f "$NEW_DIR/data/$name" ]; then
    cp -p "$NEW_DIR/data/$name" "$OLD_DIR/$name"
  fi
done
systemctl enable --now telegram_rss_bot
systemctl status telegram_rss_bot --no-pager
```

无需删除 Docker 数据或旧目录。确认稳定运行后，再按实际情况整理备份。
