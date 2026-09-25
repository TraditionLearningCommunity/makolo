"""Bounded, inert document structure over bytes already acquired by Observer.

These values are ephemeral. A document is not the thing(s) it describes.
Locators are paths in the deterministic parsed tree, never CSS selectors.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from html.parser import HTMLParser
import json
import re

DOCUMENT_VERSION = "1"
MAX_DOCUMENT_CHARS = 2_000_000
MAX_DOCUMENT_NODES = 25_000
MAX_DOCUMENT_DEPTH = 64
MAX_ATTRIBUTE_CHARS = 2_000
DOCUMENT_TYPES = frozenset({
    "article", "newsarticle", "webpage", "website", "faqpage",
    "breadcrumblist", "blogposting", "report", "scholarlyarticle",
})
ARTICLE_TYPES = frozenset({"article", "newsarticle", "blogposting", "report", "scholarlyarticle"})
_VOID = frozenset("area base br col embed hr img input link meta param source track wbr".split())
_INERT = frozenset({"script", "style", "noscript", "template"})
_CONTAINERS = frozenset("main section article nav header footer aside ul ol dl table thead tbody tfoot tr form select".split())
_TEXT = frozenset("h1 h2 h3 h4 h5 h6 p li dt dd th td address label button option pre blockquote figcaption".split())
_INLINE = frozenset({"a", "time"})
_ATTRIBUTES = frozenset({
    "lang", "xml:lang", "href", "rel", "hreflang", "title", "content", "name",
    "property", "http-equiv", "datetime", "itemprop", "itemtype", "itemscope",
    "itemid", "id", "for", "type", "action", "method", "required", "disabled",
    "multiple", "min", "max", "minlength", "maxlength", "pattern", "placeholder",
    "rowspan", "colspan", "scope", "role", "aria-label", "charset",
})
_WS = re.compile(r"\s+")
_LANG = re.compile(r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")


class DocumentLimitError(ValueError):
    """Parsing stopped at an explicit resource boundary."""


def clean_text(value: str) -> str:
    return _WS.sub(" ", value).strip()


def schema_type(value: str) -> str:
    local = value.rsplit("/", 1)[-1].rsplit("#", 1)[-1]
    return re.sub(r"[^a-z0-9]+", "_", local.lower()).strip("_")[:100]


def _ref(artifact_ref: str, locator: str, kind: str) -> str:
    payload = json.dumps([DOCUMENT_VERSION, artifact_ref, locator, kind], separators=(",", ":"))
    return "block:" + hashlib.sha256(payload.encode()).hexdigest()[:32]


@dataclass(frozen=True, slots=True)
class SemanticBlock:
    block_ref: str
    artifact_ref: str
    artifact_observation_ref: str
    locator_kind: str
    locator: str
    kind: str
    text: str
    heading_context: tuple[str, ...] = ()
    language: str | None = None
    attributes: tuple[tuple[str, str], ...] = ()
    parent_ref: str | None = None
    is_text: bool = False
    page_number: int | None = None

    def attr(self, key: str, default: str = "") -> str:
        return dict(self.attributes).get(key, default)

    def evidence(self, method: str = "document_structure"):
        from .contracts import CandidateEvidence
        return CandidateEvidence(
            self.artifact_ref, self.artifact_observation_ref, self.locator_kind,
            self.locator, method, page_number=self.page_number,
        )


@dataclass(frozen=True, slots=True)
class SemanticLink:
    block_ref: str
    href: str
    text: str = ""
    rel: tuple[str, ...] = ()
    hreflang: str | None = None


@dataclass(frozen=True, slots=True)
class StructuredFragment:
    fragment_ref: str
    block_ref: str
    kind: str
    content: str


@dataclass(frozen=True, slots=True)
class SemanticDocument:
    document_ref: str
    artifact_ref: str
    artifact_observation_ref: str
    source_locator: str | None = None
    title: str | None = None
    language: str | None = None
    type_hints: tuple[str, ...] = ()
    blocks: tuple[SemanticBlock, ...] = ()
    # Metadata entries retain the block that actually states their value.
    metadata: tuple[tuple[str, str, str], ...] = ()
    structured_fragments: tuple[StructuredFragment, ...] = ()
    links: tuple[SemanticLink, ...] = ()
    forms: tuple[str, ...] = ()
    tables: tuple[str, ...] = ()
    warning_codes: tuple[str, ...] = ()

    @property
    def article_like(self) -> bool:
        return bool(ARTICLE_TYPES.intersection(self.type_hints))

    @property
    def text_blocks(self) -> tuple[SemanticBlock, ...]:
        return tuple(block for block in self.blocks if block.is_text and block.text)

    def block_map(self) -> dict[str, SemanticBlock]:
        return {block.block_ref: block for block in self.blocks}


@dataclass(slots=True)
class _Node:
    tag: str
    attrs: dict[str, str]
    path: str
    order: int
    language: str | None
    hidden: bool = False
    parent: _Node | None = None
    children: list = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)


def _raw(node: _Node) -> str:
    return "".join(_raw(c) if isinstance(c, _Node) else c[1] for c in node.children)


def _visible(node: _Node) -> str:
    if node.hidden or node.tag in _INERT:
        return ""
    parts = []
    for child in node.children:
        if isinstance(child, _Node):
            boundary = child.tag in _TEXT or child.tag in _CONTAINERS or child.tag == "br"
            parts.append(("\n" if boundary else "") + _visible(child) + ("\n" if boundary else ""))
        else:
            parts.append(child[1])
    return "".join(parts)


def _json_types(raw: str) -> tuple[str, ...]:
    """Only document-level declarations, not arbitrary nested mentioned articles."""
    def reject_constant(value):
        raise ValueError("non-finite JSON number")
    value = json.loads(raw, parse_constant=reject_constant)
    pending = [(value, 0)]
    count = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if depth > MAX_DOCUMENT_DEPTH or count > MAX_DOCUMENT_NODES:
            raise DocumentLimitError("structured fragment limit exceeded")
        if isinstance(item, dict):
            pending.extend((v, depth + 1) for v in item.values())
        elif isinstance(item, list):
            pending.extend((v, depth + 1) for v in item)
    roots = value if isinstance(value, list) else [value]
    found = set()
    for item in roots:
        if not isinstance(item, dict):
            continue
        graph = item.get("@graph", [])
        for node in [item] + (graph if isinstance(graph, list) else []):
            if not isinstance(node, dict):
                continue
            types = node.get("@type", [])
            types = [types] if isinstance(types, str) else types
            if isinstance(types, list):
                found.update(schema_type(t) for t in types if isinstance(t, str) and schema_type(t) in DOCUMENT_TYPES)
    return tuple(sorted(found))


class _Capture(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("#document", {}, "", 0, None)
        self.stack = [self.root]
        self.nodes: list[_Node] = []
        self.sequence = 0
        self.warnings: list[str] = []

    def _next(self) -> int:
        self.sequence += 1
        if self.sequence > MAX_DOCUMENT_NODES:
            raise DocumentLimitError("document node limit exceeded")
        return self.sequence

    def _implicit_close(self, tag: str):
        # Bounded recovery for common HTML omitted end tags, not browser execution.
        closes = {"li": {"li"}, "dt": {"dt", "dd"}, "dd": {"dt", "dd"},
                  "tr": {"tr"}, "th": {"th", "td"}, "td": {"th", "td"},
                  "option": {"option"}, "thead": {"thead", "tbody", "tfoot"},
                  "tbody": {"thead", "tbody", "tfoot"}, "tfoot": {"thead", "tbody", "tfoot"}}
        targets = closes.get(tag, set())
        if tag in _TEXT or tag in _CONTAINERS or tag in {"div", "p"}:
            targets = targets | {"p"}
        barriers = {"ul", "ol"} if tag == "li" else {"table"} if tag in {"tr", "td", "th", "tbody", "thead", "tfoot"} else set()
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag in targets:
                del self.stack[index:]
                break
            if self.stack[index].tag in barriers:
                break

    def handle_starttag(self, tag, attrs):
        self._implicit_close(tag)
        if len(self.stack) > MAX_DOCUMENT_DEPTH:
            raise DocumentLimitError("document depth limit exceeded")
        raw_attrs = {k.lower(): v or "" for k, v in attrs}
        parent = self.stack[-1]
        count = parent.counts.get(tag, 0) + 1
        parent.counts[tag] = count
        path = f"{parent.path}/{tag}[{count}]"
        if len(path) > 900:
            raise DocumentLimitError("document locator limit exceeded")
        selected = {}
        for key, value in raw_attrs.items():
            if key not in _ATTRIBUTES:
                continue
            if len(value) > MAX_ATTRIBUTE_CHARS:
                self.warnings.append("document_attribute_too_long")
                continue
            selected[key] = value
        lang = raw_attrs.get("lang", raw_attrs.get("xml:lang", parent.language))
        if lang and not _LANG.fullmatch(lang):
            self.warnings.append("invalid_declared_language")
            lang = None
        hidden = parent.hidden or parent.tag in _INERT or "hidden" in raw_attrs or raw_attrs.get("aria-hidden", "").lower() == "true"
        node = _Node(tag, selected, path, self._next(), lang, hidden, parent)
        self.nodes.append(node)
        parent.children.append(node)
        if tag not in _VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in _VOID:
            return
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        if data:
            self.stack[-1].children.append((self._next(), data))


def parse_html_document(text: str, descriptor, *, source_locator: str | None = None) -> SemanticDocument:
    if not isinstance(text, str):
        raise TypeError("document text must be a string")
    if len(text) > MAX_DOCUMENT_CHARS:
        raise DocumentLimitError("document text limit exceeded")
    parser = _Capture()
    parser.feed(text)
    parser.close()
    artifact = descriptor.artifact_ref
    owner = descriptor.observation_ref
    records: list[tuple[int, _Node, str, str, bool]] = []
    chosen: set[int] = set()

    def has_primary(node):
        return any(isinstance(c, _Node) and (c.tag in _TEXT or has_primary(c)) for c in node.children)

    def choose_lines(node, blocked=False):
        blocked = blocked or node.hidden or node.tag in _INERT or node.tag in {"head", "nav", "header", "footer"}
        if blocked:
            return
        if node.tag in _TEXT or (node.tag not in {"#document", "html"} and not has_primary(node) and clean_text(_visible(node))):
            chosen.add(node.order)
            return
        text_index = 0
        for child in node.children:
            if isinstance(child, _Node):
                choose_lines(child, blocked)
            else:
                text_index += 1
                value = clean_text(child[1])
                if value:
                    # A loose text node next to a semantic child must not disappear.
                    loose = _Node("text", {}, f"{node.path}/text()[{text_index}]", child[0], node.language, parent=node)
                    records.append((child[0], loose, "text", value, True))

    choose_lines(parser.root)
    for node in parser.nodes:
        if node.hidden:
            continue
        is_json = node.tag == "script" and "ld+json" in node.attrs.get("type", "").lower()
        if node.tag in _INERT and not is_json:
            continue
        meaningful = node.tag in _TEXT | _INLINE | _CONTAINERS | {"title", "meta", "link", "input"} or "itemprop" in node.attrs or "itemscope" in node.attrs or is_json or node.order in chosen
        if meaningful:
            kind = "json_ld" if is_json else node.tag if node.tag in _TEXT | _INLINE | _CONTAINERS | {"title", "meta", "link", "input"} else "text"
            value = _raw(node) if is_json else clean_text(_visible(node)) if (node.tag in _TEXT | _INLINE | {"title"} or node.order in chosen or "itemprop" in node.attrs) else ""
            records.append((node.order, node, kind, value, node.order in chosen))

    blocks = []
    metadata = []
    fragments = []
    links = []
    forms, tables = [], []
    headings: dict[int, str] = {}
    types = {"webpage"}
    title = None
    language = next((n.language for n in parser.nodes if n.tag == "html"), None)
    record_refs = {n.path: _ref(artifact, n.path, k) for _, n, k, _, _ in records}
    for _, node, kind, value, is_text in sorted(records, key=lambda row: row[0]):
        if re.fullmatch(r"h[1-6]", kind):
            level = int(kind[1])
            headings = {k: v for k, v in headings.items() if k < level}
            context = tuple(headings.values())
            headings[level] = value
        else:
            context = tuple(headings.values())
        parent = node.parent
        while parent and parent.path not in record_refs:
            parent = parent.parent
        block = SemanticBlock(
            record_refs[node.path], artifact, owner, "html_path", node.path, kind, value,
            context, node.language, tuple(sorted(node.attrs.items())),
            record_refs.get(parent.path) if parent else None, is_text,
        )
        blocks.append(block)
        if kind == "title" and value and title is None:
            title = value
        if kind == "article":
            types.add("article")
        if kind == "meta":
            key = node.attrs.get("property") or node.attrs.get("name") or node.attrs.get("itemprop")
            raw = node.attrs.get("content")
            if key and raw:
                metadata.append((key, raw, block.block_ref))
                if key.lower() == "og:type" and raw.lower() == "article":
                    types.add("article")
                if key.lower() == "og:title" and title is None:
                    title = raw
                fragments.append(StructuredFragment("fragment:" + block.block_ref, block.block_ref, "open_graph" if key.lower().startswith("og:") else "meta", raw))
        if kind in {"a", "link"} and node.attrs.get("href"):
            links.append(SemanticLink(block.block_ref, node.attrs["href"], value, tuple(node.attrs.get("rel", "").lower().split()), node.attrs.get("hreflang") or None))
        if kind == "form":
            forms.append(block.block_ref)
        if kind == "table":
            tables.append(block.block_ref)
        if kind == "json_ld":
            fragments.append(StructuredFragment("fragment:" + block.block_ref, block.block_ref, "json_ld", value))
            try:
                types.update(_json_types(value))
            except DocumentLimitError:
                parser.warnings.append("structured_fragment_limit")
            except (ValueError, RecursionError):
                parser.warnings.append("malformed_json_ld")
        if "itemprop" in node.attrs or "itemscope" in node.attrs:
            fragments.append(StructuredFragment("microdata:" + block.block_ref, block.block_ref, "microdata", node.attrs.get("content") or node.attrs.get("datetime") or value))
    if title is None:
        title = next((b.text for b in blocks if b.kind == "h1" and b.text), None)
    return SemanticDocument(
        "document:" + _ref(artifact, "/", "document").split(":", 1)[1], artifact, owner,
        source_locator, title, language, tuple(sorted(types)), tuple(blocks), tuple(metadata),
        tuple(fragments), tuple(links), tuple(forms), tuple(tables), tuple(dict.fromkeys(parser.warnings)),
    )


def parse_text_document(text: str, descriptor, *, source_locator: str | None = None, page_number: int | None = None) -> SemanticDocument:
    if len(text) > MAX_DOCUMENT_CHARS:
        raise DocumentLimitError("document text limit exceeded")
    blocks = []
    for index, line in enumerate(text.splitlines(), 1):
        value = clean_text(line)
        if not value:
            continue
        if len(blocks) >= MAX_DOCUMENT_NODES:
            raise DocumentLimitError("document block limit exceeded")
        locator = f"page:{page_number}:line:{index}" if page_number else f"line:{index}"
        blocks.append(SemanticBlock(
            _ref(descriptor.artifact_ref, locator, "line"), descriptor.artifact_ref,
            descriptor.observation_ref, "pdf_page" if page_number else "text_span",
            locator, "line", value, is_text=True, page_number=page_number,
        ))
    return SemanticDocument(
        "document:" + _ref(descriptor.artifact_ref, "/", "document").split(":", 1)[1],
        descriptor.artifact_ref, descriptor.observation_ref, source_locator,
        type_hints=("document",), blocks=tuple(blocks),
    )