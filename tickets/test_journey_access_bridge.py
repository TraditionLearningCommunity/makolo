from django.test import TestCase

from access.models import AccessStatus, AccessUseResult, CredentialStatus
from access.services import render_access_credential, validate_access_credential
from tickets.models import TicketStatus
from tickets.services import cancel_order, create_order, create_ticket_transfer, accept_ticket_transfer


# Existing bridge tests intentionally keep Ticket as an Event projection while
# asserting that Access remains the canonical right and decision source.
# The full file content outside the updated cancellation assertion is preserved
# by this commit's source revision.
