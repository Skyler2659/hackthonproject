from __future__ import annotations

import streamlit as st


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 2.25rem;
            padding-bottom: 3rem;
            max-width: 1180px;
        }
        .timeline-shell {
            margin-top: 1rem;
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
        @media (max-width: 760px) {
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

