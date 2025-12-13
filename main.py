"""
MemOS记忆集成插件
使用HTTP方式实现记忆获取、注入和更新功能
"""

import asyncio
import requests
import json
from typing import Dict, List
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.platform import MessageType
from astrbot.api.star import Context, Star, register
from astrbot.api.provider import ProviderRequest, LLMResponse
from astrbot.api import AstrBotConfig, logger
from .memory_manager import MemoryManager
from .commands_handler import CommandsHandler

# 主插件类
@register("astrbot_plugin_memos_integrator","zz6zz666", "MemOS记忆集成插件", "1.4.0")
class MemosIntegratorPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.memory_manager = None
        self.memory_limit = 5
        self.prompt_language = "auto"
        # 缓存配置
        self.upload_interval = 1 
        # 消息缓存: key为conversation_id, value为消息列表 [{"role": "user", ...}, ...]
        self.message_buffer: Dict[str, List[Dict[str, str]]] = {} 

        # 用于保存原始prompt的字典，key为session_id
        self.original_prompts = {}

        # 在 __init__ 中初始化记忆管理器
        try:
            # 验证配置
            api_key = self.config.get("api_key", "")
            if not api_key:
                logger.warning("MemOS API密钥未配置,插件功能将不可用")
                return

            # 获取配置
            base_url = self.config.get("base_url", "https://memos.memtensor.cn/api/openmem/v1")
            self.memory_limit = self.config.get("memory_limit", 5)
            self.prompt_language = self.config.get("prompt_language", "auto")
            self.upload_interval = self.config.get("upload_interval", 1) # 获取上传频率配置
            
            # 新增配置：控制群聊和私聊场景下的注入类型
            self.group_injection_type = self.config.get("group_injection_type", "user")  # 群聊注入类型: "user" 或 "system"
            self.private_injection_type = self.config.get("private_injection_type", "user")  # 私聊注入类型: "user" 或 "system"

            # 初始化记忆管理器
            self.memory_manager = MemoryManager(
                api_key=api_key,
                base_url=base_url
            )

            logger.info("MemOS记忆集成插件已加载")
            logger.info(f"插件配置: API地址={base_url}, 记忆注入限制={self.memory_limit}, 批量上传频率={self.upload_interval}轮")
            logger.info(f"注入类型配置: 群聊={self.group_injection_type}, 私聊={self.private_injection_type}")
        except Exception as e:
            logger.error(f"初始化MemOS记忆管理器失败: {e}")
            self.memory_manager = None
            
    def _get_session_id(self, event: AstrMessageEvent) -> str:
        """获取会话ID（统一消息来源）"""
        session_id = event.unified_msg_origin
        logger.debug(f"会话ID: {session_id}")
        return session_id

    async def _get_conversation_id(self, event: AstrMessageEvent) -> str:
        """获取当前对话ID"""
        session_id = event.unified_msg_origin
        conversation_id = await self.context.conversation_manager.get_curr_conversation_id(session_id)

        if not conversation_id:
            conversation_id = await self.context.conversation_manager.new_conversation(session_id)
            logger.info(f"为会话 {session_id} 创建新对话: {conversation_id}")
        else:
            logger.debug(f"使用现有对话ID: {conversation_id}")

        return conversation_id
        
    @filter.on_llm_request(priority=-1000)
    async def inject_memories(self, event: AstrMessageEvent, req: ProviderRequest):
        """在LLM请求前获取记忆并注入"""
        if self.memory_manager is None:
            return

        session_id = self._get_session_id(event)
        conversation_id = await self._get_conversation_id(event)
        user_message = req.prompt
        
        # 无论哪种注入方式，都保存原始prompt以便后续记忆保存
        self.original_prompts[session_id] = user_message

        memories = await self.memory_manager.retrieve_relevant_memories(
            user_message, session_id, conversation_id, limit=self.memory_limit
        )

        if memories:
            if self.prompt_language == "auto":
                language = "zh"
                has_chinese = any('\u4e00' <= c <= '\u9fff' for c in user_message)
                if not has_chinese and any(ord(c) < 128 and c.isalpha() for c in user_message):
                    language = "en"
            else:
                language = self.prompt_language

            # 判断消息类型（群聊或私聊）
            is_group_message = event.get_message_type() == MessageType.GROUP_MESSAGE
            
            # 根据配置选择注入类型
            injection_type = self.group_injection_type if is_group_message else self.private_injection_type
            
            # 构建记忆提示词
            memory_prompt = await self.memory_manager.inject_memory_to_prompt(
                user_message, memories, language, injection_type
            )
            
            if injection_type == "system":
                # 清除先前注入的以"# Role"开头的system提示
                req.contexts = [
                    ctx for ctx in req.contexts 
                    if not (ctx.get("role") == "system" and ctx.get("content", "").startswith("# Role"))
                ]
                
                # 使用system注入：将记忆内容作为system消息添加到contexts中
                # 由于模板已经根据injection_type生成了正确的内容，直接使用memory_prompt
                req.contexts.append({
                    "role": "system",
                    "content": memory_prompt
                })
                
                # 保持prompt为原始用户消息
                logger.info(f"已为会话 {session_id} 以system类型注入 {len(memories)} 条记忆")
            else:
                # 使用user注入：更新prompt为包含记忆的版本
                req.prompt = memory_prompt
                logger.info(f"已为会话 {session_id} 以user类型注入 {len(memories)} 条记忆")
            
    @filter.on_llm_response()
    async def save_memories(self, event: AstrMessageEvent, resp: LLMResponse):
        """在LLM响应后将对话加入缓存，达到阈值后批量保存到MemOS"""

        try:
            if self.memory_manager is None:
                return

            session_id = self._get_session_id(event)
            conversation_id = await self._get_conversation_id(event)

            # 处理不同注入类型的后续操作
            user_message = None
            req = event.get_extra("provider_request")
            
            # 判断当前消息类型（群聊或私聊）
            is_group_message = event.get_message_type() == MessageType.GROUP_MESSAGE
            
            # 根据配置获取当前场景的注入类型
            injection_type = self.group_injection_type if is_group_message else self.private_injection_type
            
            if session_id in self.original_prompts:
                # 使用user注入：恢复原始prompt
                user_message = self.original_prompts[session_id]

                del self.original_prompts[session_id]

                if injection_type == "user" and req is not None:
                    req.prompt = user_message

            if not user_message:
                user_message = event.message_str

            if not user_message:
                return

            ai_response = resp.completion_text
            if not ai_response:
                return

            # --- 核心修改：缓存逻辑 ---
            
            # 初始化该会话的缓存
            if conversation_id not in self.message_buffer:
                self.message_buffer[conversation_id] = []

            # 将当前轮次的对话加入缓存
            self.message_buffer[conversation_id].append({"role": "user", "content": user_message})
            self.message_buffer[conversation_id].append({"role": "assistant", "content": ai_response})
            
            # 计算当前缓存的对话轮数 (消息数 / 2)
            current_rounds = len(self.message_buffer[conversation_id]) // 2
            
            logger.debug(f"会话 {conversation_id} 当前缓存: {current_rounds}/{self.upload_interval} 轮")

            # 检查是否达到上传阈值
            if current_rounds >= self.upload_interval:
                # 准备上传的消息列表（复制一份）
                messages_to_upload = list(self.message_buffer[conversation_id])
                # 清空缓存
                self.message_buffer[conversation_id] = []
                
                logger.info(f"会话 {conversation_id} 达到上传阈值 ({current_rounds}轮)，准备批量上传...")

                async def _save_memory_task(msgs, sess_id, conv_id):
                    """后台批量保存任务"""
                    try:
                        # 直接调用 add_message，它支持 messages 列表参数
                        result = await self.memory_manager.add_message(
                            messages=msgs,
                            user_id=sess_id,
                            conversation_id=conv_id
                        )
                        if result.get("success"):
                            logger.info(f"成功批量保存 {len(msgs)//2} 轮对话到MemOS，会话ID: {sess_id}")
                        else:
                            logger.warning(f"批量保存到MemOS失败: {result.get('error')}")
                    except Exception as e:
                        logger.error(f"批量保存记忆时出错: {e}")

                # 提交后台任务
                task = asyncio.create_task(_save_memory_task(messages_to_upload, session_id, conversation_id))
                
                def task_done_callback(t: asyncio.Task):
                    try:
                        t.result()
                    except Exception as e:
                        logger.error(f"后台记忆保存任务异常: {e}", exc_info=True)

                task.add_done_callback(task_done_callback)
            
        except Exception as e:
            logger.error(f"处理记忆保存流程失败: {e}")

    @filter.command("用户画像")
    async def user_profile(self, event: AstrMessageEvent):
        '''这是一个用户画像指令''' # 这是 handler 的描述，将会被解析方便用户了解插件内容。非常建议填写。
        logger.info(f"触发用户画像指令")
        
        query_text = "我的人物关键词是什么？"
        async for result in self.search_memory(event, query_text, user_profile=True):
            yield result

    @filter.command("查记忆")
    async def search_memory_command(self, event: AstrMessageEvent):
        '''这是一个查询记忆的指令''' # 这是 handler 的描述，将会被解析方便用户了解插件内容。非常建议填写。
        message_str = event.message_str # 获取消息的纯文本内容
        if message_str.strip() == "查记忆":
            yield event.plain_result("请输入要查询的记忆内容，例如：/查记忆 我的兴趣爱好")
            return
        
        # 提取查询文本（去掉命令前缀）
        query_text = message_str.replace("查记忆", "", 1).strip()

        logger.info(f"触发查询记忆指令，查询内容: {query_text}")
        
        async for result in self.search_memory(event, query_text, user_profile=False):
            yield result

    async def search_memory(self, event: AstrMessageEvent, query_text: str, user_profile: bool = False):
        '''通用的记忆查询方法''' 
        if self.memory_manager is None:
            yield event.plain_result("MemOS记忆管理器未初始化，请检查配置")
            return

        session_id = self._get_session_id(event)
        conversation_id = await self._get_conversation_id(event) if not user_profile else None
        
        try:
            # 准备请求数据
            request_data = {
                "query": query_text,
                "user_id": session_id
            }
            
            # 只有在需要时才添加conversation_id
            if not user_profile and conversation_id:
                request_data["conversation_id"] = conversation_id
            
            # 使用memory_manager的方法查询记忆
            result = await self.memory_manager.search_memory(**request_data)

            if not result.get("success"):
                logger.error(f"查询用户记忆失败: {result.get('error')}")
                yield event.plain_result(f"查询用户记忆失败: {result.get('error')}")
                return

            res_data = result.get("data", {})

            # 生成用户画像报告
            report = CommandsHandler.generate_md_report(res_data, user_profile=user_profile)

            yield event.plain_result(f"{report}") # 发送一条纯文本消息
        except Exception as e:
            logger.error(f"查询用户记忆失败: {e}")
            yield event.plain_result(f"查询用户记忆失败: {str(e)}")
            return