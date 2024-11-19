# RSS
基础指令
/start

功能：注册用户，并初始化用户数据（关键词列表、逻辑规则、RSS 源列表）。
用法：直接发送 /start。
/add

功能：添加关键词，用于简单匹配 RSS 标题。
用法：/add <关键词>
例如：/add claw
/add_logic

功能：添加逻辑规则，用于更复杂的匹配逻辑。
用法：/add_logic <规则>
+关键词 表示必须包含的关键词。
-关键词 表示必须排除的关键词。 例如：
/add_logic +amy-tom 表示标题必须包含 amy 且不能包含 tom。
/add_logic +amy+tom 表示标题必须同时包含 amy 和 tom。
/add_rss

功能：添加新的 RSS 订阅源。
用法：/add_rss <RSS_URL>
例如：/add_rss https://example.com/rss
/list

功能：查看当前用户添加的关键词、逻辑规则和 RSS 订阅源。
用法：直接发送 /list。
/rm

功能：删除关键词或逻辑规则。
用法：/rm <关键词或逻辑规则>
例如：
/rm claw 删除关键词 claw。
/rm +amy-tom 删除逻辑规则 +amy-tom。
管理员专用指令
（仅管理员可以使用，ROOT_ID 定义的用户）

/add_user

功能：将用户 ID 添加到白名单。
用法：/add_user <用户ID>
例如：/add_user 123456789
/remove_user

功能：从白名单中移除用户 ID。
用法：/remove_user <用户ID>
例如：/remove_user 123456789
/list_users

功能：列出所有已添加到白名单的用户 ID。
用法：直接发送 /list_users。
