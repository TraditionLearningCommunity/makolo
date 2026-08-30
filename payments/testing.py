"""Test-only adapter for consumers of canonical PaymentObligation fixtures.

Application runtime must never import this module. Cross-domain fixture wiring
lives in the neutral ``test_support`` package so Payments keeps no dependency
on Services.
"""

from test_support.payment_obligations import make_payment_obligation_journey

__all__ = ["make_payment_obligation_journey"]
