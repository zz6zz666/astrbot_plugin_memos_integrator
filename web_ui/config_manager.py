"""
配置持久化管理模块
"""

import json
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from astrbot.api import logger

from .data_models import BotConfig, SessionConfig
from .data_fetcher import DataFetcher


class ConfigManager:
    """配置管理器"""

    def __init__(self, data_dir: Path, plugin_instance=None):
        """
        初始化ConfigManager

        Args:
            data_dir: 数据目录路径
            plugin_instance: 插件实例（可选，用于数据库同步）
        """
        self.data_dir = data_dir
        self.plugin_instance = plugin_instance
        self.config_file = data_dir / "web_config.json"
        self.config_backup_dir = data_dir / "backups"
        self.config_data = self._load_config()
        self._in_sync = False  # 防止重入标志
        self._last_modified_time = self.config_file.stat().st_mtime if self.config_file.exists() else 0

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if not self.config_file.exists():
            # 创建默认配置
            default_config = {
                "version": "1.0",
                "bots": {}
            }
            self._save_config(default_config)
            # 如果插件实例存在，从数据库初始化配置
            if self.plugin_instance:
                self.sync_with_database()
            return default_config

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 验证配置结构
            if "version" not in config:
                config["version"] = "1.0"
            if "bots" not in config:
                config["bots"] = {}

            return config
        except (json.JSONDecodeError, IOError) as e:
            # 配置文件损坏，创建备份并返回默认配置
            if self.config_file.exists():
                backup_file = self.config_backup_dir / f"config_corrupted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                self.config_backup_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(self.config_file, backup_file)

            default_config = {
                "version": "1.0",
                "bots": {}
            }
            self._save_config(default_config)
            return default_config

    def _reload_config_if_needed(self) -> None:
        """检查配置文件是否已修改，如果是则重新加载"""
        try:
            if not self.config_file.exists():
                return

            current_mtime = self.config_file.stat().st_mtime
            if current_mtime > self._last_modified_time:
                # 文件已修改，重新加载
                new_config = self._load_config()
                self.config_data = new_config
                self._last_modified_time = current_mtime
                logger.debug("配置文件已重新加载")
        except Exception as e:
            logger.error(f"检查配置文件修改时间失败: {e}")

    def force_reload(self) -> None:
        """强制重新加载配置文件（忽略修改时间检查）"""
        try:
            if not self.config_file.exists():
                return
            # 直接重新加载配置
            new_config = self._load_config()
            self.config_data = new_config
            if self.config_file.exists():
                self._last_modified_time = self.config_file.stat().st_mtime
            logger.debug("配置文件已强制重新加载")
        except Exception as e:
            logger.error(f"强制重新加载配置文件失败: {e}")

    def _save_config(self, config: Dict[str, Any]) -> None:
        """保存配置文件"""
        # 创建备份
        if self.config_file.exists():
            self.config_backup_dir.mkdir(parents=True, exist_ok=True)
            backup_file = self.config_backup_dir / f"config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            shutil.copy2(self.config_file, backup_file)

        # 保存新配置
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        # 更新最后修改时间
        if self.config_file.exists():
            self._last_modified_time = self.config_file.stat().st_mtime

    def get_bot_config(self, bot_id: str) -> BotConfig:
        """获取Bot配置"""
        # 重新加载配置确保获取最新数据
        self._reload_config_if_needed()
        bot_data = self.config_data["bots"].get(bot_id, {})
        return BotConfig(
            custom_user_id=bot_data.get("custom_user_id", ""),
            memory_injection_enabled=bot_data.get("memory_injection_enabled", True),
            new_session_upload_enabled=bot_data.get("new_session_upload_enabled", True)
        )

    def get_session_config(self, bot_id: str, session_id: str) -> SessionConfig:
        """获取会话配置"""
        # 重新加载配置确保获取最新数据
        self._reload_config_if_needed()
        bot_data = self.config_data["bots"].get(bot_id, {})
        sessions = bot_data.get("conversations", {})
        session_data = sessions.get(session_id, {})

        return SessionConfig(
            custom_user_id=session_data.get("custom_user_id", ""),
            memory_injection_enabled=session_data.get("memory_injection_enabled", True),
            new_session_upload_enabled=session_data.get("new_session_upload_enabled", True)
        )

    def get_effective_config(self, bot_id: str, session_id: Optional[str] = None) -> BotConfig:
        """
        获取生效配置（考虑优先级：会话配置 > Bot配置）

        Args:
            bot_id: Bot ID
            session_id: 会话ID（可选）

        Returns:
            生效的配置
        """
        bot_config = self.get_bot_config(bot_id)

        if session_id:
            session_config = self.get_session_config(bot_id, session_id)

            # 合并配置，会话配置覆盖Bot配置
            effective_config = bot_config.model_copy()

            # 会话配置的custom_user_id非空时覆盖Bot配置，否则保留Bot配置的值
            if session_config.custom_user_id:
                effective_config.custom_user_id = session_config.custom_user_id

            # 布尔值直接覆盖
            effective_config.memory_injection_enabled = session_config.memory_injection_enabled
            effective_config.new_session_upload_enabled = session_config.new_session_upload_enabled

            return effective_config
        else:
            return bot_config

    def save_bot_config(self, bot_id: str, config: BotConfig) -> bool:
        """保存Bot配置"""
        try:
            # 重新加载配置确保获取最新数据
            self._reload_config_if_needed()

            # 验证用户ID格式
            if config.custom_user_id and not self._validate_user_id(config.custom_user_id):
                return False

            # 更新配置数据
            if bot_id not in self.config_data["bots"]:
                self.config_data["bots"][bot_id] = {
                    "conversations": {}
                }

            self.config_data["bots"][bot_id].update({
                "custom_user_id": config.custom_user_id,
                "memory_injection_enabled": config.memory_injection_enabled,
                "new_session_upload_enabled": config.new_session_upload_enabled
            })

            # 保存到文件
            self._save_config(self.config_data)
            return True

        except Exception as e:
            logger.error(f"保存Bot配置失败: {e}")
            return False

    def save_session_config(self, bot_id: str, session_id: str, config: SessionConfig) -> bool:
        """保存会话配置"""
        try:
            # 重新加载配置确保获取最新数据
            self._reload_config_if_needed()

            # 验证用户ID格式
            if config.custom_user_id and not self._validate_user_id(config.custom_user_id):
                return False

            # 确保Bot配置存在
            if bot_id not in self.config_data["bots"]:
                self.config_data["bots"][bot_id] = {
                    "conversations": {}
                }

            # 确保会话字典存在
            if "conversations" not in self.config_data["bots"][bot_id]:
                self.config_data["bots"][bot_id]["conversations"] = {}

            # 更新会话配置
            self.config_data["bots"][bot_id]["conversations"][session_id] = {
                "custom_user_id": config.custom_user_id,
                "memory_injection_enabled": config.memory_injection_enabled,
                "new_session_upload_enabled": config.new_session_upload_enabled
            }

            # 保存到文件
            self._save_config(self.config_data)
            return True

        except Exception as e:
            logger.error(f"保存会话配置失败: {e}")
            return False

    def delete_session_config(self, bot_id: str, session_id: str) -> bool:
        """删除会话配置"""
        try:
            # 重新加载配置确保获取最新数据
            self._reload_config_if_needed()

            if (bot_id in self.config_data["bots"] and
                "conversations" in self.config_data["bots"][bot_id] and
                session_id in self.config_data["bots"][bot_id]["conversations"]):

                del self.config_data["bots"][bot_id]["conversations"][session_id]

                # 如果会话字典为空，删除它
                if not self.config_data["bots"][bot_id]["conversations"]:
                    del self.config_data["bots"][bot_id]["conversations"]

                # 保存到文件
                self._save_config(self.config_data)
                return True

            return False

        except Exception as e:
            logger.error(f"删除会话配置失败: {e}")
            return False

    async def async_sync_with_database(self) -> None:
        """
        异步同步配置文件与数据库状态
        只同步bot列表：添加新增bot，清除不复存在的bot，不处理会话
        """
        if not self.plugin_instance:
            logger.warning("插件实例未设置，无法同步数据库")
            return

        # 防止重入
        if self._in_sync:
            logger.debug("数据库同步正在进行中，跳过")
            return

        self._in_sync = True
        try:
            # 重新加载配置确保基于最新数据同步
            self._reload_config_if_needed()

            # 临时创建DataFetcher（不传递config_manager以避免递归）
            from .data_fetcher import DataFetcher
            data_fetcher = DataFetcher(self.plugin_instance)

            # 获取数据库中的所有bot
            bots = await data_fetcher.get_bots()

            # 检查每个bot是否存在配置中，不存在则添加默认配置
            for bot in bots:
                bot_id = bot.id
                if bot_id not in self.config_data["bots"]:
                    # 添加bot配置（包含元数据）
                    self.config_data["bots"][bot_id] = {
                        "custom_user_id": "",
                        "memory_injection_enabled": True,
                        "new_session_upload_enabled": True,
                        "name": bot.name,
                        "type": bot.type,
                        "conversations": {}
                    }
                    logger.info(f"新增Bot配置: {bot.name} ({bot_id})")
                else:
                    # 更新元数据（确保name和type存在）
                    bot_data = self.config_data["bots"][bot_id]
                    if "name" not in bot_data:
                        bot_data["name"] = bot.name
                    if "type" not in bot_data:
                        bot_data["type"] = bot.type

            # 清除不复存在的bot（配置中存在但数据库中不存在）
            config_bot_ids = set(self.config_data["bots"].keys())
            db_bot_ids = {bot.id for bot in bots}
            bots_to_remove = config_bot_ids - db_bot_ids

            for bot_id in bots_to_remove:
                if bot_id in self.config_data["bots"]:
                    bot_name = self.config_data["bots"][bot_id].get("name", bot_id)
                    del self.config_data["bots"][bot_id]
                    logger.info(f"移除不复存在的Bot配置: {bot_name} ({bot_id})")

            # 保存更新后的配置
            self._save_config(self.config_data)
            logger.info("配置文件已同步数据库")

        except Exception as e:
            logger.error(f"同步数据库失败: {e}")
        finally:
            self._in_sync = False

    def sync_with_database(self) -> None:
        """同步数据库（同步包装）"""
        import asyncio
        try:
            # 尝试获取当前事件循环
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 事件循环正在运行，创建后台任务异步执行同步
                # 注意：我们不等待任务完成，同步方法立即返回
                task = asyncio.create_task(self.async_sync_with_database())
                # 添加错误回调记录错误
                def log_error(task):
                    try:
                        task.result()
                    except Exception as e:
                        logger.error(f"后台数据库同步任务失败: {e}")
                task.add_done_callback(log_error)
                logger.info("已创建后台任务同步数据库")
            else:
                # 事件循环未运行，可以直接运行
                asyncio.run(self.async_sync_with_database())
        except RuntimeError:
            # 没有事件循环，创建新的
            asyncio.run(self.async_sync_with_database())
        except Exception as e:
            logger.error(f"同步数据库失败: {e}")

    def ensure_session_config(self, bot_id: str, session_id: str, unified_msg_origin: str = "") -> None:
        """
        确保会话配置存在，如果不存在则从bot配置复制创建
        """
        # 重新加载配置确保获取最新数据
        self._reload_config_if_needed()

        if bot_id not in self.config_data["bots"]:
            # Bot不存在，先创建bot配置（使用默认值）
            self.config_data["bots"][bot_id] = {
                "custom_user_id": "",
                "memory_injection_enabled": True,
                "new_session_upload_enabled": True,
                "name": bot_id,  # 默认名称
                "type": "unknown",
                "conversations": {}
            }
            logger.info(f"自动创建Bot配置: {bot_id}")

        bot_data = self.config_data["bots"][bot_id]
        if "conversations" not in bot_data:
            bot_data["conversations"] = {}

        if session_id not in bot_data["conversations"]:
            # 从bot配置复制，并添加unified_msg_origin
            bot_config = self.get_bot_config(bot_id)
            bot_data["conversations"][session_id] = {
                "custom_user_id": "",  # 会话的custom_user_id在创建时始终保持空
                "memory_injection_enabled": bot_config.memory_injection_enabled,
                "new_session_upload_enabled": bot_config.new_session_upload_enabled,
                "unified_msg_origin": unified_msg_origin
            }
            self._save_config(self.config_data)
            logger.info(f"自动创建会话配置: {bot_id}/{session_id}")

    def get_all_bot_ids(self) -> list[str]:
        """获取所有Bot ID"""
        # 重新加载配置确保获取最新数据
        self._reload_config_if_needed()
        return list(self.config_data["bots"].keys())

    def get_all_session_ids(self, bot_id: str) -> list[str]:
        """获取指定Bot的所有会话ID"""
        # 重新加载配置确保获取最新数据
        self._reload_config_if_needed()
        bot_data = self.config_data["bots"].get(bot_id, {})
        conversations = bot_data.get("conversations", {})
        return list(conversations.keys())

    def _validate_user_id(self, user_id: str) -> bool:
        """
        验证用户ID格式

        Args:
            user_id: 用户ID字符串

        Returns:
            是否有效
        """
        if not user_id:
            return True

        # 检查长度
        if len(user_id) > 100:
            return False

        # 检查是否有危险字符（防止注入攻击）
        dangerous_chars = ['<', '>', '"', "'", '\\', '/', ';', '&', '|', '$', '`']
        for char in dangerous_chars:
            if char in user_id:
                return False

        return True

    def apply_switch_to_all_sessions(self, bot_id: str, switch_type: str, enabled: bool) -> Dict[str, Any]:
        """将指定开关状态应用到所有会话

        Args:
            bot_id: Bot ID
            switch_type: 开关类型，'memory_injection' 或 'new_session_upload'
            enabled: 开关状态，True表示开启，False表示关闭

        Returns:
            包含统计信息的字典: total, updated, failed
        """
        # 重新加载配置确保获取最新数据
        self._reload_config_if_needed()
        if bot_id not in self.config_data["bots"]:
            return {"total": 0, "updated": 0, "failed": []}

        sessions = self.config_data["bots"][bot_id].get("conversations", {})
        total = len(sessions)
        updated = 0
        failed = []

        for session_id in sessions.keys():
            try:
                # 获取当前会话配置
                session_config = self.get_session_config(bot_id, session_id)

                # 只更新指定开关，保持其他字段不变
                if switch_type == "memory_injection":
                    session_config.memory_injection_enabled = enabled
                else:  # "new_session_upload"
                    session_config.new_session_upload_enabled = enabled

                # 保存更新后的配置
                if self.save_session_config(bot_id, session_id, session_config):
                    updated += 1
                else:
                    failed.append(session_id)
            except Exception as e:
                logger.error(f"更新会话 {session_id} 开关失败: {e}")
                failed.append(session_id)

        return {"total": total, "updated": updated, "failed": failed}