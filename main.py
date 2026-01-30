"""
MemOS记忆集成插件
使用HTTP方式实现记忆获取、注入和更新功能
"""

import asyncio
import sqlite3
import random
import string
from typing import Dict, List, Optional
from pathlib import Path
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.platform import MessageType
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api.provider import ProviderRequest, LLMResponse
from astrbot.api import AstrBotConfig, logger
from .memory_manager import MemoryManager
from .commands_handler import CommandsHandler, parse_feedback_command
from .web_ui.config_manager import ConfigManager
from .web_ui.data_models import BotConfig

# 主插件类
@register("astrbot_plugin_memos_integrator","zz6zz666", "MemOS记忆集成插件", "1.6.0")
class MemosIntegratorPlugin(Star):
    PLUGIN_ID = "astrbot_plugin_memos_integrator"
    
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.memory_manager = None
        self.memory_limit = 5
        self.prompt_language = "auto"
        # 缓存配置
        self.upload_interval = 1 
        # 初始化基础目录和数据目录
        self._base_dir = Path(__file__).resolve().parent
        self._data_dir = self._resolve_data_dir()
        # 数据库文件路径
        self._db_file = self._data_dir / "message_cache.db"
        # 确保数据目录存在
        self._data_dir.mkdir(parents=True, exist_ok=True)
        # 初始化数据库连接
        self._db_conn = sqlite3.connect(self._db_file)
        self._init_db()
        # 初始化空的消息缓冲区，我们现在主要依赖数据库
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

        # Web服务器相关属性初始化
        self.web_server = None
        self.web_server_task = None
        self.web_config = {
            "enabled": self.config.get("web_enabled", False),
            "port": self.config.get("web_port", 8000),
            "lan_access": self.config.get("web_lan_access", False),
            "password": self.config.get("web_password", "")
        }

        # 配置管理器初始化
        self.config_manager = ConfigManager(self._data_dir, self)

        # 如果密码为空，生成随机8位密码
        if not self.web_config["password"]:
            self.web_config["password"] = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            logger.info(f"Web访问密码已自动生成: {self.web_config['password']}")
            
    def _resolve_data_dir(self) -> Path:
        """优先使用 StarTools 数据目录，失败时退回到 AstrBot/data/plugin_data 下。"""
        fallback_dir = self._base_dir.parent.parent / "plugin_data" / self.PLUGIN_ID
        try:
            preferred_raw = StarTools.get_data_dir(self.PLUGIN_ID)
        except Exception:
            preferred_raw = None
        if preferred_raw:
            preferred_path = Path(preferred_raw)
            try:
                preferred_path.mkdir(parents=True, exist_ok=True)
                return preferred_path
            except Exception as exc:
                logger.warning(f"[MemOS记忆集成插件] 创建数据目录失败({exc})，退回 fallback：{fallback_dir}")
        fallback_dir.mkdir(parents=True, exist_ok=True)
        return fallback_dir

    async def start_web_server(self):
        """启动FastAPI Web服务器"""
        # 检查web_config属性是否存在
        if not hasattr(self, 'web_config'):
            logger.warning("web_config属性未初始化，无法启动Web服务器")
            return
        if not self.web_config["enabled"]:
            logger.info("Web管理界面已禁用，跳过启动")
            return

        try:
            # 动态导入以避免循环依赖
            import uvicorn
            from .web_ui.server import create_app

            # 创建FastAPI应用
            app = create_app(self)

            # 配置服务器参数
            host = "0.0.0.0" if self.web_config["lan_access"] else "127.0.0.1"
            port = self.web_config["port"]

            # 创建uvicorn配置
            config = uvicorn.Config(
                app=app,
                host=host,
                port=port,
                log_level="info",
                access_log=True
            )

            # 创建服务器实例
            self.web_server = uvicorn.Server(config)

            # 在后台任务中启动服务器
            self.web_server_task = asyncio.create_task(self.web_server.serve())

            logger.info(f"Web管理界面已启动: http://{host}:{port}")
            logger.info(f"Web访问密码: {self.web_config['password']}")
            if self.web_config["lan_access"]:
                logger.info("局域网访问已启用，其他设备可访问")
            else:
                logger.info("仅限本机访问，如需跨设备访问请启用局域网访问开关")

        except ImportError as e:
            logger.error(f"启动Web服务器失败，缺少依赖: {e}")
            logger.error("请安装FastAPI、uvicorn、PyJWT和passlib: pip install fastapi uvicorn PyJWT[crypto] passlib[bcrypt]")
        except OSError as e:
            if "Address already in use" in str(e):
                logger.error(f"端口 {self.web_config['port']} 已被占用，无法启动Web服务器")
                # 尝试备用端口
                try:
                    port = self.web_config["port"] + 1
                    config = uvicorn.Config(
                        app=app,
                        host=host,
                        port=port,
                        log_level="info",
                        access_log=True
                    )
                    self.web_server = uvicorn.Server(config)
                    self.web_server_task = asyncio.create_task(self.web_server.serve())
                    logger.info(f"使用备用端口启动Web管理界面: http://{host}:{port}")
                except Exception as fallback_error:
                    logger.error(f"备用端口也失败: {fallback_error}")
            else:
                logger.error(f"启动Web服务器失败: {e}")
        except Exception as e:
            logger.error(f"启动Web服务器失败: {e}")

    async def stop_web_server(self):
        """停止Web服务器"""
        # 检查web_server属性是否存在
        if not hasattr(self, 'web_server') or not self.web_server:
            return
        try:
            # 优雅关闭服务器
            self.web_server.should_exit = True
            if self.web_server_task:
                # 等待服务器停止
                await asyncio.wait_for(self.web_server_task, timeout=5.0)
            # 清理资源
            self.web_server = None
            self.web_server_task = None
            logger.info("Web管理界面已停止")
        except asyncio.TimeoutError:
            logger.warning("Web服务器停止超时，强制终止")
            if self.web_server_task:
                self.web_server_task.cancel()
                try:
                    await self.web_server_task
                except asyncio.CancelledError:
                    pass
            self.web_server = None
            self.web_server_task = None
        except Exception as e:
            logger.error(f"停止Web服务器失败: {e}")

    async def initialize(self):
        """插件初始化，启动Web服务器"""
        await super().initialize()

        # 初始化配置文件：同步数据库中的bot和会话
        try:
            await self.config_manager.async_sync_with_database()
            logger.info("配置文件数据库同步完成")
        except Exception as e:
            logger.error(f"配置文件数据库同步失败: {e}")

        # 检查web_config属性是否存在
        if not hasattr(self, 'web_config'):
            logger.warning("web_config属性未初始化，跳过Web服务器启动")
            return
        if self.web_config["enabled"]:
            # 延迟启动，确保其他组件已初始化
            await asyncio.sleep(1)
            await self.start_web_server()

    async def terminate(self):
        """插件终止，停止Web服务器"""
        await self.stop_web_server()
        # 关闭数据库连接
        if hasattr(self, '_db_conn') and self._db_conn:
            self._db_conn.close()
            logger.info("数据库连接已关闭")
        # 清理记忆管理器
        if hasattr(self, 'memory_manager'):
            self.memory_manager = None
        await super().terminate()

    def _init_db(self):
        """初始化数据库表结构"""
        cursor = self._db_conn.cursor()
        # 创建消息缓存表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS message_cache (
            conversation_id TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            PRIMARY KEY (conversation_id, message_id)
        )
        ''')
        # 创建索引以提高查询性能
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_conversation_id ON message_cache (conversation_id)
        ''')
        self._db_conn.commit()
    
    def _save_message_to_db(self, conversation_id: str, role: str, content: str):
        """将单条消息保存到数据库"""
        cursor = self._db_conn.cursor()
        
        try:
            # 获取当前会话的最大消息ID，用于确定下一个消息ID
            cursor.execute('SELECT MAX(message_id) FROM message_cache WHERE conversation_id = ?', (conversation_id,))
            max_id = cursor.fetchone()[0]
            next_id = max_id + 1 if max_id is not None else 0
            
            # 插入新消息
            cursor.execute(
                'INSERT INTO message_cache (conversation_id, message_id, role, content) VALUES (?, ?, ?, ?)',
                (conversation_id, next_id, role, content)
            )
            
            self._db_conn.commit()
            
        except Exception as e:
            logger.error(f"将消息保存到数据库失败: {e}")
            self._db_conn.rollback()
    
    def _clear_conversation_cache(self, conversation_id: str):
        """清空特定会话的缓存"""
        cursor = self._db_conn.cursor()
        
        try:
            cursor.execute('DELETE FROM message_cache WHERE conversation_id = ?', (conversation_id,))
            self._db_conn.commit()
        except Exception as e:
            logger.error(f"清空会话缓存失败: {e}")
            self._db_conn.rollback()
    
    def _get_conversation_message_count(self, conversation_id: str) -> int:
        """获取特定会话的消息数量"""
        cursor = self._db_conn.cursor()
        
        try:
            cursor.execute('SELECT COUNT(*) FROM message_cache WHERE conversation_id = ?', (conversation_id,))
            count = cursor.fetchone()[0]
            return count
        except Exception as e:
            logger.error(f"获取会话消息数量失败: {e}")
            return 0

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

    def _parse_unified_msg_origin(self, unified_msg_origin: str):
        """
        解析unified_msg_origin格式为(bot_id, session_id)
        格式: "platform_name:message_type:session_id"
        Web界面使用session_id格式为"message_type:session_id"
        """
        parts = unified_msg_origin.split(':')
        if len(parts) >= 3:
            # platform_name作为bot_id
            bot_id = parts[0]
            # 剩余部分作为Web界面的session_id
            session_id = ':'.join(parts[1:])
            return bot_id, session_id
        else:
            # 如果不是标准格式，使用整个作为session_id，bot_id为空
            logger.warning(f"unified_msg_origin格式异常: {unified_msg_origin}")
            return '', unified_msg_origin

    @filter.on_llm_request(priority=-1000)
    async def inject_memories(self, event: AstrMessageEvent, req: ProviderRequest):
        """在LLM请求前获取记忆并注入"""
        if self.memory_manager is None:
            return

        # 获取完整的unified_msg_origin
        unified_msg_origin = self._get_session_id(event)
        # 解析为bot_id和session_id（Web界面格式）
        bot_id, session_id_web = self._parse_unified_msg_origin(unified_msg_origin)

        # 获取配置，如果配置文件访问失败则使用默认配置
        try:
            # 确保会话配置存在（如果不存在则从bot配置复制创建）
            self.config_manager.ensure_session_config(bot_id, session_id_web, unified_msg_origin)
            # 获取生效配置
            effective_config = self.config_manager.get_effective_config(bot_id, session_id_web)
        except Exception as e:
            logger.warning(f"配置文件访问失败，使用默认配置: {e}")
            # 使用默认配置
            effective_config = BotConfig(
                custom_user_id="",
                memory_injection_enabled=True,
                new_session_upload_enabled=True
            )

        # 检查记忆注入开关
        if not effective_config.memory_injection_enabled:
            logger.debug(f"记忆注入已禁用，bot_id={bot_id}, session_id={session_id_web}")
            return

        conversation_id = await self._get_conversation_id(event)
        user_message = req.prompt

        # 无论哪种注入方式，都保存原始prompt以便后续记忆保存
        self.original_prompts[unified_msg_origin] = user_message

        # 确定user_id：使用自定义ID或默认的unified_msg_origin
        user_id = effective_config.custom_user_id if effective_config.custom_user_id else unified_msg_origin

        memories = await self.memory_manager.retrieve_relevant_memories(
            user_message, user_id, conversation_id, limit=self.memory_limit
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
                logger.info(f"已为会话 {user_id} 以system类型注入 {len(memories)} 条记忆")
            else:
                # 使用user注入：更新prompt为包含记忆的版本
                req.prompt = memory_prompt
                logger.info(f"已为会话 {user_id} 以user类型注入 {len(memories)} 条记忆")
            
    @filter.on_llm_response()
    async def save_memories(self, event: AstrMessageEvent, resp: LLMResponse):
        """在LLM响应后将对话加入缓存，达到阈值后批量保存到MemOS"""

        try:
            if self.memory_manager is None:
                return

            # 获取完整的unified_msg_origin
            unified_msg_origin = self._get_session_id(event)
            # 解析为bot_id和session_id（Web界面格式）
            bot_id, session_id_web = self._parse_unified_msg_origin(unified_msg_origin)

            # 获取配置，如果配置文件访问失败则使用默认配置
            try:
                # 确保会话配置存在（如果不存在则从bot配置复制创建）
                self.config_manager.ensure_session_config(bot_id, session_id_web, unified_msg_origin)
                # 获取生效配置
                effective_config = self.config_manager.get_effective_config(bot_id, session_id_web)
            except Exception as e:
                logger.warning(f"配置文件访问失败，使用默认配置: {e}")
                # 使用默认配置
                effective_config = BotConfig(
                    custom_user_id="",
                    memory_injection_enabled=True,
                    new_session_upload_enabled=True
                )

            # 检查新会话上传开关
            if not effective_config.new_session_upload_enabled:
                logger.debug(f"新会话上传已禁用，bot_id={bot_id}, session_id={session_id_web}")
                return

            conversation_id = await self._get_conversation_id(event)
            # 为了向后兼容，保留session_id变量作为unified_msg_origin
            session_id = unified_msg_origin
            # 确定user_id：使用自定义ID或默认的unified_msg_origin
            user_id = effective_config.custom_user_id if effective_config.custom_user_id else unified_msg_origin

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
            
            # 如果upload_interval为1，直接上传，不使用缓存
            if self.upload_interval == 1:
                logger.debug(f"会话 {conversation_id} upload_interval为1，直接上传")
                messages_to_upload = [{"role": "user", "content": user_message}, {"role": "assistant", "content": ai_response}]

                logger.info(f"会话 {conversation_id} 直接上传1轮对话...")

                # 直接上传任务
                async def _save_memory_task_direct(msgs, user_id, conv_id):
                    try:
                        result = await self.memory_manager.add_message(
                            messages=msgs,
                            user_id=user_id,
                            conversation_id=conv_id
                        )
                        if result.get("success"):
                            logger.info(f"成功直接保存1轮对话到MemOS，user_id: {user_id}")
                        else:
                            logger.warning(f"直接保存到MemOS失败: {result.get('error')}")
                    except Exception as e:
                        logger.error(f"直接保存记忆时出错: {e}")

                task = asyncio.create_task(_save_memory_task_direct(messages_to_upload, user_id, conversation_id))
                task.add_done_callback(lambda t: t.exception() and logger.error(f"直接保存任务异常: {t.exception()}", exc_info=True))
            else:
                # 将当前轮次的对话保存到数据库
                self._save_message_to_db(conversation_id, "user", user_message)
                self._save_message_to_db(conversation_id, "assistant", ai_response)
                
                # 计算当前缓存的对话轮数 (消息数 / 2)
                message_count = self._get_conversation_message_count(conversation_id)
                current_rounds = message_count // 2
                
                logger.debug(f"会话 {conversation_id} 当前缓存: {current_rounds}/{self.upload_interval} 轮")

                # 检查是否达到上传阈值
                if current_rounds >= self.upload_interval:
                    # 从数据库加载该会话的所有消息用于上传
                    cursor = self._db_conn.cursor()
                    cursor.execute('SELECT role, content FROM message_cache WHERE conversation_id = ? ORDER BY message_id', (conversation_id,))
                    messages_to_upload = [{'role': role, 'content': content} for role, content in cursor.fetchall()]
                    
                    # 清空数据库中的缓存
                    self._clear_conversation_cache(conversation_id)
                    
                    logger.info(f"会话 {conversation_id} 达到上传阈值 ({current_rounds}轮)，准备批量上传...")
                else:
                    # 未达到上传阈值，不执行上传
                    return

                async def _save_memory_task(msgs, user_id, conv_id):
                    """后台批量保存任务"""
                    try:
                        # 直接调用 add_message，它支持 messages 列表参数
                        result = await self.memory_manager.add_message(
                            messages=msgs,
                            user_id=user_id,
                            conversation_id=conv_id
                        )
                        if result.get("success"):
                            logger.info(f"成功批量保存 {len(msgs)//2} 轮对话到MemOS，user_id: {user_id}")
                        else:
                            logger.warning(f"批量保存到MemOS失败: {result.get('error')}")
                    except Exception as e:
                        logger.error(f"批量保存记忆时出错: {e}")

                # 提交后台任务
                task = asyncio.create_task(_save_memory_task(messages_to_upload, user_id, conversation_id))
                
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

        # 获取完整的unified_msg_origin
        unified_msg_origin = self._get_session_id(event)
        # 解析为bot_id和session_id（Web界面格式）
        bot_id, session_id_web = self._parse_unified_msg_origin(unified_msg_origin)

        # 获取配置，如果配置文件访问失败则使用默认配置
        try:
            # 确保会话配置存在（如果不存在则从bot配置复制创建）
            self.config_manager.ensure_session_config(bot_id, session_id_web, unified_msg_origin)
            # 获取生效配置
            effective_config = self.config_manager.get_effective_config(bot_id, session_id_web)
        except Exception as e:
            logger.warning(f"配置文件访问失败，使用默认配置: {e}")
            # 使用默认配置
            effective_config = BotConfig(
                custom_user_id="",
                memory_injection_enabled=True,
                new_session_upload_enabled=True
            )

        # 确定user_id：使用自定义ID或默认的unified_msg_origin
        user_id = effective_config.custom_user_id if effective_config.custom_user_id else unified_msg_origin

        conversation_id = await self._get_conversation_id(event) if not user_profile else None

        try:
            # 准备请求数据
            request_data = {
                "query": query_text,
                "user_id": user_id
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

    @filter.command("加反馈")
    async def add_feedback_command(self, event: AstrMessageEvent):
        '''这是一个添加反馈的指令''' # 这是 handler 的描述，将会被解析方便用户了解插件内容。非常建议填写。
        message_str = event.message_str # 获取消息的纯文本内容
        if message_str.strip() == "加反馈":
            yield event.plain_result("请输入反馈内容，例如：/加反馈 不对，我们现在改成一线城市餐补150元每天，住宿补贴700元每天；二三线城市还是原来那样。")
            return
        
        # 解析反馈命令
        _, feedback_content, error = parse_feedback_command(message_str)
        if error:
            yield event.plain_result(error)
            return

        logger.info(f"触发添加反馈指令，反馈内容: {feedback_content}")
        
        if self.memory_manager is None:
            yield event.plain_result("MemOS记忆管理器未初始化，请检查配置")
            return

        session_id = self._get_session_id(event)
        conversation_id = await self._get_conversation_id(event)
        
        try:
            # 使用memory_manager的方法添加反馈
            result = await self.memory_manager.add_feedback(feedback_content, session_id, conversation_id)

            if not result.get("success"):
                logger.error(f"添加反馈失败: {result.get('error')}")
                yield event.plain_result(f"添加反馈失败: {result.get('error')}")
                return

            # 生成反馈结果报告
            report = CommandsHandler.generate_feedback_result(result.get('success'), result.get('error'))

            yield event.plain_result(f"{report}") # 发送一条纯文本消息
        except Exception as e:
            logger.error(f"添加反馈失败: {e}")
            yield event.plain_result(f"添加反馈失败: {str(e)}")
            return