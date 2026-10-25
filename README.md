# 原神剧情检索（AstrBot 插件）

为 AstrBot 提供 `search_genshin_lore` 工具，检索《原神》剧情、书籍、角色故事、武器和圣遗物原文，并返回出处及片段。

## 安装

AstrBot 管理面板进入 **插件 → 插件 → 安装插件（+）→ 从链接安装**，填写本仓库地址：

```text
https://github.com/Zomedk/astrbot_plugin_genshin_lite
```

也可以直接克隆到 AstrBot 的插件目录：

```bash
git clone https://github.com/Zomedk/astrbot_plugin_genshin_lite \
  data/plugins/astrbot_plugin_genshin_lite
```

插件附带 v3 SQLite 索引压缩包 `knowledge.db.gz`（约 85 MiB）。首次加载时会自动解压到 AstrBot 的插件数据目录，后续更新插件不会覆盖已生成的索引。索引解压后约 158 MiB；请为 AstrBot 数据盘预留空间。本仓库通过 GitHub 直接安装；由于插件包超过 AstrBot 插件市场 16 MB 的限制，目前不适合提交到插件市场。

## 启用

安装后在 AstrBot 插件页面确认插件加载成功，再到机器人实际使用的人格/配置中启用 `search_genshin_lore`。建议在系统提示词中说明：询问原神剧情、书籍或角色设定中的具体事实时先检索；依据返回原文回答并保留出处；资料不足时明确说明。

可以直接让机器人测试这些问题：

- `《日月前事》关于四影怎么说？`
- `风鹰剑的故事里提到了谁？`
- `魔女会和小魔女会有什么区别？`

检查 AstrBot 的追踪或日志，确认模型调用了 `search_genshin_lore`，并查看答复是否对应到正确来源。

## 检索说明

- 使用 Python 标准库 `sqlite3` 和 SQLite FTS5；在线检索不需要向量库、Embedding API、Docker 或独立服务。
- 中文查询拆成二字/三字词组，结合 FTS5 BM25、标题命中和原文命中排序。
- 默认返回最多五个片段，每段最多 440 个字符，并限制单个来源的重复结果。
- 索引包含 37,826 个片段。适合人物名、书名、专名和明确线索；抽象问题、同义改写及多步推理仍可能漏检或排错。
- 对话节点保留原始节点 ID 和分支边，但不是线性剧情顺序；NPC ID 不等于角色真名。

## 数据来源与限制

数据库由第三方整理的中文文本构建，包含 `Genshin_Database` 资料和 `game-text-data` 提取的任务/字幕内容。资料可能缺漏或过时。剧情转换未纳入未映射进任务对话的孤立 Talk，也无法还原完整分支顺序。游戏文本及角色设定的权利归原权利人。

## 兼容性

- AstrBot：`>=4.5.7,<5`
- Python：3.10+
- 运行依赖：仅 Python 标准库和 AstrBot API
