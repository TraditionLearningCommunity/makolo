"""Legacy notification signals intentionally retired by Task 8A.

Runtime TicketOrder and Payment transitions now emit canonical Domain Events. The
Notifications system consumer is the single automatic path for migrated
transactional messages. Explicit compatibility helpers remain in services.py for
callers that invoke them deliberately.
"""
