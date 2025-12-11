# MemOS记忆集成插件包
# 这个文件使插件目录成为Python包，支持相对导入

# 导入插件的主要模块
from .main import MemosIntegratorPlugin
from .memos_client import MemOS_Client
from .memory_manager import MemoryManager
from .memory_templates import MemoryTemplates

__all__ = ["MemosIntegratorPlugin", "MemOS_Client", "MemoryManager", "MemoryTemplates"]