from __future__ import annotations

from typing import Any, Dict

import streamlit as st

from web_ui.session_state import mark_schedule_dirty
from web_ui.user_memory import (
    ENVIRONMENT_LABELS_CN,
    build_memory_from_answers,
    default_profile_memory,
    save_profile_memory,
)


def render_profile_onboarding() -> None:
    if not st.session_state.get("show_profile_test", False):
        return
    if hasattr(st, "dialog"):
        st.dialog("先给 AI 一点你的生活手感")(_profile_dialog)()
    else:
        render_profile_test_body(in_dialog=False)


def _profile_dialog() -> None:
    render_profile_test_body(in_dialog=True)


def render_profile_test_body(*, in_dialog: bool) -> None:
    if st.session_state.get("onboarding_step") == "survey":
        render_survey()
        return
    st.markdown(
        """
        **做一个很短的小测试，我们就能更像“懂你节奏的日程搭子”。**

        它不会问什么沉重问题，只会摸清：你什么时候脑子最好用、DDL 会不会追着你跑、
        你更爱整块专注还是碎片推进。之后排程会把这些偏好记到本地 `data/` 里。
        """
    )
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("来，测一下我的节奏", type="primary", use_container_width=True):
            st.session_state.onboarding_step = "survey"
            st.rerun()
    with col_b:
        if st.button("先按默认节奏试跑", use_container_width=True):
            save_memory(default_profile_memory(completed=True))
            st.rerun()
    if not in_dialog:
        st.info("你的 Streamlit 版本不支持弹窗，所以测试会显示在页面顶部。")


def render_survey() -> None:
    st.markdown("**选最像你的那个就好，不用太认真，第一反应通常最准确。**")
    with st.form("profile_rhythm_survey"):
        answers: Dict[str, Any] = {}
        answers["rhythm"] = st.radio(
            "1. 你的大脑通常什么时候最像刚充满电？",
            options=["sunrise", "lunch", "moon", "weather"],
            format_func=lambda value: {
                "sunrise": "早上：咖啡还没凉，脑子已经上线",
                "lunch": "下午：上午热身，午后才进入主场",
                "moon": "晚上：越夜越清醒，白天只是铺垫",
                "weather": "看天气和心情：灵感随机刷新",
            }[value],
        )
        answers["day_shape"] = st.radio(
            "2. 哪种一天的可用时间更像你？",
            options=["classic", "split", "late", "compact"],
            format_func=lambda value: {
                "classic": "标准白天档：上午 + 下午比较稳",
                "split": "三段式：白天做事，晚上还能补一波",
                "late": "晚启动：上午慢热，傍晚和晚上更有戏",
                "compact": "紧凑档：可用时间不长，但希望别浪费",
            }[value],
        )
        answers["deep_tank"] = st.radio(
            "3. 连续认真用脑多久后，你会想把世界静音？",
            options=["sprint", "movie", "chapter", "marathon"],
            format_func=lambda value: {
                "sprint": "90 分钟以内：短跑型，冲完要回血",
                "movie": "2-3 小时：像看完一部电影那样刚好",
                "chapter": "3 小时左右：进入状态后能啃一大章",
                "marathon": "4 小时以上：深潜型，别轻易打断我",
            }[value],
        )
        answers["deadline_style"] = st.radio(
            "4. DDL 靠近时，你希望系统怎么对你？",
            options=["fire", "steady", "buffer", "soft"],
            format_func=lambda value: {
                "fire": "拉响警报：快到期的先救",
                "steady": "稳一点：重要但别把整天打乱",
                "buffer": "提前铺垫：我不想最后一天狂奔",
                "soft": "温柔提醒：能完成就好，别太压迫",
            }[value],
        )
        answers["energy_match"] = st.radio(
            "5. 难任务应该被安排在什么时段？",
            options=["strict", "balanced", "casual"],
            format_func=lambda value: {
                "strict": "必须放在高能时段，我低电量时不想硬刚",
                "balanced": "尽量匹配就行，现实也要有弹性",
                "casual": "我适应力还行，时间空出来更重要",
            }[value],
        )
        answers["switching"] = st.radio(
            "6. 一天里任务类型切来切去，你的感受是？",
            options=["batch", "mixed", "shuffle"],
            format_func=lambda value: {
                "batch": "很耗电：同类任务最好凑一起",
                "mixed": "还可以：别太频繁就行",
                "shuffle": "无所谓：换一换反而清醒",
            }[value],
        )
        answers["block_style"] = st.radio(
            "7. 你偏爱的时间块长什么样？",
            options=["deep", "medium", "snack"],
            format_func=lambda value: {
                "deep": "大块完整时间，最好别切碎",
                "medium": "中等块，完成感和灵活性都要",
                "snack": "小块也行，我擅长见缝插针",
            }[value],
        )
        answers["focus_noise"] = st.radio(
            "8. 关于安静程度，你更像哪种？",
            options=["cave", "hum", "flex", "chaos"],
            format_func=lambda value: {
                "cave": "需要洞穴模式：安静时段很珍贵",
                "hum": "低噪白噪可以，别突然打断",
                "flex": "下午更容易沉下来",
                "chaos": "环境不是核心，我主要靠意志力",
            }[value],
        )
        answers["preference_style"] = st.radio(
            "9. 系统要多照顾你的习惯和场地偏好？",
            options=["ritual", "normal", "anywhere"],
            format_func=lambda value: {
                "ritual": "很重要：对的地方和仪式感能救命",
                "normal": "适中：照顾习惯，但别牺牲效率",
                "anywhere": "少一点：先把事情排进去",
            }[value],
        )
        answers["environments"] = st.multiselect(
            "10. 哪些地方/设备最适合安排你的正式任务？",
            options=list(ENVIRONMENT_LABELS_CN),
            default=["desk", "library"],
            format_func=lambda value: ENVIRONMENT_LABELS_CN[value],
        )
        submitted = st.form_submit_button("生成我的节奏画像", type="primary", use_container_width=True)
    if submitted:
        if not answers["environments"]:
            answers["environments"] = ["desk"]
        save_memory(build_memory_from_answers(answers))
        st.success("已记住你的节奏画像。之后排程会按这套偏好来理解你。")
        st.rerun()


def save_memory(memory: Dict[str, Any]) -> None:
    save_profile_memory(memory)
    st.session_state.profile_memory = memory
    st.session_state.show_profile_test = False
    st.session_state.onboarding_step = "intro"
    mark_schedule_dirty()
