"""
Security Guardrails for AI Agent Tool Calling

This module implements multi-layered security controls for the communication agent:
1. Input validation and sanitization
2. Rate limiting and transaction limits
3. Amount thresholds and confirmation requirements
4. Callbacks for pre/post tool execution validation
5. Audit logging for security monitoring

These guardrails work in both interactive and non-interactive modes:
- Interactive:     User confirmations can be requested for high-value transactions.
                  Run with: adk web  (uses gemini-live-2.5-flash-native-audio)
- Non-interactive: Stricter automatic limits apply, no confirmation prompts.
                  Run with: adk run agentops_agent  (uses gemini-2.5-flash)

Configure the mode:
    export AGENT_MODE=interactive      # default, for web / voice UI
    export AGENT_MODE=non-interactive  # for CLI / API / batch use
"""

import re
import time
import logging
import json
import os
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class SecurityConfig:
    """Centralised configuration for all guardrails."""

    interactive_mode: bool = True
    max_transactions_per_session: int = 50
    max_transactions_per_minute: int = 10
    max_amount_per_transaction: float = 1000.0
    max_total_amount_per_session: float = 5000.0
    require_confirmation_above: float = 100.0
    allowed_phone_patterns: List[str] = field(default_factory=lambda: [r'^\+\d{10,15}$'])
    blocked_phone_patterns: List[str] = field(default_factory=list)
    allowed_url_domains: List[str] = field(
        default_factory=lambda: ['africastalking.com', 'twilio.com', 's3.amazonaws.com']
    )
    max_message_length: int = 1600
    enable_pii_detection: bool = True
    audit_log_path: str = "logs/security_audit.log"


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class SecurityViolation(Exception):
    """Raised when a guardrail policy violation is detected."""


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """Rolling-window token-bucket rate limiter."""

    def __init__(self, max_calls: int, time_window: int = 60):
        self.max_calls = max_calls
        self.time_window = time_window
        self._calls: List[float] = []

    def check_limit(self, tool_name: str) -> Tuple[bool, Optional[str]]:
        now = time.monotonic()
        self._calls = [t for t in self._calls if now - t < self.time_window]
        if len(self._calls) >= self.max_calls:
            wait = int(self.time_window - (now - self._calls[0])) + 1
            return False, (
                f"Rate limit exceeded for '{tool_name}'. Please try again in {wait} second(s)."
            )
        self._calls.append(now)
        return True, None


# ---------------------------------------------------------------------------
# Transaction tracker
# ---------------------------------------------------------------------------

class TransactionTracker:
    """Tracks financial transaction counts and cumulative amounts per session."""

    def __init__(self, max_amount: float, max_count: int):
        self.max_amount = max_amount
        self.max_count = max_count
        self.total_amount: float = 0.0
        self.transaction_count: int = 0
        self.history: List[Dict[str, Any]] = []

    @property
    def remaining_amount(self) -> float:
        return max(0.0, self.max_amount - self.total_amount)

    @property
    def remaining_count(self) -> int:
        return max(0, self.max_count - self.transaction_count)

    def can_transact(self, amount: float) -> Tuple[bool, Optional[str]]:
        if self.transaction_count >= self.max_count:
            return False, (
                f"Session transaction limit ({self.max_count}) reached. No further transactions are permitted this session."
            )
        if self.total_amount + amount > self.max_amount:
            return False, (
                f"Transaction would exceed the session spending limit. Remaining budget: {self.remaining_amount:.2f}"
            )
        return True, None

    def record(self, tool_name: str, amount: float, details: Dict[str, Any]):
        self.transaction_count += 1
        self.total_amount += amount
        self.history.append({
            "timestamp": datetime.now().isoformat(),
            "tool": tool_name,
            "amount": amount,
            "details": details,
        })


# ---------------------------------------------------------------------------
# Main guardrails manager
# ---------------------------------------------------------------------------

class GuardrailsManager:
    _INJECTION_PATTERNS: List[str] = [
        r'ignore\s+previous\s+instructions',
        r'system\s*:',
        r'<\s*script\s*>',
        r'javascript\s*:',
        r'\$\{.*\}',
        r'\{\{.*\}\}',
    ]

    _PII_PATTERNS: Dict[str, str] = {
        "credit_card": r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
        "email":       r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
        "ssn_like":    r'\b\d{3}-\d{2}-\d{4}\b',
    }

    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig()
        self.rate_limiter = RateLimiter(
            max_calls=self.config.max_transactions_per_minute,
            time_window=60,
        )
        self.tracker = TransactionTracker(
            max_amount=self.config.max_total_amount_per_session,
            max_count=self.config.max_transactions_per_session,
        )
        self._setup_audit_log()

    def _setup_audit_log(self):
        os.makedirs(os.path.dirname(self.config.audit_log_path), exist_ok=True)
        self._audit = logging.getLogger("security_audit")
        if not self._audit.handlers:
            self._audit.setLevel(logging.INFO)
            h = logging.FileHandler(self.config.audit_log_path)
            h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
            self._audit.addHandler(h)
            self._audit.propagate = False

    def _audit_log(self, event_type: str, details: Dict[str, Any], severity: str = "INFO"):
        entry = json.dumps({
            "event_type": event_type,
            "severity": severity,
            "details": details,
        })
        getattr(self._audit, severity.lower(), self._audit.info)(entry)

    def validate_phone_number(self, number: str) -> Tuple[bool, Optional[str]]:
        if not number:
            return False, "Phone number is required."
        if not number.startswith("+"):
            return False, "Phone number must be in international format (start with +)."
        if not 11 <= len(number) <= 16:
            return False, f"Phone number length {len(number)} is invalid (expected 11–16 chars)."

        if self.config.allowed_phone_patterns:
            if not any(re.match(p, number) for p in self.config.allowed_phone_patterns):
                return False, "Phone number does not match any allowed pattern."

        if self.config.blocked_phone_patterns:
            if any(re.match(p, number) for p in self.config.blocked_phone_patterns):
                return False, "Phone number is on the blocked list."

        return True, None

    def validate_amount(self, amount: str) -> Tuple[bool, Optional[str], float]:
        try:
            value = float(amount)
        except (ValueError, TypeError):
            return False, f"Amount '{amount}' is not a valid number.", 0.0
        if value <= 0:
            return False, "Amount must be a positive number.", 0.0
        if value > self.config.max_amount_per_transaction:
            return False, (
                f"Amount {value} exceeds the per-transaction limit ({self.config.max_amount_per_transaction})."
            ), 0.0
        return True, None, value

    def validate_message(self, message: str) -> Tuple[bool, Optional[str]]:
        if not message:
            return False, "Message body cannot be empty."
        if len(message) > self.config.max_message_length:
            return False, (
                f"Message length ({len(message)}) exceeds the maximum ({self.config.max_message_length} characters)."
            )

        for pattern in self._INJECTION_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                self._audit_log("injection_attempt_blocked", {"snippet": message[:80]}, severity="warning")
                return False, "Message contains disallowed content and was blocked."

        if self.config.enable_pii_detection:
            found = [k for k, p in self._PII_PATTERNS.items() if re.search(p, message)]
            if found:
                self._audit_log("pii_detected", {"types": found, "snippet": message[:60]}, severity="warning")
                logger.warning("Potential PII detected in outgoing message: %s", found)

        return True, None

    def validate_url(self, url: str) -> Tuple[bool, Optional[str]]:
        if not url:
            return False, "URL is required."
        if not (url.startswith("http://") or url.startswith("https://")):
            return False, "URL must use HTTP or HTTPS."

        from urllib.parse import urlparse
        try:
            domain = urlparse(url).netloc.lower()
        except Exception as exc:
            return False, f"Malformed URL: {exc}"

        if self.config.allowed_url_domains:
            if not any(d in domain for d in self.config.allowed_url_domains):
                return False, f"Domain '{domain}' is not in the allowed list."

        return True, None

    # Backwards-compatible wrapper expected by existing agent code
    def validate_airtime_transaction(self, phone_number: str, currency: str, amount: str) -> Dict[str, Any]:
        """Compatibility wrapper: validate airtime transaction parameters.

        Returns a dict with keys: allowed, errors, warnings, requires_confirmation, amount_value
        """
        return self.check_financial_tool("api_send_airtime", phone_number, amount, currency)

    def check_financial_tool(self, tool_name: str, phone_number: str, amount: str, currency: str = "") -> Dict[str, Any]:
        result: Dict[str, Any] = {"allowed": True, "errors": [], "warnings": [], "requires_confirmation": False, "amount_value": 0.0}

        ok, msg = self.rate_limiter.check_limit(tool_name)
        if not ok:
            result.update(allowed=False, errors=[msg])
            return result

        ok, msg = self.validate_phone_number(phone_number)
        if not ok:
            result["allowed"] = False
            result["errors"].append(msg)

        ok, msg, amount_float = self.validate_amount(amount)
        if not ok:
            result["allowed"] = False
            result["errors"].append(msg)
        else:
            result["amount_value"] = amount_float
            ok, msg = self.tracker.can_transact(amount_float)
            if not ok:
                result["allowed"] = False
                result["errors"].append(msg)
            elif (self.config.interactive_mode and amount_float > self.config.require_confirmation_above):
                result["requires_confirmation"] = True
                result["warnings"].append(f"High-value transaction ({amount_float} {currency}) — please confirm before proceeding.")

        return result

    def check_voice_call(self, tool_name: str, from_number: str, to_number: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {"allowed": True, "errors": [], "warnings": []}

        ok, msg = self.rate_limiter.check_limit(tool_name)
        if not ok:
            result.update(allowed=False, errors=[msg])
            return result

        for label, num in [("from_number", from_number), ("to_number", to_number)]:
            ok, msg = self.validate_phone_number(num)
            if not ok:
                result["allowed"] = False
                result["errors"].append(f"{label}: {msg}")

        return result

    def check_messaging(self, tool_name: str, phone_number: str, message: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {"allowed": True, "errors": [], "warnings": []}

        ok, msg = self.rate_limiter.check_limit(tool_name)
        if not ok:
            result.update(allowed=False, errors=[msg])
            return result

        ok, msg = self.validate_phone_number(phone_number)
        if not ok:
            result["allowed"] = False
            result["errors"].append(msg)

        ok, msg = self.validate_message(message)
        if not ok:
            result["allowed"] = False
            result["errors"].append(msg)

        return result

    def record_successful_transaction(self, tool_name: str, amount: float, details: Dict[str, Any]):
        self.tracker.record(tool_name, amount, details)
        self._audit_log("transaction_success", {"tool": tool_name, "amount": amount, "session_total": self.tracker.total_amount, "details": details})


# ---------------------------------------------------------------------------
# ADK callback factories
# ---------------------------------------------------------------------------

def _blocked(errors: List[str]) -> Dict[str, Any]:
    return {"status": "error", "error_message": "Security check failed: " + "; ".join(errors)}


def create_before_tool_callback(gm: GuardrailsManager):
    def before_tool_callback(tool_name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        logger.debug("Guardrails pre-check: tool=%s", tool_name)

        if tool_name == "api_send_airtime":
            v = gm.check_financial_tool(tool_name, args.get("phone_number", ""), args.get("amount", ""), args.get("currency_code", ""))
            if not v["allowed"]:
                gm._audit_log("tool_blocked", {"tool": tool_name, "errors": v["errors"]}, severity="warning")
                return _blocked(v["errors"])
            if v["requires_confirmation"] and gm.config.interactive_mode:
                return {"status": "confirmation_required", "message": (f"Please confirm: send {args.get('amount')} {args.get('currency_code', '')} airtime to {args.get('phone_number')}?")}

        elif tool_name == "api_send_mobile_data":
            ok, msg = gm.validate_phone_number(args.get("phone_number", ""))
            if not ok:
                return _blocked([msg])
            ok, msg = gm.rate_limiter.check_limit(tool_name)
            if not ok:
                return _blocked([msg])

        elif tool_name in ("api_make_voice_call", "api_make_voice_call_with_text", "api_make_voice_call_and_play_audio"):
            v = gm.check_voice_call(tool_name, args.get("from_number", ""), args.get("to_number", ""))
            if not v["allowed"]:
                gm._audit_log("tool_blocked", {"tool": tool_name, "errors": v["errors"]}, severity="warning")
                return _blocked(v["errors"])
            if "audio_url" in args:
                ok, msg = gm.validate_url(args["audio_url"])
                if not ok:
                    return _blocked([msg])

        elif tool_name in ("api_send_message", "api_send_whatsapp_message"):
            v = gm.check_messaging(tool_name, args.get("phone_number", ""), args.get("message", ""))
            if not v["allowed"]:
                gm._audit_log("tool_blocked", {"tool": tool_name, "errors": v["errors"]}, severity="warning")
                return _blocked(v["errors"])

        gm._audit_log("tool_validated", {"tool": tool_name})
        return None

    return before_tool_callback


def create_after_tool_callback(gm: GuardrailsManager):
    _SENSITIVE_KEYS = {"api_key", "apiKey", "password", "secret", "token", "access_token"}

    def after_tool_callback(tool_name: str, args: Dict[str, Any], result: Any) -> Any:
        if tool_name == "api_send_airtime" and isinstance(result, dict):
            if result.get("status") == "success":
                try:
                    amount = float(args.get("amount", 0))
                    gm.record_successful_transaction(tool_name, amount, {"phone": args.get("phone_number"), "currency": args.get("currency_code")})
                except (ValueError, TypeError):
                    pass

        if isinstance(result, dict):
            for key in list(result.keys()):
                if key in _SENSITIVE_KEYS:
                    result[key] = "[REDACTED]"

        return result

    return after_tool_callback
