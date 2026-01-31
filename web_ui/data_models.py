"""
Pydantic数据模型定义
"""

from typing import Optional, Dict, Any, List, Literal, Union
from pydantic import BaseModel, Field
import time
import base64


class LoginRequest(BaseModel):
    """登录请求模型"""
    password: str = Field(..., description="Web访问密码")


class LoginResponse(BaseModel):
    """登录响应模型"""
    access_token: str = Field(..., description="JWT访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")


class ApiKeyInfo(BaseModel):
    """API密钥信息模型"""
    id: str = Field(..., description="密钥ID")
    name: str = Field(..., description="密钥名称")
    source: Literal["plugin_config", "user_defined"] = Field(..., description="密钥来源")
    created_at: str = Field(..., description="创建时间")
    is_default: bool = Field(default=False, description="是否为默认密钥")

class ApiKeyListResponse(BaseModel):
    """API密钥列表响应模型"""
    keys: List[ApiKeyInfo] = Field(..., description="密钥列表")

class CreateApiKeyRequest(BaseModel):
    """创建API密钥请求模型"""
    name: str = Field(..., min_length=1, max_length=50, description="密钥名称")
    value: str = Field(..., description="base64编码的密钥值")

class UpdateApiKeyRequest(BaseModel):
    """更新API密钥请求模型"""
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="密钥名称")
    value: Optional[str] = Field(None, description="base64编码的密钥值")

class BotConfig(BaseModel):
    """Bot配置模型"""
    custom_user_id: str = Field(default="", description="MemOS user_id")
    memory_injection_enabled: bool = Field(default=True, description="记忆注入开关")
    new_session_upload_enabled: bool = Field(default=True, description="新会话上传开关")
    api_key_selection: str = Field(default="default", description="API密钥选择")  # 新增字段


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
    available_keys: List[ApiKeyInfo] = Field(default=[], description="可用API密钥列表")


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


class ApplySwitchRequest(BaseModel):
    """应用开关到所有会话请求模型"""
    switch_type: Literal["memory_injection", "new_session_upload", "api_key_selection"]
    enabled: bool
    value: Optional[str] = Field(None, description="开关值（用于api_key_selection时存储密钥ID）")


class ApplySwitchResponse(BaseModel):
    """应用开关到所有会话响应模型"""
    success: bool = Field(..., description="是否成功")
    total_sessions: int = Field(..., description="总会话数")
    updated_sessions: int = Field(..., description="成功更新的会话数")
    failed_sessions: List[str] = Field(default=[], description="失败的会话ID列表")
    message: str = Field(..., description="消息")