# -*- coding: utf-8 -*-
"""paeg_vocabulary.llm_client —— DeepSeek LLM 客户端（OpenAI 兼容，零第三方依赖）。

让词汇表工具【独立接入 LLM】：不再依赖宿主注入 chat_fn，直接读环境变量即可调用。

Key 读取顺序（与主项目 resume_product.llm_client 一致）：
  1. 环境变量 DEEPSEEK_API_KEY（最优先，跨进程可配）
  2. ~/.local/share/opencode/auth.json 的 deepseek.key（本地 opencode 配置）

可选环境变量：
  - DEEPSEEK_MODEL     模型名（默认 deepseek-chat）
  - DEEPSEEK_API_URL   API 地址（默认 https://api.deepseek.com/chat/completions）

无 key 时 __call__ 返回空串（等价 NullLLM），调用方（gate/enrich/metadata/review）
自动降级到确定性规则层——不抛异常、不阻塞管线。

用法：
    from paeg_vocabulary.llm_client import chat, EnvLLM, available

    # 直接同步调用
    text = chat(system_prompt, user_prompt, max_tokens=2000)

    # 作为 LLMCallable 协议实现（默认已接入 VocabularyRegistry.llm）
    llm = EnvLLM()
    text = llm(system_prompt, user_prompt, max_tokens=2000, temperature=0.3)

    # 判断是否已配置可用 key
    if available():
        ...
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Optional

_API_URL = os.environ.get("DEEPSEEK_API_URL",
                           "https://api.deepseek.com/chat/completions")
_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
_KEY_ENV = "DEEPSEEK_API_KEY"

# key 缓存：None = 未读；"" = 已读但无 key（避免每批重复读 auth.json）
_KEY_CACHE: Optional[str] = None


def _get_key() -> str:
    """读 DeepSeek key：环境变量优先，其次 opencode auth.json。结果缓存。"""
    global _KEY_CACHE
    if _KEY_CACHE is not None:
        return _KEY_CACHE

    env = os.environ.get(_KEY_ENV, "").strip()
    if env:
        _KEY_CACHE = env
        return env

    auth = os.path.expanduser("~/.local/share/opencode/auth.json")
    if os.path.exists(auth):
        try:
            with open(auth, encoding="utf-8") as f:
                d = json.load(f)
            key = (d.get("deepseek") or {}).get("key", "")
            _KEY_CACHE = str(key).strip()
            return _KEY_CACHE
        except Exception:
            pass

    _KEY_CACHE = ""
    return ""


def available() -> bool:
    """是否已配置可用的 DeepSeek key（供上层判断是否走 LLM 增强）。"""
    return bool(_get_key())


def chat(system: str, user: str, *, temperature: float = 0.3,
         max_tokens: int = 2000, timeout: int = 120) -> str:
    """同步调用 DeepSeek（无第三方依赖）。失败 / 无 key 一律返回空串。"""
    key = _get_key()
    if not key:
        return ""

    payload = {
        "model": _MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    req = urllib.request.Request(
        _API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        choices = data.get("choices") or []
        if choices:
            msg = choices[0].get("message") or {}
            return (msg.get("content") or "").strip()
        return ""
    except Exception:
        return ""


class EnvLLM:
    """环境变量 LLM 客户端——实现 LLMCallable 协议 (system, user, *, max_tokens, temperature)。

    无 key 时返回空串（等价 NullLLM 弱模式降级），不抛异常。
    """

    def __init__(self, timeout: int = 120):
        self.timeout = timeout

    def __call__(self, system: str, user: str, *, max_tokens: int = 2000,
                 temperature: float = 0.7) -> str:
        return chat(system, user, temperature=temperature,
                    max_tokens=max_tokens, timeout=self.timeout)
