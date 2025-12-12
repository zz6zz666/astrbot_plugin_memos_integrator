"""
MemOS记忆管理器
负责与MemOS API交互,保存和检索记忆
使用HTTP请求方式,无需安装SDK
"""

import time
from typing import List, Dict, Any
from .memory_templates import MemoryTemplates

from astrbot.api import logger
import aiohttp


class MemoryManager:
    """MemOS记忆管理器 - 使用HTTP API直接访问MemOS服务"""

    def __init__(self, api_key: str, base_url: str = "https://memos.memtensor.cn/api/openmem/v1"):
        """初始化记忆管理器

        Args:
            api_key: MemOS API密钥
            base_url: MemOS API基础URL
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        logger.info(f"MemoryManager初始化完成, API地址: {self.base_url}")

    async def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """发送HTTP请求到MemOS API

        Args:
            endpoint: API端点 (如 '/add/message')
            data: 请求数据

        Returns:
            响应数据字典，格式: {"success": bool, "data": API返回的内容}
        """
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Token {self.api_key}"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        result = await response.json()

                        # MemOS API 响应格式: {"code": 0/200, "message": "...", "data": {...}}
                        # code=0 表示成功 

                        if isinstance(result, dict):
                            code = result.get("code")
                            message = result.get("message", "")

                            # 成功的code是 0 
                            if code == 0:
                                data = result.get("data")
                                logger.debug(f"MemOS API调用成功: {message}")
                                return {"success": True, "data": data if data is not None else {}}
                            else:
                                # 其他code视为错误
                                logger.error(f"MemOS API返回错误 (code={code}): {message}")
                                return {"success": False, "error": f"API错误 (code={code}): {message}"}
                        else:
                            logger.error(f"MemOS API返回了非字典类型的数据: {type(result)}")
                            return {"success": False, "error": "响应格式错误"}
                    else:
                        error_text = await response.text()
                        logger.error(f"MemOS API请求失败 [{response.status}]: {error_text}")
                        return {"success": False, "error": f"HTTP {response.status}: {error_text}"}
        except aiohttp.ClientError as e:
            logger.error(f"MemOS API网络请求失败: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"MemOS API请求异常: {e}")
            return {"success": False, "error": str(e)}

    async def add_message(self, messages: List[Dict[str, str]], user_id: str, conversation_id: str) -> Dict[str, Any]:
        """添加对话消息到MemOS

        Args:
            messages: 对话消息列表,格式为[{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
            user_id: 用户ID
            conversation_id: 对话ID

        Returns:
            操作结果字典
        """
        data = {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "messages": messages
        }

        result = await self._make_request("/add/message", data)
        if result.get("success"):
            logger.info(f"成功添加对话消息,用户ID: {user_id}, 对话ID: {conversation_id}")
        return result

    async def search_memory(self, query: str, user_id: str, conversation_id: str) -> Dict[str, Any]:
        """搜索相关记忆

        Args:
            query: 查询内容
            user_id: 用户ID
            conversation_id: 对话ID

        Returns:
            操作结果字典
        """
        data = {
            "query": query,
            "user_id": user_id,
            "conversation_id": conversation_id
        }

        result = await self._make_request("/search/memory", data)
        if result.get("success"):
            logger.info(f"成功搜索到记忆,用户ID: {user_id}")
        return result

    async def save_conversation(self, user_message: str, ai_response: str, user_id: str, conversation_id: str) -> bool:
        """保存对话到MemOS

        Args:
            user_message: 用户消息
            ai_response: AI响应
            user_id: 用户ID
            conversation_id: 对话ID

        Returns:
            保存是否成功
        """
        try:
            result = await self.add_message(
                messages=[
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": ai_response}
                ],
                user_id=user_id,
                conversation_id=conversation_id
            )

            if result.get("success", False):
                logger.info(f"对话保存成功,用户ID: {user_id}, 对话ID: {conversation_id}")
                return True
            else:
                error_msg = result.get("error", "未知错误")
                logger.error(f"对话保存失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"保存对话时出错: {e}")
            return False

    async def retrieve_relevant_memories(self, query: str, user_id: str, conversation_id: str, limit: int = 5) -> List[Dict]:
        """检索相关记忆

        Args:
            query: 查询内容
            user_id: 用户ID
            conversation_id: 对话ID
            limit: 返回的记忆数量限制

        Returns:
            相关记忆的列表，包含事实记忆和偏好记忆
        """
        try:
            logger.debug(f"开始检索相关记忆,查询: {query[:50]}..., 用户ID: {user_id}, 对话ID: {conversation_id}")

            result = await self.search_memory(query, user_id, conversation_id)

            if result.get("success", False):
                data = result.get("data", {})

                # 检查data是否为字典类型（MemOS API返回格式）
                if not isinstance(data, dict):
                    logger.warning(f"API返回的data不是字典类型: {type(data)}")
                    return []

                memory_list = []

                # 解析事实记忆 (memory_detail_list)
                memory_detail_list = data.get("memory_detail_list", [])
                if isinstance(memory_detail_list, list):
                    for memory in memory_detail_list:
                        if isinstance(memory, dict):
                            # 提取记忆内容和元数据
                            content = memory.get("memory_value", "")
                            memory_type = memory.get("memory_type", "LongTermMemory")
                            update_time = memory.get("update_time", 0)

                            # 格式化时间戳
                            if isinstance(update_time, (int, float)) and update_time > 1000000000000:
                                # 毫秒时间戳转换为秒
                                update_time = update_time / 1000

                            # 转换为可读日期格式
                            if isinstance(update_time, (int, float)) and update_time > 0:
                                timestamp = time.strftime("%Y-%m-%d", time.localtime(update_time))
                            else:
                                timestamp = str(update_time) if update_time else ""

                            memory_list.append({
                                "type": "fact",
                                "content": content,
                                "timestamp": timestamp,
                                "update_time": update_time,
                                "memory_type": memory_type
                            })

                # 解析偏好记忆 (preference_detail_list)
                preference_detail_list = data.get("preference_detail_list", [])
                if isinstance(preference_detail_list, list):
                    for pref in preference_detail_list:
                        if isinstance(pref, dict):
                            # 提取偏好内容和元数据
                            content = pref.get("preference", "")
                            pref_type = pref.get("preference_type", "implicit_preference")
                            update_time = pref.get("update_time", 0)

                            # 格式化时间戳
                            if isinstance(update_time, (int, float)) and update_time > 1000000000000:
                                update_time = update_time / 1000

                            if isinstance(update_time, (int, float)) and update_time > 0:
                                timestamp = time.strftime("%Y-%m-%d", time.localtime(update_time))
                            else:
                                timestamp = str(update_time) if update_time else ""

                            memory_list.append({
                                "type": "preference",
                                "content": content,
                                "timestamp": timestamp,
                                "update_time": update_time,
                                "preference_type": pref_type
                            })

                # 分别处理事实记忆和偏好记忆
                # limit 只限制事实记忆的数量，偏好记忆全部保留
                fact_memories = [m for m in memory_list if m.get("type") == "fact"]
                preference_memories = [m for m in memory_list if m.get("type") == "preference"]

                # 限制事实记忆数量，保留所有偏好记忆
                final_memory_list = fact_memories[:limit] + preference_memories

                logger.info(f"检索到 {len(memory_list)} 条相关记忆 (事实: {len(memory_detail_list)}, 偏好: {len(preference_detail_list)}), 用户ID: {user_id}")

                return final_memory_list
            else:
                logger.error(f"检索记忆失败: {result.get('error', '未知错误')}")
                return []
        except Exception as e:
            logger.error(f"检索相关记忆时出错: {e}", exc_info=True)
            return []

    async def update_memory(self, messages: List[Dict], user_id: str, session_id: str, conversation_id: str) -> bool:
        """更新记忆(保存对话到MemOS)

        Args:
            messages: 对话消息列表
            user_id: 用户ID
            session_id: 会话ID(未使用)
            conversation_id: 对话ID

        Returns:
            更新是否成功
        """
        try:
            result = await self.add_message(messages=messages, user_id=user_id, conversation_id=conversation_id)

            if result.get("success", False):
                logger.info(f"记忆更新成功,用户ID: {user_id}, 对话ID: {conversation_id}")
                return True
            else:
                error_msg = result.get("error", "未知错误")
                logger.error(f"记忆更新失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"更新记忆时出错: {e}")
            return False

    async def inject_memory_to_prompt(self, original_prompt: str, memories: List[Dict], language: str = "zh", injection_type: str = "user") -> str:
        """将记忆注入到用户提示中

        Args:
            original_prompt: 原始用户提示
            memories: 记忆列表
            language: 语言,"zh"为中文,"en"为英文
            model_type: 模型类型,"default"为默认模型,"qwen"为通义千问模型
            injection_type: 注入类型,"user"为用户注入,"system"为系统注入

        Returns:
            注入记忆后的提示
        """
        if not memories:
            logger.debug("没有记忆需要注入")
            return original_prompt

        try:
            # 格式化记忆内容
            memory_content = MemoryTemplates.format_memory_content(memories, language)
            logger.debug(f"格式化后的记忆内容:\n{memory_content}")

            # 获取当前时间
            current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

            # 获取记忆注入模板
            template = MemoryTemplates.get_injection_template(language, injection_type)
            logger.debug(f"使用的记忆注入模板类型: {language}-{injection_type}")

            # 填充模板
            injected_prompt = template.format(
                original_query=original_prompt,
                memory_content=memory_content,
                current_time=current_time
            )

            logger.info(f"已注入 {len(memories)} 条记忆到提示中")

            return injected_prompt
        except Exception as e:
            logger.error(f"注入记忆到提示时出错: {e}")
            return original_prompt
