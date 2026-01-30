"""
Pydantic数据模型定义
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """登录请求模型"""
    password: str = Field(..., description="Web访问密码")


class LoginResponse(BaseModel):
    """登录响应模型"""
    access_token: str = Field(..., description="JWT访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")


class BotConfig(BaseModel):
    """Bot配置模型"""
    custom_user_id: str = Field(default="", description="MemOS user_id")
    memory_injection_enabled: bool = Field(default=True, description="记忆注入开关")
    new_session_upload_enabled: bool = Field(default=True, description="新会话上传开关")


class SessionConfig(BotConfig):
    """会话配置模型（继承Bot配置）"""
    pass


class BotInfo(BaseModel):
    """Bot信息模型"""
    id: str = Field(..., description="Bot ID")
    name: str = Field(..., description="Bot名称")
    type: str = Field(..., description="Bot类型/适配器名称")
    enabled: bool = Field(default=True, description="是否启用")


class SessionInfo(BaseModel):
    """会话信息模型"""
    id: str = Field(..., description="会话ID")
    unified_msg_origin: str = Field(..., description="统一消息来源")
    conversation_count: Optional[int] = Field(default=None, description="对话数量")


class BotTreeItem(BaseModel):
    """树形结构项模型"""
    bot: BotInfo = Field(..., description="Bot信息")
    sessions: list[SessionInfo] = Field(default=[], description="会话列表")
    config: BotConfig = Field(default_factory=BotConfig, description="Bot配置")


class ConfigTreeResponse(BaseModel):
    """配置树响应模型"""
    bots: list[BotTreeItem] = Field(..., description="Bot树形列表")


class SaveConfigRequest(BaseModel):
    """保存配置请求模型"""
    config: BotConfig = Field(..., description="配置数据")


class SaveConfigResponse(BaseModel):
    """保存配置响应模型"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="消息")


class HealthResponse(BaseModel):
    """健康检查响应模型"""
    status: str = Field(..., description="状态")
    version: str = Field(..., description="版本")
    web_enabled: bool = Field(..., description="Web是否启用")