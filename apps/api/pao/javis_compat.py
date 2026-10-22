"""Compatibility primitives for migrating Javis OS backend capabilities into PAO.

This module deliberately contains policy, not provider calls.  It mirrors the useful
part of Javis' fast-path gate: only a self-contained chat question with no attachment
and no capability-like intent may be considered for a direct model call.  The first
release is shadow-only; the PAO runtime records the decision in the durable execution
plan and keeps its existing planner/memory path unchanged.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


JAVIS_COMPAT_VERSION = "javis-compat-v1"


def normalize(value: str) -> str:
    raw = str(value or "").replace("đ", "d").replace("Đ", "D")
    folded = unicodedata.normalize("NFKD", raw.casefold())
    return " ".join("".join(c for c in folded if not unicodedata.combining(c)).split())


@dataclass(frozen=True)
class FastPathDecision:
    eligible: bool
    intent_class: str
    reason: str
    confidence: float
    policy_version: str = JAVIS_COMPAT_VERSION


class JavisFastPathClassifier:
    """Conservative, provider-independent Javis fast-path classifier.

    False negatives only use the normal PAO pipeline.  False positives could skip
    memory, tools or specialist routing, so capability and side-effect language is
    denied before the allow rules are considered.
    """

    _DENY = (
        ("tool", re.compile(r"\b(?:tim|tra|search|google|web|api|mcp|cong cu)\b")),
        ("action", re.compile(r"\b(?:gui|tao|sua|xoa|dat lich|gui email|dang bai|chay)\b")),
        ("current_data", re.compile(r"\b(?:hom nay|bay gio|hien tai|so lieu|bao cao|chi phi|doanh thu)\b")),
        ("memory", re.compile(r"\b(?:nho|ghi nho|remember|memory|da luu|lich su)\b")),
    )
    _ALLOW = (
        ("greeting", re.compile(r"^(?:xin chao|chao|hello|hi|cam on|thanks)(?:[!. ]|$)")),
        ("rewrite", re.compile(r"\b(?:viet lai|tom tat|dich|sua cau|giai thich)\b")),
        ("question", re.compile(r"[?]|\b(?:la gi|nghia la gi|what is|how does)\b")),
    )

    def classify(self, objective: str, *, has_attachments: bool = False,
                 max_chars: int = 2_000) -> FastPathDecision:
        text = str(objective or "").strip()
        if not text:
            return FastPathDecision(False, "empty", "empty_objective", 1.0)
        if has_attachments:
            return FastPathDecision(False, "attachment", "attachment_present", 1.0)
        if len(text) > max_chars:
            return FastPathDecision(False, "oversized", "objective_too_large", 1.0)
        normalized = normalize(text)
        for intent, pattern in self._DENY:
            if pattern.search(normalized):
                return FastPathDecision(False, intent, f"requires_full_path:{intent}", 0.98)
        for intent, pattern in self._ALLOW:
            if pattern.search(normalized):
                return FastPathDecision(True, intent, "self_contained_chat", 0.90)
        return FastPathDecision(False, "uncertain", "intent_uncertain", 0.65)


def capability_manifest() -> dict[str, dict[str, str]]:
    """Stable migration map used by Settings/System Status and future adapters."""
    return {
        "fast_path": {"source": "Javis fast_path_runtime", "target": "pao.javis_compat", "status": "shadow"},
        "model_router": {"source": "Javis model_router", "target": "pao.gateway", "status": "planned"},
        "brain_memory": {"source": "Javis memory_index/learn", "target": "pao.memory", "status": "mapped"},
        "skills_workflows": {"source": "Javis skill_router/workflow_runtime", "target": "pao.agents/automation", "status": "mapped"},
        "channels": {"source": "Javis telegram/zalo/chatbot", "target": "pao.telegram", "status": "partial"},
        "voice": {"source": "Javis voice_live/voice_brain", "target": "pao.voice", "status": "partial"},
        "local_tools": {"source": "Javis terminal/plugins_host", "target": "pao.tool_gateway", "status": "restricted"},
    }
