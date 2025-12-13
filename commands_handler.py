from datetime import datetime, timezone, timedelta


def ts_to_beijing(ts):
    """将时间戳转换为北京时间"""
    if isinstance(ts, (int, float)):
        if ts > 1000000000000:  # 毫秒时间戳
            ts = ts / 1000
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
    return str(ts)


class CommandsHandler:

    @classmethod
    def generate_md_report(cls, data, user_profile: bool = False):
        """生成Markdown格式的记忆查询报告"""
        if not data:
            return "### 🧠 记忆查询报告\n\n> ∅ 未找到相关记忆"
            
        lines = []
        
        # 检查是否是人物关键词查询
        if user_profile:
            lines.append("### 🧠 用户画像报告")
        else:
            lines.append("### 🧠 记忆查询报告")
            
        lines.append("")

        # --- 1. 渲染事实记忆 ---
        # 检查是否存在且列表长度大于0
        if data.get("memory_detail_list"):
            for item in data["memory_detail_list"]:
                title_with_time = f"#### {item['memory_key']} ⏰ {ts_to_beijing(item['create_time'])}"
                lines.append(title_with_time)
                lines.append(f"- **内容**：{item['memory_value']}")
                lines.append(f"- **标签**：{' '.join([f'`{tag}`' for tag in item['tags']])}")
                lines.append(f"- **元数据**：`置信度：{item['confidence']:.2f}`｜`相关性：{item['relativity']:.6f}`｜`类型：{item['memory_type']}`")
                lines.append("")
        else:
            lines.append("> ∅ 未找到相关记忆 ")
            lines.append("")

        # --- 2. 渲染偏好记忆 ---
        # 只有当 preference_detail_list 存在且有数据时，才渲染整个“偏好洞察区”
        if data.get("preference_detail_list"):
            lines.append("---")
            lines.append("")
            lines.append("#### 🔍 偏好洞察区（系统推断）")
            for i, pref in enumerate(data["preference_detail_list"], 1):
                lines.append(f"**{i}. {pref['preference']}**  ")
                lines.append(f"🕒 {ts_to_beijing(pref['create_time'])}  ")
                lines.append(f"> 💡 **推理依据**：{pref['reasoning']}")
                lines.append("")

        # --- 3. 始终渲染底部说明 ---
        note = data.get("preference_note")
        if note:
            lines.append(f"*{note}*")

        return "\n".join(lines)