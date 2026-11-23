# OVH 补货 RSS

使用 [StockHawk for OVH](https://github.com/super888-png/stockhawk-ovh) 同一公开库存 API，并对照市场的公开目录校验内存和硬盘选项，将套餐、硬件配置和机房的补货记录转换为 RSS 2.0。首次查询会收录当前可用库存。持续有货时保持原条目，确认售罄后再次有货时生成新 GUID。查询失败会保留该套餐的上次状态，历史保留最近 200 条。

库存和交付时效以 API 回报为准，条目链接打开对应市场的 OVH 产品页，实际可选配置以官网为准。服务只需网络访问 OVH 的公开接口。

## 在 Feed-Push 订阅

启动下方的 Docker 服务后，在 Telegram 私聊里发送 `/add_rss http://服务器地址:8787/rss.xml`，然后用 `/list_rss` 查到该订阅的编号。再发送 `/add <订阅编号> 补货` 匹配全部补货条目，或把关键词换成 `24ska012`、`24sk40`、`27skle03`、`GRA` 等。

GitHub 提供 [首份真实库存快照](https://raw.githubusercontent.com/kingboy20230509/Feed-Push/ovh-stock-feed/rss.xml)，可用于验证 Feed-Push 的订阅和关键词匹配。持续更新请订阅 Docker 实例的地址。

## Docker 自部署

```bash
git clone https://github.com/kingboy20230509/Feed-Push.git
cd Feed-Push/ovh-stock-rss
docker compose up -d --build
curl -fsS http://localhost:8787/rss.xml
```

把 Feed-Push 能访问的 `http://服务器地址:8787/rss.xml` 或反向代理后的 HTTPS 地址作为订阅 URL。Docker 里的 Feed-Push 要使用可访问的服务器地址或域名。状态保存在 Compose 的 `state` 卷，更新、重建容器后继续沿用原 GUID。每个卷由一个 RSS 容器轮询。

在本目录建立 `.env` 可覆盖以下值，修改后执行 `docker compose up -d`。

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `OVH_WATCH` | `eu:24ska012-sgp,eu:24sk40-v1,eu:27skle01-v1,eu:27skle03-v1` | 逗号分隔的 `区域:planCode`，公开目录分别使用 `eu` 的 IE、`ca` 的 CA 和 `us` 的 US 市场 |
| `OVH_DATACENTERS` | 空 | 默认所有机房，可填写 `gra,rbx` |
| `POLL_SECONDS` | `60` | 每轮查询后的等待秒数，最小 15 秒 |
| `HOST_PORT` | `8787` | 宿主机端口 |
| `BIND_ADDRESS` | `0.0.0.0` | 宿主机绑定地址，宿主机反代时可用 `127.0.0.1` |
