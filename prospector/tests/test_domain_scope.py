from unittest import TestCase

from prospector.adapters.domain_scope import TldExtractDomainScope


class TldExtractDomainScopeTests(TestCase):
    def setUp(self):
        self.scope = TldExtractDomainScope()

    def test_public_suffix_domain_is_not_naively_split(self):
        self.assertEqual(
            self.scope.registrable_domain("forums.bbc.co.uk"),
            "bbc.co.uk",
        )

    def test_private_psl_suffix_keeps_tenant_budget_separate(self):
        self.assertEqual(
            self.scope.registrable_domain("team.github.io"),
            "team.github.io",
        )
