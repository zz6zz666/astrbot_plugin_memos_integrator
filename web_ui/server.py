"""
FastAPI服务器模块
"""

import os
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.security import HTTPAuthorizationCredentials

from . import auth
from .data_models import (
    LoginRequest, LoginResponse, BotInfo, SessionInfo,
    BotTreeItem, ConfigTreeResponse, SaveConfigRequest,
    SaveConfigResponse, HealthResponse, BotConfig,
    ApplySwitchRequest, ApplySwitchResponse,
    ApiKeyInfo, ApiKeyListResponse, CreateApiKeyRequest, UpdateApiKeyRequest,
    UserProfileRequest, UserProfileResponse, MemosConfigResponse
)
from .config_manager import ConfigManager
from .data_fetcher import DataFetcher
from .crypto_utils import get_transport_crypto, DEFAULT_TRANSPORT_KEY


def create_app(plugin_instance):
    """
    创建FastAPI应用

    Args:
        plugin_instance: 插件实例

    Returns:
        FastAPI应用实例
    """
    # 创建FastAPI应用
    app = FastAPI(
        title="MemOS Web管理界面",
        description="MemOS插件Web管理界面",
        version="1.0.0",
        docs_url="/api/docs" if plugin_instance.web_config["lan_access"] else None,
        redoc_url="/api/redoc" if plugin_instance.web_config["lan_access"] else None,
    )

    # 配置CORS
    if plugin_instance.web_config["lan_access"]:
        origins = ["*"]  # 允许所有来源
    else:
        origins = ["http://localhost", "http://localhost:8000", "http://127.0.0.1", "http://127.0.0.1:8000"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 添加GZIP压缩中间件
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # 初始化管理器
    config_manager = ConfigManager(plugin_instance._data_dir, plugin_instance)
    data_fetcher = DataFetcher(plugin_instance, config_manager)

    # 存储插件实例供依赖使用
    app.state.plugin_instance = plugin_instance
    app.state.config_manager = config_manager
    app.state.data_fetcher = data_fetcher

    # 挂载静态文件
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # API路由定义

    # 认证依赖函数
    async def get_current_user_dependency(
        credentials: HTTPAuthorizationCredentials = Depends(auth.security)
    ):
        """获取当前用户的依赖函数"""
        return await auth.get_current_user(
            credentials=credentials,
            plugin_instance=plugin_instance
        )

    @app.get("/", response_class=HTMLResponse)
    async def serve_index():
        """提供前端界面"""
        index_file = Path(__file__).parent / "static" / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        else:
            return HTMLResponse("""
                <html>
                    <head><title>MemOS Web管理界面</title></head>
                    <body>
                        <h1>MemOS Web管理界面</h1>
                        <p>前端界面正在开发中...</p>
                        <p>API文档: <a href="/api/docs">/api/docs</a></p>
                    </body>
                </html>
            """)

    @app.get("/api/health", response_model=HealthResponse)
    async def health_check():
        """健康检查"""
        return HealthResponse(
            status="healthy",
            version="1.0.0",
            web_enabled=plugin_instance.web_config["enabled"]
        )

    @app.post("/api/login", response_model=LoginResponse)
    async def login(login_data: LoginRequest):
        """用户登录"""
        auth_manager = await auth.get_auth_manager(plugin_instance)
        login_response = await auth.login_user(auth_manager, login_data)

        if not login_response:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="密码错误",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return login_response

    @app.get("/api/bots", response_model=List[BotInfo])
    async def get_bots(
        current_user: dict = Depends(get_current_user_dependency)
    ):
        """获取Bot列表"""
        return await data_fetcher.get_bots()

    @app.get("/api/bots/{bot_id}/sessions", response_model=List[SessionInfo])
    async def get_bot_sessions(
        bot_id: str,
        current_user: dict = Depends(get_current_user_dependency)
    ):
        """获取指定Bot的会话列表"""
        return await data_fetcher.get_sessions(bot_id)

    @app.get("/api/config/tree", response_model=ConfigTreeResponse)
    async def get_config_tree(
        current_user: dict = Depends(get_current_user_dependency)
    ):
        """获取完整的配置树"""
        bot_tree = await data_fetcher.get_bot_tree()

        # 为每个Bot项添加配置
        for item in bot_tree:
            item.config = config_manager.get_bot_config(item.bot.id)

        # 获取可用API密钥列表
        available_keys = config_manager.get_api_keys()

        return ConfigTreeResponse(bots=bot_tree, available_keys=available_keys)

    # ==================== API密钥管理端点 ====================

    @app.get("/api/keys", response_model=ApiKeyListResponse)
    async def get_api_keys(
        current_user: dict = Depends(get_current_user_dependency)
    ):
        """获取API密钥列表（密钥值使用传输加密）"""
        keys = config_manager.get_api_keys()

        # 对密钥值进行传输加密
        crypto = get_transport_crypto()
        encrypted_keys = []
        for key in keys:
            key_dict = key.dict()
            if key_dict.get('value'):
                key_dict['value'] = crypto.encrypt(key_dict['value'])
            encrypted_keys.append(ApiKeyInfo(**key_dict))

        return ApiKeyListResponse(keys=encrypted_keys)

    @app.post("/api/keys", response_model=dict)
    async def create_api_key(
        request_data: CreateApiKeyRequest,
        current_user: dict = Depends(get_current_user_dependency)
    ):
        """创建新的API密钥"""
        try:
            # 解密传输的密钥值
            crypto = get_transport_crypto()
            decrypted_value = crypto.decrypt(request_data.value)

            if decrypted_value is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="密钥值解密失败，请检查加密格式"
                )

            key_id = config_manager.add_api_key(request_data.name, decrypted_value)
            if not key_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="密钥创建失败，可能是名称已存在"
                )

            return {"success": True, "key_id": key_id, "message": "密钥创建成功"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"密钥创建失败: {str(e)}"
            )

    @app.put("/api/keys/{key_id}", response_model=dict)
    async def update_api_key(
        key_id: str,
        request_data: UpdateApiKeyRequest,
        current_user: dict = Depends(get_current_user_dependency)
    ):
        """更新API密钥信息"""
        try:
            # 解密传输的密钥值（如果提供了新值）
            decrypted_value = None
            if request_data.value is not None:
                crypto = get_transport_crypto()
                decrypted_value = crypto.decrypt(request_data.value)

                if decrypted_value is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="密钥值解密失败，请检查加密格式"
                    )

            success = config_manager.update_api_key(
                key_id,
                name=request_data.name,
                value=decrypted_value
            )
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="密钥更新失败，可能是名称已存在或密钥不存在"
                )

            return {"success": True, "message": "密钥更新成功"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"密钥更新失败: {str(e)}"
            )

    @app.delete("/api/keys/{key_id}", response_model=dict)
    async def delete_api_key(
        key_id: str,
        current_user: dict = Depends(get_current_user_dependency)
    ):
        """删除API密钥"""
        try:
            success = config_manager.delete_api_key(key_id)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="密钥删除失败，可能是密钥不存在或是默认密钥"
                )

            return {"success": True, "message": "密钥删除成功"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"密钥删除失败: {str(e)}"
            )

    @app.post("/api/config/{bot_id}/apply-key-to-all", response_model=ApplySwitchResponse)
    async def apply_api_key_to_all(
        bot_id: str,
        request_data: ApplySwitchRequest,  # 复用ApplySwitchRequest，使用value字段存储密钥ID
        current_user: dict = Depends(get_current_user_dependency)
    ):
        """将API密钥选择应用到所有会话"""
        try:
            if request_data.switch_type != "api_key_selection":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="无效的开关类型"
                )

            if not request_data.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="必须提供密钥ID"
                )

            result = config_manager.apply_api_key_to_all_sessions(bot_id, request_data.value)

            success = result["updated"] == result["total"]
            if success:
                message = f"成功更新 {result['updated']}/{result['total']} 个会话"
            else:
                # 只显示前5个失败的会话ID，避免消息过长
                failed_preview = ", ".join(result["failed"][:5])
                if len(result["failed"]) > 5:
                    failed_preview += f" 等{len(result['failed'])}个"
                message = f"部分更新成功：{result['updated']}/{result['total']} 个会话，失败：{failed_preview}"

            return ApplySwitchResponse(
                success=success,
                total_sessions=result["total"],
                updated_sessions=result["updated"],
                failed_sessions=result["failed"],
                message=message
            )
        except HTTPException:
            raise
        except Exception as e:
            return ApplySwitchResponse(
                success=False,
                total_sessions=0,
                updated_sessions=0,
                failed_sessions=[],
                message=f"应用API密钥失败: {str(e)}"
            )

    @app.get("/api/config/{bot_id}", response_model=BotConfig)
    async def get_bot_config(
        bot_id: str,
        current_user: dict = Depends(get_current_user_dependency)
    ):
        """获取Bot配置"""
        return config_manager.get_bot_config(bot_id)

    @app.get("/api/config/{bot_id}/{session_id}", response_model=BotConfig)
    async def get_session_config(
        bot_id: str,
        session_id: str,
        current_user: dict = Depends(get_current_user_dependency)
    ):
        """获取会话配置"""
        return config_manager.get_session_config(bot_id, session_id)

    @app.get("/api/config/{bot_id}/{session_id}/effective", response_model=BotConfig)
    async def get_effective_config(
        bot_id: str,
        session_id: str,
        current_user: dict = Depends(get_current_user_dependency)
    ):
        """获取生效配置（考虑优先级）"""
        return config_manager.get_effective_config(bot_id, session_id)


    @app.post("/api/config/{bot_id}/apply-switch-to-all", response_model=ApplySwitchResponse)
    async def apply_switch_to_all(
        bot_id: str,
        request_data: ApplySwitchRequest,
        current_user: dict = Depends(get_current_user_dependency)
    ):
        """将开关状态应用到所有会话"""
        try:
            if request_data.switch_type == "api_key_selection":
                # API密钥选择应用到全部
                if not request_data.value:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="API密钥选择必须提供密钥ID"
                    )
                result = config_manager.apply_api_key_to_all_sessions(bot_id, request_data.value)
            else:
                # 原有的布尔开关应用到全部
                result = config_manager.apply_switch_to_all_sessions(
                    bot_id, request_data.switch_type, request_data.enabled
                )

            success = result["updated"] == result["total"]
            if success:
                message = f"成功更新 {result['updated']}/{result['total']} 个会话"
            else:
                # 只显示前5个失败的会话ID，避免消息过长
                failed_preview = ", ".join(result["failed"][:5])
                if len(result["failed"]) > 5:
                    failed_preview += f" 等{len(result['failed'])}个"
                message = f"部分更新成功：{result['updated']}/{result['total']} 个会话，失败：{failed_preview}"

            return ApplySwitchResponse(
                success=success,
                total_sessions=result["total"],
                updated_sessions=result["updated"],
                failed_sessions=result["failed"],
                message=message
            )
        except HTTPException:
            raise
        except Exception as e:
            return ApplySwitchResponse(
                success=False,
                total_sessions=0,
                updated_sessions=0,
                failed_sessions=[],
                message=f"应用开关失败: {str(e)}"
            )

    @app.post("/api/config/{bot_id}", response_model=SaveConfigResponse)
    async def save_bot_config(
        bot_id: str,
        config_data: SaveConfigRequest,
        current_user: dict = Depends(get_current_user_dependency)
    ):
        """保存Bot配置"""
        success = config_manager.save_bot_config(bot_id, config_data.config)

        return SaveConfigResponse(
            success=success,
            message="配置保存成功" if success else "配置保存失败，请检查用户ID格式"
        )

    @app.post("/api/config/{bot_id}/reset", response_model=SaveConfigResponse)
    async def reset_bot_config(
        bot_id: str,
        current_user: dict = Depends(get_current_user_dependency)
    ):
        """重置Bot配置为默认状态，并清除所有会话配置"""
        result = config_manager.reset_bot_config(bot_id)

        return SaveConfigResponse(
            success=result["success"],
            message=result["message"]
        )

    @app.post("/api/config/{bot_id}/{session_id}", response_model=SaveConfigResponse)
    async def save_session_config(
        bot_id: str,
        session_id: str,
        config_data: SaveConfigRequest,
        current_user: dict = Depends(get_current_user_dependency)
    ):
        """保存会话配置"""
        success = config_manager.save_session_config(bot_id, session_id, config_data.config)

        return SaveConfigResponse(
            success=success,
            message="配置保存成功" if success else "配置保存失败，请检查用户ID格式"
        )

    @app.delete("/api/config/{bot_id}/{session_id}", response_model=SaveConfigResponse)
    async def delete_session_config(
        bot_id: str,
        session_id: str,
        current_user: dict = Depends(get_current_user_dependency)
    ):
        """删除会话配置"""
        success = config_manager.delete_session_config(bot_id, session_id)

        return SaveConfigResponse(
            success=success,
            message="配置删除成功" if success else "配置删除失败"
        )


    @app.get("/api/memos-config/{bot_id}/{session_id}", response_model=MemosConfigResponse)
    async def get_memos_config(
        bot_id: str,
        session_id: str,
        current_user: dict = Depends(get_current_user_dependency)
    ):
        """获取MemOS服务器配置（用于前端直接请求MemOS服务器）"""
        try:
            # 获取生效配置
            effective_config = config_manager.get_effective_config(bot_id, session_id)

            # 确定user_id
            user_id = effective_config.custom_user_id if effective_config.custom_user_id else session_id

            # 获取API密钥
            api_key = ""
            api_keys = config_manager.config_data.get("api_keys", {})
            key_id = effective_config.api_key_selection

            if key_id == "default":
                # 使用插件配置的默认密钥
                api_key = plugin_instance.config.get("api_key", "")
            elif key_id in api_keys:
                api_key = api_keys[key_id].get("value", "")

            # 加密API密钥用于传输
            if api_key:
                crypto = get_transport_crypto()
                api_key = crypto.encrypt(api_key)

            # 获取MemOS服务器地址
            base_url = plugin_instance.config.get("base_url", "https://memos.memtensor.cn/api/openmem/v1")

            return MemosConfigResponse(
                base_url=base_url,
                api_key=api_key,
                user_id=user_id
            )

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"获取MemOS配置失败: {str(e)}"
            )

    @app.post("/api/config/bulk", response_model=SaveConfigResponse)
    async def save_bulk_config(
        request: Request,
        current_user: dict = Depends(get_current_user_dependency)
    ):
        """批量保存配置"""
        try:
            data = await request.json()
            all_success = True

            # 处理Bot配置
            for bot_id, bot_config in data.get("bots", {}).items():
                config = BotConfig(**bot_config)
                if not config_manager.save_bot_config(bot_id, config):
                    all_success = False

            # 处理会话配置
            for bot_id, sessions in data.get("sessions", {}).items():
                for session_id, session_config in sessions.items():
                    config = BotConfig(**session_config)
                    if not config_manager.save_session_config(bot_id, session_id, config):
                        all_success = False

            return SaveConfigResponse(
                success=all_success,
                message="批量配置保存成功" if all_success else "部分配置保存失败"
            )

        except Exception as e:
            return SaveConfigResponse(
                success=False,
                message=f"批量保存失败: {str(e)}"
            )


    @app.post("/api/logout")
    async def logout(
        current_user: dict = Depends(get_current_user_dependency)
    ):
        """用户注销"""
        # JWT是无状态的，客户端只需删除令牌即可
        return {"message": "注销成功"}

    # 错误处理
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """HTTP异常处理"""
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """通用异常处理"""
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "内部服务器错误"},
        )

    return app