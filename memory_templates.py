"""
记忆注入模板
包含记忆和技能注入逻辑
"""

from typing import List, Dict, Optional


class MemoryTemplates:
    """记忆注入模板类"""

    # 中文记忆注入模板
    MEM_TOOL_QUERY_ROLE = """# Role

你是一个由 MemOS 驱动的智能助手。你的目标是利用检索到的记忆片段和专项技能，为用户提供个性化且准确的回答，同时严格避免由过去 AI 推断引起的幻觉。"""

    MEM_TOOL_SYSTEM_CONTEXT_PREFIX = """
# System Context

- 当前时间："""

    MEM_TOOL_SYSTEM_CONTEXT_SUFFIX = """ (时效性基准)"""

    MEM_TOOL_MEMORY_DATA_SECTION = """
# Memory Data

以下是 MemOS 检索到的信息，分为"事实"和"偏好"。
- **事实 (Facts)**：可能包含用户属性、历史记录或第三方详细信息。
- **警告**：标记为 '[assistant观点]' 或 '[summary]' 的内容代表 **AI 过去的推断**，**并非**用户的直接陈述。
- **偏好 (Preferences)**：用户对回答风格、格式或逻辑的显式/隐式要求。"""

    MEM_TOOL_SKILL_DATA_SECTION = """
# Skill Data

以下是针对当前上下文检索到的专项技能（"程序性记忆"）。这些代表用户已建立处理模式的任务。
- 状态：仅应考虑 'activated' 状态的技能。
- **技能可能以列表形式返回，且不保证对当前查询有用。你必须主动筛选。**"""

    MEM_TOOL_MEMORY_PROTOCOL = """
# Critical Protocol: Memory Safety (记忆安全协议)

你必须严格执行以下 **"四步判决"**。如果某条记忆未能通过任一步骤，**丢弃它**：

1. **来源验证 (Source Verification)**（关键）：
   - 区分"用户输入"与"AI 推断"。
   - 如果记忆标记为 '[assistant观点]' 或 '[summary]'，将其视为 **假设**，而非确凿事实。
   - **原则：AI 总结的权威性远低于用户的直接陈述。**

2. **主体归因检查 (Attribution Check)**：
   - 记忆的"主体"确定是用户本人吗？
   - 如果描述的是 **第三方**，绝不要将这些特征归因于用户。

3. **相关性检查 (Relevance Check)**：
   - 该记忆是否直接有助于回答当前的 'user原始查询'？
   - 如果只是关键词匹配但语境不同，**忽略它**。

4. **时效性检查 (Freshness Check)**：
   - 当前的 'user原始查询' 始终是最高的事实标准。"""

    MEM_TOOL_SKILL_PROTOCOL = """
# Critical Protocol: Skill Execution (技能执行协议)

当存在技能时，你必须遵守以下执行规则：

1. **适用性优先 (Applicability First)**（强制筛选）：
   - **将每个技能视为"可选"。不要假设它应该被使用。**
   - **对每个技能，判断它是否实质性帮助解决当前查询（正确性/有用性/个性化）。**
   - **如果某个技能对当前查询没有帮助，完全忽略它。**
   - **如果没有适用的技能，继续执行而不使用任何技能。**

2. **工作流组合 (Workflow Composition)**（技能作为骨架）：
   - 按顺序遵循 `<procedure>` 中定义的步骤。
   - 除非用户在当前回合已提供该信息，否则不要跳过步骤。
   - **技能是从用户过去交互中提炼的。当你选择使用技能时，将其 `<procedure>` 作为工作流骨架，应与以下内容结合：**
     - **(a) `<preferences>` 中经过验证的用户偏好**
     - **(b) `<facts>` 中经过验证的相关事实**
     - **(c) 用户当前查询的约束条件**
   - **你可以省略已满足的不必要步骤，但保留剩余步骤的内部顺序。**
   - **如果多个技能适用，以模块化方式合并它们：保留每个技能的内部步骤顺序，删除重复步骤，产生一个连贯的流程。**

3. **个性化 (Personalization)**（有依据的）：
   - 应用 `<guidance>` 来自定义你的回答。
   - **同时将技能的 `<example>` 作为信号，了解用户倾向于关注什么以及他们倾向于如何决策——但仅当它与当前查询不冲突且通过记忆安全检查时。**
   - **不要发明新的偏好。任何个性化必须基于经过验证的记忆或当前用户输入。**
   - **目标：使结果与用户的习惯决策风格一致，而非通用答案。**

4. **冲突解决 (Conflict Resolution)**：
   - 如果技能的指令与 Memory Data 部分的显式 `<preferences>` 冲突，以 Memory Data 为准。
   - **如果技能之间冲突，优先选择最符合当前查询目标和显式用户偏好的那个；否则删除冲突部分，该段落不使用技能继续执行。**"""

    MEM_TOOL_INSTRUCTIONS = """
# Instructions

1. **筛选 (Filter)**：对所有 `<facts>` 应用"四步判决"，剔除噪音。
2. **匹配 (Match)**：**从返回的技能列表中，执行适用性筛选；忽略任何对当前查询没有帮助的技能。**
3. **综合 (Synthesize)**：**如果一个或多个技能适用，将其必要的 `<procedure>` 步骤与经过验证的用户偏好和当前查询约束相结合，产生符合用户习惯工作流的输出。**
4. **风格 (Style)**：严格遵守 `<preferences>`。
5. **输出 (Output)**：直接回答。**严禁**提及"检索到的记忆"、"技能"、"数据库"或"AI 观点"。"""

    # 英文记忆注入模板
    MEM_TOOL_QUERY_ROLE_EN = """# Role

You are an intelligent assistant powered by MemOS. Your goal is to provide personalized and accurate responses by leveraging retrieved memory fragments and specialized skills, while strictly avoiding hallucinations caused by past AI inferences."""

    MEM_TOOL_SYSTEM_CONTEXT_PREFIX_EN = """
# System Context

- Current Time: """

    MEM_TOOL_SYSTEM_CONTEXT_SUFFIX_EN = """ (Baseline for freshness)"""

    MEM_TOOL_MEMORY_DATA_SECTION_EN = """
# Memory Data

Below is the information retrieved by MemOS, categorized into "Facts" and "Preferences".
- **Facts**: May contain user attributes, historical logs, or third-party details.
- **Warning**: Content tagged with '[assistant观点]' or '[summary]' represents **past AI inferences**, **NOT** direct user quotes.
- **Preferences**: Explicit or implicit user requirements regarding response style and format."""

    MEM_TOOL_SKILL_DATA_SECTION_EN = """
# Skill Data

Below are the specialized skills ("Procedural Memories") retrieved for the current context. These represent tasks the user has established patterns for.
- Status: Only 'activated' skills should be considered.
- **Skills may be returned as a list and are NOT guaranteed to be useful for the current query. You must actively filter them.**"""

    MEM_TOOL_MEMORY_PROTOCOL_EN = """
# Critical Protocol: Memory Safety

You must strictly execute the following **"Four-Step Verdict"**. If a memory fails any step, **DISCARD IT**:

1. **Source Verification (CRITICAL)**:
   - Distinguish between "User's Input" and "AI's Inference".
   - If a memory is tagged as '[assistant观点]' or '[summary]', treat it as a **hypothesis**, not a hard fact.
   - **Principle: AI summaries have much lower authority than direct user statements.**

2. **Attribution Check**:
   - Is the "Subject" of the memory definitely the User?
   - If it describes a **Third Party**, NEVER attribute these traits to the User.

3. **Relevance Check**:
   - Does the memory directly help answer the current 'Original Query'?
   - If it is merely a keyword match with different context, IGNORE IT.

4. **Freshness Check**:
   - The current 'Original Query' is always the supreme Source of Truth."""

    MEM_TOOL_SKILL_PROTOCOL_EN = """
# Critical Protocol: Skill Execution

When Skills are present, you must adhere to the following execution rules:

1. **Applicability First (Mandatory Filtering)**:
   - **Treat every skill as "optional". Do NOT assume it should be used.**
   - **For each skill, decide whether it materially helps solve the current query (correctness / usefulness / personalization).**
   - **If a skill does not help this query, ignore it completely.**
   - **If no skills are applicable, proceed without any skill.**

2. **Workflow Composition (Skill as a Skeleton)**:
   - Follow the steps defined in `<procedure>` sequentially.
   - Do not skip steps unless the user has already provided that information in the current turn.
   - **Skills are distilled from the user's past interactions. When you choose to use a skill, treat its `<procedure>` as a workflow skeleton that should be combined with:**
     - **(a) validated user preferences in `<preferences>`**
     - **(b) validated relevant facts in `<facts>`**
     - **(c) constraints from the user's current query**
   - **You may omit unnecessary steps that are already satisfied, but keep the internal order of the remaining steps.**
   - **If multiple skills are applicable, merge them modularly: preserve each skill's internal step order, remove duplicate steps, and produce one coherent flow.**

3. **Personalization (Grounded)**:
   - Apply `<guidance>` to customize your response.
   - **Also leverage the skill's `<example>` as a signal of what the user tends to care about and how they tend to decide—BUT only when it does not conflict with the current query and passes Memory Safety.**
   - **Do not invent new preferences. Any personalization must be grounded in validated memories or the current user input.**
   - **Goal: make the result align with the user's habitual decision style, not a generic answer.**

4. **Conflict Resolution**:
   - If a Skill's instruction conflicts with explicit `<preferences>` in the Memory Data section, the Memory Data takes precedence.
   - **If skills conflict with each other, prioritize the one that best matches the current query goal and explicit user preferences; otherwise, drop the conflicting part and proceed without skill for that segment.**"""

    MEM_TOOL_INSTRUCTIONS_EN = """
# Instructions

1. **Filter**: Apply the "Four-Step Verdict" to all `<facts>` to filter out noise.
2. **Match**: **From the returned skill list, perform applicability filtering; ignore any skill that does not help the current query.**
3. **Synthesize**: **If one or more skills are applicable, combine their necessary `<procedure>` steps with validated user preferences and the current query constraints to produce an output that fits the user's habitual workflow.**
4. **Style**: Strictly adhere to `<preferences>`.
5. **Output**: Answer directly. **NEVER** mention "retrieved memories," "skills," "database," or "AI views" in your response."""

    @classmethod
    def get_injection_template(cls, language: str = "zh", injection_type: str = "user", enable_skill: bool = True) -> str:
        """获取记忆注入模板
        
        Args:
            language: 语言，"zh"为中文，"en"为英文
            injection_type: 注入类型，"user"为用户注入，"system"为系统注入
            enable_skill: 是否启用技能注入，默认True
            
        Returns:
            记忆注入模板字符串
        """
        if language == "en":
            # 英文模板
            mem_text = cls.MEM_TOOL_QUERY_ROLE_EN + "\n"
            system_context = cls.MEM_TOOL_SYSTEM_CONTEXT_PREFIX_EN + "{current_time}" + cls.MEM_TOOL_SYSTEM_CONTEXT_SUFFIX_EN + "\n"
            memory_data_section = cls.MEM_TOOL_MEMORY_DATA_SECTION_EN + "\n"
            skill_data_section = cls.MEM_TOOL_SKILL_DATA_SECTION_EN + "\n" if enable_skill else ""
            memory_protocol = cls.MEM_TOOL_MEMORY_PROTOCOL_EN + "\n"
            skill_protocol = cls.MEM_TOOL_SKILL_PROTOCOL_EN + "\n" if enable_skill else ""
            query_instructions = cls.MEM_TOOL_INSTRUCTIONS_EN + "\n"
            query_marker = "\nOriginal Query"
        else:
            # 中文模板
            mem_text = cls.MEM_TOOL_QUERY_ROLE + "\n"
            system_context = cls.MEM_TOOL_SYSTEM_CONTEXT_PREFIX + "{current_time}" + cls.MEM_TOOL_SYSTEM_CONTEXT_SUFFIX + "\n"
            memory_data_section = cls.MEM_TOOL_MEMORY_DATA_SECTION + "\n"
            skill_data_section = cls.MEM_TOOL_SKILL_DATA_SECTION + "\n" if enable_skill else ""
            memory_protocol = cls.MEM_TOOL_MEMORY_PROTOCOL + "\n"
            skill_protocol = cls.MEM_TOOL_SKILL_PROTOCOL + "\n" if enable_skill else ""
            query_instructions = cls.MEM_TOOL_INSTRUCTIONS + "\n"
            query_marker = "\nuser原始查询："
        
        # 根据是否启用技能构建模板
        if enable_skill:
            skill_content_placeholder = "{skill_content}"
            skill_section = f"""{skill_data_section}{skill_content_placeholder}

"""
            protocol_section = f"""{memory_protocol}{skill_protocol}"""
        else:
            skill_section = ""
            protocol_section = f"""{memory_protocol}"""
        
        if injection_type == "system":
            # System注入模板：不包含Original Query部分
            template = f"""{mem_text}{system_context}{memory_data_section}
{{memory_content}}

{skill_section}{protocol_section}{query_instructions}"""
        else:
            # User注入模板：包含Original Query部分
            template = f"""{mem_text}{system_context}{memory_data_section}
{{memory_content}}

{skill_section}{protocol_section}{query_instructions}
{query_marker}
{{original_query}}"""
        
        return template

    @classmethod
    def format_memory_content(cls, memories: List[Dict], language: str = "zh") -> str:
        """格式化记忆内容
        
        Args:
            memories: 记忆列表
            language: 语言，"zh"为中文，"en"为英文
            
        Returns:
            格式化后的记忆内容
        """
        if not memories:
            # 返回空的 memories 结构
            return """```xml
<memories>
  <facts>
  </facts>
  <preferences>
  </preferences>
</memories>
```"""
        
        # 分离事实记忆和偏好记忆
        fact_memories = []
        preference_memories = []
        
        for memory in memories:
            if memory.get("type") == "preference":
                preference_memories.append(memory)
            else:
                fact_memories.append(memory)
        
        # 格式化事实记忆行
        fact_lines = []
        for memory in fact_memories:
            timestamp = memory.get("timestamp", "")
            content = memory.get("content", "")
            if content:
                if timestamp:
                    fact_lines.append(f"   -[{timestamp}] {content}")
                else:
                    fact_lines.append(f"   - {content}")
        
        # 格式化偏好记忆行
        pref_lines = []
        for memory in preference_memories:
            timestamp = memory.get("timestamp", "")
            pref_type = memory.get("preference_type", "explicit_preference")
            content = memory.get("content", "")
            if content:
                if language == "en":
                    pref_type_text = "Implicit Preference" if pref_type == "implicit_preference" else "Explicit Preference"
                else:
                    pref_type_text = "隐式偏好" if pref_type == "implicit_preference" else "显式偏好"
                
                if timestamp:
                    pref_lines.append(f"   -[{timestamp}] [{pref_type_text}] {content}")
                else:
                    pref_lines.append(f"   - [{pref_type_text}] {content}")
        
        # 构建记忆块
        lines = ["```xml", "<memories>"]
        
        # 添加事实部分
        lines.append("  <facts>")
        lines.extend(fact_lines)
        lines.append("  </facts>")
        
        # 添加偏好部分
        lines.append("  <preferences>")
        lines.extend(pref_lines)
        lines.append("  </preferences>")
        
        lines.append("</memories>")
        lines.append("```")
        
        return "\n".join(lines)

    @classmethod
    def format_skill_content(cls, skills: List[Dict], language: str = "zh") -> str:
        """格式化技能内容
        
        Args:
            skills: 技能列表
            language: 语言，"zh"为中文，"en"为英文
            
        Returns:
            格式化后的技能内容
        """
        if not skills:
            # 返回空的 skills 结构
            return """```xml
<skills>
</skills>
```"""
        
        lines = ["```xml", "<skills>"]
        
        for skill in skills:
            skill_id = skill.get("id", "")
            name = skill.get("name", "")
            status = skill.get("status", "activated")
            procedure = skill.get("procedure", "")
            guidance = skill.get("guidance", "")
            example = skill.get("example", "")
            
            lines.append("  <skill>")
            if skill_id:
                lines.append(f"    <id>{skill_id}</id>")
            if name:
                lines.append(f"    <name>{name}</name>")
            if status:
                lines.append(f"    <status>{status}</status>")
            if procedure:
                lines.append(f"    <procedure>{procedure}</procedure>")
            if guidance:
                lines.append(f"    <guidance>{guidance}</guidance>")
            if example:
                lines.append(f"    <example>{example}</example>")
            lines.append("  </skill>")
        
        lines.append("</skills>")
        lines.append("```")
        
        return "\n".join(lines)

    @classmethod
    def build_injection_prompt(
        cls,
        original_query: str,
        memories: List[Dict],
        skills: Optional[List[Dict]] = None,
        language: str = "zh",
        injection_type: str = "user",
        current_time: Optional[str] = None,
        enable_skill: bool = True
    ) -> str:
        """构建完整的注入提示词
        
        Args:
            original_query: 原始查询
            memories: 记忆列表
            skills: 技能列表（可选）
            language: 语言
            injection_type: 注入类型
            current_time: 当前时间（可选，默认使用系统时间）
            enable_skill: 是否启用技能注入，默认True
            
        Returns:
            完整的注入提示词
        """
        import time as time_module
        
        if current_time is None:
            current_time = time_module.strftime("%Y-%m-%d %H:%M", time_module.localtime())
        
        # 获取模板（根据是否启用技能）
        template = cls.get_injection_template(language, injection_type, enable_skill)
        
        # 格式化记忆内容
        memory_content = cls.format_memory_content(memories, language)
        
        # 填充模板
        if enable_skill:
            # 格式化技能内容
            skill_content = cls.format_skill_content(skills or [], language)
            
            if injection_type == "system":
                return template.format(
                    memory_content=memory_content,
                    skill_content=skill_content,
                    current_time=current_time
                )
            else:
                return template.format(
                    original_query=original_query,
                    memory_content=memory_content,
                    skill_content=skill_content,
                    current_time=current_time
                )
        else:
            # 不启用技能时，不包含 skill_content
            if injection_type == "system":
                return template.format(
                    memory_content=memory_content,
                    current_time=current_time
                )
            else:
                return template.format(
                    original_query=original_query,
                    memory_content=memory_content,
                    current_time=current_time
                )
