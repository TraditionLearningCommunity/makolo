from django.core.exceptions import ValidationError
from django.core.signing import Signer
from django.test import TestCase

from access.models import CredentialStatus
from access.services import render_access_credential, rotate_access_credential
from tickets.models import QR_SIGNING_SALT
from tickets.services import validate_qr_token

from .models import ScanResult
from .services import scan_ticket
from .tests import ScannerFixtureMixin


class ScannerAccessBridgeTests(ScannerFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()
        self.ticket.refresh_from_db()

    def test_rotated_credential_rejects_old_qr_and_accepts_new_qr(self):
        access = self.ticket.access
        old = access.credentials.get(status=CredentialStatus.ACTIVE)
        old_token = render_access_credential(old)
        new = rotate_access_credential(access=access)
        new_token = render_access_credential(new)

        old_outcome = scan_ticket(
            token=old_token,
            actor=self.agent,
            event=self.event,
            client_reference="rotated-old",
        )
        self.assertEqual(old_outcome.result, ScanResult.INVALID_STATUS)
        self.assertFalse(old_outcome.accepted)

        new_outcome = scan_ticket(
            token=new_token,
            actor=self.agent,
            event=self.event,
            client_reference="rotated-new",
        )
        self.assertEqual(new_outcome.result, ScanResult.ACCEPTED)
        self.assertTrue(new_outcome.accepted)

    def test_historical_ticket_qr_resolves_to_access_when_no_credential_exists(self):
        access = self.ticket.access
        access.credentials.all().delete()
        legacy_token = Signer(salt=QR_SIGNING_SALT).sign(str(self.ticket.code))

        outcome = scan_ticket(
            token=legacy_token,
            actor=self.agent,
            event=self.event,
            client_reference="legacy-ticket",
        )
        access.refresh_from_db()
        self.assertEqual(outcome.result, ScanResult.ACCEPTED)
        self.assertTrue(outcome.accepted)
        self.assertEqual(access.status, "used")

    def test_issuing_canonical_credential_invalidates_historical_ticket_qr_everywhere(self):
        access = self.ticket.access
        access.credentials.all().delete()
        old_code = self.ticket.code
        legacy_token = Signer(salt=QR_SIGNING_SALT).sign(str(old_code))

        canonical = rotate_access_credential(access=access)
        self.ticket.refresh_from_db()
        self.assertNotEqual(self.ticket.code, old_code)
        self.assertEqual(canonical.status, CredentialStatus.ACTIVE)

        with self.assertRaises(ValidationError):
            validate_qr_token(legacy_token)

        outcome = scan_ticket(
            token=legacy_token,
            actor=self.agent,
            event=self.event,
            client_reference="legacy-after-canonical",
        )
        self.assertFalse(outcome.accepted)
        self.assertEqual(outcome.result, ScanResult.UNKNOWN_TICKET)
