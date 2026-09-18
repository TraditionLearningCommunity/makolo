from __future__ import annotations

import tldextract


class TldExtractDomainScope:
    """Offline Public Suffix List classifier.

    suffix_list_urls=() prevents runtime network fetching. Private PSL entries
    are treated as suffixes so tenant platforms receive independent domain
    budgets where the PSL declares that boundary.
    """

    def __init__(self) -> None:
        self._extract = tldextract.TLDExtract(
            suffix_list_urls=(),
            include_psl_private_domains=True,
        )

    def registrable_domain(self, hostname: str) -> str:
        result = self._extract(hostname)
        return result.top_domain_under_public_suffix or hostname
