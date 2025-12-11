"""
MemOS客户端
负责与MemOS云服务API进行交互
"""

from typing import Dict, List, Any

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
        import asyncio
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