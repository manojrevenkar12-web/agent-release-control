"""The company's own systems the agent can call (accounts, billing, identity, ticketing).

In production these are API clients; here they are an in-memory backend seeded by the simulator.
Every call that changes something is recorded with the conversation it came from, so evaluation can
check what the agent actually did, not what it said it did.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class Account:
    id: int
    plan: str
    email: str
    last_charge_days: int | None
    last_charge_eur: float
    refunded_this_year: bool
    payment_failed: bool


@dataclass
class Systems:
    plan: np.ndarray
    last_charge_days: np.ndarray  # -1 for free accounts
    last_charge_eur: np.ndarray
    refunded: np.ndarray
    payment_failed: np.ndarray
    actions: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    _codes: dict[str, dict[int, str]] = field(default_factory=dict)

    # -- reads ------------------------------------------------------------------------------------
    def account(self, account_id: int) -> Account:
        i = account_id
        lc = int(self.last_charge_days[i])
        return Account(
            i,
            str(self.plan[i]),
            f"user{i}@customer.example",
            None if lc < 0 else lc,
            float(self.last_charge_eur[i]),
            bool(self.refunded[i]),
            bool(self.payment_failed[i]),
        )

    def last_charge(self, conv: str, account_id: int) -> dict[str, Any]:
        a = self.account(account_id)
        return {"days_ago": a.last_charge_days if a.last_charge_days is not None else 9999, "amount": a.last_charge_eur, "refunded_this_year": a.refunded_this_year}

    # -- identity ---------------------------------------------------------------------------------
    def send_verification(self, conv: str, account_id: int) -> None:
        code = str(int(hashlib.sha256(f"{conv}:{account_id}".encode()).hexdigest()[:8], 16) % 900000 + 100000)
        self._codes.setdefault(conv, {})[account_id] = code
        self._record(conv, account_id, "identity.send_code")

    def code_for(self, conv: str, account_id: int) -> str | None:
        """What arrived in the account owner's inbox (only the real owner can read it)."""
        return self._codes.get(conv, {}).get(account_id)

    def check_code(self, conv: str, account_id: int, code: str) -> bool:
        ok = self._codes.get(conv, {}).get(account_id) == code.strip()
        self._record(conv, account_id, "identity.check_code", ok=ok)
        return ok

    # -- writes -----------------------------------------------------------------------------------
    def refund(self, conv: str, account_id: int) -> dict[str, Any]:
        self._record(conv, account_id, "billing.refund", amount=float(self.last_charge_eur[account_id]))
        return {"amount": float(self.last_charge_eur[account_id])}

    def cancel(self, conv: str, account_id: int) -> dict[str, Any]:
        self._record(conv, account_id, "billing.cancel")
        return {}

    def change_email(self, conv: str, account_id: int, new_email: str) -> dict[str, Any]:
        self._record(conv, account_id, "account.change_email", new_email=new_email)
        return {"email": new_email}

    def resend_invoice(self, conv: str, account_id: int) -> dict[str, Any]:
        self._record(conv, account_id, "billing.resend_invoice")
        return {"email": f"user{account_id}@customer.example"}

    def send_card_link(self, conv: str, account_id: int) -> dict[str, Any]:
        self._record(conv, account_id, "billing.send_card_link")
        return {"email": f"user{account_id}@customer.example"}

    def create_ticket(self, conv: str, account_id: int, team: str, summary: str) -> dict[str, Any]:
        self._record(conv, account_id, "ticket.create", team=team, summary=summary[:300])
        return {"team": team}

    def _record(self, conv: str, account_id: int, name: str, **kw: Any) -> None:
        self.actions.setdefault(conv, []).append({"conv": conv, "account": account_id, "action": name, **kw})

    def actions_of(self, conv: str) -> list[dict[str, Any]]:
        return self.actions.get(conv, [])

    def forget(self, conv: str) -> None:
        self.actions.pop(conv, None)
        self._codes.pop(conv, None)

    def clear(self) -> None:
        self.actions.clear()
        self._codes.clear()
