from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import shutil
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple

import streamlit as st


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
AUTH_STORE_PATH = DATA_DIR / "auth_users.json"
USER_DATA_ROOT = DATA_DIR / "users"
LEGACY_ARCHIVE_PATH = DATA_DIR / "session_archive.json"
LEGACY_MEMORY_PATH = DATA_DIR / "user_profile_memory.json"
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")
PASSWORD_ITERATIONS = 200_000


def require_authentication() -> bool:
    user = st.session_state.get("auth_user")
    if isinstance(user, dict) and is_active_user(str(user.get("username", ""))):
        return True
    st.session_state.pop("auth_user", None)
    render_login_gate()
    return False


def render_login_gate() -> None:
    _, center, _ = st.columns([0.24, 0.52, 0.24])
    with center:
        with st.container(key="auth_gate", border=False):
            st.markdown(
                """
                <div class="auth-gate-kicker">\u672c\u5730\u8d26\u53f7</div>
                <div class="auth-gate-title">\u767b\u5f55 Chrona</div>
                <div class="auth-gate-copy">\u8bf7\u8f93\u5165\u8d26\u53f7\u540e\u7ee7\u7eed\u4f7f\u7528\u4f60\u7684\u672c\u5730\u65e5\u7a0b\u4e0e\u7528\u6237\u753b\u50cf\u3002</div>
                """,
                unsafe_allow_html=True,
            )
            store = load_user_store()
            if not store["users"]:
                render_bootstrap_admin()
                return
            render_login_form(store)


def render_bootstrap_admin() -> None:
    st.caption("\u9996\u6b21\u542f\u52a8\u9700\u8981\u521b\u5efa\u4e00\u4e2a\u672c\u5730\u7ba1\u7406\u5458\u8d26\u53f7\u3002\u8d26\u53f7\u6570\u636e\u53ea\u4fdd\u5b58\u5728\u8fd9\u53f0\u673a\u5668\u3002")
    username = st.text_input("\u7ba1\u7406\u5458\u7528\u6237\u540d", value="admin", key="bootstrap_username")
    display_name = st.text_input("\u663e\u793a\u540d\u79f0", value="\u7ba1\u7406\u5458", key="bootstrap_display_name")
    password = st.text_input("\u5bc6\u7801", type="password", key="bootstrap_password")
    confirm = st.text_input("\u786e\u8ba4\u5bc6\u7801", type="password", key="bootstrap_confirm")
    submitted = st.button("\u521b\u5efa\u5e76\u767b\u5f55", type="primary", use_container_width=True, key="bootstrap_submit")
    if not submitted:
        return
    ok, message = validate_new_user(username, password, confirm)
    if not ok:
        st.error(message)
        return
    ok, message = create_user(
        username=username,
        password=password,
        display_name=display_name,
        role="admin",
        seed_from_legacy=True,
    )
    if not ok:
        st.error(message)
        return
    sign_in(normalize_username(username))
    st.rerun()


def render_login_form(store: Dict[str, Any]) -> None:
    username = st.text_input("\u7528\u6237\u540d", key="login_username")
    password = st.text_input("\u5bc6\u7801", type="password", key="login_password")
    submitted = st.button("\u767b\u5f55", type="primary", use_container_width=True, key="login_submit")
    if not submitted:
        return
    ok, message = authenticate(username, password, store)
    if not ok:
        st.error(message)
        return
    sign_in(normalize_username(username))
    st.rerun()


def render_user_menu() -> None:
    user = current_user()
    if not user:
        return

    role_text = "管理员" if user.get("role") == "admin" else "用户"
    st.markdown(
        f"""
        <div class="auth-user-card">
          <div class="auth-user-name">{user.get("display_name") or user["username"]}</div>
          <div class="auth-user-meta">@{user["username"]} · {role_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("退出登录", use_container_width=True):
        logout()

    with st.expander("账号设置"):
        render_own_password_form(user["username"])

    if user.get("role") == "admin":
        with st.expander("用户管理"):
            render_admin_user_management()


def render_own_password_form(username: str) -> None:
    with st.form("change_own_password_form"):
        old_password = st.text_input("当前密码", type="password")
        new_password = st.text_input("新密码", type="password")
        confirm = st.text_input("确认新密码", type="password")
        submitted = st.form_submit_button("更新密码", use_container_width=True)
    if not submitted:
        return
    ok, message = change_own_password(username, old_password, new_password, confirm)
    if ok:
        st.success(message)
    else:
        st.error(message)


def render_admin_user_management() -> None:
    store = load_user_store()
    users = store["users"]

    st.caption(f"当前共有 {len(users)} 个本地账号")
    for item in sorted(users.values(), key=lambda raw: raw["username"]):
        status = "停用" if item.get("disabled") else "启用"
        role = "管理员" if item.get("role") == "admin" else "用户"
        st.write(f"**{item.get('display_name') or item['username']}** · @{item['username']} · {role} · {status}")

    with st.form("create_user_form"):
        st.markdown("**新增用户**")
        username = st.text_input("用户名", key="admin_new_username")
        display_name = st.text_input("显示名称", key="admin_new_display_name")
        password = st.text_input("初始密码", type="password", key="admin_new_password")
        confirm = st.text_input("确认初始密码", type="password", key="admin_new_confirm")
        role = st.selectbox("角色", ["user", "admin"], format_func=role_label, key="admin_new_role")
        submitted = st.form_submit_button("创建用户", type="primary", use_container_width=True)
    if submitted:
        ok, message = validate_new_user(username, password, confirm)
        if ok:
            ok, message = create_user(username=username, password=password, display_name=display_name, role=role)
        if ok:
            st.success(message)
            st.rerun()
        else:
            st.error(message)

    usernames = sorted(users)
    if not usernames:
        return

    selected = st.selectbox("选择要管理的用户", usernames, format_func=user_option_label, key="admin_selected_user")
    selected_user = users.get(selected)
    if not selected_user:
        return
    with st.form("update_user_form"):
        st.markdown("**编辑用户**")
        display_name = st.text_input("显示名称", value=str(selected_user.get("display_name") or ""), key="admin_edit_display")
        role = st.selectbox(
            "角色",
            ["user", "admin"],
            index=1 if selected_user.get("role") == "admin" else 0,
            format_func=role_label,
            key="admin_edit_role",
        )
        disabled = st.checkbox("停用此账号", value=bool(selected_user.get("disabled")), key="admin_edit_disabled")
        new_password = st.text_input("重置密码（留空则不修改）", type="password", key="admin_reset_password")
        submitted = st.form_submit_button("保存用户设置", use_container_width=True)
    if submitted:
        ok, message = update_user(
            selected,
            display_name=display_name,
            role=role,
            disabled=disabled,
            new_password=new_password,
        )
        if ok:
            st.success(message)
            st.rerun()
        else:
            st.error(message)

    if selected != current_username():
        if st.button("删除此用户和本地数据", use_container_width=True, key="admin_delete_user"):
            ok, message = delete_user(selected)
            if ok:
                st.success(message)
                st.rerun()
            else:
                st.error(message)


def validate_new_user(username: str, password: str, confirm: str) -> Tuple[bool, str]:
    username = normalize_username(username)
    if not USERNAME_PATTERN.match(username):
        return False, "用户名需为 3-32 位，只能包含字母、数字、下划线、点或短横线。"
    if len(password) < 6:
        return False, "密码至少需要 6 位。"
    if password != confirm:
        return False, "两次输入的密码不一致。"
    return True, ""


def authenticate(username: str, password: str, store: Dict[str, Any] | None = None) -> Tuple[bool, str]:
    username = normalize_username(username)
    store = store or load_user_store()
    user = store["users"].get(username)
    if not user or user.get("disabled"):
        return False, "用户名或密码不正确。"
    if not verify_password(password, str(user.get("password_hash", ""))):
        return False, "用户名或密码不正确。"
    user["last_login_at"] = now_iso()
    save_user_store(store)
    ensure_user_data_dir(username)
    return True, "登录成功。"


def sign_in(username: str) -> None:
    store = load_user_store()
    user = store["users"][username]
    theme_mode = st.session_state.get("theme_mode", "day")
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.theme_mode = theme_mode
    st.session_state.auth_user = public_user(user)


def logout() -> None:
    theme_mode = st.session_state.get("theme_mode", "day")
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.theme_mode = theme_mode
    st.rerun()


def current_user() -> Dict[str, Any] | None:
    user = st.session_state.get("auth_user")
    return user if isinstance(user, dict) else None


def current_username() -> str | None:
    user = current_user()
    if not user:
        return None
    username = normalize_username(str(user.get("username", "")))
    return username or None


def is_active_user(username: str) -> bool:
    username = normalize_username(username)
    user = load_user_store()["users"].get(username)
    return bool(user and not user.get("disabled"))


def public_user(user: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "username": user["username"],
        "display_name": user.get("display_name") or user["username"],
        "role": user.get("role", "user"),
    }


def create_user(
    *,
    username: str,
    password: str,
    display_name: str,
    role: str = "user",
    seed_from_legacy: bool = False,
) -> Tuple[bool, str]:
    username = normalize_username(username)
    store = load_user_store()
    if username in store["users"]:
        return False, "这个用户名已经存在。"
    user = {
        "username": username,
        "display_name": display_name.strip() or username,
        "role": role if role in {"admin", "user"} else "user",
        "password_hash": hash_password(password),
        "disabled": False,
        "created_at": now_iso(),
        "last_login_at": None,
    }
    store["users"][username] = user
    save_user_store(store)
    ensure_user_data_dir(username, seed_from_legacy=seed_from_legacy)
    return True, "用户已创建。"


def update_user(
    username: str,
    *,
    display_name: str,
    role: str,
    disabled: bool,
    new_password: str,
) -> Tuple[bool, str]:
    username = normalize_username(username)
    store = load_user_store()
    user = store["users"].get(username)
    if not user:
        return False, "用户不存在。"
    next_user = deepcopy(user)
    next_user["display_name"] = display_name.strip() or username
    next_user["role"] = role if role in {"admin", "user"} else "user"
    next_user["disabled"] = bool(disabled)
    if new_password:
        if len(new_password) < 6:
            return False, "新密码至少需要 6 位。"
        next_user["password_hash"] = hash_password(new_password)
    next_store = deepcopy(store)
    next_store["users"][username] = next_user
    if not has_active_admin(next_store):
        return False, "至少需要保留一个启用状态的管理员。"
    save_user_store(next_store)
    if username == current_username():
        st.session_state.auth_user = public_user(next_user)
    return True, "用户设置已保存。"


def delete_user(username: str) -> Tuple[bool, str]:
    username = normalize_username(username)
    if username == current_username():
        return False, "不能删除当前登录账号。"
    store = load_user_store()
    if username not in store["users"]:
        return False, "用户不存在。"
    next_store = deepcopy(store)
    del next_store["users"][username]
    if not has_active_admin(next_store):
        return False, "至少需要保留一个启用状态的管理员。"
    save_user_store(next_store)
    path = user_data_dir(username)
    if path.exists():
        shutil.rmtree(path)
    return True, "用户和本地数据已删除。"


def change_own_password(username: str, old_password: str, new_password: str, confirm: str) -> Tuple[bool, str]:
    username = normalize_username(username)
    store = load_user_store()
    user = store["users"].get(username)
    if not user:
        return False, "当前用户不存在。"
    if not verify_password(old_password, str(user.get("password_hash", ""))):
        return False, "当前密码不正确。"
    if len(new_password) < 6:
        return False, "新密码至少需要 6 位。"
    if new_password != confirm:
        return False, "两次输入的新密码不一致。"
    user["password_hash"] = hash_password(new_password)
    save_user_store(store)
    return True, "密码已更新。"


def load_user_store() -> Dict[str, Any]:
    if not AUTH_STORE_PATH.exists():
        return {"version": 1, "users": {}}
    try:
        payload = json.loads(AUTH_STORE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "users": {}}
    users = payload.get("users", {})
    if not isinstance(users, dict):
        users = {}
    normalized = {
        normalize_username(username): normalize_user_payload(username, raw)
        for username, raw in users.items()
        if isinstance(raw, dict) and normalize_username(username)
    }
    return {"version": 1, "users": normalized}


def normalize_user_payload(username: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    username = normalize_username(username)
    return {
        "username": username,
        "display_name": str(raw.get("display_name") or username),
        "role": "admin" if raw.get("role") == "admin" else "user",
        "password_hash": str(raw.get("password_hash", "")),
        "disabled": bool(raw.get("disabled", False)),
        "created_at": str(raw.get("created_at") or now_iso()),
        "last_login_at": raw.get("last_login_at"),
    }


def save_user_store(store: Dict[str, Any]) -> None:
    AUTH_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUTH_STORE_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PASSWORD_ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations_raw, salt_raw, digest_raw = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        salt = base64.b64decode(salt_raw)
        expected = base64.b64decode(digest_raw)
    except (ValueError, TypeError, OSError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def ensure_user_data_dir(username: str, *, seed_from_legacy: bool = False) -> Path:
    path = user_data_dir(username)
    path.mkdir(parents=True, exist_ok=True)
    if seed_from_legacy:
        copy_legacy_file(LEGACY_ARCHIVE_PATH, path / "session_archive.json")
        copy_legacy_file(LEGACY_MEMORY_PATH, path / "user_profile_memory.json")
    return path


def copy_legacy_file(source: Path, destination: Path) -> None:
    if source.exists() and not destination.exists():
        shutil.copy2(source, destination)


def user_data_dir(username: str) -> Path:
    username = normalize_username(username) or "local"
    return USER_DATA_ROOT / username


def has_active_admin(store: Dict[str, Any]) -> bool:
    return any(
        user.get("role") == "admin" and not user.get("disabled")
        for user in store.get("users", {}).values()
    )


def normalize_username(username: str) -> str:
    return str(username or "").strip().lower()


def role_label(role: str) -> str:
    return "管理员" if role == "admin" else "普通用户"


def user_option_label(username: str) -> str:
    user = load_user_store()["users"].get(username, {})
    name = user.get("display_name") or username
    role = role_label(str(user.get("role", "user")))
    status = "停用" if user.get("disabled") else "启用"
    return f"{name} (@{username}) · {role} · {status}"


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()
