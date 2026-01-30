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

        // 初始化事件监听
        this.initEventListeners();

        // 检查认证状态
        this.checkAuth();

        // 初始化主题
        this.initTheme();
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

        // 操作按钮
        document.getElementById('save-btn')?.addEventListener('click', () => this.saveAllConfigs());
        document.getElementById('reset-btn')?.addEventListener('click', () => this.resetConfigs());
        document.getElementById('expand-all-btn')?.addEventListener('click', () => this.expandAllSessions());
        document.getElementById('collapse-all-btn')?.addEventListener('click', () => this.collapseAllSessions());

        // Bot配置输入监听
        document.getElementById('bot-custom-user-id')?.addEventListener('input', () => this.markUnsaved());
        document.getElementById('bot-memory-injection')?.addEventListener('change', () => this.markUnsaved());
        document.getElementById('bot-new-session-upload')?.addEventListener('change', () => this.markUnsaved());

        // 窗口事件
        window.addEventListener('beforeunload', (e) => {
            if (this.unsavedChanges) {
                e.preventDefault();
                e.returnValue = '您有未保存的更改，确定要离开吗？';
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

    // 显示主界面
    showMainScreen() {
        document.getElementById('login-screen').style.display = 'none';
        document.getElementById('main-screen').style.display = 'flex';
        document.getElementById('logout-btn').style.display = 'block';
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
            throw new Error(error.detail || `HTTP ${response.status}`);
        }

        return await response.json();
    }

    // 加载Bot列表
    async loadBots() {
        const botListElement = document.getElementById('bot-list');
        if (!botListElement) return;

        botListElement.innerHTML = `
            <div class="loading-state">
                <i class="fas fa-spinner fa-spin"></i>
                <p>加载Bot列表中...</p>
            </div>
        `;

        try {
            const bots = await this.apiRequest('/api/bots');
            this.renderBotList(bots);
        } catch (error) {
            console.error('加载Bot列表失败:', error);
            botListElement.innerHTML = `
                <div class="error-message">
                    <i class="fas fa-exclamation-triangle"></i>
                    <p>加载失败: ${error.message}</p>
                    <button class="btn btn-small" onclick="window.ui.loadBots()">重试</button>
                </div>
            `;
        }
    }

    // 渲染Bot列表
    renderBotList(bots) {
        const botListElement = document.getElementById('bot-list');
        if (!botListElement) return;

        if (bots.length === 0) {
            botListElement.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-robot"></i>
                    <p>未找到可用的Bot</p>
                </div>
            `;
            return;
        }

        let html = '';
        bots.forEach(bot => {
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
            item.addEventListener('click', () => {
                const botId = item.getAttribute('data-bot-id');
                const botName = item.getAttribute('data-bot-name');
                this.selectBot(botId, botName);
            });
        });
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

        // 启用保存/重置按钮
        document.getElementById('save-btn').disabled = false;
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
                new_session_upload_enabled: true
            };
            this.renderBotConfig(botId, this.botConfigs[botId]);
        }
    }

    // 渲染Bot配置
    renderBotConfig(botId, config) {
        document.getElementById('bot-custom-user-id').value = config.custom_user_id || '';
        document.getElementById('bot-memory-injection').checked = config.memory_injection_enabled;
        document.getElementById('bot-new-session-upload').checked = config.new_session_upload_enabled;

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

            html += `
                <div class="session-config-panel" data-session-id="${sessionId}">
                    <div class="session-header" onclick="window.ui.toggleSession('${sessionId}')">
                        <h4 class="session-title">
                            <i class="fas fa-comment-dots"></i>
                            <span class="session-id">${sessionId}</span>
                        </h4>
                        <div class="session-actions">
                            <button class="btn btn-small btn-toggle-session" data-action="toggle">
                                <i class="fas fa-chevron-down"></i>
                            </button>
                        </div>
                    </div>
                    <div class="session-body" style="display: none;">
                        <div class="config-form">
                            <div class="form-group">
                                <label>
                                    <i class="fas fa-id-card"></i> MemOS user_id
                                </label>
                                <input type="text" class="session-custom-user-id"
                                       data-session-id="${sessionId}"
                                       placeholder="${this.currentBotName}:${sessionId}"
                                       oninput="window.ui.markUnsaved()">
                                <div class="form-hint">
                                    优先级：会话配置 > Bot配置
                                </div>
                            </div>

                            <div class="form-group">
                                <label>
                                    <i class="fas fa-memory"></i> 记忆注入开关
                                </label>
                                <div class="toggle-switch">
                                    <input type="checkbox" class="session-memory-injection"
                                           data-session-id="${sessionId}"
                                           onchange="window.ui.markUnsaved()" checked>
                                    <label class="toggle-label">
                                        <span class="toggle-handle"></span>
                                    </label>
                                </div>
                                <div class="form-hint">
                                    可覆盖Bot配置，控制该会话是否启用记忆注入
                                </div>
                            </div>

                            <div class="form-group">
                                <label>
                                    <i class="fas fa-upload"></i> 新会话上传开关
                                </label>
                                <div class="toggle-switch">
                                    <input type="checkbox" class="session-new-session-upload"
                                           data-session-id="${sessionId}"
                                           onchange="window.ui.markUnsaved()" checked>
                                    <label class="toggle-label">
                                        <span class="toggle-handle"></span>
                                    </label>
                                </div>
                                <div class="form-hint">
                                    可覆盖Bot配置，控制该会话是否启用新会话上传
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
                new_session_upload_enabled: true
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
    }

    // 切换会话展开/折叠
    toggleSession(sessionId) {
        const sessionElement = document.querySelector(`[data-session-id="${sessionId}"]`);
        if (!sessionElement) return;

        const body = sessionElement.querySelector('.session-body');
        const icon = sessionElement.querySelector('.btn-toggle-session i');

        if (body.style.display === 'none') {
            body.style.display = 'block';
            icon.className = 'fas fa-chevron-up';
        } else {
            body.style.display = 'none';
            icon.className = 'fas fa-chevron-down';
        }
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
        document.getElementById('save-btn').textContent = '保存*';
    }

    // 保存所有配置
    async saveAllConfigs() {
        if (!this.currentBotId) return;

        const botConfig = {
            custom_user_id: document.getElementById('bot-custom-user-id').value.trim(),
            memory_injection_enabled: document.getElementById('bot-memory-injection').checked,
            new_session_upload_enabled: document.getElementById('bot-new-session-upload').checked
        };

        // 验证用户ID格式
        if (botConfig.custom_user_id && !this.validateUserId(botConfig.custom_user_id)) {
            this.showSaveStatus('用户ID格式无效，不能包含特殊字符', 'error');
            return;
        }

        // 保存Bot配置
        try {
            await this.saveBotConfig(this.currentBotId, botConfig);

            // 收集所有会话配置
            const sessionConfigs = {};
            const sessionElements = document.querySelectorAll('.session-config-panel');

            for (const element of sessionElements) {
                const sessionId = element.getAttribute('data-session-id');
                const sessionConfig = {
                    custom_user_id: element.querySelector('.session-custom-user-id').value.trim(),
                    memory_injection_enabled: element.querySelector('.session-memory-injection').checked,
                    new_session_upload_enabled: element.querySelector('.session-new-session-upload').checked
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
            document.getElementById('save-btn').textContent = '保存';
            this.showSaveStatus('配置保存成功', 'success');

        } catch (error) {
            console.error('保存配置失败:', error);
            this.showSaveStatus(`保存失败: ${error.message}`, 'error');
        }
    }

    // 保存Bot配置
    async saveBotConfig(botId, config) {
        const response = await this.apiRequest(`/api/config/${botId}`, {
            method: 'POST',
            body: JSON.stringify({ config })
        });

        if (!response.success) {
            throw new Error(response.message);
        }
    }

    // 保存会话配置
    async saveSessionConfig(botId, sessionId) {
        const sessionElement = document.querySelector(`[data-session-id="${sessionId}"]`);
        if (!sessionElement) return;

        const config = {
            custom_user_id: sessionElement.querySelector('.session-custom-user-id').value.trim(),
            memory_injection_enabled: sessionElement.querySelector('.session-memory-injection').checked,
            new_session_upload_enabled: sessionElement.querySelector('.session-new-session-upload').checked
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

        const response = await this.apiRequest('/api/config/bulk', {
            method: 'POST',
            body: JSON.stringify({ sessions })
        });

        if (!response.success) {
            throw new Error(response.message);
        }
    }

    // 删除会话配置
    async deleteSessionConfig(botId, sessionId) {
        if (!confirm(`确定要删除会话 ${sessionId} 的配置吗？`)) {
            return;
        }

        try {
            const response = await this.apiRequest(`/api/config/${botId}/${sessionId}`, {
                method: 'DELETE'
            });

            if (response.success) {
                this.showSaveStatus('会话配置已删除', 'success');
                // 重新加载会话列表
                await this.loadSessions(botId);
            } else {
                throw new Error(response.message);
            }
        } catch (error) {
            console.error('删除会话配置失败:', error);
            this.showSaveStatus(`删除失败: ${error.message}`, 'error');
        }
    }

    // 重置配置
    resetConfigs() {
        if (!this.currentBotId || !confirm('确定要重置所有更改吗？未保存的更改将丢失。')) {
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
        document.getElementById('save-btn').textContent = '保存';
        this.showSaveStatus('配置已重置', 'info');
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

    // 验证用户ID格式
    validateUserId(userId) {
        if (!userId) return true;

        // 检查长度
        if (userId.length > 100) return false;

        // 检查危险字符
        const dangerousChars = ['<', '>', '"', "'", '\\', '/', ';', '&', '|', '$', '`'];
        return !dangerousChars.some(char => userId.includes(char));
    }

    // HTML转义
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    window.ui = new MemOSWebUI();
});