"""Rol teklifi doğrulama — kayıt öncesi kural kontrolleri."""
from __future__ import annotations

import re
from dataclasses import dataclass

from mnacp.no_code.role_builder import RoleProposal


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]
    warnings: list[str]


def validate_proposal(proposal: RoleProposal) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not proposal.agent_name or len(proposal.agent_name) < 2:
        errors.append("Ajan adı en az 2 karakter olmalı")
    if not re.match(r"^[A-Za-z][A-Za-z0-9_]*$", proposal.agent_name):
        errors.append("Ajan adı harf ile başlamalı, sadece harf/rakam/alt çizgi içermeli")

    if not proposal.agent_description or len(proposal.agent_description) < 10:
        errors.append("Ajan açıklaması en az 10 karakter olmalı")

    if not proposal.tools:
        errors.append("En az bir araç tanımlanmalı")
    if len(proposal.tools) > 10:
        warnings.append("10'dan fazla araç tanımlandı — performans etkilenebilir")

    tool_names = [t.name for t in proposal.tools]
    if len(tool_names) != len(set(tool_names)):
        errors.append("Araç isimleri benzersiz olmalı")

    for tool in proposal.tools:
        if not re.match(r"^[a-z][a-z0-9_]*$", tool.name):
            errors.append(f"Araç adı snake_case olmalı: '{tool.name}'")
        if len(tool.description) < 5:
            warnings.append(f"'{tool.name}' aracının açıklaması çok kısa")

    return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)
