from __future__ import annotations

import streamlit as st


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 2.25rem;
            padding-bottom: 12rem;
            max-width: 1180px;
        }
        .task-list-shell {
            max-width: 980px;
            margin: 1.25rem auto 1.5rem auto;
        }
        .task-list-empty {
            min-height: 260px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            border: 1px dashed rgba(100, 116, 139, 0.42);
            border-radius: 8px;
            background: rgba(248, 250, 252, 0.66);
        }
        .task-list-empty-title {
            font-size: 1.08rem;
            font-weight: 750;
            color: #0f172a;
        }
        .task-list-empty-copy {
            margin-top: 0.35rem;
            max-width: 430px;
            color: #64748b;
            font-size: 0.9rem;
            line-height: 1.5;
        }
        .timeline-shell {
            margin-top: 1rem;
        }
        .day-list-shell {
            display: grid;
            gap: 0.78rem;
            margin-top: 0.75rem;
        }
        .day-list-summary {
            color: #475569;
            font-size: 0.88rem;
            font-weight: 650;
            padding: 0 0.1rem;
        }
        .day-list-empty {
            min-height: 260px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            border: 1px dashed rgba(14, 165, 233, 0.34);
            border-radius: 8px;
            background: linear-gradient(180deg, rgba(240, 249, 255, 0.72), rgba(248, 250, 252, 0.76));
            margin-top: 0.65rem;
        }
        .day-list-empty-title {
            color: #0f172a;
            font-size: 1.06rem;
            font-weight: 760;
        }
        .day-list-empty-copy {
            margin-top: 0.35rem;
            color: #64748b;
            font-size: 0.9rem;
        }
        .day-task-card {
            height: 136px;
            margin-top: 0.78rem;
            border: 2px solid rgba(14, 165, 233, 0.68);
            border-radius: 8px;
            padding: 0.86rem 1rem;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
            box-sizing: border-box;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            color: #0f172a;
        }
        .day-task-time {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
            color: #334155;
            font-size: 0.86rem;
            font-weight: 750;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        }
        .day-task-time strong {
            color: #475569;
            font-size: 0.75rem;
            font-weight: 760;
            white-space: nowrap;
        }
        .day-task-title {
            font-size: 1.02rem;
            font-weight: 790;
            line-height: 1.28;
            overflow-wrap: anywhere;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }
        .day-task-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 0.42rem;
            color: #475569;
            font-size: 0.76rem;
            font-weight: 650;
        }
        .day-task-meta span {
            border: 1px solid rgba(148, 163, 184, 0.28);
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.46);
            padding: 0.12rem 0.46rem;
            max-width: 100%;
            overflow-wrap: anywhere;
        }
        div[class*="st-key-day_task_card_"] {
            height: 136px;
            margin-top: 0.78rem;
            border: 2px solid rgba(14, 165, 233, 0.68);
            border-radius: 8px;
            padding: 0.72rem 0.85rem;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
            box-sizing: border-box;
            overflow: hidden;
            color: #0f172a;
        }
        div[class*="st-key-day_task_card_"] [data-testid="stHorizontalBlock"] {
            align-items: stretch;
        }
        div[class*="st-key-day_task_card_"] button {
            border-radius: 999px;
            border: 1px solid rgba(15, 23, 42, 0.12);
            background: rgba(255, 255, 255, 0.72);
            color: #0f172a;
            font-weight: 760;
            min-height: 2.15rem;
        }
        .day-task-content {
            height: 106px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            overflow: hidden;
        }
        .day-task-done-badge {
            border: 1px solid rgba(5, 150, 105, 0.28);
            border-radius: 999px;
            padding: 0.42rem 0.55rem;
            background: rgba(209, 250, 229, 0.66);
            color: #047857;
            font-size: 0.82rem;
            font-weight: 780;
            text-align: center;
            white-space: nowrap;
        }
        div[class*="st-key-unresolved_task_card_"] {
            min-height: 112px;
            margin-top: 0.78rem;
            border: 2px solid rgba(148, 163, 184, 0.48);
            border-radius: 8px;
            padding: 0.86rem 1rem;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
            box-sizing: border-box;
            color: #0f172a;
        }
        div[class*="st-key-unresolved_task_card_"] [data-testid="stHorizontalBlock"] {
            align-items: stretch;
        }
        div[class*="st-key-unresolved_task_card_"] button {
            border-radius: 999px;
            border: 1px solid rgba(15, 23, 42, 0.12);
            background: rgba(255, 255, 255, 0.72);
            color: #0f172a;
            font-weight: 760;
            min-height: 2.15rem;
        }
        .unresolved-task-content {
            min-height: 82px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .unresolved-task-head {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 0.75rem;
            font-size: 1rem;
            font-weight: 790;
            line-height: 1.28;
        }
        .unresolved-task-head span {
            overflow-wrap: anywhere;
        }
        .unresolved-task-head strong {
            border-radius: 999px;
            padding: 0.14rem 0.5rem;
            background: rgba(255, 255, 255, 0.62);
            color: #475569;
            font-size: 0.76rem;
            white-space: nowrap;
        }
        .unresolved-task-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 0.42rem;
            margin-top: 0.8rem;
            color: #475569;
            font-size: 0.76rem;
            font-weight: 650;
        }
        .unresolved-task-meta span {
            border: 1px solid rgba(148, 163, 184, 0.28);
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.46);
            padding: 0.12rem 0.46rem;
            max-width: 100%;
            overflow-wrap: anywhere;
        }
        .task-edit-shell {
            margin: 1.05rem 0 1.1rem 0;
            padding: 1rem;
            border: 1px solid rgba(14, 165, 233, 0.24);
            border-radius: 8px;
            background: rgba(240, 249, 255, 0.58);
            box-shadow: 0 12px 34px rgba(15, 23, 42, 0.08);
        }
        .task-edit-shell [data-testid="stForm"] {
            border: 0;
            padding: 0;
        }
        .task-edit-shell button[kind="primaryFormSubmit"] {
            border-radius: 999px;
            background: linear-gradient(135deg, #0ea5e9, #10b981);
            border: 0;
            color: white;
            font-weight: 760;
        }
        .calendar-week-title {
            text-align: center;
            font-weight: 750;
            color: #0f172a;
            padding: 0.45rem 0 0.35rem 0;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        }
        .calendar-shell {
            margin-top: 0.55rem;
            overflow-x: auto;
            padding-bottom: 0.35rem;
        }
        .calendar-empty {
            min-height: 260px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            border: 1px dashed rgba(14, 165, 233, 0.34);
            border-radius: 8px;
            background: linear-gradient(180deg, rgba(240, 249, 255, 0.72), rgba(248, 250, 252, 0.76));
            margin-top: 0.65rem;
        }
        .calendar-empty-title {
            color: #0f172a;
            font-size: 1.06rem;
            font-weight: 760;
        }
        .calendar-empty-copy {
            margin-top: 0.35rem;
            color: #64748b;
            font-size: 0.9rem;
        }
        .calendar-grid {
            min-width: 920px;
            display: grid;
            grid-template-columns: 82px repeat(7, minmax(112px, 1fr));
            border: 1px solid rgba(148, 163, 184, 0.34);
            border-radius: 8px;
            overflow: hidden;
            background: rgba(255, 255, 255, 0.64);
        }
        .calendar-time-column,
        .calendar-day-column {
            border-right: 1px solid rgba(148, 163, 184, 0.22);
            background: rgba(248, 250, 252, 0.62);
        }
        .calendar-day-column:last-child {
            border-right: 0;
        }
        .calendar-corner,
        .calendar-day-head {
            height: 48px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-bottom: 1px solid rgba(148, 163, 184, 0.26);
            background: rgba(241, 245, 249, 0.72);
            color: #334155;
            font-size: 0.86rem;
            font-weight: 750;
            box-sizing: border-box;
        }
        .calendar-day-head {
            flex-direction: column;
            gap: 0.08rem;
        }
        .calendar-day-head span {
            color: #0f172a;
        }
        .calendar-day-head strong {
            color: #64748b;
            font-size: 0.74rem;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        }
        .calendar-time-body,
        .calendar-day-body {
            position: relative;
        }
        .calendar-day-body {
            background:
                repeating-linear-gradient(
                    to bottom,
                    rgba(148, 163, 184, 0.18) 0,
                    rgba(148, 163, 184, 0.18) 1px,
                    transparent 1px,
                    transparent 46px
                ),
                rgba(255, 255, 255, 0.54);
        }
        .calendar-time-label {
            position: absolute;
            right: 0.7rem;
            color: #475569;
            font-size: 0.8rem;
            font-weight: 650;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            white-space: nowrap;
        }
        .calendar-task-block {
            position: absolute;
            left: 0.44rem;
            right: 0.44rem;
            border-left: 4px solid rgba(14, 165, 233, 0.68);
            border-radius: 10px;
            padding: 0.25rem 0.38rem;
            box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
            overflow: hidden;
            color: #0f172a;
            backdrop-filter: blur(2px);
        }
        .profile-memory-card {
            border: 1px solid rgba(14, 165, 233, 0.24);
            border-radius: 8px;
            padding: 0.78rem 0.82rem;
            background: rgba(240, 249, 255, 0.58);
            margin: 0.4rem 0 0.8rem 0;
        }
        .profile-memory-title {
            font-size: 0.98rem;
            font-weight: 780;
            color: #0f172a;
            margin-bottom: 0.35rem;
        }
        .profile-memory-card p {
            margin: 0.28rem 0;
            color: #475569;
            font-size: 0.84rem;
            line-height: 1.42;
        }
        .calendar-task-time {
            font-size: 0.64rem;
            color: #475569;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            white-space: nowrap;
        }
        .calendar-task-title {
            margin-top: 0.08rem;
            font-size: 0.76rem;
            font-weight: 750;
            line-height: 1.22;
            overflow-wrap: anywhere;
        }
        .calendar-task-meta {
            margin-top: 0.12rem;
            font-size: 0.63rem;
            color: #64748b;
            line-height: 1.2;
            overflow-wrap: anywhere;
        }
        .schedule-block {
            border: 1px solid rgba(148, 163, 184, 0.28);
            border-left: 6px solid #2563eb;
            border-radius: 8px;
            padding: 1rem 1.05rem;
            margin: 0 0 0.9rem 0;
            background: rgba(15, 23, 42, 0.035);
        }
        .schedule-head {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            align-items: flex-start;
        }
        .schedule-time {
            color: #64748b;
            font-size: 0.82rem;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        }
        .schedule-title {
            font-weight: 750;
            font-size: 1.05rem;
            margin-top: 0.2rem;
            line-height: 1.35;
        }
        .priority-badge {
            color: white;
            border-radius: 999px;
            padding: 0.28rem 0.68rem;
            font-size: 0.78rem;
            font-weight: 750;
            white-space: nowrap;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        }
        .schedule-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin: 0.75rem 0;
        }
        .schedule-meta span {
            border: 1px solid rgba(148, 163, 184, 0.35);
            border-radius: 999px;
            padding: 0.16rem 0.55rem;
            font-size: 0.78rem;
            color: #475569;
            background: rgba(255, 255, 255, 0.45);
        }
        .dimension-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.8rem;
            margin: 0.55rem 0 0.7rem 0;
        }
        .dimension-label {
            font-size: 0.78rem;
            color: #475569;
            margin-bottom: 0.24rem;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        }
        .bar {
            height: 8px;
            border-radius: 999px;
            overflow: hidden;
            background: rgba(148, 163, 184, 0.26);
        }
        .bar span {
            display: block;
            height: 100%;
            border-radius: 999px;
        }
        .reason {
            color: #64748b;
            font-size: 0.82rem;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        }
        .st-key-task_composer {
            position: relative;
            width: 100%;
            margin: 1.05rem 0 2rem 0;
            padding: 0.95rem 1rem 0.9rem 1rem;
            border: 1px solid rgba(14, 165, 233, 0.22);
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.94);
            box-shadow: 0 12px 34px rgba(15, 23, 42, 0.1);
        }
        .st-key-task_composer .composer-greeting {
            color: #0f172a;
            font-size: 1rem;
            font-weight: 780;
            line-height: 1.25;
            margin: 0 0 0.42rem 0.05rem;
        }
        .st-key-task_composer textarea {
            min-height: 88px !important;
            border-radius: 10px;
            border-color: rgba(14, 165, 233, 0.28);
            background: rgba(240, 249, 255, 0.56);
            color: #0f172a;
            font-size: 0.9rem;
            line-height: 1.45;
        }
        .st-key-task_composer textarea::placeholder {
            color: #64748b;
            font-size: 0.84rem;
            font-weight: 500;
            line-height: 1.45;
        }
        .st-key-task_composer button[kind="primaryFormSubmit"] {
            border-radius: 999px;
            background: linear-gradient(135deg, #0ea5e9, #10b981);
            border: 0;
            color: white;
            font-weight: 760;
            min-height: 2.35rem;
        }
        .st-key-task_composer [data-testid="stForm"] {
            border: 0;
            padding: 0;
        }
        @media (max-width: 760px) {
            .calendar-grid {
                min-width: 820px;
                grid-template-columns: 74px repeat(7, minmax(104px, 1fr));
            }
            .st-key-task_composer {
                padding: 0.78rem;
            }
            .day-task-card {
                height: 148px;
                padding: 0.78rem;
            }
            div[class*="st-key-day_task_card_"] {
                height: 156px;
                padding: 0.68rem;
            }
            .day-task-content {
                height: 126px;
            }
            .day-task-time {
                align-items: flex-start;
                flex-direction: column;
                gap: 0.2rem;
            }
            .schedule-head {
                display: block;
            }
            .priority-badge {
                display: inline-block;
                margin-top: 0.65rem;
            }
            .dimension-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
