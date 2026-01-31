# AstrBot 的 MemOS 集成插件

这是一个为AstrBot开发的MemOS集成插件,允许Bot记忆用户对话内容,并在后续对话中提供个性化响应。

## 📋 快速指令

| 指令       | 功能说明                     |
|------------|------------------------------|
| `/查记忆 <查询内容>`   | 搜索与指定内容相关的记忆     |
| `/用户画像` | 生成用户的人物关键词画像报告 |
| `/加反馈 <反馈内容>` | 给指定消息添加反馈，描述需要如何修正 |

## 🎯 核心功能

- **自动记忆管理**：自动保存对话，智能检索相关记忆
- **记忆注入**：在LLM请求前注入相关记忆，提供上下文
- **Web管理界面**：可视化配置Bot和会话规则，管理API密钥，查看用户画像
- **多密钥支持**：不同Bot和会话可使用不同的MemOS API密钥
- **安全协议**：使用"四步判决"确保记忆使用的安全性

**重要强调**：本插件的记忆注入模板与记忆安全协议完全复用了 MemOS 官方浏览器扩展 [**MemOS-MindDock 个人记忆助手**](https://alidocs.dingtalk.com/i/p/e3ZxX84Z5KM6X7dRZxX8v66wA7xaBG7d?dontjump=true) 的源码逻辑。

## 📖 MemOS 介绍

MemOS 是一个先进的记忆操作系统，为 AI 提供长期记忆、智能检索和个性化响应能力。
更多介绍请访问 [MemOS 官方文档](https://memos-docs.openmem.net/cn/overview/introduction/)

## 安装

1. 将插件文件夹复制到AstrBot的plugins目录
2. 安装依赖: `pip install -r requirements.txt`
3. 在AstrBot配置界面中配置插件

## 配置

```json
{
  "api_key": "your_memos_api_key",
  "base_url": "https://memos.memtensor.cn/api/openmem/v1",
  "web_enabled": true,
  "web_port": 8000
}
```

- `api_key`: MemOS API密钥，从 [官网](https://memos-dashboard.openmem.net/cn/apikeys/) 获取
- `web_enabled`: 是否启用Web管理界面

## 🌐 Web管理界面 (v3.0.0+)

访问 `http://localhost:8000`，使用配置密码登录。

### 主要功能

| 功能 | 说明 |
|------|------|
| **Bot配置** | 为每个Bot设置user_id、API密钥、记忆注入/上传开关 |
| **会话配置** | 为特定会话设置个性化规则（优先级高于Bot配置）|
| **密钥管理** | 添加多个MemOS API密钥，供不同Bot/会话选择使用 |
| **用户画像** | 在WebUI中直接查看用户的事实记忆和偏好洞察 |
| **主题切换** | 支持亮色/暗色主题切换 |

### 配置优先级
会话配置 > Bot配置 > 默认配置

详细使用说明请查看 [配置指南](#详细配置说明)。

## 使用方法

### 自动记忆
插件会自动在LLM请求前注入相关记忆，在响应后保存对话内容，无需手动干预。

### 手动指令
使用[快速指令](#📋-快速指令)手动查询记忆或生成用户画像。

## 详细配置说明

### Web界面启用步骤

1. 设置 `web_enabled` 为 `true`
2. 可选配置：`web_port`（端口）、`web_password`（密码）
3. 重启插件，访问 `http://localhost:8000`

### Bot全局配置
- 应用于该Bot的所有会话
- 会话可覆盖这些配置
- user_id留空使用默认生成规则

### 会话级配置
- 优先级高于Bot配置
- 可独立选择API密钥，实现不同会话使用不同MemOS账户

### MemOS密钥管理
1. 点击左侧"MemOS密钥管理"
2. 添加/编辑/删除API密钥（密钥使用AES加密存储）
3. 在Bot或会话配置中选择要使用的密钥

### 用户画像查看
1. 选择Bot，展开会话列表
2. 点击会话卡片的"用户画像"按钮
3. 查看事实记忆和偏好洞察，支持复制内容

## 文件结构

```
astrbot_plugin_memos_integrator/
├── main.py              # 主插件类
├── memory_manager.py    # 记忆管理器
├── memory_templates.py  # 记忆注入模板
├── web_ui/              # Web管理界面
│   ├── server.py        # FastAPI服务器
│   ├── config_manager.py
│   └── static/          # 前端文件
├── metadata.yaml
├── _conf_schema.json
└── requirements.txt
```

## 技术细节

### 记忆安全协议
1. **来源真值检查**：区分用户原话与AI推测
2. **主语归因检查**：确认记忆中的行为主体是用户本人
3. **强相关性检查**：确认记忆与当前查询相关
4. **时效性检查**：确认记忆内容与用户最新意图不冲突

### 记忆管理器 API
- `add_message()`: 添加对话消息
- `search_memory()`: 搜索相关记忆
- `inject_memory_to_prompt()`: 将记忆注入到提示词

## 作者

zz6zz666

## 许可证

GPLv3
