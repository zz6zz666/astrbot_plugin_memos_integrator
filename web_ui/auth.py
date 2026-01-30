"""
身份验证管理模块
"""

import os
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
from jwt import PyJWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .data_models import LoginRequest, LoginResponse


# JWT配置
SECRET_KEY = "memos_integrator_web_secret_key_change_in_production"  # 生产环境应该使用强密钥
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24小时

# 密码哈希上下文
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# HTTP Bearer认证
security = HTTPBearer()


class AuthManager:
    """身份验证管理器"""

    def __init__(self, password_hash: str):
        """
        初始化AuthManager

        Args:
            password_hash: 密码的哈希值
        """
        self.password_hash = password_hash

    def verify_password(self, plain_password: str) -> bool:
        """验证密码"""
        return pwd_context.verify(plain_password, self.password_hash)

    def create_access_token(self) -> str:
        """创建JWT访问令牌"""
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {"exp": expire, "sub": "web_admin", "type": "access"}
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    def verify_token(self, token: str) -> bool:
        """验证JWT令牌"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            # 检查令牌类型
            if payload.get("type") != "access":
                return False
            # 检查是否过期（jwt.decode会自动检查exp）
            return True
        except PyJWTError:
            return False

    def get_token_payload(self, token: str) -> Optional[Dict[str, Any]]:
        """获取令牌负载（不验证过期）"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except PyJWTError:
            return None


async def get_auth_manager(plugin_instance) -> AuthManager:
    """
    获取AuthManager实例的依赖函数

    Args:
        plugin_instance: 插件实例

    Returns:
        AuthManager实例
    """
    # 从插件配置获取密码哈希
    # 注意：实际使用时应该存储密码哈希而不是明文
    # 这里为了简化，我们直接使用明文密码进行哈希验证
    password = plugin_instance.web_config["password"]

    # 创建密码哈希
    password_hash = pwd_context.hash(password)

    return AuthManager(password_hash)


async def login_user(
    auth_manager: AuthManager,
    login_data: LoginRequest
) -> Optional[LoginResponse]:
    """
    用户登录

    Args:
        auth_manager: AuthManager实例
        login_data: 登录请求数据

    Returns:
        LoginResponse或None（登录失败）
    """
    if auth_manager.verify_password(login_data.password):
        access_token = auth_manager.create_access_token()
        return LoginResponse(access_token=access_token, token_type="bearer")
    return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    plugin_instance = None
) -> Dict[str, Any]:
    """
    获取当前用户的依赖函数

    Args:
        credentials: HTTP Bearer凭证
        plugin_instance: 插件实例（通过依赖注入）

    Returns:
        用户信息字典

    Raises:
        HTTPException: 认证失败
    """
    if plugin_instance is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="插件实例未初始化"
        )

    token = credentials.credentials

    # 创建临时的AuthManager来验证令牌
    auth_manager = await get_auth_manager(plugin_instance)

    if not auth_manager.verify_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"username": "web_admin", "authenticated": True}


# 工具函数
def hash_password(password: str) -> str:
    """生成密码哈希"""
    return pwd_context.hash(password)