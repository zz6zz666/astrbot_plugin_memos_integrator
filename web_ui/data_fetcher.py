"""
Bot和会话数据获取模块
"""

import asyncio
from typing import List, Dict, Any, Optional
from astrbot.api import logger
from .data_models import BotInfo, SessionInfo, BotTreeItem


class DataFetcher:
    """数据获取器"""

    def __init__(self, plugin_instance):
        """
        初始化DataFetcher

        Args:
            plugin_instance: 插件实例
        """
        self.plugin = plugin_instance

    async def get_bots(self) -> List[BotInfo]:
        """
        获取Bot列表

        从AstrBot的platform_manager获取所有启用的平台适配器

        Returns:
            Bot信息列表
        """
        bots = []

        try:
            # 获取平台管理器实例
            platform_manager = self.plugin.context.platform_manager

            # 获取所有平台实例
            platform_insts = platform_manager.get_insts()

            for platform in platform_insts:
                try:
                    # 检查是否启用
                    platform_config = platform.config
                    if not platform_config.get("enable", True):
                        continue

                    # 获取平台元数据
                    meta = platform.meta()

                    # 构建Bot信息
                    # 优先使用适配器显示名称，其次尝试配置中的名称，最后使用适配器类型
                    display_name = meta.adapter_display_name
                    if not display_name:
                        # 尝试从配置中获取显示名称
                        display_name = platform_config.get("name") or platform_config.get("id") or meta.name

                    bot_info = BotInfo(
                        id=platform_config.get("id", ""),
                        name=display_name,
                        type=meta.name,
                        enabled=True
                    )

                    # 确保ID不为空
                    if not bot_info.id:
                        # 使用类型作为后备ID
                        bot_info.id = meta.name

                    bots.append(bot_info)

                except Exception as e:
                    logger.warning(f"获取平台 {platform} 信息失败: {e}")
                    continue

        except Exception as e:
            logger.error(f"获取Bot列表失败: {e}")

        return bots

    async def get_sessions(self, bot_id: str) -> List[SessionInfo]:
        """
        获取指定Bot的会话列表

        从AstrBot的conversation_manager获取会话数据

        Args:
            bot_id: Bot ID

        Returns:
            会话信息列表
        """
        sessions = []

        try:
            # 获取对话管理器实例
            conversation_manager = self.plugin.context.conversation_manager

            # 获取该Bot的所有对话
            conversations = await conversation_manager.get_conversations(
                platform_id=bot_id
            )

            # 使用字典按user_id（unified_msg_origin）分组，统计对话数量
            session_dict = {}
            for conv in conversations:
                try:
                    # 获取user_id（unified_msg_origin）
                    user_id = conv.user_id  # 格式: "platform_name:message_type:session_id"

                    if not user_id:
                        continue

                    # 提取message_type:session_id部分
                    parts = user_id.split(":")
                    if len(parts) >= 3:
                        # 平台名称是parts[0]，消息类型是parts[1]，会话ID是parts[2:]
                        # 如果还有更多部分（如额外参数），将会话ID部分重新连接
                        session_identifier = f"{parts[1]}:{':'.join(parts[2:])}"
                    else:
                        # 如果不是标准格式，使用整个user_id
                        session_identifier = user_id

                    # 统计该会话的对话数量
                    if session_identifier in session_dict:
                        session_dict[session_identifier]["count"] += 1
                    else:
                        session_dict[session_identifier] = {
                            "id": session_identifier,
                            "unified_msg_origin": user_id,
                            "count": 1
                        }

                except Exception as e:
                    logger.warning(f"解析会话信息失败: {e}")
                    continue

            # 转换为SessionInfo列表
            for session_data in session_dict.values():
                session_info = SessionInfo(
                    id=session_data["id"],  # 显示用的标识符: "message_type:session_id"
                    unified_msg_origin=session_data["unified_msg_origin"],  # 完整的unified_msg_origin
                    conversation_count=session_data["count"]
                )
                sessions.append(session_info)

        except Exception as e:
            logger.error(f"获取会话列表失败: {e}")

        return sessions

    async def get_bot_tree(self) -> List[BotTreeItem]:
        """
        获取完整的Bot树形结构

        Returns:
            Bot树形项列表
        """
        bots = await self.get_bots()
        bot_tree = []

        for bot in bots:
            try:
                # 获取该Bot的会话列表
                sessions = await self.get_sessions(bot.id)

                # 构建树形项
                tree_item = BotTreeItem(
                    bot=bot,
                    sessions=sessions
                )

                bot_tree.append(tree_item)

            except Exception as e:
                logger.warning(f"构建Bot {bot.name} 树形项失败: {e}")
                continue

        return bot_tree

    async def search_bots(self, query: str) -> List[BotInfo]:
        """
        搜索Bot

        Args:
            query: 搜索关键词

        Returns:
            匹配的Bot信息列表
        """
        all_bots = await self.get_bots()
        query = query.lower()

        results = []
        for bot in all_bots:
            if (query in bot.name.lower() or
                query in bot.type.lower() or
                query in bot.id.lower()):
                results.append(bot)

        return results

    async def search_sessions(self, bot_id: str, query: str) -> List[SessionInfo]:
        """
        搜索会话

        Args:
            bot_id: Bot ID
            query: 搜索关键词

        Returns:
            匹配的会话信息列表
        """
        all_sessions = await self.get_sessions(bot_id)
        query = query.lower()

        results = []
        for session in all_sessions:
            if (query in session.id.lower() or
                query in session.unified_msg_origin.lower()):
                results.append(session)

        return results