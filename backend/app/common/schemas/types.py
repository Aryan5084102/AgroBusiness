"""Reusable Pydantic field types.

``Email`` intentionally uses a permissive syntactic check rather than
``pydantic.EmailStr``: the latter rejects special-use TLDs such as ``.local``,
which the product's demo/internal accounts (``owner@agriflow.local``) rely on.
Deliverability is not our concern at validation time.
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email(value: str) -> str:
    value = value.strip().lower()
    if not _EMAIL_RE.match(value):
        raise ValueError("Enter a valid email address.")
    return value


Email = Annotated[str, AfterValidator(_validate_email)]
