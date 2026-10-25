"""AstrBot plugin: read-only Genshin Chinese text retrieval, no server, no model."""
from __future__ import annotations

import asyncio
import gzip
import shutil
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.core.utils.astrbot_path import get_astrbot_plugin_data_path

from .search_engine import search


class GenshinLitePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        plugin_dir = Path(__file__).resolve().parent
        data_dir = Path(get_astrbot_plugin_data_path()) / plugin_dir.name
        data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = data_dir / "knowledge.db"

        # Keep the database outside the plugin directory so plugin updates do not
        # overwrite user data. The compressed starter index ships with the repo.
        if not self.db_path.is_file():
            bundled_index = plugin_dir / "knowledge.db.gz"
            legacy_index = plugin_dir / "knowledge.db"
            if legacy_index.is_file():
                shutil.copy2(legacy_index, self.db_path)
            elif bundled_index.is_file():
                temp_path = self.db_path.with_suffix(".db.building")
                try:
                    with gzip.open(bundled_index, "rb") as source, temp_path.open("wb") as target:
                        shutil.copyfileobj(source, target, length=1024 * 1024)
                    temp_path.replace(self.db_path)
                finally:
                    temp_path.unlink(missing_ok=True)
        logger.info(f"原神轻量 RAG 插件已加载；索引存在: {self.db_path.is_file()}")

    @filter.llm_tool(name="search_genshin_lore")
    async def search_genshin_lore(self, event: AstrMessageEvent, query: str):
        """搜索《原神》中文游戏原文（剧情、书籍、角色故事、武器与圣遗物故事）。使用角色名、专有名词或简短组合关键词查询。只有需要考证游戏原文时才调用，结果不是事实推理结论。

        Args:
            query(string): 检索关键词，最好2至4个简短关键词，如「艾莉丝 魔女会」「日月前事 第二降临者」。
        """
        try:
            hits = await asyncio.to_thread(search, self.db_path, query, limit=5)
            if not hits:
                yield event.plain_result("原神知识库未找到匹配文本。可以换用官方名称、相关地点或其他关键词再次搜索。")
                return
            lines = ["以下是第三方整理的《原神》游戏内文本片段。仅作参考，需结合剧情上下文判断；不得将猜测当成官方设定。"]
            for n, hit in enumerate(hits, 1):
                lines.append(
                    f"{n}. [{hit['category']}] {hit['title']}\n"
                    f"来源文件：{hit['path']}，片段 {hit['chunk']}\n"
                    f"原文：{hit['text']}"
                )
            yield event.plain_result("\n\n".join(lines))
        except FileNotFoundError:
            yield event.plain_result("原神知识库索引不可用。请检查插件是否完整安装，或按 README 生成索引。")
        except Exception as exc:
            logger.exception("原神知识库查询失败")
            yield event.plain_result(f"原神知识库查询异常：{type(exc).__name__}")
