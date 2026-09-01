# Makolo Product Signature System

## Principle

Makolo must remain recognizable in the product even when the primary violet is absent. The brand is therefore carried by a small set of reusable product signatures: the official Makolo Mark, monochrome QR treatment, Access presentation, scanner language, empty states, confirmation states and restrained motion.

The domain model remains authoritative. Branding is presentation only.

## Official assets

Only the canonical assets under `static/brand/` may represent Makolo. The reusable Mark partial is `templates/partials/brand_mark.html`.

Primary variants:

- `makolo-mark-ink.svg` for monochrome/light surfaces and QR-related presentation;
- `makolo-mark-white.svg` for dark brand surfaces;
- `makolo-mark-violet.svg` when the brand color is appropriate;
- `makolo-mark-gradient.svg` for selected expressive surfaces.

Do not redraw the Mark, synthesize a letter M, or create vertical-specific replicas.

## Palette

The existing Makolo design tokens remain canonical. The reference values are:

- primary violet: `#5232DB`;
- deep violet: `#2B176E`;
- coral: `#FF704D`;
- light text: `#FAF7F5`;
- dark/ink text: `#0F172A`.

The signature must still work in monochrome.

## Makolo QR

`core.branding.render_makolo_qr_png()` is a presentation renderer. It never creates, signs, rotates or validates credentials.

For canonical Access QR codes, the flow remains:

`Access -> AccessCredential -> render_access_credential() -> Makolo QR renderer`

The renderer uses:

- black/ink modules on white;
- QR error correction level H;
- a four-module quiet zone;
- the official Ink Mark centered on a small white safety plate;
- a fallback to the same high-correction QR without the Mark if the official asset cannot be rendered.

Never place secrets, salts, signing material or human references in the visible branding layer. Never change the signed payload to add branding.

The participant/scanner E2E flow is the definitive scannability contract: it captures the displayed Access QR as an image and submits that image to Makolo Scanner. A branding change that breaks that flow must not be merged.

## Access signature

Personal Access surfaces may display the Mark, contextual vocabulary and status together. The user-facing nouns remain contextual (`Billet`, `Confirmation`, `Invitation`, `Réservation`) while the backend continues to use canonical Access models.

The Mark must not imply a new authority. Event/Ticket remains a vertical projection and must not replace `AccessCredential` as the canonical credential source.

Human-readable short references are intentionally deferred until an unambiguous collision-safe contract can be defined without creating a second business identifier. The existing canonical identifier may remain visible for support in the meantime.

## Scanner signature

The scanner already exposes canonical server decisions and must keep doing so. Product branding may strengthen hierarchy and identity, but JavaScript must never invent or override validation status.

Required user-visible states include valid, already used, expired, revoked, wrong context and invalid/unknown credential. Success and failure must be communicated with text/symbols, not color alone.

## Empty states

`templates/partials/brand_empty.html` is the shared lightweight Makolo empty-state primitive. It combines the official Mark, useful copy and an optional action. Empty states should be calm product guidance, not advertising.

## Motion

Makolo motion is deliberately limited. `mk-brand-enter` provides a short entry/confirmation movement. All brand motion must respect `prefers-reduced-motion` and must never be required to understand state.

Do not add confetti, heavy animation libraries or decorative motion that delays an operational action.

## Printing and generated surfaces

The browser print/PDF representation of an Access includes the same official Mark and branded QR as the on-screen Access. Existing generated surfaces should be branded by composition, not by creating new domain models or a new document engine.

Additional legacy or marketing QR producers may adopt the shared renderer only when doing so does not change their owning domain contract. Canonical Access remains the priority.

## Verification

Organization verification is a real business concept in Makolo, but the Mark itself must not be used as a generic trust or quality badge. A dedicated verification treatment may only be introduced when its scope, evidence and user meaning are explicit.

## Accessibility

- decorative Marks are hidden from assistive technology;
- meaningful brand images need useful labels;
- QR codes keep maximum contrast;
- status never depends on color alone;
- motion respects reduced-motion preferences;
- Mark dimensions remain stable to avoid layout shifts.

## Prohibited uses

Do not create `BrandedAccess`, `BrandedTicket`, `BrandCredential`, a separate Makolo QR business entity, or any other model whose only purpose is presentation. Do not duplicate Access, status, permissions, capacity, payment or ticket truth inside Event or another vertical.
