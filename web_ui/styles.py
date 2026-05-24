from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            color-scheme: light;
            --ink: #0A2540;
            --ink-2: #083B66;
            --muted: #4f6478;
            --teal: #14B8A6;
            --blue: #3B82F6;
            --violet: #8B5CF6;
            --accent: #14B8A6;
            --accent-strong: #0F766E;
            --accent-soft: rgba(20, 184, 166, 0.18);
            --accent-track: rgba(20, 184, 166, 0.22);
            --glass: rgba(255, 255, 255, 0.75);
            --glass-strong: rgba(255, 255, 255, 0.88);
            --line: rgba(20, 184, 166, 0.30);
            --shadow: 0 18px 46px rgba(10, 37, 64, 0.10);
            --shadow-hover: 0 24px 58px rgba(59, 130, 246, 0.16);
            --radius-sm: 12px;
            --radius-md: 16px;
            --radius-lg: 20px;
            --ease: 0.3s ease;
        }

        @keyframes flow-bg {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }

        @keyframes gradient-shift {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }

        @keyframes gradient-border {
            0% { border-color: rgba(20, 184, 166, 0.70); }
            33% { border-color: rgba(59, 130, 246, 0.70); }
            66% { border-color: rgba(139, 92, 246, 0.70); }
            100% { border-color: rgba(20, 184, 166, 0.70); }
        }

        html,
        body {
            background: linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 25%, #f0f9ff 50%, #faf5ff 75%, #f0fdf4 100%) !important;
            height: 100% !important;
            min-height: 100% !important;
            overflow: hidden !important;
            overscroll-behavior: none !important;
        }

        #root,
        #root > div,
        .stApp {
            height: 100vh !important;
            height: 100dvh !important;
            max-height: 100vh !important;
            max-height: 100dvh !important;
            min-height: 0 !important;
            overflow: hidden !important;
        }

        .stApp {
            color: var(--ink);
            background:
                linear-gradient(135deg,
                    rgba(167, 243, 208, 0.70) 0%,
                    rgba(224, 242, 254, 0.65) 25%,
                    rgba(139, 92, 246, 0.12) 50%,
                    rgba(167, 243, 208, 0.55) 75%,
                    rgba(224, 242, 254, 0.60) 100%);
            background-size: 400% 400% !important;
            animation: flow-bg 25s ease infinite;
            position: relative;
            isolation: isolate;
        }

        .stApp::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background:
                radial-gradient(circle at 15% 20%, rgba(20, 184, 166, 0.28), transparent 40%),
                radial-gradient(circle at 85% 15%, rgba(59, 130, 246, 0.24), transparent 38%),
                radial-gradient(circle at 50% 80%, rgba(139, 92, 246, 0.18), transparent 35%),
                radial-gradient(circle at 70% 50%, rgba(167, 243, 208, 0.35), transparent 30%);
            pointer-events: none;
            z-index: 0;
            animation: flow-bg 30s ease infinite reverse;
        }

        [data-testid="stAppViewContainer"],
        [data-testid="stAppViewContainer"] > .main {
            color: var(--ink);
            background: transparent !important;
            position: relative;
            z-index: 1;
        }

        [data-testid="stAppViewContainer"] {
            height: 100vh !important;
            height: 100dvh !important;
            max-height: 100vh !important;
            max-height: 100dvh !important;
            min-height: 0 !important;
            overflow: hidden !important;
        }

        [data-testid="stAppViewContainer"] > .main,
        section[data-testid="stMain"],
        div[data-testid="stMain"] {
            height: 100vh !important;
            height: 100dvh !important;
            max-height: 100vh !important;
            max-height: 100dvh !important;
            min-height: 0 !important;
            overflow-x: hidden !important;
            overflow-y: auto !important;
            overscroll-behavior: contain !important;
        }

        section[data-testid="stSidebar"] {
            height: 100vh !important;
            height: 100dvh !important;
            max-height: 100vh !important;
            max-height: 100dvh !important;
            min-height: 0 !important;
            overflow-x: hidden !important;
            overflow-y: auto !important;
            overscroll-behavior: contain !important;
        }

        body:has(:is([role="dialog"], [data-testid="stDialog"], [data-baseweb="modal"])) #root,
        body:has(:is([role="dialog"], [data-testid="stDialog"], [data-baseweb="modal"])) #root > div,
        body:has(:is([role="dialog"], [data-testid="stDialog"], [data-baseweb="modal"])) .stApp,
        body:has(:is([role="dialog"], [data-testid="stDialog"], [data-baseweb="modal"])) [data-testid="stAppViewContainer"],
        body:has(:is([role="dialog"], [data-testid="stDialog"], [data-baseweb="modal"])) [data-testid="stAppViewContainer"] > .main,
        body:has(:is([role="dialog"], [data-testid="stDialog"], [data-baseweb="modal"])) section[data-testid="stMain"],
        body:has(:is([role="dialog"], [data-testid="stDialog"], [data-baseweb="modal"])) div[data-testid="stMain"] {
            height: auto !important;
            max-height: none !important;
            min-height: 100vh !important;
            min-height: 100dvh !important;
            overflow: visible !important;
        }

        [role="dialog"],
        [data-testid="stDialog"],
        [data-baseweb="modal"] {
            height: auto !important;
            max-height: calc(100vh - 2rem) !important;
            max-height: calc(100dvh - 2rem) !important;
            overflow: visible !important;
        }

        [role="dialog"] > div,
        [data-testid="stDialog"] > div,
        [data-baseweb="modal"] > div {
            height: auto !important;
            max-height: calc(100vh - 2rem) !important;
            max-height: calc(100dvh - 2rem) !important;
            overflow-x: hidden !important;
            overflow-y: auto !important;
        }

        [role="dialog"] [data-testid="stVerticalBlock"],
        [role="dialog"] [data-testid="stForm"],
        [role="dialog"] [data-testid="stElementContainer"],
        [data-testid="stDialog"] [data-testid="stVerticalBlock"],
        [data-testid="stDialog"] [data-testid="stForm"],
        [data-testid="stDialog"] [data-testid="stElementContainer"],
        [data-baseweb="modal"] [data-testid="stVerticalBlock"],
        [data-baseweb="modal"] [data-testid="stForm"],
        [data-baseweb="modal"] [data-testid="stElementContainer"] {
            height: auto !important;
            max-height: none !important;
            min-height: 0 !important;
            overflow: visible !important;
            opacity: 1 !important;
            visibility: visible !important;
        }

        @keyframes task-fab-pulse {
            0%, 100% { box-shadow: 0 14px 34px rgba(20, 184, 166, 0.34), 0 0 0 0 rgba(59, 130, 246, 0.18); }
            50% { box-shadow: 0 18px 42px rgba(59, 130, 246, 0.38), 0 0 0 10px rgba(20, 184, 166, 0); }
        }

        .st-key-task_fab,
        .st-key-task_fab [data-testid="stVerticalBlock"],
        .st-key-task_fab [data-testid="stElementContainer"] {
            position: fixed !important;
            right: 1.35rem !important;
            bottom: 1.35rem !important;
            left: auto !important;
            top: auto !important;
            z-index: 99990 !important;
            width: 3.75rem !important;
            min-width: 3.75rem !important;
            max-width: 3.75rem !important;
            height: 3.75rem !important;
            min-height: 3.75rem !important;
            max-height: 3.75rem !important;
            margin: 0 !important;
            padding: 0 !important;
            pointer-events: none !important;
        }

        .st-key-task_fab [data-testid="stButton"] {
            pointer-events: auto !important;
        }

        .st-key-task_fab button {
            width: 3.75rem !important;
            min-width: 3.75rem !important;
            height: 3.75rem !important;
            min-height: 3.75rem !important;
            padding: 0 !important;
            border-radius: 50% !important;
            border: 0 !important;
            color: white !important;
            font-size: 1.35rem !important;
            font-weight: 800 !important;
            line-height: 1 !important;
            background: linear-gradient(135deg, var(--teal), var(--blue), var(--violet)) !important;
            background-size: 220% 220% !important;
            animation: gradient-shift 8s ease infinite, task-fab-pulse 2.8s ease-in-out infinite;
            box-shadow: 0 14px 34px rgba(20, 184, 166, 0.34);
        }

        .st-key-task_fab button:hover {
            transform: translateY(-3px) scale(1.04);
            box-shadow: 0 20px 46px rgba(59, 130, 246, 0.42);
        }

        body:has([data-chrona-composer-open="true"]) .st-key-task_fab button {
            background: linear-gradient(135deg, #64748b, #475569) !important;
            animation: none !important;
        }

        .chrona-composer-state {
            display: none !important;
            width: 0 !important;
            height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
            overflow: hidden !important;
            pointer-events: none !important;
        }

        div[class*="st-key-task_composer_panel"] {
            position: fixed !important;
            left: 50% !important;
            top: 50% !important;
            transform: translate(-50%, -50%) !important;
            z-index: 99991 !important;
            width: min(520px, calc(100vw - 2rem)) !important;
            max-width: min(520px, calc(100vw - 2rem)) !important;
            margin: 0 !important;
            padding: 0.85rem 1rem 1rem !important;
            border-radius: var(--radius-lg) !important;
            border: 1px solid rgba(20, 184, 166, 0.38) !important;
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.96) 0%, rgba(240, 253, 244, 0.92) 100%) !important;
            backdrop-filter: blur(18px) !important;
            box-shadow: 0 28px 72px rgba(10, 37, 64, 0.22) !important;
            pointer-events: auto !important;
            box-sizing: border-box !important;
        }

        div[class*="st-key-task_composer_panel"].chrona-user-positioned {
            transform: none !important;
        }

        div[class*="st-key-task_composer_panel"] [data-testid="stVerticalBlock"] {
            position: static !important;
            width: 100% !important;
            transform: none !important;
        }

        .task-composer-panel-header {
            margin: 0 0 0.45rem 0;
            cursor: grab;
            user-select: none;
            touch-action: none;
        }

        .task-composer-panel-header:active {
            cursor: grabbing;
        }

        .task-composer-drag-handle {
            display: flex;
            align-items: center;
            gap: 0.55rem;
            padding: 0.2rem 0.15rem;
        }

        .task-composer-drag-hint {
            margin-left: auto;
            color: var(--muted);
            font-size: 0.72rem;
            font-weight: 600;
            letter-spacing: 0.02em;
        }

        .chrona-task-panel-dragging,
        .chrona-task-panel-dragging * {
            user-select: none !important;
            -webkit-user-select: none !important;
        }

        .chrona-task-panel-dragging .task-composer-panel-header {
            cursor: grabbing !important;
        }

        .task-composer-drag-grip {
            display: inline-flex;
            flex-direction: column;
            gap: 3px;
            width: 14px;
            flex-shrink: 0;
        }

        .task-composer-drag-grip::before,
        .task-composer-drag-grip::after {
            content: '';
            display: block;
            height: 2px;
            border-radius: 999px;
            background: linear-gradient(90deg, var(--teal), var(--blue));
        }

        .task-composer-drag-grip::before {
            width: 14px;
        }

        .task-composer-drag-grip::after {
            width: 10px;
            opacity: 0.75;
        }

        .task-composer-panel-title {
            color: var(--ink);
            font-size: 0.98rem;
            font-weight: 780;
            line-height: 1.25;
        }

        div[class*="st-key-task_composer_panel"] [data-testid="stButton"],
        div[class*="st-key-task_composer_panel"] [data-testid="stForm"],
        div[class*="st-key-task_composer_panel"] [data-testid="stTextArea"],
        div[class*="st-key-task_composer_panel"] button,
        div[class*="st-key-task_composer_panel"] textarea,
        div[class*="st-key-task_composer_panel"] input {
            pointer-events: auto !important;
        }

        div[class*="st-key-task_composer_panel"] [data-testid="stButton"] button {
            min-height: 2rem !important;
            padding: 0.2rem 0.55rem !important;
            font-size: 1rem !important;
            line-height: 1 !important;
        }

        .st-key-task_composer {
            margin: 0 !important;
            padding: 0.15rem 0.1rem 0.35rem !important;
            border: 0 !important;
            background: transparent !important;
            box-shadow: none !important;
            backdrop-filter: none !important;
        }

        .st-key-task_composer:hover {
            transform: none !important;
            box-shadow: none !important;
            border-color: transparent !important;
        }

        .stApp iframe[data-chrona-theme-bridge="true"],
        .stApp iframe[data-chrona-floating-panel-bridge="true"],
        .stApp [data-testid="stIFrame"]:has(iframe[data-chrona-theme-bridge="true"]),
        .stApp [data-testid="stIFrame"]:has(iframe[data-chrona-floating-panel-bridge="true"]) {
            position: absolute !important;
            width: 0 !important;
            height: 0 !important;
            min-width: 0 !important;
            min-height: 0 !important;
            opacity: 0 !important;
            visibility: hidden !important;
            border: 0 !important;
            pointer-events: none !important;
            background: transparent !important;
        }

        .stApp [data-testid="stElementContainer"]:has(iframe[data-chrona-theme-bridge="true"]),
        .stApp [data-testid="stElementContainer"]:has(> [data-testid="stIFrame"] iframe[data-chrona-theme-bridge="true"]),
        .stApp [data-testid="stElementContainer"]:has(iframe[data-chrona-floating-panel-bridge="true"]),
        .stApp [data-testid="stElementContainer"]:has(> [data-testid="stIFrame"] iframe[data-chrona-floating-panel-bridge="true"]) {
            height: 0 !important;
            min-height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
            overflow: hidden !important;
            pointer-events: none !important;
            border: 0 !important;
            background: transparent !important;
        }

        body:has(.st-key-auth_gate) {
            overflow: auto !important;
        }

        body:has(.st-key-auth_gate) #root,
        body:has(.st-key-auth_gate) #root > div,
        body:has(.st-key-auth_gate) .stApp,
        body:has(.st-key-auth_gate) [data-testid="stAppViewContainer"] {
            overflow: visible !important;
        }

        .st-key-auth_gate,
        .st-key-auth_gate [data-testid="stVerticalBlock"],
        .st-key-auth_gate [data-testid="stElementContainer"],
        .st-key-auth_gate [data-testid="stTextInput"],
        .st-key-auth_gate [data-testid="stButton"] {
            height: auto !important;
            min-height: unset !important;
            max-height: none !important;
            overflow: visible !important;
            opacity: 1 !important;
            visibility: visible !important;
            pointer-events: auto !important;
        }

        [data-testid="stDecoration"],
        [data-testid="stToolbar"],
        [data-testid="stStatusWidget"] {
            color: var(--ink);
            background: rgba(255, 255, 255, 0.50);
        }

        [data-testid="stHeader"] {
            background: rgba(255, 255, 255, 0.30);
        }

        .block-container {
            padding-top: 2.25rem;
            padding-bottom: 12rem;
            max-width: 1180px;
        }

        h1,
        h2,
        h3,
        [data-testid="stMarkdownContainer"] h1,
        [data-testid="stMarkdownContainer"] h2,
        [data-testid="stMarkdownContainer"] h3 {
            color: var(--ink);
            font-weight: 780;
            letter-spacing: 0;
        }

        h1,
        [data-testid="stMarkdownContainer"] h1 {
            background: linear-gradient(110deg, var(--ink), var(--ink-2), var(--teal));
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
        }

        .stCaption,
        [data-testid="stCaptionContainer"],
        p,
        label,
        .stMarkdown {
            color: var(--muted);
        }

        .stApp,
        section[data-testid="stSidebar"] {
            accent-color: var(--accent);
            --primary-color: var(--accent);
            --st-primary-color: var(--accent);
        }

        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.82) 0%, rgba(240, 253, 244, 0.78) 100%) !important;
            backdrop-filter: blur(16px);
            border-right: 1px solid rgba(20, 184, 166, 0.28);
        }

        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
            color: var(--ink);
        }

        button,
        [data-testid="stBaseButton-primary"],
        [data-testid="stBaseButton-secondary"],
        button[kind="primary"],
        button[kind="secondary"],
        button[kind="primaryFormSubmit"],
        button[kind="formSubmit"] {
            border-radius: 999px !important;
            border: 1px solid rgba(20, 184, 166, 0.28) !important;
            color: var(--ink) !important;
            background: rgba(255, 255, 255, 0.72) !important;
            box-shadow: 0 10px 26px rgba(10, 37, 64, 0.08);
            font-weight: 700 !important;
            transition: transform var(--ease), box-shadow var(--ease), border-color var(--ease), background var(--ease);
        }

        button:hover,
        [data-testid="stBaseButton-secondary"]:hover {
            transform: translateY(-2px);
            border-color: rgba(59, 130, 246, 0.42) !important;
            box-shadow: var(--shadow-hover);
        }

        [data-testid="stBaseButton-primary"],
        button[kind="primary"],
        button[kind="primaryFormSubmit"],
        .st-key-task_composer button[kind="primaryFormSubmit"],
        .task-edit-shell button[kind="primaryFormSubmit"] {
            border: 0 !important;
            color: white !important;
            background: linear-gradient(120deg, var(--teal), var(--blue), var(--violet)) !important;
            background-size: 220% 220% !important;
            animation: gradient-shift 8s ease infinite;
        }

        [data-testid="stTextInput"] input,
        [data-testid="stTextArea"] textarea,
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        [data-testid="stDateInput"] input,
        [data-testid="stTimeInput"] input,
        [data-testid="stNumberInput"] input {
            border-radius: var(--radius-sm) !important;
            border-color: rgba(20, 184, 166, 0.28) !important;
            background: rgba(255, 255, 255, 0.64) !important;
            color: var(--ink) !important;
            transition: border-color var(--ease), box-shadow var(--ease), background var(--ease);
        }

        [data-testid="stTextInput"] input:focus,
        [data-testid="stTextArea"] textarea:focus,
        [data-testid="stDateInput"] input:focus,
        [data-testid="stTimeInput"] input:focus,
        [data-testid="stNumberInput"] input:focus {
            border-color: rgba(59, 130, 246, 0.58) !important;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12) !important;
        }

        [data-testid="stMetric"],
        [data-testid="stAlert"],
        [data-testid="stExpander"],
        div[data-testid="stForm"] {
            border-radius: var(--radius-md) !important;
            border: 1px solid var(--line) !important;
            background: var(--glass) !important;
            backdrop-filter: blur(10px);
            box-shadow: 0 14px 36px rgba(10, 37, 64, 0.08);
        }

        [data-testid="stMetric"] {
            padding: 0.75rem 0.9rem;
        }

        [data-testid="stAlert"] {
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.90) 0%, rgba(240, 253, 244, 0.75) 100%) padding-box !important;
            border: 2px solid transparent !important;
            border-image: linear-gradient(135deg, var(--teal), var(--blue), var(--violet)) 1 !important;
            border-radius: var(--radius-md) !important;
            backdrop-filter: blur(12px) !important;
        }

        [data-testid="stAlert"] > div {
            color: var(--ink) !important;
        }

        [data-testid="stAlert"] [data-testid="stAlertInner"] {
            color: var(--ink) !important;
        }

        section[data-testid="stSidebar"] [data-testid="stAlert"] {
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.92) 0%, rgba(240, 253, 244, 0.80) 100%) padding-box !important;
        }

        div[data-testid="stSuccess"],
        div[data-testid="stWarning"],
        div[data-testid="stError"],
        div[data-testid="stInfo"] {
            border: none !important;
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.92) 0%, rgba(240, 253, 244, 0.80) 100%) padding-box !important;
            border-radius: var(--radius-md) !important;
            backdrop-filter: blur(12px) !important;
        }

        div[data-testid="stSuccess"]::before,
        div[data-testid="stWarning"]::before,
        div[data-testid="stError"]::before,
        div[data-testid="stInfo"]::before {
            content: '';
            position: absolute;
            top: -2px;
            left: -2px;
            right: -2px;
            bottom: -2px;
            background: linear-gradient(135deg, var(--teal), var(--blue), var(--violet));
            border-radius: calc(var(--radius-md) + 2px);
            z-index: -1;
        }

        div[data-testid="stSuccess"],
        div[data-testid="stWarning"],
        div[data-testid="stError"],
        div[data-testid="stInfo"] {
            position: relative;
            z-index: 1;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.75rem;
            border-radius: 999px;
            padding: 0.35rem;
            background: rgba(255, 255, 255, 0.54);
            border: 1px solid rgba(20, 184, 166, 0.18);
            backdrop-filter: blur(10px);
        }

        .stTabs [data-baseweb="tab"] {
            border-radius: 999px;
            color: var(--muted);
            font-weight: 700;
            padding: 0.5rem 1.5rem;
            min-width: 120px;
            transition: color var(--ease), background var(--ease);
        }

        .stTabs [aria-selected="true"] {
            color: white;
            background: linear-gradient(120deg, var(--teal), var(--blue));
        }

        .stTabs [aria-selected="true"]::after,
        .stTabs [data-baseweb="tab-highlight"] {
            background-color: var(--accent) !important;
            border-color: var(--accent) !important;
        }

        [data-testid="stRadio"] label,
        [data-testid="stCheckbox"] label {
            color: var(--muted) !important;
        }

        [data-testid="stRadio"] label:has(input:checked),
        [data-testid="stCheckbox"] label:has(input:checked) {
            color: var(--ink) !important;
        }

        [data-testid="stRadio"] label:has(input:checked) > div:first-child,
        [data-testid="stCheckbox"] label:has(input:checked) > div:first-child,
        [data-testid="stRadio"] [aria-checked="true"] > div:first-child,
        [data-testid="stCheckbox"] [aria-checked="true"] > div:first-child {
            border-color: var(--accent) !important;
            background-color: var(--accent) !important;
            box-shadow: 0 0 0 4px var(--accent-soft) !important;
        }

        [data-testid="stRadio"] label > div:first-child,
        [data-testid="stCheckbox"] label > div:first-child {
            border-color: rgba(79, 100, 120, 0.32) !important;
            background-color: rgba(255, 255, 255, 0.56) !important;
        }

        [data-testid="stRadio"] svg,
        [data-testid="stCheckbox"] svg {
            fill: white !important;
        }

        [data-testid="stSlider"] [role="slider"] {
            background: var(--accent) !important;
            border-color: rgba(255, 255, 255, 0.78) !important;
            box-shadow: 0 0 0 4px var(--accent-soft) !important;
        }

        [data-testid="stSlider"] div[data-testid="stThumbValue"] {
            color: var(--ink) !important;
            background: rgba(255, 255, 255, 0.86) !important;
            border-color: rgba(20, 184, 166, 0.42) !important;
        }

        .task-list-shell {
            max-width: 980px;
            margin: 1.25rem auto 1.5rem auto;
        }

        .task-list-empty,
        .day-list-empty,
        .calendar-empty {
            min-height: 260px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            border: 1px dashed rgba(20, 184, 166, 0.50);
            border-radius: var(--radius-lg);
            background: linear-gradient(var(--glass), var(--glass)) padding-box,
                        linear-gradient(135deg, rgba(20, 184, 166, 0.20), rgba(59, 130, 246, 0.15), rgba(139, 92, 246, 0.12)) border-box;
            backdrop-filter: blur(12px);
            box-shadow: var(--shadow);
            transition: transform var(--ease), box-shadow var(--ease), border-color var(--ease);
        }

        .task-list-empty:hover,
        .day-list-empty:hover,
        .calendar-empty:hover {
            transform: translateY(-3px);
            border-color: rgba(59, 130, 246, 0.60);
            box-shadow: var(--shadow-hover);
        }

        .task-list-empty-title,
        .day-list-empty-title,
        .profile-memory-title {
            font-size: 1.08rem;
            font-weight: 780;
            background: linear-gradient(110deg, var(--ink), var(--ink-2), var(--teal));
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
        }

        .task-list-empty-copy,
        .day-list-empty-copy {
            margin-top: 0.35rem;
            max-width: 430px;
            color: var(--muted);
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
            color: var(--ink-2);
            font-size: 0.88rem;
            font-weight: 700;
            padding: 0 0.1rem;
        }

        .day-task-card,
        div[class*="st-key-day_task_card_"],
        div[class*="st-key-unresolved_task_card_"],
        div[class*="st-key-task_edit_shell"],
        .task-edit-shell,
        .profile-memory-card,
        .schedule-block {
            border: 1px solid rgba(20, 184, 166, 0.35);
            border-radius: var(--radius-md);
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.82) 0%, rgba(240, 253, 244, 0.65) 100%);
            backdrop-filter: blur(12px);
            box-shadow: var(--shadow);
            color: var(--ink);
            box-sizing: border-box;
            transition: transform var(--ease), box-shadow var(--ease), border-color var(--ease), background var(--ease);
        }

        .day-task-card:hover,
        div[class*="st-key-day_task_card_"]:hover,
        div[class*="st-key-unresolved_task_card_"]:hover,
        div[class*="st-key-task_edit_shell"]:hover,
        .task-edit-shell:hover,
        .profile-memory-card:hover,
        .schedule-block:hover {
            transform: translateY(-3px);
            box-shadow: var(--shadow-hover);
            border-color: rgba(59, 130, 246, 0.50);
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.90) 0%, rgba(240, 253, 244, 0.75) 100%);
        }

        .day-task-card {
            min-height: 152px;
            margin-top: 0.78rem;
            padding: 1rem 1.05rem;
            overflow: visible;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }

        div[class*="st-key-day_task_card_"] {
            min-height: 152px;
            margin-top: 0.78rem;
            padding: 0.9rem 0.95rem 1.05rem;
            overflow: visible;
        }

        div[class*="st-key-day_task_card_"] [data-testid="stHorizontalBlock"],
        div[class*="st-key-unresolved_task_card_"] [data-testid="stHorizontalBlock"] {
            align-items: stretch;
        }

        div[class*="st-key-day_task_card_"] button,
        div[class*="st-key-unresolved_task_card_"] button {
            min-height: 2.15rem;
        }

        .day-task-time {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
            color: var(--ink-2);
            font-size: 0.86rem;
            font-weight: 750;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        }

        .day-task-time strong {
            color: var(--teal);
            font-size: 0.75rem;
            font-weight: 760;
            white-space: nowrap;
        }

        .day-task-title,
        .unresolved-task-head,
        .schedule-title,
        .calendar-task-title {
            color: var(--ink);
            font-weight: 780;
            letter-spacing: 0;
        }

        .day-task-title {
            font-size: 1.02rem;
            line-height: 1.28;
            overflow-wrap: anywhere;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        .day-task-meta,
        .unresolved-task-meta,
        .schedule-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 0.42rem;
            color: var(--muted);
            font-size: 0.76rem;
            font-weight: 650;
        }

        .day-task-meta {
            padding-bottom: 0.18rem;
        }

        .day-task-meta span,
        .unresolved-task-meta span,
        .schedule-meta span,
        .unresolved-task-head strong {
            border: 1px solid rgba(20, 184, 166, 0.30);
            border-radius: 999px;
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.70) 0%, rgba(240, 253, 244, 0.55) 100%);
            padding: 0.12rem 0.46rem;
            max-width: 100%;
            overflow-wrap: anywhere;
            color: var(--ink-2);
        }

        .day-task-content {
            min-height: 116px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            overflow: visible;
            gap: 0.58rem;
        }

        .day-task-done-badge {
            border: 1px solid rgba(20, 184, 166, 0.30);
            border-radius: 999px;
            padding: 0.42rem 0.55rem;
            background: rgba(167, 243, 208, 0.62);
            color: #0f766e;
            font-size: 0.82rem;
            font-weight: 780;
            text-align: center;
            white-space: nowrap;
        }

        div[class*="st-key-unresolved_task_card_"] {
            min-height: 112px;
            margin-top: 0.78rem;
            padding: 0.86rem 1rem;
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
            line-height: 1.28;
        }

        .unresolved-task-head span {
            overflow-wrap: anywhere;
        }

        .unresolved-task-head strong {
            font-size: 0.76rem;
            white-space: nowrap;
        }

        .unresolved-task-meta {
            margin-top: 0.8rem;
        }

        div[class*="st-key-task_edit_shell"],
        .task-edit-shell {
            margin: 1.05rem 0 1.1rem 0;
            padding: clamp(1.35rem, 2.4vw, 2rem) !important;
            overflow: visible;
        }

        div[class*="st-key-task_edit_shell"] [data-testid="stForm"],
        .task-edit-shell [data-testid="stForm"],
        .st-key-task_composer [data-testid="stForm"] {
            border: 0 !important;
            padding: 0 !important;
            background: transparent !important;
            box-shadow: none !important;
        }

        div[class*="st-key-task_edit_shell"] [data-testid="stVerticalBlock"] {
            gap: 0.85rem;
        }

        div[class*="st-key-task_edit_shell"] [data-testid="stHorizontalBlock"] {
            gap: 1.15rem;
        }

        div[class*="st-key-task_edit_shell"] [data-testid="stWidgetLabel"] {
            margin-bottom: 0.25rem;
        }

        .calendar-week-title {
            text-align: center;
            font-weight: 750;
            color: var(--ink);
            padding: 0.45rem 0 0.35rem 0;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        }

        .calendar-shell {
            margin-top: 0.55rem;
            overflow-x: auto;
            padding-bottom: 0.35rem;
        }

        .calendar-grid {
            min-width: 920px;
            display: grid;
            grid-template-columns: 82px repeat(7, minmax(112px, 1fr));
            border: 1px solid rgba(20, 184, 166, 0.35);
            border-radius: var(--radius-md);
            overflow: hidden;
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.85) 0%, rgba(240, 253, 244, 0.70) 100%);
            backdrop-filter: blur(12px);
            box-shadow: var(--shadow);
        }

        .calendar-time-column,
        .calendar-day-column {
            border-right: 1px solid rgba(20, 184, 166, 0.22);
            background: rgba(255, 255, 255, 0.50);
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
            border-bottom: 1px solid rgba(20, 184, 166, 0.25);
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.75) 0%, rgba(240, 253, 244, 0.60) 100%);
            color: var(--ink-2);
            font-size: 0.86rem;
            font-weight: 750;
            box-sizing: border-box;
        }

        .calendar-day-head {
            flex-direction: column;
            gap: 0.08rem;
        }

        .calendar-day-head span {
            color: var(--ink);
        }

        .calendar-day-head strong {
            color: var(--muted);
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
                    rgba(20, 184, 166, 0.18) 0,
                    rgba(20, 184, 166, 0.18) 1px,
                    transparent 1px,
                    transparent 46px
                ),
                linear-gradient(135deg, rgba(255, 255, 255, 0.55) 0%, rgba(240, 253, 244, 0.40) 100%);
        }

        .calendar-time-label {
            position: absolute;
            right: 0.7rem;
            color: var(--muted);
            font-size: 0.8rem;
            font-weight: 650;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            white-space: nowrap;
        }

        .calendar-task-block {
            position: absolute;
            left: 0.44rem;
            right: 0.44rem;
            border-left: 4px solid rgba(20, 184, 166, 0.72);
            border-radius: var(--radius-sm);
            padding: 0.25rem 0.38rem;
            box-shadow: 0 10px 26px rgba(10, 37, 64, 0.10);
            overflow: hidden;
            color: var(--ink);
            backdrop-filter: blur(8px);
            transition: transform var(--ease), box-shadow var(--ease);
        }

        .calendar-task-block:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-hover);
        }

        .profile-memory-card {
            padding: 0.78rem 0.82rem;
            margin: 0.4rem 0 0.8rem 0;
        }

        .auth-user-card {
            margin: 0.72rem 0 0.82rem 0;
            padding: 0.78rem 0.84rem;
            border: 1px solid rgba(20, 184, 166, 0.28);
            border-radius: var(--radius-md);
            background: rgba(255, 255, 255, 0.58);
            box-shadow: 0 10px 26px rgba(10, 37, 64, 0.07);
        }

        .auth-user-name {
            color: var(--ink);
            font-size: 0.95rem;
            font-weight: 780;
            line-height: 1.25;
        }

        .auth-user-meta {
            margin-top: 0.18rem;
            color: var(--muted);
            font-size: 0.78rem;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        }

        .profile-memory-card p {
            margin: 0.28rem 0;
            color: var(--muted);
            font-size: 0.84rem;
            line-height: 1.42;
        }

        .calendar-task-time {
            font-size: 0.64rem;
            color: var(--ink-2);
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            white-space: nowrap;
        }

        .calendar-task-title {
            margin-top: 0.08rem;
            font-size: 0.76rem;
            line-height: 1.22;
            overflow-wrap: anywhere;
        }

        .calendar-task-meta {
            margin-top: 0.12rem;
            font-size: 0.63rem;
            color: var(--muted);
            line-height: 1.2;
            overflow-wrap: anywhere;
        }

        .schedule-block {
            border-left-width: 6px;
            padding: 1rem 1.05rem;
            margin: 0 0 0.9rem 0;
        }

        .schedule-head {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            align-items: flex-start;
        }

        .schedule-time {
            color: var(--muted);
            font-size: 0.82rem;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        }

        .schedule-title {
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
            box-shadow: 0 10px 26px rgba(59, 130, 246, 0.22);
        }

        .schedule-meta {
            margin: 0.75rem 0;
        }

        .dimension-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.8rem;
            margin: 0.55rem 0 0.7rem 0;
        }

        .dimension-label {
            font-size: 0.78rem;
            color: var(--muted);
            margin-bottom: 0.24rem;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        }

        .bar {
            height: 8px;
            border-radius: 999px;
            overflow: hidden;
            background: rgba(20, 184, 166, 0.14);
        }

        .bar span {
            display: block;
            height: 100%;
            border-radius: 999px;
        }

        .reason {
            color: var(--muted);
            font-size: 0.82rem;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        }

        .st-key-auth_gate {
            margin: clamp(2rem, 8vh, 4rem) auto 2rem auto;
            padding: clamp(1.25rem, 3vw, 2rem);
            border: 1px solid rgba(20, 184, 166, 0.35);
            border-radius: var(--radius-lg);
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.88) 0%, rgba(240, 253, 244, 0.76) 100%);
            box-shadow: 0 24px 64px rgba(10, 37, 64, 0.14);
            backdrop-filter: blur(14px);
        }

        .auth-gate-kicker {
            color: var(--teal);
            font-size: 0.78rem;
            font-weight: 760;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 0.28rem;
        }

        .auth-gate-title {
            color: var(--ink);
            font-size: clamp(2rem, 4vw, 3rem);
            font-weight: 820;
            line-height: 1.08;
            margin-bottom: 0.42rem;
        }

        .auth-gate-copy {
            color: var(--muted);
            font-size: 0.92rem;
            line-height: 1.48;
            margin-bottom: 1.2rem;
        }

        .st-key-auth_gate div[data-testid="stForm"] {
            padding: 0 !important;
            border: 0 !important;
            background: transparent !important;
            box-shadow: none !important;
        }

        .st-key-auth_gate [data-testid="stTextInput"] {
            margin-bottom: 0.55rem;
        }

        .st-key-auth_gate [data-testid="stButton"] button {
            color: white !important;
        }

        .st-key-task_composer .composer-greeting {
            color: var(--ink);
            font-size: 1rem;
            font-weight: 780;
            line-height: 1.25;
            margin: 0 0 0.42rem 0.05rem;
        }

        .st-key-task_composer textarea {
            min-height: 88px !important;
            border-radius: var(--radius-sm);
            border-color: rgba(20, 184, 166, 0.28);
            background: rgba(255, 255, 255, 0.58);
            color: var(--ink);
            font-size: 0.9rem;
            line-height: 1.45;
        }

        .st-key-task_composer textarea::placeholder {
            color: var(--muted);
            font-size: 0.84rem;
            font-weight: 500;
            line-height: 1.45;
        }

        @media (max-width: 760px) {
            .calendar-grid {
                min-width: 820px;
                grid-template-columns: 74px repeat(7, minmax(104px, 1fr));
            }
            div[class*="st-key-task_edit_shell"],
            .task-edit-shell {
                padding: 1rem !important;
            }
            .day-task-card {
                min-height: 164px;
                padding: 0.88rem;
            }
            div[class*="st-key-day_task_card_"] {
                min-height: 172px;
                padding: 0.78rem 0.78rem 0.95rem;
            }
            .day-task-content {
                min-height: 136px;
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

        .styled-alert {
            padding: 0.85rem 1rem;
            border-radius: var(--radius-md);
            margin: 0.5rem 0;
            font-size: 0.9rem;
            line-height: 1.5;
            position: relative;
            backdrop-filter: blur(12px);
        }

        .styled-alert::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            border-radius: var(--radius-md);
            background: linear-gradient(135deg, var(--teal), var(--blue), var(--violet));
            z-index: -1;
            padding: 2px;
        }

        .styled-alert::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            border-radius: var(--radius-md);
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.95) 0%, rgba(240, 253, 244, 0.85) 100%);
            z-index: -1;
        }

        .styled-alert > *:last-child {
            margin-bottom: 0;
        }

        .styled-alert-warning,
        .styled-alert-error {
            color: var(--ink);
        }

        .styled-alert-success {
            color: var(--ink);
        }

        .styled-alert-info {
            color: var(--ink);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    if st.session_state.get("theme_mode") == "night":
        st.markdown(night_theme_css(), unsafe_allow_html=True)


def ensure_floating_panel_scripts() -> None:
    if st.session_state.get("_chrona_floating_panel_bridge"):
        return
    st.session_state._chrona_floating_panel_bridge = True
    inject_floating_panel_scripts()


def inject_floating_panel_scripts() -> None:
    components.html(
        """
        <script>
        (() => {
            const storageKey = "chrona-task-composer-pos";
            const win = window.parent;
            const doc = win.document;

            function clamp(value, min, max) {
                return Math.min(Math.max(value, min), max);
            }

            function collapseComponentHost() {
                const frame = window.frameElement;
                if (!frame) {
                    return;
                }
                frame.setAttribute("data-chrona-floating-panel-bridge", "true");
                frame.setAttribute("aria-hidden", "true");
                frame.style.cssText =
                    "position:absolute!important;width:0!important;height:0!important;" +
                    "opacity:0!important;visibility:hidden!important;border:0!important;" +
                    "pointer-events:none!important;";
                const iframeHost = frame.closest('[data-testid="stIFrame"]');
                if (!iframeHost) {
                    return;
                }
                iframeHost.style.setProperty("height", "0", "important");
                iframeHost.style.setProperty("min-height", "0", "important");
                iframeHost.style.setProperty("margin", "0", "important");
                iframeHost.style.setProperty("padding", "0", "important");
                iframeHost.style.setProperty("overflow", "hidden", "important");
                iframeHost.style.setProperty("pointer-events", "none", "important");
            }

            function readSavedPosition() {
                try {
                    const saved = JSON.parse(win.sessionStorage.getItem(storageKey) || "null");
                    if (!saved || !Number.isFinite(saved.left) || !Number.isFinite(saved.top)) {
                        return null;
                    }
                    return saved;
                } catch (error) {
                    return null;
                }
            }

            function writeSavedPosition(left, top) {
                try {
                    win.sessionStorage.setItem(storageKey, JSON.stringify({ left, top }));
                } catch (error) {}
            }

            function isVisiblePosition(shell, left, top) {
                const width = shell.offsetWidth || 420;
                const height = shell.offsetHeight || 280;
                return (
                    left + width > 48 &&
                    top + height > 48 &&
                    left < win.innerWidth - 48 &&
                    top < win.innerHeight - 48
                );
            }

            function resolvePanelShell(handle) {
                return handle.closest('div[class*="st-key-task_composer_panel"]');
            }

            function applyPosition(shell, left, top) {
                shell.classList.add("chrona-user-positioned");
                shell.style.setProperty("left", `${left}px`, "important");
                shell.style.setProperty("top", `${top}px`, "important");
                shell.style.setProperty("right", "auto", "important");
                shell.style.setProperty("bottom", "auto", "important");
            }

            function restoreSavedIfVisible(shell) {
                const saved = readSavedPosition();
                if (!saved) {
                    return;
                }
                if (!isVisiblePosition(shell, saved.left, saved.top)) {
                    win.sessionStorage.removeItem(storageKey);
                    return;
                }
                applyPosition(shell, saved.left, saved.top);
            }

            function bindTaskComposerPanel() {
                const handle = doc.querySelector('[data-chrona-drag-handle="true"]');
                if (!handle) {
                    return;
                }

                const shell = resolvePanelShell(handle);
                if (!shell || shell.dataset.chronaDragReady === "true") {
                    return;
                }

                shell.dataset.chronaDragReady = "true";
                restoreSavedIfVisible(shell);

                const startDrag = (clientX, clientY) => {
                    const rect = shell.getBoundingClientRect();
                    const offsetX = clientX - rect.left;
                    const offsetY = clientY - rect.top;
                    shell.classList.add("chrona-task-panel-dragging");

                    const onMove = (moveX, moveY) => {
                        const margin = 12;
                        const width = shell.offsetWidth;
                        const height = shell.offsetHeight;
                        const maxLeft = win.innerWidth - width - margin;
                        const maxTop = win.innerHeight - height - margin;
                        applyPosition(
                            shell,
                            clamp(moveX - offsetX, margin, Math.max(margin, maxLeft)),
                            clamp(moveY - offsetY, margin, Math.max(margin, maxTop)),
                        );
                    };

                    const stopDrag = () => {
                        shell.classList.remove("chrona-task-panel-dragging");
                        doc.removeEventListener("mousemove", onMouseMove);
                        doc.removeEventListener("mouseup", onMouseUp);
                        const left = parseFloat(shell.style.left);
                        const top = parseFloat(shell.style.top);
                        if (Number.isFinite(left) && Number.isFinite(top)) {
                            writeSavedPosition(left, top);
                        }
                    };

                    const onMouseMove = (event) => onMove(event.clientX, event.clientY);
                    const onMouseUp = () => stopDrag();

                    doc.addEventListener("mousemove", onMouseMove);
                    doc.addEventListener("mouseup", onMouseUp);
                };

                handle.addEventListener("mousedown", (event) => {
                    if (event.button !== 0) {
                        return;
                    }
                    if (event.target.closest("button, a, input, textarea, select, label")) {
                        return;
                    }
                    startDrag(event.clientX, event.clientY);
                });
            }

            function syncPanels() {
                collapseComponentHost();
                bindTaskComposerPanel();
            }

            collapseComponentHost();
            syncPanels();
            try {
                new MutationObserver(syncPanels).observe(doc.body, {
                    childList: true,
                    subtree: true,
                });
            } catch (error) {}
        })();
        </script>
        """,
        height=0,
    )


def sync_streamlit_native_theme() -> None:
    css = night_theme_css().replace("<style>", "", 1).rsplit("</style>", 1)[0]
    components.html(
        f"""
        <script>
        (() => {{
            const nightCss = {json.dumps(css)};
            const styleId = "chrona-native-dark-style";

            function collapseComponentHost() {{
                const frame = window.frameElement;
                if (!frame) {{
                    return;
                }}
                frame.dataset.chronaThemeBridge = "true";
                frame.setAttribute("data-chrona-theme-bridge", "true");
                frame.setAttribute("aria-hidden", "true");
                frame.style.setProperty("position", "absolute", "important");
                frame.style.setProperty("width", "0", "important");
                frame.style.setProperty("height", "0", "important");
                frame.style.setProperty("min-width", "0", "important");
                frame.style.setProperty("min-height", "0", "important");
                frame.style.setProperty("opacity", "0", "important");
                frame.style.setProperty("visibility", "hidden", "important");
                frame.style.setProperty("border", "0", "important");
                frame.style.setProperty("pointer-events", "none", "important");
                let node = frame.parentElement;
                for (let depth = 0; depth < 2 && node; depth += 1) {{
                    if (node.querySelector && node.querySelector(".st-key-auth_gate")) {{
                        break;
                    }}
                    const marker = `${{node.getAttribute("data-testid") || ""}} ${{node.className || ""}}`;
                    const isStreamlitShell =
                        marker.includes("stIFrame") ||
                        marker.includes("stElementContainer");
                    if (!isStreamlitShell) {{
                        break;
                    }}
                    node.style.setProperty("height", "0", "important");
                    node.style.setProperty("min-height", "0", "important");
                    node.style.setProperty("margin", "0", "important");
                    node.style.setProperty("padding", "0", "important");
                    node.style.setProperty("overflow", "hidden", "important");
                    node.style.setProperty("pointer-events", "none", "important");
                    node.style.setProperty("border", "0", "important");
                    node.style.setProperty("background", "transparent", "important");
                    node = node.parentElement;
                }}
            }}

            function hasOpenDialog(doc) {{
                return Boolean(doc.querySelector("[role='dialog'], [data-testid='stDialog'], [data-baseweb='modal']"));
            }}

            function lockOuterScroll() {{
                const doc = window.parent.document;
                const viewportHeight = "100dvh";
                [doc.documentElement, doc.body].forEach((node) => {{
                    if (!node) return;
                    node.style.setProperty("height", "100%", "important");
                    node.style.setProperty("min-height", "100%", "important");
                    node.style.setProperty("overflow", "hidden", "important");
                    node.style.setProperty("overscroll-behavior", "none", "important");
                }});
                if (hasOpenDialog(doc)) {{
                    doc.querySelectorAll("#root, #root > div, .stApp, [data-testid='stAppViewContainer'], [data-testid='stAppViewContainer'] > .main, section[data-testid='stMain'], div[data-testid='stMain']").forEach((node) => {{
                        node.style.setProperty("height", "auto", "important");
                        node.style.setProperty("max-height", "none", "important");
                        node.style.setProperty("min-height", viewportHeight, "important");
                        node.style.setProperty("overflow", "visible", "important");
                    }});
                    doc.querySelectorAll("[role='dialog'], [data-testid='stDialog'], [data-baseweb='modal']").forEach((node) => {{
                        node.style.setProperty("height", "auto", "important");
                        node.style.setProperty("max-height", "calc(100dvh - 2rem)", "important");
                        node.style.setProperty("overflow", "visible", "important");
                    }});
                    return;
                }}
                doc.querySelectorAll("#root, #root > div, .stApp, [data-testid='stAppViewContainer']").forEach((node) => {{
                    node.style.setProperty("height", viewportHeight, "important");
                    node.style.setProperty("max-height", viewportHeight, "important");
                    node.style.setProperty("min-height", "0", "important");
                    node.style.setProperty("overflow", "hidden", "important");
                }});
                doc.querySelectorAll("[data-testid='stAppViewContainer'] > .main, section[data-testid='stMain'], div[data-testid='stMain']").forEach((node) => {{
                    node.style.setProperty("height", viewportHeight, "important");
                    node.style.setProperty("max-height", viewportHeight, "important");
                    node.style.setProperty("min-height", "0", "important");
                    node.style.setProperty("overflow-x", "hidden", "important");
                    node.style.setProperty("overflow-y", "auto", "important");
                    node.style.setProperty("overscroll-behavior", "contain", "important");
                }});
            }}

            function normalize(value) {{
                return String(value || "").toLowerCase().replace(/\\s+/g, "");
            }}

            function streamlitThemeValue() {{
                try {{
                    const storage = window.parent.localStorage;
                    for (let index = 0; index < storage.length; index += 1) {{
                        const key = storage.key(index) || "";
                        const value = storage.getItem(key) || "";
                        const keyText = normalize(key);
                        const valueText = normalize(value);
                        const isThemeRecord =
                            keyText.includes("theme") ||
                            keyText.includes("streamlit") ||
                            valueText.includes("theme") ||
                            valueText.includes("base");
                        if (!isThemeRecord) {{
                            continue;
                        }}
                        if (
                            valueText === "dark" ||
                            valueText.includes('"base":"dark"') ||
                            valueText.includes('"theme":"dark"') ||
                            valueText.includes('"currenttheme":"dark"') ||
                            valueText.includes('"activetheme":"dark"') ||
                            valueText.includes("dark")
                        ) return "dark";
                        if (
                            valueText === "light" ||
                            valueText.includes('"base":"light"') ||
                            valueText.includes('"theme":"light"') ||
                            valueText.includes('"currenttheme":"light"') ||
                            valueText.includes('"activetheme":"light"') ||
                            valueText.includes("light")
                        ) return "light";
                    }}
                }} catch (error) {{
                    return null;
                }}
                return null;
            }}

            function syncSliderAccents(doc, shouldUseDark) {{
                const accent = shouldUseDark ? "#2DD4BF" : "#14B8A6";
                const soft = shouldUseDark ? "rgba(45, 212, 191, 0.20)" : "rgba(20, 184, 166, 0.18)";
                const primaryPattern = /(255,\\s*75,\\s*75|255,\\s*43,\\s*43|246,\\s*51,\\s*102)/;
                doc.documentElement.style.setProperty("--st-primary-color", accent);
                doc.documentElement.style.setProperty("--primary-color", accent);
                doc.querySelectorAll('[data-testid="stSlider"], .stSlider').forEach((slider) => {{
                    slider.style.setProperty("--st-primary-color", accent, "important");
                    slider.style.setProperty("--primary-color", accent, "important");
                    slider.querySelectorAll('[role="slider"]').forEach((thumb) => {{
                        thumb.style.setProperty("background", accent, "important");
                        thumb.style.setProperty("border-color", "rgba(255, 255, 255, 0.72)", "important");
                        thumb.style.setProperty("box-shadow", `0 0 0 4px ${{soft}}`, "important");
                    }});
                    slider.querySelectorAll("div").forEach((el) => {{
                        const rect = el.getBoundingClientRect();
                        if (rect.height <= 0 || rect.height > 10 || rect.width < 8) {{
                            return;
                        }}
                        const style = window.parent.getComputedStyle(el);
                        const bg = style.backgroundColor || "";
                        if (!primaryPattern.test(bg)) {{
                            return;
                        }}
                        el.style.setProperty("background", accent, "important");
                        el.style.setProperty("background-color", accent, "important");
                        el.style.setProperty("border-color", accent, "important");
                    }});
                }});
            }}

            function sync() {{
                const doc = window.parent.document;
                const value = streamlitThemeValue();
                const shouldUseDark = value === "dark";
                lockOuterScroll();
                let style = doc.getElementById(styleId);
                if (shouldUseDark && !style) {{
                    style = doc.createElement("style");
                    style.id = styleId;
                    style.textContent = nightCss;
                }}
                if (shouldUseDark && style) {{
                    if (style.textContent !== nightCss) {{
                        style.textContent = nightCss;
                    }}
                    const container = doc.body || doc.head;
                    if (style.parentElement !== container || style.nextElementSibling) {{
                        container.appendChild(style);
                    }}
                }}
                if (!shouldUseDark && style) {{
                    style.remove();
                }}
                doc.documentElement.classList.toggle("chrona-native-dark-active", shouldUseDark);
                syncSliderAccents(doc, shouldUseDark);
            }}

            collapseComponentHost();
            sync();
            window.setInterval(() => {{
                collapseComponentHost();
                sync();
            }}, 400);
            try {{
                new MutationObserver(sync).observe(window.parent.document.documentElement, {{
                    attributes: true,
                    childList: true,
                    subtree: true
                }});
            }} catch (error) {{}}
        }})();
        </script>
        """,
        height=0,
    )


def night_theme_css() -> str:
    return """
        <style>
        :root {
            color-scheme: dark;
            --ink: #EAF6FF;
            --ink-2: #BFEAFF;
            --muted: #94A9BE;
            --teal: #2DD4BF;
            --blue: #60A5FA;
            --violet: #A78BFA;
            --accent: #2DD4BF;
            --accent-strong: #5EEAD4;
            --accent-soft: rgba(45, 212, 191, 0.20);
            --accent-track: rgba(45, 212, 191, 0.24);
            --glass: rgba(10, 23, 42, 0.68);
            --glass-strong: rgba(15, 28, 48, 0.84);
            --line: rgba(45, 212, 191, 0.30);
            --shadow: 0 20px 54px rgba(0, 0, 0, 0.34);
            --shadow-hover: 0 24px 64px rgba(96, 165, 250, 0.22);
        }

        html,
        body {
            background: linear-gradient(135deg, #07111f 0%, #0a1b2e 32%, #101534 64%, #071f22 100%) !important;
        }

        .stApp {
            color: var(--ink);
            background:
                linear-gradient(135deg,
                    rgba(10, 23, 42, 0.96) 0%,
                    rgba(12, 32, 52, 0.94) 28%,
                    rgba(26, 21, 58, 0.92) 58%,
                    rgba(7, 45, 49, 0.88) 100%) !important;
            background-size: 400% 400% !important;
        }

        .stApp::before {
            background:
                radial-gradient(circle at 16% 18%, rgba(45, 212, 191, 0.18), transparent 38%),
                radial-gradient(circle at 86% 14%, rgba(96, 165, 250, 0.22), transparent 36%),
                radial-gradient(circle at 52% 78%, rgba(167, 139, 250, 0.18), transparent 34%),
                linear-gradient(180deg, rgba(2, 6, 23, 0.22), rgba(2, 6, 23, 0.52));
        }

        [data-testid="stAppViewContainer"],
        [data-testid="stAppViewContainer"] > .main,
        [data-testid="stMarkdownContainer"],
        [data-testid="stMarkdownContainer"] p,
        p,
        label,
        .stMarkdown,
        .stCaption,
        [data-testid="stCaptionContainer"] {
            color: var(--muted) !important;
        }

        h1,
        h2,
        h3,
        [data-testid="stMarkdownContainer"] h1,
        [data-testid="stMarkdownContainer"] h2,
        [data-testid="stMarkdownContainer"] h3 {
            color: var(--ink) !important;
        }

        h1,
        [data-testid="stMarkdownContainer"] h1 {
            background: linear-gradient(110deg, #F8FBFF, #A7F3D0, #93C5FD) !important;
            -webkit-background-clip: text !important;
            background-clip: text !important;
            color: transparent !important;
        }

        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"] {
            background: rgba(6, 16, 30, 0.58) !important;
            color: var(--ink) !important;
        }

        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, rgba(6, 18, 32, 0.92) 0%, rgba(8, 30, 38, 0.88) 100%) !important;
            border-right: 1px solid rgba(45, 212, 191, 0.34) !important;
            box-shadow: 18px 0 56px rgba(0, 0, 0, 0.18);
        }

        section[data-testid="stSidebar"] * {
            color: var(--muted);
        }

        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
            color: var(--ink) !important;
        }

        button,
        [data-testid="stBaseButton-primary"],
        [data-testid="stBaseButton-secondary"],
        button[kind="primary"],
        button[kind="secondary"],
        button[kind="primaryFormSubmit"],
        button[kind="formSubmit"] {
            color: var(--ink) !important;
            background: rgba(15, 32, 52, 0.82) !important;
            border-color: rgba(45, 212, 191, 0.34) !important;
            box-shadow: 0 12px 28px rgba(0, 0, 0, 0.30);
        }

        [data-testid="stBaseButton-primary"],
        button[kind="primary"],
        button[kind="primaryFormSubmit"],
        .st-key-task_composer button[kind="primaryFormSubmit"],
        .task-edit-shell button[kind="primaryFormSubmit"] {
            background: linear-gradient(120deg, #0D9488, #2563EB, #7C3AED) !important;
            color: white !important;
        }

        [data-testid="stTextInput"] input,
        [data-testid="stTextArea"] textarea,
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        [data-testid="stDateInput"] input,
        [data-testid="stTimeInput"] input,
        [data-testid="stNumberInput"] input {
            background: rgba(8, 19, 35, 0.76) !important;
            border-color: rgba(45, 212, 191, 0.30) !important;
            color: var(--ink) !important;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
        }

        section[data-testid="stSidebar"] [data-testid="stTextInput"] div[data-baseweb="input"],
        section[data-testid="stSidebar"] [data-testid="stTextInput"] div[data-baseweb="base-input"],
        section[data-testid="stSidebar"] [data-testid="stTextInput"] > div > div,
        section[data-testid="stSidebar"] [data-testid="stSelectbox"] div[data-baseweb="select"],
        section[data-testid="stSidebar"] [data-testid="stSelectbox"] div[data-baseweb="select"] > div {
            background: rgba(8, 19, 35, 0.78) !important;
            border: 1px solid rgba(45, 212, 191, 0.30) !important;
            border-radius: var(--radius-sm) !important;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04) !important;
            outline: none !important;
        }

        section[data-testid="stSidebar"] [data-testid="stTextInput"] input {
            background: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
            outline: none !important;
        }

        section[data-testid="stSidebar"] [data-testid="stTextInput"] button {
            background: rgba(15, 32, 52, 0.86) !important;
            border-color: rgba(45, 212, 191, 0.34) !important;
        }

        section[data-testid="stSidebar"] [data-testid="stTextInput"] div[data-baseweb="input"]:focus-within,
        section[data-testid="stSidebar"] [data-testid="stTextInput"] div[data-baseweb="base-input"]:focus-within,
        section[data-testid="stSidebar"] [data-testid="stSelectbox"] div[data-baseweb="select"]:focus-within {
            border-color: rgba(94, 234, 212, 0.58) !important;
            box-shadow: 0 0 0 3px rgba(45, 212, 191, 0.12) !important;
        }

        [data-testid="stTextArea"] textarea::placeholder,
        [data-testid="stTextInput"] input::placeholder {
            color: #7890A8 !important;
        }

        [data-testid="stMetric"],
        [data-testid="stAlert"],
        [data-testid="stExpander"],
        div[data-testid="stForm"],
        .profile-memory-card,
        div[class*="st-key-task_edit_shell"],
        .task-edit-shell,
        .schedule-block,
        .timeline-shell,
        .calendar-shell,
        .day-list-empty,
        .task-list-empty,
        div[class*="st-key-day_task_card_"],
        div[class*="st-key-unresolved_task_card_"] {
            background: linear-gradient(135deg, rgba(15, 32, 52, 0.78) 0%, rgba(9, 33, 43, 0.58) 100%) !important;
            border-color: rgba(45, 212, 191, 0.32) !important;
            box-shadow: var(--shadow) !important;
            color: var(--ink) !important;
        }

        .day-task-card:hover,
        div[class*="st-key-day_task_card_"]:hover,
        div[class*="st-key-unresolved_task_card_"]:hover,
        div[class*="st-key-task_edit_shell"]:hover,
        .task-edit-shell:hover,
        .profile-memory-card:hover,
        .schedule-block:hover {
            background: linear-gradient(135deg, rgba(19, 45, 72, 0.86) 0%, rgba(10, 51, 58, 0.70) 100%) !important;
            box-shadow: var(--shadow-hover) !important;
        }

        .day-task-time,
        .day-task-title,
        .unresolved-task-head,
        .schedule-title,
        .profile-memory-title,
        .calendar-week-title,
        .day-list-summary {
            color: var(--ink) !important;
        }

        .day-task-meta,
        .unresolved-task-meta,
        .schedule-meta,
        .reason,
        .timeline-block-reason,
        .day-list-empty-copy,
        .task-list-empty-copy {
            color: var(--muted) !important;
        }

        .day-task-meta span,
        .unresolved-task-meta span,
        .schedule-meta span,
        .unresolved-task-head strong,
        .priority-badge,
        .day-task-done-badge {
            background: rgba(8, 25, 42, 0.76) !important;
            border-color: rgba(45, 212, 191, 0.34) !important;
            color: var(--ink-2) !important;
        }

        .auth-user-card {
            background: rgba(8, 25, 42, 0.78) !important;
            border-color: rgba(45, 212, 191, 0.32) !important;
            box-shadow: 0 12px 28px rgba(0, 0, 0, 0.26) !important;
        }

        .st-key-auth_gate {
            background: linear-gradient(135deg, rgba(15, 32, 52, 0.88) 0%, rgba(9, 33, 43, 0.72) 100%) !important;
            border-color: rgba(45, 212, 191, 0.34) !important;
            box-shadow: 0 24px 68px rgba(0, 0, 0, 0.34) !important;
        }

        div[class*="st-key-task_composer_panel"] {
            background: linear-gradient(135deg, rgba(15, 32, 52, 0.96) 0%, rgba(9, 33, 43, 0.92) 100%) !important;
            border-color: rgba(45, 212, 191, 0.38) !important;
            box-shadow: 0 28px 72px rgba(0, 0, 0, 0.48) !important;
        }

        .task-composer-drag-hint {
            color: var(--muted) !important;
        }

        .st-key-task_fab button {
            box-shadow: 0 14px 34px rgba(0, 0, 0, 0.42);
        }

        .auth-gate-title {
            color: var(--ink) !important;
        }

        .auth-gate-copy {
            color: var(--muted) !important;
        }

        .auth-user-name {
            color: var(--ink) !important;
        }

        .auth-user-meta {
            color: var(--muted) !important;
        }

        .stTabs [data-baseweb="tab-list"] {
            background: rgba(8, 22, 39, 0.62) !important;
            border-color: rgba(45, 212, 191, 0.22) !important;
        }

        .stTabs [data-baseweb="tab"] {
            color: var(--muted) !important;
            background: transparent !important;
        }

        .stTabs [aria-selected="true"] {
            color: var(--ink) !important;
            background: rgba(15, 32, 52, 0.86) !important;
        }

        [data-testid="stSlider"] [role="slider"] {
            background: var(--teal) !important;
            border-color: rgba(255, 255, 255, 0.20) !important;
        }

        [data-testid="stSlider"] div[data-testid="stThumbValue"] {
            color: var(--ink) !important;
        }

        .styled-alert {
            background: rgba(13, 31, 50, 0.88) !important;
            color: var(--ink) !important;
        }

        .styled-alert::after {
            background: linear-gradient(135deg, rgba(13, 31, 50, 0.96) 0%, rgba(10, 48, 52, 0.90) 100%) !important;
        }
        </style>
    """


def styled_alert(message: str, alert_type: str = "info") -> None:
    st.markdown(
        f"""
        <div class="styled-alert styled-alert-{alert_type}">
            {message}
        </div>
        """,
        unsafe_allow_html=True,
    )


def styled_warning(message: str) -> None:
    styled_alert(message, "warning")


def styled_error(message: str) -> None:
    styled_alert(message, "error")


def styled_success(message: str) -> None:
    styled_alert(message, "success")


def styled_info(message: str) -> None:
    styled_alert(message, "info")
