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
    SaveConfigResponse, HealthResponse, BotConfig
)
from .config_manager import ConfigManager
from .data_fetcher import DataFetcher


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
    config_manager = ConfigManager(plugin_instance._data_dir)
    data_fetcher = DataFetcher(plugin_instance)

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

        return ConfigTreeResponse(bots=bot_tree)

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