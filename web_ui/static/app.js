// MemOS Web管理界面前端逻辑

class MemOSWebUI {
    constructor() {
        this.apiBase = window.location.origin;
        this.accessToken = localStorage.getItem('memos_web_token') || '';
        this.currentBotId = null;
        this.currentBotName = null;
        this.botConfigs = {};
        this.sessionConfigs = {};
        this.isAuthenticated = false;
        this.unsavedChanges = false;
        this.applyingToAllInProgress = false;

        // 新增密钥管理相关属性
        this.apiKeys = [];  // 存储密钥列表
        this.currentEditingKeyId = null;  // 当前正在编辑的密钥ID
        this.keyManagementExpanded = false;  // 密钥管理区域是否展开

        // 初始化事件监听
        this.initEventListeners();

        // 检查认证状态
        this.checkAuth();

        // 初始化主题
        this.initTheme();

        // 初始化侧边栏
        this.initSidebar();
    }

    // 初始化事件监听器
    initEventListeners() {
        // 登录相关
        document.getElementById('login-btn')?.addEventListener('click', () => this.handleLogin());
        document.getElementById('password')?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.handleLogin();
        });
        document.getElementById('toggle-password')?.addEventListener('click', () => this.togglePasswordVisibility());
        document.getElementById('logout-btn')?.addEventListener('click', () => this.handleLogout());

        // 主题切换
        document.getElementById('theme-toggle')?.addEventListener('click', () => this.toggleTheme());

        // 搜索功能
        document.getElementById('bot-search')?.addEventListener('input', (e) => this.searchBots(e.target.value));
        document.getElementById('session-search')?.addEventListener('input', (e) => this.searchSessions(e.target.value));

        // Bot列表折叠功能
        document.getElementById('bot-list-toggle')?.addEventListener('click', () => this.toggleBotList());

        // 操作按钮
        document.getElementById('save-bot-config-btn')?.addEventListener('click', async () => {
            try {
                await this.saveBotConfig();
                this.showSaveStatus('Bot配置保存成功', 'success');
            } catch (error) {
                this.showSaveStatus(`保存失败: ${error.message}`, 'error');
            }
        });
        document.getElementById('reset-btn')?.addEventListener('click', () => this.resetConfigs());
        document.getElementById('expand-all-btn')?.addEventListener('click', () => this.expandAllSessions());
        document.getElementById('collapse-all-btn')?.addEventListener('click', () => this.collapseAllSessions());
        document.getElementById('apply-memory-injection-to-all')?.addEventListener('click', () => this.applyMemoryInjectionToAll());
        document.getElementById('apply-new-session-upload-to-all')?.addEventListener('click', () => this.applyNewSessionUploadToAll());

        // Bot配置输入监听
        document.getElementById('bot-custom-user-id')?.addEventListener('input', () => this.markUnsaved());
        document.getElementById('bot-memory-injection')?.addEventListener('change', () => this.markUnsaved());
        document.getElementById('bot-new-session-upload')?.addEventListener('change', () => this.markUnsaved());

        // 密钥管理相关
        document.getElementById('key-management-toggle')?.addEventListener('click', () => this.toggleKeyManagement());
        document.getElementById('add-key-btn')?.addEventListener('click', async () => await this.handleAddKey());
        document.getElementById('apply-api-key-to-all')?.addEventListener('click', async () => await this.applyApiKeyToAll());

        // Bot配置输入监听
        document.getElementById('bot-api-key-selection')?.addEventListener('change', () => this.markUnsaved());

        // 会话配置输入监听（动态添加）

        // 密钥编辑/删除按钮（动态添加）

        // 编辑对话框事件
        document.querySelector('.btn-close-modal')?.addEventListener('click', () => this.hideKeyEditDialog());
        document.querySelector('.btn-cancel-edit')?.addEventListener('click', () => this.hideKeyEditDialog());
        document.querySelector('.btn-save-edit')?.addEventListener('click', async () => await this.handleSaveKeyEdit());

        // 窗口事件
        window.addEventListener('beforeunload', (e) => {
            if (this.unsavedChanges) {
                e.preventDefault();
                e.returnValue = '您有未保存的更改，确定要离开吗？';
            }
        });

        // 侧边栏切换
        document.getElementById('sidebar-toggle')?.addEventListener('click', () => this.toggleSidebar());

        // 遮罩层点击关闭侧栏
        document.getElementById('sidebar-overlay')?.addEventListener('click', () => {
            if (window.innerWidth <= 768) {
                this.closeSidebar();
            }
        });
    }

    // 初始化主题
    initTheme() {
        const savedTheme = localStorage.getItem('memos_web_theme');
        const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        const theme = savedTheme || systemTheme;

        document.documentElement.setAttribute('data-theme', theme);
        this.updateThemeIcon(theme);
    }

    // 切换主题
    toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('memos_web_theme', newTheme);
        this.updateThemeIcon(newTheme);
    }

    // 更新主题图标
    updateThemeIcon(theme) {
        const icon = document.querySelector('#theme-toggle i');
        if (icon) {
            icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        }
    }

    // 切换密码可见性
    togglePasswordVisibility() {
        const passwordInput = document.getElementById('password');
        const toggleBtn = document.getElementById('toggle-password');

        if (passwordInput.type === 'password') {
            passwordInput.type = 'text';
            toggleBtn.innerHTML = '<i class="fas fa-eye-slash"></i>';
        } else {
            passwordInput.type = 'password';
            toggleBtn.innerHTML = '<i class="fas fa-eye"></i>';
        }
    }

    // 检查认证状态
    async checkAuth() {
        if (this.accessToken) {
            try {
                const response = await this.apiRequest('/api/health');
                if (response.status === 'healthy') {
                    this.isAuthenticated = true;
                    this.showMainScreen();
                    this.loadBots();
                } else {
                    this.showLoginScreen();
                }
            } catch (error) {
                console.error('认证检查失败:', error);
                this.showLoginScreen();
            }
        } else {
            this.showLoginScreen();
        }
    }

    // 处理登录
    async handleLogin() {
        const passwordInput = document.getElementById('password');
        const password = passwordInput.value.trim();
        const errorElement = document.getElementById('login-error');

        if (!password) {
            this.showError('请输入访问密码');
            return;
        }

        try {
            const response = await fetch(`${this.apiBase}/api/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ password })
            });

            if (response.ok) {
                const data = await response.json();
                this.accessToken = data.access_token;
                localStorage.setItem('memos_web_token', this.accessToken);
                this.isAuthenticated = true;

                this.showMainScreen();
                this.loadBots();
                this.clearError();
            } else {
                const error = await response.json();
                this.showError(error.detail || '登录失败');
            }
        } catch (error) {
            console.error('登录请求失败:', error);
            this.showError('网络连接失败，请检查服务器状态');
        }
    }

    // 处理退出
    handleLogout() {
        this.accessToken = '';
        localStorage.removeItem('memos_web_token');
        this.isAuthenticated = false;
        this.showLoginScreen();
        document.getElementById('password').value = '';
    }

    // 显示错误信息
    showError(message) {
        const errorElement = document.getElementById('login-error');
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.style.display = 'block';
        }
    }

    // 清除错误信息
    clearError() {
        const errorElement = document.getElementById('login-error');
        if (errorElement) {
            errorElement.style.display = 'none';
        }
    }

    // 显示登录界面
    showLoginScreen() {
        document.getElementById('login-screen').style.display = 'flex';
        document.getElementById('main-screen').style.display = 'none';
        document.getElementById('logout-btn').style.display = 'none';
    }

    // 初始化侧边栏
    initSidebar() {
        const sidebar = document.getElementById('sidebar');
        const mainContainer = document.getElementById('main-screen');
        const sidebarToggle = document.getElementById('sidebar-toggle');
        const overlay = document.getElementById('sidebar-overlay');

        // 检查窗口宽度
        const checkWindowWidth = () => {
            if (window.innerWidth <= 768) {
                // 移动端：使用expanded类控制显示，移除collapsed类
                sidebar.classList.remove('collapsed');
                mainContainer.classList.remove('sidebar-collapsed');
                // 确保遮罩层和变暗效果根据expanded类同步
                const isExpanded = sidebar.classList.contains('expanded');
                if (overlay) {
                    overlay.classList.toggle('active', isExpanded);
                }
                mainContainer.classList.toggle('sidebar-expanded', isExpanded);
                // 如果侧栏展开，禁止body滚动
                document.body.style.overflow = isExpanded ? 'hidden' : '';
            } else {
                // 桌面端：使用collapsed类控制显示，移除expanded类
                sidebar.classList.remove('expanded');
                // 桌面端隐藏遮罩层和移除变暗效果
                if (overlay) {
                    overlay.classList.remove('active');
                }
                mainContainer.classList.remove('sidebar-expanded');
                // 桌面端总是允许body滚动
                document.body.style.overflow = '';
            }
        };

        // 初始检查
        checkWindowWidth();

        // 窗口大小变化监听
        window.addEventListener('resize', () => {
            checkWindowWidth();
            this.updateLayoutBasedOnContentWidth();
        });
    }

    // 切换侧边栏
    toggleSidebar() {
        const sidebar = document.getElementById('sidebar');
        const mainContainer = document.getElementById('main-screen');
        const sidebarToggle = document.getElementById('sidebar-toggle');
        const overlay = document.getElementById('sidebar-overlay');
        const icon = sidebarToggle.querySelector('i');
        const footer = document.querySelector('.app-footer');

        // 移动端逻辑
        if (window.innerWidth <= 768) {
            const isExpanding = !sidebar.classList.contains('expanded');
            sidebar.classList.toggle('expanded');
            // 移动端确保页脚没有左边距类
            if (footer) {
                footer.classList.remove('sidebar-collapsed-footer');
            }
            // 控制遮罩层和内容变暗
            if (overlay) {
                overlay.classList.toggle('active', isExpanding);
            }
            mainContainer.classList.toggle('sidebar-expanded', isExpanding);
            // 控制body滚动
            document.body.style.overflow = isExpanding ? 'hidden' : '';
        } else {
            // 桌面端逻辑
            sidebar.classList.toggle('collapsed');
            mainContainer.classList.toggle('sidebar-collapsed');
            // 切换页脚类
            if (footer) {
                footer.classList.toggle('sidebar-collapsed-footer');
            }
            // 桌面端隐藏遮罩层
            if (overlay) {
                overlay.classList.remove('active');
            }
            mainContainer.classList.remove('sidebar-expanded');
            // 桌面端恢复body滚动
            document.body.style.overflow = '';
        }

        // 图标始终为三根杠
        icon.className = 'fas fa-bars';
        // 更新title提示
        if (window.innerWidth <= 768) {
            // 移动端：有expanded类时显示，无expanded类时隐藏
            sidebarToggle.title = sidebar.classList.contains('expanded') ? '折叠侧栏' : '展开侧栏';
        } else {
            // 桌面端：无collapsed类时显示，有collapsed类时隐藏
            sidebarToggle.title = sidebar.classList.contains('collapsed') ? '展开侧栏' : '折叠侧栏';
        }

        // 延迟更新布局，等待CSS过渡完成
        setTimeout(() => {
            this.updateLayoutBasedOnContentWidth();
        }, 300);
    }

    // 关闭侧边栏（移动端）
    closeSidebar() {
        const sidebar = document.getElementById('sidebar');
        const mainContainer = document.getElementById('main-screen');
        const overlay = document.getElementById('sidebar-overlay');
        const footer = document.querySelector('.app-footer');

        if (window.innerWidth <= 768) {
            sidebar.classList.remove('expanded');
            if (overlay) {
                overlay.classList.remove('active');
            }
            mainContainer.classList.remove('sidebar-expanded');
            // 移动端确保页脚没有左边距类
            if (footer) {
                footer.classList.remove('sidebar-collapsed-footer');
            }
            // 恢复body滚动
            document.body.style.overflow = '';
        } else {
            // 桌面端折叠侧栏
            sidebar.classList.add('collapsed');
            mainContainer.classList.add('sidebar-collapsed');
            if (footer) {
                footer.classList.add('sidebar-collapsed-footer');
            }
            // 桌面端恢复body滚动
            document.body.style.overflow = '';
        }

        // 延迟更新布局，等待CSS过渡完成
        setTimeout(() => {
            this.updateLayoutBasedOnContentWidth();
        }, 300);
    }

    // 显示主界面
    showMainScreen() {
        document.getElementById('login-screen').style.display = 'none';
        document.getElementById('main-screen').style.display = 'flex';
        document.getElementById('logout-btn').style.display = 'block';

        // 延迟更新布局，确保DOM已渲染
        setTimeout(() => {
            this.updateLayoutBasedOnContentWidth();
        }, 100);
    }

    // API请求封装
    async apiRequest(endpoint, options = {}) {
        const url = `${this.apiBase}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };

        if (this.accessToken) {
            headers['Authorization'] = `Bearer ${this.accessToken}`;
        }

        const response = await fetch(url, {
            ...options,
            headers
        });

        if (!response.ok) {
            if (response.status === 401) {
                // 未授权，返回登录界面
                this.handleLogout();
                throw new Error('会话已过期，请重新登录');
            }
            const error = await response.json().catch(() => ({ detail: '请求失败' }));
            let errorMessage = '请求失败';
            if (error.detail) {
                if (Array.isArray(error.detail)) {
                    // 处理验证错误数组
                    errorMessage = error.detail.map(err => {
                        const field = err.loc?.join('.') || '未知字段';
                        return `${field}: ${err.msg}`;
                    }).join('; ');
                } else if (typeof error.detail === 'string') {
                    errorMessage = error.detail;
                } else {
                    errorMessage = JSON.stringify(error.detail);
                }
            } else {
                errorMessage = `HTTP ${response.status}`;
            }
            throw new Error(errorMessage);
        }

        return await response.json();
    }

    // 加载Bot列表
    async loadBots() {
        try {
            const response = await this.apiRequest('/api/config/tree');
            this.bots = response.bots || [];
            this.apiKeys = response.available_keys || []; // 获取密钥列表
            this.renderBotList();
            this.updateKeySelectionOptions(); // 更新密钥选择选项
        } catch (error) {
            console.error('加载Bot列表失败:', error);
            this.showToast('加载Bot列表失败', 'error');
        }
    }

    // 渲染Bot列表
    renderBotList() {
        const botListElement = document.getElementById('bot-list');
        if (!botListElement) return;

        if (this.bots.length === 0) {
            botListElement.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-robot"></i>
                    <p>未找到可用的Bot</p>
                </div>
            `;
            return;
        }

        let html = '';
        this.bots.forEach(botItem => {
            const bot = botItem.bot;
            html += `
                <div class="bot-item" data-bot-id="${bot.id}" data-bot-name="${this.escapeHtml(bot.name)}">
                    <div class="bot-icon">
                        <i class="fas fa-robot"></i>
                    </div>
                    <div class="bot-info">
                        <div class="bot-name">${this.escapeHtml(bot.name)}</div>
                        <div class="bot-id">${this.escapeHtml(bot.type)}</div>
                    </div>
                </div>
            `;
        });

        botListElement.innerHTML = html;

        // Attach click event listeners programmatically instead of inline handlers
        document.querySelectorAll('.bot-item').forEach(item => {
            item.addEventListener('click', async () => {
                const botId = item.getAttribute('data-bot-id');
                const botName = item.getAttribute('data-bot-name');

                // 检查是否有未保存的更改
                if (this.unsavedChanges) {
                    if (!confirm('您有未保存的更改，确定要切换Bot吗？未保存的更改将丢失。')) {
                        return;
                    }
                }

                this.selectBot(botId, botName);
            });
        });

        // 首次加载时自动选择第一个Bot
        if (!this.currentBotId && this.bots.length > 0) {
            const firstBot = this.bots[0].bot;
            this.selectBot(firstBot.id, firstBot.name);
        }
    }

    // 选择Bot
    async selectBot(botId, botName) {
        // 更新UI状态
        document.querySelectorAll('.bot-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelector(`[data-bot-id="${botId}"]`)?.classList.add('active');

        this.currentBotId = botId;
        this.currentBotName = botName;

        // 更新标题
        document.getElementById('current-bot-title').textContent = botName;
        document.getElementById('bot-type-tag').textContent = 'Bot配置';
        document.getElementById('bot-status-badge').textContent = '已启用';
        document.getElementById('bot-info').style.display = 'flex';

        // 显示配置面板
        document.getElementById('bot-config-panel').style.display = 'block';
        document.getElementById('sessions-panel').style.display = 'block';

        // 启用重置按钮
        document.getElementById('reset-btn').disabled = false;

        // 加载Bot配置
        await this.loadBotConfig(botId);

        // 加载会话列表
        await this.loadSessions(botId);
    }

    // 加载Bot配置
    async loadBotConfig(botId) {
        try {
            const config = await this.apiRequest(`/api/config/${botId}`);
            this.botConfigs[botId] = config;
            this.renderBotConfig(botId, config);
        } catch (error) {
            console.error('加载Bot配置失败:', error);
            // 使用默认配置
            this.botConfigs[botId] = {
                custom_user_id: '',
                memory_injection_enabled: true,
                new_session_upload_enabled: true,
                api_key_selection: 'default'
            };
            this.renderBotConfig(botId, this.botConfigs[botId]);
        }
    }

    // 渲染Bot配置
    renderBotConfig(botId, config) {
        document.getElementById('bot-custom-user-id').value = config.custom_user_id || '';
        document.getElementById('bot-memory-injection').checked = config.memory_injection_enabled;
        document.getElementById('bot-new-session-upload').checked = config.new_session_upload_enabled;

        // 新增：API密钥选择
        const keySelect = document.getElementById('bot-api-key-selection');
        if (keySelect) {
            keySelect.value = config.api_key_selection || 'default';
        }

        this.unsavedChanges = false;
    }

    // 加载会话列表
    async loadSessions(botId) {
        const sessionsListElement = document.getElementById('sessions-list');
        if (!sessionsListElement) return;

        sessionsListElement.innerHTML = `
            <div class="loading-state">
                <i class="fas fa-spinner fa-spin"></i>
                <p>加载会话列表中...</p>
            </div>
        `;

        try {
            const sessions = await this.apiRequest(`/api/bots/${botId}/sessions`);
            this.renderSessionsList(botId, sessions);
        } catch (error) {
            console.error('加载会话列表失败:', error);
            sessionsListElement.innerHTML = `
                <div class="error-message">
                    <i class="fas fa-exclamation-triangle"></i>
                    <p>加载失败: ${error.message}</p>
                    <button class="btn btn-small" onclick="window.ui.loadSessions('${botId}')">重试</button>
                </div>
            `;
        }
    }

    // 渲染会话列表
    renderSessionsList(botId, sessions) {
        const sessionsListElement = document.getElementById('sessions-list');
        const sessionsCountElement = document.getElementById('sessions-count');

        if (!sessionsListElement) return;

        if (sessions.length === 0) {
            sessionsListElement.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-comments"></i>
                    <p>该Bot暂无会话</p>
                </div>
            `;
            sessionsCountElement.textContent = '0个会话';
            return;
        }

        sessionsCountElement.textContent = `${sessions.length}个会话`;

        let html = '';
        sessions.forEach(session => {
            const sessionId = this.escapeHtml(session.id);
            const botConfig = this.botConfigs[botId] || {};
            const placeholder = botConfig.custom_user_id ? botConfig.custom_user_id : `${this.currentBotName}:${sessionId}`;

            html += `
                <div class="session-config-panel" data-session-id="${sessionId}">
                    <div class="session-header" onclick="window.ui.toggleSession('${sessionId}')">
                        <h4 class="session-title">
                            <i class="fas fa-comment-dots"></i>
                            <span class="session-id">${sessionId}</span>
                        </h4>
                        <div class="session-actions">
                            <button class="btn btn-small btn-user-profile" data-session-id="${sessionId}" title="用户画像" onclick="window.ui.viewUserProfile('${sessionId}'); event.stopPropagation();">
                                <i class="fas fa-user"></i>
                            </button>
                            <button class="btn btn-small btn-toggle-session" data-action="toggle" onclick="window.ui.toggleSession('${sessionId}'); event.stopPropagation();">
                                <i class="fas fa-chevron-down"></i>
                            </button>
                        </div>
                    </div>
                    <div class="session-body" style="display: block;">
                        <div class="config-form">
                            <div class="desktop-horizontal-row">
                                <div class="form-group desktop-horizontal-item">
                                    <label>
                                        <i class="fas fa-id-card"></i> MemOS user_id
                                    </label>
                                    <input type="text" class="session-custom-user-id"
                                           data-session-id="${sessionId}"
                                           placeholder="${placeholder}"
                                           oninput="window.ui.markUnsaved()">
                                    <div class="form-hint">
                                        优先级：会话配置 > Bot配置
                                    </div>
                                </div>

                                <div class="form-group desktop-horizontal-item">
                                    <label for="session-memory-injection-${sessionId}">
                                        <i class="fas fa-memory"></i> 记忆注入开关
                                    </label>
                                    <div class="toggle-switch">
                                        <input type="checkbox" class="session-memory-injection"
                                               id="session-memory-injection-${sessionId}"
                                               data-session-id="${sessionId}"
                                               onchange="window.ui.markUnsaved()">
                                        <label for="session-memory-injection-${sessionId}" class="toggle-label">
                                            <span class="toggle-handle"></span>
                                        </label>
                                    </div>
                                    <div class="form-hint">
                                        可覆盖Bot配置，控制该会话是否启用记忆注入
                                    </div>
                                </div>

                                <div class="form-group desktop-horizontal-item">
                                    <label for="session-new-session-upload-${sessionId}">
                                        <i class="fas fa-upload"></i> 新会话上传开关
                                    </label>
                                    <div class="toggle-switch">
                                        <input type="checkbox" class="session-new-session-upload"
                                               id="session-new-session-upload-${sessionId}"
                                               data-session-id="${sessionId}"
                                               onchange="window.ui.markUnsaved()">
                                        <label for="session-new-session-upload-${sessionId}" class="toggle-label">
                                            <span class="toggle-handle"></span>
                                        </label>
                                    </div>
                                    <div class="form-hint">
                                        可覆盖Bot配置，控制该会话是否启用新会话上传
                                    </div>
                                </div>
                            </div>

                            <div class="form-group">
                                <label for="session-api-key-selection-${sessionId}">
                                    <i class="fas fa-key"></i> MemOS API密钥
                                </label>
                                <div class="key-selection-container">
                                    <select class="session-api-key-selection" data-session-id="${sessionId}">
                                        <option value="default">default</option>
                                        <!-- 密钥选项将通过JavaScript动态加载 -->
                                    </select>
                                </div>
                                <div class="form-hint">
                                    优先级：会话配置 > Bot配置
                                </div>
                            </div>

                            <div class="form-actions">
                                <button class="btn btn-small" onclick="window.ui.saveSessionConfig('${botId}', '${sessionId}')">
                                    <i class="fas fa-save"></i> 保存此会话
                                </button>
                                <button class="btn btn-small" onclick="window.ui.deleteSessionConfig('${botId}', '${sessionId}')">
                                    <i class="fas fa-trash"></i> 删除配置
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });

        sessionsListElement.innerHTML = html;

        // 加载每个会话的配置
        sessions.forEach(session => {
            this.loadSessionConfig(botId, session.id);
        });

        // 更新密钥选择选项
        this.updateKeySelectionOptions();
    }

    // 加载会话配置
    async loadSessionConfig(botId, sessionId) {
        try {
            const config = await this.apiRequest(`/api/config/${botId}/${sessionId}`);
            this.sessionConfigs[`${botId}_${sessionId}`] = config;
            this.renderSessionConfig(botId, sessionId, config);
        } catch (error) {
            console.error(`加载会话 ${sessionId} 配置失败:`, error);
            // 使用默认配置
            this.sessionConfigs[`${botId}_${sessionId}`] = {
                custom_user_id: '',
                memory_injection_enabled: true,
                new_session_upload_enabled: true,
                api_key_selection: 'default'
            };
            this.renderSessionConfig(botId, sessionId, this.sessionConfigs[`${botId}_${sessionId}`]);
        }
    }

    // 渲染会话配置
    renderSessionConfig(botId, sessionId, config) {
        const sessionElement = document.querySelector(`[data-session-id="${sessionId}"]`);
        if (!sessionElement) return;

        sessionElement.querySelector('.session-custom-user-id').value = config.custom_user_id || '';
        sessionElement.querySelector('.session-memory-injection').checked = config.memory_injection_enabled;
        sessionElement.querySelector('.session-new-session-upload').checked = config.new_session_upload_enabled;

        // 新增：API密钥选择
        const keySelect = sessionElement.querySelector('.session-api-key-selection');
        if (keySelect) {
            keySelect.value = config.api_key_selection || 'default';
        }
    }

    // 切换会话展开/折叠
    toggleSession(sessionId) {
        const sessionElement = document.querySelector(`[data-session-id="${sessionId}"]`);
        if (!sessionElement) return;

        const body = sessionElement.querySelector('.session-body');
        const icon = sessionElement.querySelector('.btn-toggle-session i');

        const isCollapsed = body.classList.toggle('collapsed');
        body.style.display = isCollapsed ? 'none' : 'block';
        icon.className = isCollapsed ? 'fas fa-chevron-down' : 'fas fa-chevron-up';
    }

    // 切换Bot列表展开/折叠
    toggleBotList() {
        const toggleBtn = document.getElementById('bot-list-toggle');
        const botListSection = document.getElementById('bot-list-section');

        if (!toggleBtn || !botListSection) return;

        const isCollapsing = !botListSection.classList.contains('collapsed');
        botListSection.classList.toggle('collapsed');
        toggleBtn.classList.toggle('collapsed', isCollapsing);
        toggleBtn.title = isCollapsing ? '展开Bot列表' : '折叠Bot列表';
    }

    // 查看记忆（占位符）
    viewMemory(sessionId) {
        alert('查看记忆功能开发中...\n会话ID: ' + sessionId);
    }

    // 用户画像（占位符）
    viewUserProfile(sessionId) {
        alert('用户画像功能开发中...\n会话ID: ' + sessionId);
    }

    // 展开所有会话
    expandAllSessions() {
        document.querySelectorAll('.session-body').forEach(body => {
            body.style.display = 'block';
        });
        document.querySelectorAll('.btn-toggle-session i').forEach(icon => {
            icon.className = 'fas fa-chevron-up';
        });
    }

    // 折叠所有会话
    collapseAllSessions() {
        document.querySelectorAll('.session-body').forEach(body => {
            body.style.display = 'none';
        });
        document.querySelectorAll('.btn-toggle-session i').forEach(icon => {
            icon.className = 'fas fa-chevron-down';
        });
    }

    // 搜索Bot
    searchBots(query) {
        const botItems = document.querySelectorAll('.bot-item');
        const searchTerm = query.toLowerCase();

        botItems.forEach(item => {
            const botName = item.querySelector('.bot-name').textContent.toLowerCase();
            const botId = item.querySelector('.bot-id').textContent.toLowerCase();

            if (botName.includes(searchTerm) || botId.includes(searchTerm)) {
                item.style.display = 'flex';
            } else {
                item.style.display = 'none';
            }
        });
    }

    // 搜索会话
    searchSessions(query) {
        const sessionItems = document.querySelectorAll('.session-config-panel');
        const searchTerm = query.toLowerCase();

        sessionItems.forEach(item => {
            const sessionId = item.getAttribute('data-session-id').toLowerCase();

            if (sessionId.includes(searchTerm)) {
                item.style.display = 'block';
            } else {
                item.style.display = 'none';
            }
        });
    }

    // 标记有未保存的更改
    markUnsaved() {
        this.unsavedChanges = true;
    }

    // 保存所有配置
    async saveAllConfigs() {
        if (!this.currentBotId) return;

        const botConfig = {
            custom_user_id: document.getElementById('bot-custom-user-id').value.trim(),
            memory_injection_enabled: document.getElementById('bot-memory-injection').checked,
            new_session_upload_enabled: document.getElementById('bot-new-session-upload').checked,
            api_key_selection: document.getElementById('bot-api-key-selection').value
        };

        // 验证用户ID格式
        if (botConfig.custom_user_id && !this.validateUserId(botConfig.custom_user_id)) {
            this.showSaveStatus('用户ID格式无效，不能包含特殊字符', 'error');
            return;
        }

        // 保存Bot配置
        try {
            // 调用新的saveBotConfig方法
            await this.saveBotConfig();

            // 收集所有会话配置
            const sessionConfigs = {};
            const sessionElements = document.querySelectorAll('.session-config-panel');

            for (const element of sessionElements) {
                const sessionId = element.getAttribute('data-session-id');
                const sessionConfig = {
                    custom_user_id: element.querySelector('.session-custom-user-id').value.trim(),
                    memory_injection_enabled: element.querySelector('.session-memory-injection').checked,
                    new_session_upload_enabled: element.querySelector('.session-new-session-upload').checked,
                    api_key_selection: element.querySelector(`.session-api-key-selection[data-session-id="${sessionId}"]`).value
                };

                // 验证会话用户ID
                if (sessionConfig.custom_user_id && !this.validateUserId(sessionConfig.custom_user_id)) {
                    this.showSaveStatus(`会话 ${sessionId} 的用户ID格式无效`, 'error');
                    return;
                }

                sessionConfigs[sessionId] = sessionConfig;
            }

            // 批量保存会话配置
            if (Object.keys(sessionConfigs).length > 0) {
                await this.saveBulkSessionConfigs(this.currentBotId, sessionConfigs);
            }

            this.unsavedChanges = false;
            this.showSaveStatus('配置保存成功', 'success');

        } catch (error) {
            console.error('保存配置失败:', error);
            this.showSaveStatus(`保存失败: ${error.message}`, 'error');
        }
    }

    // 保存Bot配置
    async saveBotConfig() {
        if (!this.currentBotId) {
            throw new Error('未选择Bot');
        }

        const botConfig = {
            custom_user_id: document.getElementById('bot-custom-user-id').value.trim(),
            memory_injection_enabled: document.getElementById('bot-memory-injection').checked,
            new_session_upload_enabled: document.getElementById('bot-new-session-upload').checked,
            api_key_selection: document.getElementById('bot-api-key-selection').value // 新增
        };

        // 验证用户ID格式
        if (botConfig.custom_user_id && !this.validateUserId(botConfig.custom_user_id)) {
            throw new Error('用户ID格式无效，不能包含特殊字符');
        }

        try {
            const response = await this.apiRequest(`/api/config/${this.currentBotId}`, {
                method: 'POST',
                body: JSON.stringify({ config: botConfig })
            });

            if (response.success) {
                this.botConfigs[this.currentBotId] = botConfig;
                this.unsavedChanges = false;

                // 更新所有会话输入框的placeholder
                this.updateSessionPlaceholders();

                // 不显示成功消息，由调用者决定
                return true;
            } else {
                throw new Error(response.message);
            }
        } catch (error) {
            console.error('保存Bot配置失败:', error);
            throw error; // 重新抛出错误，由调用者处理
        }
    }

    // 保存会话配置
    async saveSessionConfig(botId, sessionId) {
        const sessionElement = document.querySelector(`[data-session-id="${sessionId}"]`);
        if (!sessionElement) return;

        const config = {
            custom_user_id: sessionElement.querySelector('.session-custom-user-id').value.trim(),
            memory_injection_enabled: sessionElement.querySelector('.session-memory-injection').checked,
            new_session_upload_enabled: sessionElement.querySelector('.session-new-session-upload').checked,
            api_key_selection: document.querySelector(`.session-api-key-selection[data-session-id="${sessionId}"]`).value // 新增
        };

        // 验证用户ID
        if (config.custom_user_id && !this.validateUserId(config.custom_user_id)) {
            this.showSaveStatus('用户ID格式无效，不能包含特殊字符', 'error');
            return;
        }

        try {
            const response = await this.apiRequest(`/api/config/${botId}/${sessionId}`, {
                method: 'POST',
                body: JSON.stringify({ config })
            });

            if (response.success) {
                // 更新缓存
                this.sessionConfigs[`${botId}_${sessionId}`] = config;
                // 重置未保存标志
                this.unsavedChanges = false;
                this.showSaveStatus('会话配置保存成功', 'success');
            } else {
                throw new Error(response.message);
            }
        } catch (error) {
            console.error('保存会话配置失败:', error);
            this.showSaveStatus(`保存失败: ${error.message}`, 'error');
        }
    }

    // 批量保存会话配置
    async saveBulkSessionConfigs(botId, sessionConfigs) {
        const sessions = {};
        sessions[botId] = sessionConfigs;

        try {
            const response = await this.apiRequest('/api/config/bulk', {
                method: 'POST',
                body: JSON.stringify({ sessions })
            });

            if (!response.success) {
                throw new Error(response.message || '保存失败');
            }
        } catch (error) {
            console.error('批量保存会话配置失败:', error);
            throw error;
        }
    }

    // 保存所有会话配置
    async saveAllSessionConfigs() {
        if (!this.currentBotId) return;

        try {
            // 收集所有会话配置
            const sessionConfigs = {};
            const sessionElements = document.querySelectorAll('.session-config-panel');

            for (const element of sessionElements) {
                const sessionId = element.getAttribute('data-session-id');
                const sessionConfig = {
                    custom_user_id: element.querySelector('.session-custom-user-id').value.trim(),
                    memory_injection_enabled: element.querySelector('.session-memory-injection').checked,
                    new_session_upload_enabled: element.querySelector('.session-new-session-upload').checked,
                    api_key_selection: element.querySelector(`.session-api-key-selection[data-session-id="${sessionId}"]`).value
                };

                // 验证会话用户ID
                if (sessionConfig.custom_user_id && !this.validateUserId(sessionConfig.custom_user_id)) {
                    this.showSaveStatus(`会话 ${sessionId} 的用户ID格式无效`, 'error');
                    return;
                }

                sessionConfigs[sessionId] = sessionConfig;
            }

            // 批量保存会话配置
            if (Object.keys(sessionConfigs).length > 0) {
                await this.saveBulkSessionConfigs(this.currentBotId, sessionConfigs);
            }

            this.unsavedChanges = false;
            this.showSaveStatus('所有会话配置已保存', 'success');

        } catch (error) {
            console.error('保存会话配置失败:', error);
            // 处理不同类型的错误
            let errorMessage = '保存失败';
            if (error.message) {
                errorMessage += `: ${error.message}`;
            } else if (error.response) {
                errorMessage += `: ${JSON.stringify(error.response)}`;
            } else {
                errorMessage += `: ${JSON.stringify(error)}`;
            }
            this.showSaveStatus(errorMessage, 'error');
        }
    }

    // 删除会话配置
    async deleteSessionConfig(botId, sessionId) {
        if (!confirm(`确定要删除会话 ${sessionId} 的配置吗？配置将从配置文件中永久删除。`)) {
            return;
        }

        try {
            const response = await this.apiRequest(`/api/config/${botId}/${sessionId}`, {
                method: 'DELETE'
            });

            if (response.success) {
                // 从DOM中移除会话配置面板
                const sessionElement = document.querySelector(`[data-session-id="${sessionId}"]`);
                if (sessionElement) {
                    sessionElement.remove();
                }

                // 从缓存中删除配置
                delete this.sessionConfigs[`${botId}_${sessionId}`];

                // 更新会话计数
                this.updateSessionCount();

                this.showSaveStatus('会话配置已删除', 'success');
            } else {
                throw new Error(response.message);
            }
        } catch (error) {
            console.error('删除会话配置失败:', error);
            this.showSaveStatus(`删除失败: ${error.message}`, 'error');
        }
    }

    // 应用记忆注入开关到所有会话
    async applyMemoryInjectionToAll() {
        if (!this.currentBotId) return;
        if (this.applyingToAllInProgress) return;

        const enabled = document.getElementById('bot-memory-injection').checked;

        // 弹出确认对话框
        if (!confirm(`确定要将记忆注入开关${enabled ? '开启' : '关闭'}应用到所有会话吗？Bot配置将先保存，然后应用到所有会话。`)) {
            return;
        }

        this.applyingToAllInProgress = true;
        this.showSaveStatus('正在保存Bot配置...', 'info');

        try {
            // 先保存Bot配置
            await this.saveBotConfig();

            this.showSaveStatus('Bot配置已保存，正在应用到所有会话...', 'info');

            // 调用新API端点应用到所有会话
            const response = await this.apiRequest(`/api/config/${this.currentBotId}/apply-switch-to-all`, {
                method: 'POST',
                body: JSON.stringify({
                    switch_type: "memory_injection",
                    enabled: enabled
                })
            });

            if (response.success) {
                // 更新UI中所有会话的开关状态
                const sessionElements = document.querySelectorAll('.session-config-panel');
                sessionElements.forEach(element => {
                    const checkbox = element.querySelector('.session-memory-injection');
                    if (checkbox) {
                        checkbox.checked = enabled;
                    }
                });

                this.showSaveStatus(`Bot配置已保存，${response.message}`, 'success');
            } else {
                this.showSaveStatus(response.message, 'error');
            }
        } catch (error) {
            console.error('应用到所有会话失败:', error);
            // 如果错误发生在保存Bot配置阶段，显示相应的错误消息
            this.showSaveStatus(`Bot配置保存失败: ${error.message}`, 'error');
        } finally {
            this.applyingToAllInProgress = false;
        }
    }

    // 应用新会话上传开关到所有会话
    async applyNewSessionUploadToAll() {
        if (!this.currentBotId) return;
        if (this.applyingToAllInProgress) return;

        const enabled = document.getElementById('bot-new-session-upload').checked;

        // 弹出确认对话框
        if (!confirm(`确定要将新会话上传开关${enabled ? '开启' : '关闭'}应用到所有会话吗？Bot配置将先保存，然后应用到所有会话。`)) {
            return;
        }

        this.applyingToAllInProgress = true;
        this.showSaveStatus('正在保存Bot配置...', 'info');

        try {
            // 先保存Bot配置
            await this.saveBotConfig();

            this.showSaveStatus('Bot配置已保存，正在应用到所有会话...', 'info');

            // 调用新API端点应用到所有会话
            const response = await this.apiRequest(`/api/config/${this.currentBotId}/apply-switch-to-all`, {
                method: 'POST',
                body: JSON.stringify({
                    switch_type: "new_session_upload",
                    enabled: enabled
                })
            });

            if (response.success) {
                // 更新UI中所有会话的开关状态
                const sessionElements = document.querySelectorAll('.session-config-panel');
                sessionElements.forEach(element => {
                    const checkbox = element.querySelector('.session-new-session-upload');
                    if (checkbox) {
                        checkbox.checked = enabled;
                    }
                });

                this.showSaveStatus(`Bot配置已保存，${response.message}`, 'success');
            } else {
                this.showSaveStatus(response.message, 'error');
            }
        } catch (error) {
            console.error('应用到所有会话失败:', error);
            // 如果错误发生在保存Bot配置阶段，显示相应的错误消息
            this.showSaveStatus(`Bot配置保存失败: ${error.message}`, 'error');
        } finally {
            this.applyingToAllInProgress = false;
        }
    }

    // 重置配置
    resetConfigs() {
        if (!this.currentBotId) return;
        
        // 直接弹出确认对话框
        if (!confirm('确定要重置所有更改吗？未保存的更改将丢失。')) {
            return;
        }

        // 重置Bot配置
        const botConfig = this.botConfigs[this.currentBotId];
        if (botConfig) {
            this.renderBotConfig(this.currentBotId, botConfig);
        }

        // 重置所有会话配置
        const sessionElements = document.querySelectorAll('.session-config-panel');
        sessionElements.forEach(element => {
            const sessionId = element.getAttribute('data-session-id');
            const sessionConfig = this.sessionConfigs[`${this.currentBotId}_${sessionId}`];
            if (sessionConfig) {
                this.renderSessionConfig(this.currentBotId, sessionId, sessionConfig);
            }
        });

        this.unsavedChanges = false;
        this.showSaveStatus('配置已重置', 'info');
    }

    // 更新所有会话输入框的placeholder
    updateSessionPlaceholders() {
        if (!this.currentBotId) return;

        const botConfig = this.botConfigs[this.currentBotId];
        if (!botConfig) return;

        const sessionElements = document.querySelectorAll('.session-config-panel');
        sessionElements.forEach(element => {
            const sessionId = element.getAttribute('data-session-id');
            const input = element.querySelector('.session-custom-user-id');
            if (input) {
                // 计算placeholder：如果Bot有自定义user_id则使用，否则使用默认格式
                const placeholder = botConfig.custom_user_id ? botConfig.custom_user_id : `${this.currentBotName}:${sessionId}`;
                input.placeholder = placeholder;
            }
        });
    }

    // 显示保存状态
    showSaveStatus(message, type = 'info') {
        const statusElement = document.getElementById('save-status');
        const textElement = document.getElementById('save-status-text');
        const iconElement = statusElement.querySelector('i');

        if (!statusElement || !textElement) return;

        // 更新内容和样式
        textElement.textContent = message;

        // 设置图标和颜色
        switch (type) {
            case 'success':
                iconElement.className = 'fas fa-check-circle';
                statusElement.style.backgroundColor = 'var(--success-color)';
                break;
            case 'error':
                iconElement.className = 'fas fa-exclamation-circle';
                statusElement.style.backgroundColor = 'var(--danger-color)';
                break;
            case 'info':
                iconElement.className = 'fas fa-info-circle';
                statusElement.style.backgroundColor = 'var(--info-color)';
                break;
            default:
                iconElement.className = 'fas fa-spinner fa-spin';
                statusElement.style.backgroundColor = 'var(--primary-color)';
        }

        // 显示状态
        statusElement.style.display = 'flex';

        // 3秒后自动隐藏（成功/错误/信息消息）
        if (type !== 'info') {
            setTimeout(() => {
                statusElement.style.display = 'none';
            }, 3000);
        }
    }

    // 显示Toast通知
    showToast(message, type = 'info') {
        // 移除现有的toast
        const existingToast = document.querySelector('.toast-notification');
        if (existingToast) {
            existingToast.remove();
        }

        // 创建toast元素
        const toast = document.createElement('div');
        toast.className = `toast-notification toast-${type}`;
        toast.innerHTML = `
            <div class="toast-content">
                <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
                <span>${message}</span>
            </div>
        `;

        document.body.appendChild(toast);

        // 3秒后自动移除
        setTimeout(() => {
            if (toast.parentNode) {
                toast.remove();
            }
        }, 3000);
    }

    // 加载API密钥列表
    async loadApiKeys() {
        try {
            const response = await this.apiRequest('/api/keys');
            this.apiKeys = response.keys || [];
            this.renderKeyManagement();
            this.updateKeySelectionOptions();
        } catch (error) {
            console.error('加载API密钥列表失败:', error);
            this.showToast('加载密钥列表失败', 'error');
        }
    }

    // 渲染密钥管理UI
    renderKeyManagement() {
        const keysList = document.getElementById('api-keys-list');
        if (!keysList) return;

        if (this.apiKeys.length === 0) {
            keysList.innerHTML = '<div class="empty-state">暂无自定义密钥，请添加新的API密钥</div>';
            return;
        }

        const template = document.getElementById('key-item-template');
        if (!template) return;

        keysList.innerHTML = '';

        this.apiKeys.forEach(key => {
            const keyHtml = template.innerHTML
                .replace(/{id}/g, key.id)
                .replace(/{name}/g, key.name)
                .replace(/{created_at}/g, new Date(key.created_at).toLocaleString())
                .replace(/{value}/g, key.value || '');

            const keyElement = document.createElement('div');
            keyElement.innerHTML = keyHtml;
            keysList.appendChild(keyElement.firstElementChild);

            // 添加事件监听
            const keyItem = keysList.querySelector(`[data-key-id="${key.id}"]`);
            if (keyItem) {
                const editBtn = keyItem.querySelector('.btn-edit-key');
                const deleteBtn = keyItem.querySelector('.btn-delete-key');

                // 如果是默认密钥，隐藏编辑和删除按钮
                if (key.is_default) {
                    if (editBtn) editBtn.style.display = 'none';
                    if (deleteBtn) deleteBtn.style.display = 'none';
                } else {
                    if (editBtn) {
                        editBtn.addEventListener('click', () => this.showKeyEditDialog(key.id));
                    }
                    if (deleteBtn) {
                        deleteBtn.addEventListener('click', () => this.handleDeleteKey(key.id, key.name, key.is_default));
                    }
                }
            }
        });
    }

    // 更新密钥选择下拉框选项
    updateKeySelectionOptions() {
        const botSelect = document.getElementById('bot-api-key-selection');
        const sessionSelects = document.querySelectorAll('.session-api-key-selection');

        if (botSelect) {
            // 保存当前选中的值
            const currentValue = botSelect.value;

            // 清空现有选项
            botSelect.innerHTML = '';

            // 添加密钥选项，处理默认密钥
            this.apiKeys.forEach(key => {
                const option = document.createElement('option');
                option.value = key.id;
                // 使用密钥名称（默认密钥名称应为"default"）
                option.textContent = key.name;
                botSelect.appendChild(option);
            });

            // 如果没有密钥选项，添加默认选项作为后备
            if (this.apiKeys.length === 0) {
                const defaultOption = document.createElement('option');
                defaultOption.value = 'default';
                defaultOption.textContent = 'default';
                botSelect.appendChild(defaultOption);
            }

            // 恢复选中的值（如果仍然存在）
            if (currentValue && botSelect.querySelector(`option[value="${currentValue}"]`)) {
                botSelect.value = currentValue;
            }
        }

        // 更新所有会话配置的密钥选择框
        sessionSelects.forEach(select => {
            const currentValue = select.value;
            select.innerHTML = '';

            // 添加密钥选项，处理默认密钥
            this.apiKeys.forEach(key => {
                const option = document.createElement('option');
                option.value = key.id;
                // 使用密钥名称（默认密钥名称应为"default"）
                option.textContent = key.name;
                select.appendChild(option);
            });

            // 如果没有密钥选项，添加默认选项作为后备
            if (this.apiKeys.length === 0) {
                const defaultOption = document.createElement('option');
                defaultOption.value = 'default';
                defaultOption.textContent = 'default';
                select.appendChild(defaultOption);
            }

            if (currentValue && select.querySelector(`option[value="${currentValue}"]`)) {
                select.value = currentValue;
            }
        });
    }

    // 切换密钥管理区域显示/隐藏
    toggleKeyManagement() {
        const content = document.querySelector('.key-management-content');
        const toggleBtn = document.getElementById('key-management-toggle');

        if (!content || !toggleBtn) return;

        this.keyManagementExpanded = !this.keyManagementExpanded;

        if (this.keyManagementExpanded) {
            content.style.display = 'block';
            toggleBtn.innerHTML = '<i class="fas fa-chevron-up"></i>';
            // 总是加载密钥列表以确保数据最新
            this.loadApiKeys();
        } else {
            content.style.display = 'none';
            toggleBtn.innerHTML = '<i class="fas fa-chevron-down"></i>';
        }
    }

    // 添加新密钥
    async handleAddKey() {
        const nameInput = document.getElementById('new-key-name');
        const valueInput = document.getElementById('new-key-value');

        if (!nameInput || !valueInput) return;

        const name = nameInput.value.trim();
        const value = valueInput.value.trim();

        // 验证输入
        if (!name) {
            this.showToast('请输入密钥名称', 'error');
            return;
        }
        if (!value) {
            this.showToast('请输入API密钥值', 'error');
            return;
        }

        // 检查名称是否已存在
        if (this.apiKeys.some(key => key.name === name)) {
            this.showToast('密钥名称已存在，请使用其他名称', 'error');
            return;
        }

        try {
            // base64编码密钥值
            const base64Value = btoa(value);

            const response = await this.apiRequest('/api/keys', {
                method: 'POST',
                body: JSON.stringify({
                    name: name,
                    value: base64Value
                })
            });

            if (response.success) {
                this.showToast('密钥添加成功', 'success');
                // 清空输入框
                nameInput.value = '';
                valueInput.value = '';
                // 重新加载密钥列表
                await this.loadApiKeys();
            } else {
                this.showToast(`添加失败: ${response.message || '未知错误'}`, 'error');
            }
        } catch (error) {
            console.error('添加密钥失败:', error);
            this.showToast(`添加失败: ${error.message}`, 'error');
        }
    }

    // 删除密钥
    async handleDeleteKey(keyId, keyName, isDefault) {
        if (isDefault) {
            this.showToast('默认密钥无法删除', 'error');
            return;
        }

        if (!confirm(`确定要删除密钥 "${keyName}" 吗？\n\n注意：使用此密钥的Bot和会话将自动切换为默认密钥。`)) {
            return;
        }

        try {
            const response = await this.apiRequest(`/api/keys/${keyId}`, {
                method: 'DELETE'
            });

            if (response.success) {
                this.showToast('密钥删除成功', 'success');
                await this.loadApiKeys();
                // 重新加载当前Bot配置（如果当前正在编辑的Bot使用了被删除的密钥）
                if (this.currentBotId) {
                    await this.loadBotConfig(this.currentBotId);
                }
            } else {
                this.showToast(`删除失败: ${response.message || '未知错误'}`, 'error');
            }
        } catch (error) {
            console.error('删除密钥失败:', error);
            this.showToast(`删除失败: ${error.message}`, 'error');
        }
    }

    // 显示密钥编辑对话框
    showKeyEditDialog(keyId) {
        const key = this.apiKeys.find(k => k.id === keyId);
        if (!key) return;

        this.currentEditingKeyId = keyId;

        const nameInput = document.getElementById('edit-key-name');
        const valueInput = document.getElementById('edit-key-value');
        const overlay = document.getElementById('key-edit-overlay');

        if (nameInput) nameInput.value = key.name;
        if (valueInput) valueInput.value = key.value || ''; // 显示解密后的密钥值
        if (overlay) overlay.style.display = 'flex';
    }

    // 隐藏密钥编辑对话框
    hideKeyEditDialog() {
        const overlay = document.getElementById('key-edit-overlay');
        if (overlay) overlay.style.display = 'none';
        this.currentEditingKeyId = null;
    }

    // 保存密钥编辑
    async handleSaveKeyEdit() {
        if (!this.currentEditingKeyId) return;

        const nameInput = document.getElementById('edit-key-name');
        const valueInput = document.getElementById('edit-key-value');

        if (!nameInput) return;

        const name = nameInput.value.trim();
        const value = valueInput.value.trim();

        if (!name) {
            this.showToast('密钥名称不能为空', 'error');
            return;
        }

        try {
            const updateData = {};

            // 检查名称是否已存在（排除自身）
            const existingKey = this.apiKeys.find(k => k.name === name && k.id !== this.currentEditingKeyId);
            if (existingKey) {
                this.showToast('密钥名称已存在，请使用其他名称', 'error');
                return;
            }

            updateData.name = name;

            // 如果提供了新密钥值，则base64编码
            if (value) {
                updateData.value = btoa(value);
            }

            const response = await this.apiRequest(`/api/keys/${this.currentEditingKeyId}`, {
                method: 'PUT',
                body: JSON.stringify(updateData)
            });

            if (response.success) {
                this.showToast('密钥更新成功', 'success');
                this.hideKeyEditDialog();
                await this.loadApiKeys();
            } else {
                this.showToast(`更新失败: ${response.message || '未知错误'}`, 'error');
            }
        } catch (error) {
            console.error('更新密钥失败:', error);
            this.showToast(`更新失败: ${error.message}`, 'error');
        }
    }

    // 将API密钥应用到全部会话
    async applyApiKeyToAll() {
        if (!this.currentBotId) return;

        const selectElement = document.getElementById('bot-api-key-selection');
        if (!selectElement) return;

        const keyId = selectElement.value;
        if (!keyId) return;

        // 确认提示
        if (!confirm(`确定要将当前选择的API密钥应用到该Bot的所有会话吗？\n\n此操作将覆盖所有会话的API密钥配置。`)) {
            return;
        }

        try {
            const response = await this.apiRequest(`/api/config/${this.currentBotId}/apply-key-to-all`, {
                method: 'POST',
                body: JSON.stringify({
                    switch_type: 'api_key_selection',
                    value: keyId,
                    enabled: true
                })
            });

            if (response.success) {
                this.showToast(`成功更新 ${response.updated_sessions}/${response.total_sessions} 个会话`, 'success');
            } else {
                this.showToast(`应用失败: ${response.message}`, 'error');
            }
        } catch (error) {
            console.error('应用API密钥到全部会话失败:', error);
            this.showToast(`应用失败: ${error.message}`, 'error');
        }
    }

    // 验证用户ID格式
    validateUserId(userId) {
        if (!userId) return true;

        // 检查长度
        if (userId.length > 100) return false;

        // 检查危险字符
        const dangerousChars = ['<', '>', '"', "'", '\\', '/', ';', '&', '|', '$', '`'];
        return !dangerousChars.some(char => userId.includes(char));
    }

    // 更新会话计数显示
    updateSessionCount() {
        const sessionsCountElement = document.getElementById('sessions-count');
        if (!sessionsCountElement) return;

        const sessionElements = document.querySelectorAll('.session-config-panel');
        const count = sessionElements.length;
        sessionsCountElement.textContent = `${count}个会话`;
    }

    // HTML转义
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // 基于内容宽度更新布局
    updateLayoutBasedOnContentWidth() {
        const contentArea = document.querySelector('.content-area');
        if (!contentArea) return;

        const contentWidth = contentArea.offsetWidth;
        // 如果内容区域不可见，跳过更新
        if (contentWidth === 0) return;

        const configContainer = document.querySelector('.config-container');
        if (!configContainer) return;

        // 移除现有的布局类
        configContainer.classList.remove('layout-wide', 'layout-medium', 'layout-narrow');

        // 根据内容宽度应用布局类
        if (contentWidth >= 1025) {
            configContainer.classList.add('layout-wide');
        } else if (contentWidth >= 768) {
            configContainer.classList.add('layout-medium');
        } else {
            configContainer.classList.add('layout-narrow');
        }
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    window.ui = new MemOSWebUI();
});