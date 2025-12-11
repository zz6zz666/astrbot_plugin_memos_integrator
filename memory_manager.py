"""
MemOS记忆管理器
负责与MemOS API交互，保存和检索记忆
"""

import time
import asyncio
from typing import List, Dict, Any
from .memory_templates import MemoryTemplates

from astrbot.api import logger
from memos.api.client import MemOSClient

class MemOS_Client:
    """MemOS云服务API客户端"""
    
    def __init__(self, api_key: str):
        """初始化MemOS客户端
        
        Args:
            api_key: API密钥
        """
        self.client = MemOSClient(api_key=api_key)
        logger.info("MemOS客户端初始化完成")
    
    async def add_message(self, messages: List[Dict[str, str]], user_id: str, conversation_id: str) -> Dict[str, Any]:
        """添加对话消息到MemOS
        
        Args:
            messages: 对话消息列表，格式为[{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
            user_id: 用户ID
            conversation_id: 对话ID
            
        Returns:
            操作结果字典，包含success状态和相关信息
        """
        try:
            # 使用官方客户端API（同步方法转换为异步执行）
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, 
                lambda: self.client.add_message(messages=messages, user_id=user_id, conversation_id=conversation_id)
            )
            logger.info(f"成功添加对话消息，用户ID: {user_id}, 对话ID: {conversation_id}")
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"添加对话消息时出错: {e}")
            return {"success": False, "error": str(e)}
    
    async def search_memory(self, query: str, user_id: str, conversation_id: str) -> Dict[str, Any]:
        """搜索相关记忆
        
        Args:
            query: 查询内容
            user_id: 用户ID
            conversation_id: 对话ID
            
        Returns:
            操作结果字典，包含success状态和记忆列表
        """
        try:
            # 使用官方客户端API
            result = self.client.search_memory(query=query, user_id=user_id, conversation_id=conversation_id)
            logger.info(f"成功搜索到记忆，用户ID: {user_id}")
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"搜索记忆时出错: {e}")
            return {"success": False, "error": str(e)}

class MemoryManager:
    """MemOS记忆管理器"""
    
    def __init__(self, client: MemOS_Client):
        """初始化记忆管理器
        
        Args:
            client: MemOS客户端
        """
        self.client = client
        logger.info("MemoryManager初始化完成")
    
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
            # 直接传递消息，避免重复构建列表
            result = await self.client.add_message(
                messages=[
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": ai_response}
                ],
                user_id=user_id, 
                conversation_id=conversation_id
            )
            
            if result.get("success", False):
                logger.info(f"对话保存成功，用户ID: {user_id}, 对话ID: {conversation_id}")
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
            相关记忆的列表，格式与浏览器插件兼容
        """
        try:
            logger.debug(f"开始检索相关记忆，查询: {query[:50]}..., 用户ID: {user_id}, 对话ID: {conversation_id}, 限制: {limit}")
            
            # 使用MemOS云服务的search_memory API
            result = await self.client.search_memory(query, user_id, conversation_id)
            
            if result.get("success", False):
                memories = result.get("data", [])
                logger.info(f"检索到 {len(memories)} 条相关记忆，用户ID: {user_id}")
                
                # 转换为浏览器插件兼容的记忆格式
                memory_list = []
                for memory in memories:
                    # 假设记忆已经是浏览器插件兼容的格式
                    memory_list.append({
                        "type": memory.get("type", "fact"),
                        "content": memory.get("content", ""),
                        "timestamp": memory.get("timestamp", ""),
                        "update_time": memory.get("update_time", time.time())
                    })
                
                return memory_list
            else:
                logger.error(f"检索记忆失败: {result.get('error', '未知错误')}")
                return []
        except Exception as e:
            logger.error(f"检索相关记忆时出错: {e}")
            return []
    
    async def update_memory(self, messages: List[Dict], user_id: str, session_id: str, conversation_id: str) -> bool:
        """更新记忆（保存对话到MemOS）
        
        Args:
            messages: 对话消息列表
            user_id: 用户ID
            session_id: 会话ID（未使用）
            conversation_id: 对话ID
            
        Returns:
            更新是否成功
        """
        try:
            # 使用MemOS云服务的add_message API
            result = await self.client.add_message(messages=messages, user_id=user_id, conversation_id=conversation_id)
            
            if result.get("success", False):
                logger.info(f"记忆更新成功，用户ID: {user_id}, 对话ID: {conversation_id}")
                return True
            else:
                error_msg = result.get("error", "未知错误")
                logger.error(f"记忆更新失败: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"更新记忆时出错: {e}")
            return False
    
    async def inject_memory_to_prompt(self, original_prompt: str, memories: List[Dict], language: str = "zh", model_type: str = "default") -> str:
        """将记忆注入到用户提示中，使用浏览器插件中的记忆注入逻辑
        
        Args:
            original_prompt: 原始用户提示
            memories: 记忆列表
            language: 语言，"zh"为中文，"en"为英文
            model_type: 模型类型，"default"为默认模型，"qwen"为通义千问模型
            
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
            template = MemoryTemplates.get_injection_template(language, model_type)
            logger.debug(f"使用的记忆注入模板类型: {language}-{model_type}")
            
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