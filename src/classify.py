"""
classify.py — Role classification, the heart of fit scoring.

Key data lesson (from exploring the sample): career_history *descriptions* are
partly shuffled/templated noise — a "Project Manager" role can be described in
"brand design" language. Structured fields (title, industry, company) are
reliable. So we classify a role primarily by TITLE + INDUSTRY, and use the
description only as a weak corroborating *bonus* — never to drive a score down.

Behavior here is preserved verbatim from the validated prototype (features.py).
"""

from __future__ import annotations

from .vocab import (
    ADJACENT_TITLE_TERMS,
    CONSULTING_FIRMS,
    ML_TITLE_TERMS,
    SERVICES_INDUSTRIES,
    SHIPPED_SYSTEM_PHRASES,
)


def _lower(s) -> str:
    return (s or "").lower()


def _any(text, terms) -> bool:
    t = _lower(text)
    return any(term in t for term in terms)


def classify_role(job: dict) -> tuple[float, bool]:
    """Return (ml_weight, is_product) for one career-history entry.

    ml_weight in [0,1]: how much this role counts as real ML/IR/ranking work.
    is_product: True if at a product company (not IT-services/consulting).
    """
    title = _lower(job.get("title"))
    industry = _lower(job.get("industry"))
    company = _lower(job.get("company"))
    desc = job.get("description", "")

    # Product vs services. Industry is the reliable structured signal.
    is_services = industry in SERVICES_INDUSTRIES or any(
        f in company for f in CONSULTING_FIRMS
    )
    is_product = not is_services

    # ML weight from title (trustworthy) ...
    if _any(title, ML_TITLE_TERMS):
        w = 1.0
    elif _any(title, ADJACENT_TITLE_TERMS):
        w = 0.4
    else:
        w = 0.0

    # ... nudged up if the (noisy) description corroborates real systems work.
    # We only ADD on corroboration, never subtract, because descriptions are noisy.
    if w > 0 and _any(desc, SHIPPED_SYSTEM_PHRASES):
        w = min(1.0, w + 0.2)

    return w, is_product
