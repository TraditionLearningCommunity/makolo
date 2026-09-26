# W — Web Desktop Experience — Closure contract

## Status

W is the desktop Presentation programme layered on the Mature Web experience. W1–W4 are merged on `main`; W5 and W6 close the remaining deep-workspace and desktop-accelerator work through their own PRs and CI gates.

This document records architectural decisions, not a substitute for the current GitHub state. The repository, tests and current PR checks remain authoritative.

## Responsive regimes

Makolo keeps one Web product with different compositions by available space.

- Compact: **< 768 CSS px** — phone/mobile Web, bottom navigation, no desktop rail.
- Adaptive: **768–1199 CSS px** — tablet and narrow desktop, compact desktop rail, no bottom navigation, primarily one main column.
- Expanded: **>= 1200 CSS px** — full desktop workspace, with simultaneous context only when that context helps the user act.

A narrow laptop must not fall back to a phone composition simply because it cannot sustain multiple panes. Adaptive is the desktop-like middle regime: it uses desktop navigation and accelerators without forcing Master/Detail, Explore or Inspect into insufficient width.

Expanded must never be interpreted as “make mobile cards wider”. It enables multi-pane compositions when the available width actually supports them.

## Canonical desktop compositions

W standardizes a small set of Presentation layouts:

- Focus — one main workspace.
- Master/Detail — list plus selected detail.
- Explore — discovery/results plus preview/context.
- Inspect — main object plus one contextual rail.

One persistent secondary zone is the normal maximum. Pages that gain nothing from a secondary zone remain Focus.

## Runtime

The canonical Web navigation remains Django templates + HTMX. W does not introduce a SPA router.

Direct URLs, refresh, browser back/forward, new tabs and server-rendered HTML remain valid.

The Z APIs are used selectively for secondary projections, previews or local refresh where they improve continuity. They are not used to reconstruct business state in the browser.

Private projection caches remain ephemeral and scoped. After a business mutation, the client invalidates/refetches rather than recomputing Readiness, Access, Permission, Mandate, Capacity or Payment.

## Deep workspaces

W5 applies Inspect only where the existing content benefits from simultaneous context:

- Journey / Démarche;
- Dossier;
- Project.

Access remains deliberately conservative because Access, AccessCredential and AccessUse have distinct security semantics. Activity/Event and the Space console already have useful desktop compositions and are not mechanically refactored.

Dossier remains an active composed objective. Project remains a durable horizon. Neither becomes a generic task manager, and composition never transfers authority.

## Desktop power layer

W6 adds accelerators, never hidden requirements.

The initial power layer is intentionally small:

- visible navigation-quick-access trigger;
- `Ctrl/Cmd+K` command palette;
- `?` help/quick navigation;
- arrow-key selection;
- Enter to open;
- Escape to close and restore focus.

Commands are derived from current server-rendered navigation. The palette does not maintain a second routing table and does not add network prefetch.

Drag & drop, context menus and multi-selection are excluded until a concrete owner-domain operation demonstrates a need.

## Accessibility and motion

Keyboard paths remain first-class. Modal focus stays contained and returns to the invoking control after close.

Any essential action keeps a visible non-shortcut path.

Animations stay short and functional and respect `prefers-reduced-motion`.

## Performance

W adds no frontend framework and no new product-wide dependency.

The first render remains server HTML. Secondary behavior is progressively enhanced. No page should download all Makolo data after login, and no desktop feature should create an artificial polling or prefetch flood.

## Closure gates

Before W is considered closed:

1. W5 and W6 must each have targeted tests.
2. Compact/mobile Web must remain usable without horizontal overflow.
3. Responsive boundaries must be explicitly covered: Compact around 400 px, Adaptive at 800 px and 1199 px, Expanded at 1200 px.
4. HTMX navigation, direct URLs and browser history must remain valid.
5. No migration or new business model may be introduced by W.
6. All applicable PR CI gates must be terminally green before merge.
7. Each PR must be reconciled with the current `main` before final merge.
8. The final `main` HEAD must be verified after W6 merge.
