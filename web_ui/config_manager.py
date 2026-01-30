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


class ConfigManager:
    """配置管理器"""

    def __init__(self, data_dir: Path):
        """
        初始化ConfigManager

        Args:
            data_dir: 数据目录路径
        """
        self.data_dir = data_dir
        self.config_file = data_dir / "web_config.json"
        self.config_backup_dir = data_dir / "backups"
        self.config_data = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if not self.config_file.exists():
            # 创建默认配置
            default_config = {
                "version": "1.0",
                "bots": {}
            }
            self._save_config(default_config)
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

    def get_bot_config(self, bot_id: str) -> BotConfig:
        """获取Bot配置"""
        bot_data = self.config_data["bots"].get(bot_id, {})
        return BotConfig(
            custom_user_id=bot_data.get("custom_user_id", ""),
            memory_injection_enabled=bot_data.get("memory_injection_enabled", True),
            new_session_upload_enabled=bot_data.get("new_session_upload_enabled", True)
        )

    def get_session_config(self, bot_id: str, session_id: str) -> SessionConfig:
        """获取会话配置"""
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

            # 只覆盖非空的会话配置
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

    def get_all_bot_ids(self) -> list[str]:
        """获取所有Bot ID"""
        return list(self.config_data["bots"].keys())

    def get_all_session_ids(self, bot_id: str) -> list[str]:
        """获取指定Bot的所有会话ID"""
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