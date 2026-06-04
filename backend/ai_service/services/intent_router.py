import re
from dataclasses import dataclass


@dataclass(frozen=True)
class IntentDecision:
    intent: str
    confidence: float
    reason: str


class IntentRouter:
    policy_keywords = {
        "policy",
        "policies",
        "reimbursement",
        "expense",
        "travel",
        "remote work",
        "work remotely",
        "vpn",
        "mfa",
        "multi-factor",
        "data security",
        "confidential",
        "restricted data",
        "receipt",
        "receipts",
        "meal",
        "hotel",
        "approval",
        "least privilege",
    }
    database_patterns = (
        re.compile(r"\bPO\d+\b", re.IGNORECASE),
        re.compile(r"\bSO\d+\b", re.IGNORECASE),
        re.compile(r"\bMAT\d+\b", re.IGNORECASE),
        re.compile(r"\bCUST\d+\b", re.IGNORECASE),
        re.compile(r"\bSUP\d+\b", re.IGNORECASE),
    )
    database_keywords = {
        "supplier",
        "customer",
        "material",
        "stock",
        "inventory",
        "committed",
        "quantity",
        "purchase order",
        "sales order",
        "orders",
        "invoice",
        "shipment",
    }

    def decide(self, question: str) -> IntentDecision:
        normalized = question.strip().lower()

        if any(pattern.search(question) for pattern in self.database_patterns):
            return IntentDecision(
                intent="database",
                confidence=0.95,
                reason="Detected business entity code such as PO, SO, MAT, CUST, or SUP.",
            )

        policy_hits = [keyword for keyword in self.policy_keywords if keyword in normalized]
        database_hits = [keyword for keyword in self.database_keywords if keyword in normalized]

        if policy_hits and not database_hits:
            return IntentDecision(
                intent="policy",
                confidence=0.90,
                reason=f"Detected policy keywords: {', '.join(sorted(policy_hits))}.",
            )

        if database_hits:
            return IntentDecision(
                intent="database",
                confidence=0.80,
                reason=f"Detected database keywords: {', '.join(sorted(database_hits))}.",
            )

        return IntentDecision(
            intent="database",
            confidence=0.55,
            reason="Defaulted to live database because no clear policy intent was detected.",
        )
