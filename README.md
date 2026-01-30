# AstrBot 的 MemOS 集成插件

这是一个为AstrBot开发的MemOS集成插件,允许Bot记忆用户对话内容,并在后续对话中提供个性化响应。

## 📋 快速指令

| 指令       | 功能说明                     |
|------------|------------------------------|
| `/查记忆 <查询内容>`   | 搜索与指定内容相关的记忆     |
| `/用户画像` | 生成用户的人物关键词画像报告 |
| `/加反馈 <反馈内容>` | 给指定消息添加反馈，描述需要如何修正 |

## 🔍 核心特性说明

**重要强调**：本插件的**记忆注入模板**与**记忆安全协议**等核心逻辑，完全复用了 MemOS 官方浏览器扩展 [**MemOS-MindDock 个人记忆助手**](https://alidocs.dingtalk.com/i/p/e3ZxX84Z5KM6X7dRZxX8v66wA7xaBG7d?dontjump=true) 的源码逻辑。这样确保了记忆注入能够达到与官方工具完全一致的最佳效果，提供最可靠的用户体验。

## 📖 MemOS 介绍

MemOS 是一个先进的记忆操作系统，为 AI 提供强大的记忆能力。通过 MemOS，AI 可以：
- **长期记忆**：持久化存储用户对话和交互历史
- **智能检索**：根据用户当前查询快速找到相关记忆
- **上下文理解**：理解记忆之间的关联和上下文关系
- **个性化响应**：基于用户历史行为提供个性化服务

更多关于 MemOS 的信息，请访问 [MemOS 官方介绍](https://memos-docs.openmem.net/cn/overview/introduction/)

## 🎯 插件作用与原理

本插件将 AstrBot 与 MemOS 深度集成，实现以下核心功能：

### 自动记忆管理
- **对话保存**：自动将用户与Bot的对话内容保存到MemOS
- **智能检索**：根据当前对话上下文检索最相关的历史记忆
- **上下文注入**：将相关记忆无缝注入到LLM提示词中，提供完整上下文

### 工作原理
1. **对话捕获**：监听用户与Bot的所有对话
2. **记忆存储**：将对话内容发送到MemOS进行持久化存储，**异步执行，避免阻塞**
3. **智能检索**：当用户发起新查询时，基于语义相似度检索相关记忆
4. **上下文增强**：将检索到的记忆格式化为提示词，增强LLM的理解和响应能力
5. **持续学习**：随着对话的进行，不断更新和完善用户的记忆库

## 功能特点

- **记忆管理**: 自动保存和管理用户对话内容
- **智能检索**: 根据当前对话检索相关记忆
- **记忆注入**: 在LLM请求前注入相关记忆,提供上下文
- **用户指令**: 支持手动查询记忆和生成用户画像
- **多语言支持**: 支持中文和英文记忆注入
- **安全协议**: 使用"四步判决"确保记忆使用的安全性

## 查记忆、用户画像指令返回预览
（图片中使用了额外的文转图功能，以支持markdown的渲染）
<img width="1341" height="1347" alt="image" src="https://github.com/user-attachments/assets/36c66e83-6aac-45d7-8733-e7642ed5a200" />

## 安装

1. 将插件文件夹复制到AstrBot的plugins目录
2. 安装依赖:
   ```bash
   pip install -r requirements.txt
   ```
3. 在AstrBot的配置界面中配置插件

## 配置

插件使用AstrBot的配置系统。配置项如下:

```json
{
  "api_key": "your_memos_api_key",
  "base_url": "https://memos.memtensor.cn/api/openmem/v1",
  "max_memory_length": 1000,
  "memory_limit": 5,
  "prompt_language": "auto",
  "upload_interval": 1
}
```

### 配置项说明

- `api_key` (必填): MemOS API密钥,请前往 [MemOS API密钥页面](https://memos-dashboard.openmem.net/cn/apikeys/) 获取
- `base_url` (可选): MemOS API基础URL,默认为官方地址

## 使用方法

### 自动记忆

插件会自动执行以下操作:
1. **LLM请求前**: 检索相关记忆并注入到提示词
2. **LLM响应后**: 保存对话内容到记忆

无需手动干预,插件会在后台自动工作。

### 手动指令

详细使用方法请参考[快速指令](#📋-快速指令)部分。

## 记忆注入逻辑

插件使用以下逻辑进行记忆注入:

1. **语言检测**: 自动检测用户消息的语言(中文/英文)
2. **模型检测**: 识别LLM模型类型(通义千问/Gemini/其他)
3. **记忆检索**: 根据用户查询检索相关记忆
4. **记忆格式化**: 将记忆格式化为适合的模板
5. **提示词注入**: 将格式化的记忆注入到提示词中

## 记忆安全协议

插件使用"四步判决"确保记忆使用的安全性:

1. **来源真值检查**: 区分用户原话与AI推测
2. **主语归因检查**: 确认记忆中的行为主体是用户本人
3. **强相关性检查**: 确认记忆与当前查询相关
4. **时效性检查**: 确认记忆内容与用户最新意图不冲突

## 文件结构

```
astrbot_plugin_memos_integrator/
├── __init__.py              # 包标识文件(空文件,通过@register自动发现)
├── main.py                  # 主插件类
├── memory_manager.py        # 记忆管理器(HTTP API)
├── memory_templates.py      # 记忆注入模板(工具类)
├── metadata.yaml            # 插件元数据
├── _conf_schema.json        # 配置项定义
├── requirements.txt         # 依赖列表
└── README.md                # 本文件
```

## 技术细节

### 类结构

```
main.py → MemoryManager (直接HTTP API)
       → MemoryTemplates (纯工具类,无依赖)
```

MemoryManager 直接使用 HTTP API 与 MemOS 交互，无需额外的 SDK 依赖，结构简洁高效。

### 初始化流程

1. 插件加载时,`on_load()` 方法被调用
2. 读取配置文件中的 `api_key` 和 `base_url`
3. 创建单一的 `MemoryManager` 实例
4. `MemoryManager` 持有 API 密钥和基础 URL
5. 后续请求直接通过 `aiohttp` 发送 HTTP 请求

### HTTP API 端点

- `POST /add/message` - 添加对话消息
- `POST /search/memory` - 搜索相关记忆
- `POST /add/feedback` - 添加反馈到消息

### 记忆管理器 API

`MemoryManager` 类提供以下方法:

- `add_message()`: 添加对话消息到 MemOS
- `search_memory()`: 搜索相关记忆
- `save_conversation()`: 保存对话到 MemOS
- `retrieve_relevant_memories()`: 检索相关记忆
- `update_memory()`: 更新记忆内容
- `inject_memory_to_prompt()`: 将记忆注入到提示词
- `add_feedback()`: 添加反馈到消息

### 记忆模板

`MemoryTemplates` 类提供不同语言和模型的记忆注入模板:

- `get_injection_template()`: 获取注入模板
- `format_memory_content()`: 格式化记忆内容

## 🌐 Web管理界面

从v1.6.0版本开始，插件提供了基于FastAPI的Web管理界面，用于配置Bot和会话级别的MemOS规则。

### 功能特性

1. **树形结构展示**：
   - 第一级：Bot名称（从平台适配器获取）
   - 第二级：会话ID（从对话数据获取）
   - 支持展开/折叠，快速定位

2. **个性化配置项**（Bot父项+会话子项均支持）：
   - **MemOS用户ID自定义**：替代默认用户ID生成方式
   - **记忆注入开关**：控制是否启用MemOS记忆注入
   - **新会话上传开关**：控制是否启用新会话数据上传

3. **配置优先级**：
   - 会话子项配置 > Bot父项配置
   - 会话可覆盖Bot的全局配置

4. **Web界面配置**：
   - **启用开关**：控制是否开启Web界面
   - **访问端口**：自定义端口（默认8000）
   - **局域网访问**：控制是否允许跨设备访问
   - **访问密码**：登录验证密码（默认随机生成8位）

5. **安全特性**：
   - 密码认证不可跳过
   - JWT令牌验证
   - 未登录状态禁止访问配置页面

6. **用户体验**：
   - 亮色/暗色主题切换
   - 响应式布局（支持PC/移动端）
   - 保存/重置按钮
   - 数据格式校验
   - 操作流程清晰提示

### 启用步骤

1. **安装依赖**：
   ```bash
   pip install -r requirements.txt
   ```

2. **配置Web界面**：
   - 在AstrBot管理界面中找到MemOS插件配置
   - 设置 `web_enabled` 为 `true`
   - 可选的配置项：
     - `web_port`: 访问端口（默认8000）
     - `web_lan_access`: 局域网访问开关（默认false）
     - `web_password`: 访问密码（留空则自动生成）

3. **重启插件**：
   - 重启AstrBot或重新加载插件

4. **访问Web界面**：
   - 打开浏览器访问 `http://localhost:8000`（或配置的端口）
   - 使用配置的密码登录

### 配置说明

#### Bot全局配置
- 应用于该Bot的所有会话
- 会话可以覆盖这些配置
- 用户ID留空则使用默认生成规则

#### 会话级配置
- 优先级高于Bot配置
- 可为特定会话设置个性化规则
- 支持单独保存和删除

### 注意事项

1. **端口冲突**：如果端口8000被占用，Web服务器会尝试8001端口
2. **密码安全**：生产环境建议设置强密码
3. **局域网访问**：启用后其他设备可通过IP地址访问
4. **数据存储**：配置保存在插件数据目录的 `web_config.json` 文件中
5. **兼容性**：支持Chrome、Firefox、Edge、Safari等主流浏览器

### 故障排除

1. **Web服务器启动失败**：
   - 检查端口是否被占用
   - 查看AstrBot日志获取详细错误信息
   - 确保已安装所有依赖

2. **无法访问界面**：
   - 检查 `web_enabled` 是否设置为true
   - 确认防火墙是否允许端口访问
   - 局域网访问需要启用 `web_lan_access`

3. **登录失败**：
   - 确认密码是否正确
   - 查看插件日志获取自动生成的密码
   - 密码在插件配置中查看或修改

### API端点

Web界面提供以下API端点：

- `GET /` - 前端界面
- `GET /api/health` - 健康检查
- `POST /api/login` - 用户登录
- `GET /api/bots` - 获取Bot列表
- `GET /api/config/tree` - 获取完整配置树
- `POST /api/config/{bot_id}` - 保存Bot配置
- `POST /api/config/{bot_id}/{session_id}` - 保存会话配置
- `DELETE /api/config/{bot_id}/{session_id}` - 删除会话配置

## 作者

zz6zz666

## 许可证

本插件基于 GPLv3 许可证发布。
