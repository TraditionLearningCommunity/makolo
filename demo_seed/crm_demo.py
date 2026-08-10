from __future__ import annotations

from datetime import timedelta

from crm.models import (
    AudienceKind,
    AudienceSegment,
    CampaignAttribution,
    CampaignAttributionStatus,
    CampaignRecipient,
    CampaignRecipientStatus,
    CampaignTemplate,
    CommunicationCampaign,
    CommunicationCampaignStatus,
    CommunicationKind,
    CRMContact,
    CRMContactFieldValue,
    CRMContactNote,
    CRMContactTag,
    CRMCustomField,
    CRMTag,
    ContactSource,
    CustomFieldType,
    MarketingConsent,
)
from events.models import EventStatus
from tickets.models import TicketOrderStatus

from .common import SeedContext, backdate, choose, upsert


def _seed_crm(ctx: SeedContext) -> None:
    ctx.contacts.clear()
    ctx.crm_campaigns.clear()
    campaign_orders_used = set()
    for org_index, org in enumerate(ctx.organizations[:7]):
        owner = org.memberships.filter(role="owner", is_active=True).first().user
        org_events = [e for e in ctx.events if e.organization_id == org.id]
        primary_event = next((e for e in reversed(org_events) if e.status in {EventStatus.PUBLISHED, EventStatus.COMPLETED}), org_events[0] if org_events else None)

        tags = []
        for j, (name, color) in enumerate([
            ("VIP", "amber"), ("Participant régulier", "indigo"),
            ("À relancer", "rose"), ("Ambassadeur potentiel", "emerald"),
        ]):
            tags.append(upsert(CRMTag, f"org-{org_index}-tag-{j}", defaults={
                "organization": org, "name": name, "color": color, "created_by": owner,
            }))

        fields = []
        for j, spec in enumerate([
            ("secteur", "Secteur professionnel", CustomFieldType.SELECT, ["Tech", "Finance", "Mines", "Créatif", "Éducation"]),
            ("taille_entreprise", "Taille entreprise", CustomFieldType.NUMBER, []),
            ("interesse_sponsoring", "Intéressé par le sponsoring", CustomFieldType.BOOLEAN, []),
        ]):
            key, label, ftype, options = spec
            fields.append(upsert(CRMCustomField, f"org-{org_index}-field-{j}", defaults={
                "organization": org, "key": key, "label": label, "field_type": ftype,
                "options": options, "is_active": True, "created_by": owner,
            }))

        org_users, seen = [], set()
        for order in [o for o in ctx.orders if o.event.organization_id == org.id]:
            if order.buyer_id and order.buyer_id not in seen:
                org_users.append(order.buyer); seen.add(order.buyer_id)
        for follow in org.followers.select_related("user").all():
            if follow.user_id not in seen:
                org_users.append(follow.user); seen.add(follow.user_id)
        if len(org_users) < 16:
            org_users += [u for u in ctx.users if u.id not in seen][:16-len(org_users)]

        contacts = []
        for j, user in enumerate(org_users[:min(28, len(org_users))]):
            profile = getattr(user, "profile", None)
            contact = upsert(CRMContact, f"org-{org_index}-contact-{j}", defaults={
                "organization": org,
                "user": user,
                "email": user.email,
                "name": user.full_name,
                "phone": user.phone or "",
                "source": choose([ContactSource.TICKET_ORDER, ContactSource.FOLLOWER, ContactSource.TICKET, ContactSource.MANUAL], j),
                "marketing_consent": choose([MarketingConsent.SUBSCRIBED, MarketingConsent.SUBSCRIBED, MarketingConsent.UNKNOWN, MarketingConsent.UNSUBSCRIBED], j),
                "consent_source": "Formulaire événement" if j % 3 == 0 else "Compte Makolo",
                "consent_updated_at": ctx.as_of - timedelta(days=20+j) if j % 4 != 2 else None,
                "first_seen_at": ctx.as_of - timedelta(days=300 + (j * 17) % 500),
                "last_seen_at": ctx.as_of - timedelta(days=j % 45),
                "metadata": {"seed": "makolo-demo", "city": profile.city if profile else ""},
            })
            backdate(contact, created_at=contact.first_seen_at, updated_at=contact.last_seen_at)
            contacts.append(contact); ctx.contacts.append(contact)

            linked_tags = [tags[j % len(tags)], tags[(j + 1) % len(tags)]] if j % 4 == 0 else [tags[j % len(tags)]]
            for tag in linked_tags:
                link = upsert(CRMContactTag, f"org-{org_index}-contact-{j}-tag-{tag.id}", defaults={
                    "contact": contact, "tag": tag, "assigned_by": owner,
                })
                backdate(link, created_at=contact.first_seen_at + timedelta(days=4))

            values = [choose(fields[0].options, j), 1 + (j * 7) % 250, j % 5 == 0]
            for field, value in zip(fields, values):
                fv = upsert(CRMContactFieldValue, f"org-{org_index}-contact-{j}-field-{field.id}", defaults={
                    "contact": contact, "field": field, "value": value, "updated_by": owner,
                })
                backdate(fv, created_at=contact.first_seen_at + timedelta(days=6), updated_at=contact.last_seen_at)

            if j < 6:
                note = upsert(CRMContactNote, f"org-{org_index}-contact-{j}-note", defaults={
                    "contact": contact,
                    "author": owner,
                    "body": choose([
                        "A déjà participé à un événement et souhaite recevoir le prochain programme.",
                        "Contact corporate à relancer pour un pack groupe.",
                        "Bon retour lors du dernier événement, potentiel ambassadeur.",
                        "Préfère les communications WhatsApp et les rappels courts.",
                    ], j),
                })
                backdate(note, created_at=ctx.as_of - timedelta(days=80+j*5))

        if not contacts:
            continue

        segments = []
        for j, (name, kind, event, consent_only) in enumerate([
            ("Tous les contacts", AudienceKind.ALL, None, False),
            ("Abonnés engagés", AudienceKind.FOLLOWERS, None, True),
            ("Acheteurs confirmés", AudienceKind.CONFIRMED_BUYERS, primary_event, False),
            ("Participants présents", AudienceKind.ATTENDEES, primary_event, False),
        ]):
            segment = upsert(AudienceSegment, f"org-{org_index}-segment-{j}", defaults={
                "organization": org,
                "event": event,
                "ticket_type": event.ticket_types.first() if event and j == 2 else None,
                "name": name,
                "description": f"Segment de démonstration {name.lower()}.",
                "audience_kind": kind,
                "marketing_consent_only": consent_only,
                "city": org.city if j == 1 else "",
                "country": "CD" if j == 1 else "",
                "custom_filters": {"interesse_sponsoring": True} if j == 1 else {},
                "is_active": True,
                "created_by": owner,
            })
            if j == 1:
                segment.required_tags.set([tags[1]])
            segments.append(segment)

        templates = []
        for j, (name, kind, subject) in enumerate([
            ("Annonce nouvel événement", CommunicationKind.MARKETING, "Une nouvelle expérience Makolo vous attend"),
            ("Infos pratiques J-1", CommunicationKind.EVENT_UPDATE, "Votre événement : informations pratiques"),
        ]):
            templates.append(upsert(CampaignTemplate, f"org-{org_index}-template-{j}", defaults={
                "organization": org,
                "name": name,
                "kind": kind,
                "subject": subject,
                "preview_text": "Horaires, accès et informations essentielles.",
                "body": "Bonjour {{ contact_name }},\n\nRetrouvez les informations utiles pour votre prochaine expérience.\n\nÀ très bientôt.",
                "cta_label": "Voir l'événement",
                "cta_url": "https://makolo.pythonanywhere.com/",
                "is_active": True,
                "use_count": 4 + org_index,
                "created_by": owner,
            }))

        campaign_specs = [
            ("Campagne lancement", CommunicationCampaignStatus.SENT, CommunicationKind.MARKETING, segments[1], templates[0]),
            ("Rappel participants", CommunicationCampaignStatus.SCHEDULED, CommunicationKind.EVENT_UPDATE, segments[2], templates[1]),
            ("Relance communauté", CommunicationCampaignStatus.DRAFT, CommunicationKind.MARKETING, segments[0], templates[0]),
        ]
        for j, (name, status, kind, segment, template) in enumerate(campaign_specs):
            event = primary_event if kind == CommunicationKind.EVENT_UPDATE or j == 0 else None
            campaign = upsert(CommunicationCampaign, f"org-{org_index}-campaign-{j}", defaults={
                "organization": org, "segment": segment, "template": template, "event": event,
                "name": f"{name} {org_index+1}", "kind": kind, "subject": template.subject,
                "preview_text": template.preview_text, "body": template.body, "cta_label": template.cta_label,
                "cta_url": template.cta_url, "track_conversions": True, "attribution_window_days": 30,
                "status": status,
                "scheduled_at": ctx.as_of + timedelta(days=5+j) if status == CommunicationCampaignStatus.SCHEDULED else None,
                "started_at": ctx.as_of - timedelta(days=40+org_index) if status == CommunicationCampaignStatus.SENT else None,
                "completed_at": ctx.as_of - timedelta(days=39+org_index) if status == CommunicationCampaignStatus.SENT else None,
                "cancelled_at": None, "created_by": owner,
            })
            backdate(campaign, created_at=ctx.as_of - timedelta(days=80 + org_index*3+j), updated_at=ctx.as_of - timedelta(days=10+j))
            ctx.crm_campaigns.append(campaign)

            for k, contact in enumerate(contacts[:12]):
                recipient_status = choose([CampaignRecipientStatus.SENT, CampaignRecipientStatus.SENT, CampaignRecipientStatus.SKIPPED, CampaignRecipientStatus.FAILED], k) if status == CommunicationCampaignStatus.SENT else CampaignRecipientStatus.QUEUED
                recipient = upsert(CampaignRecipient, f"campaign-{org_index}-{j}-recipient-{k}", defaults={
                    "campaign": campaign, "contact": contact, "user": contact.user, "email": contact.email,
                    "name": contact.name, "status": recipient_status,
                    "attempts": 1 if recipient_status in {CampaignRecipientStatus.SENT, CampaignRecipientStatus.FAILED} else 0,
                    "max_attempts": 3, "scheduled_for": campaign.scheduled_at or campaign.started_at or ctx.as_of,
                    "last_error": "SMTP temporairement indisponible (démo)." if recipient_status == CampaignRecipientStatus.FAILED else "",
                    "skipped_reason": "Consentement marketing absent." if recipient_status == CampaignRecipientStatus.SKIPPED else "",
                    "sent_at": campaign.completed_at if recipient_status == CampaignRecipientStatus.SENT else None,
                    "click_count": 1 + (k % 3) if recipient_status == CampaignRecipientStatus.SENT and k % 2 == 0 else 0,
                    "first_clicked_at": campaign.completed_at + timedelta(hours=2) if campaign.completed_at and recipient_status == CampaignRecipientStatus.SENT and k % 2 == 0 else None,
                    "last_clicked_at": campaign.completed_at + timedelta(days=1) if campaign.completed_at and recipient_status == CampaignRecipientStatus.SENT and k % 2 == 0 else None,
                })
                backdate(recipient, created_at=campaign.created_at + timedelta(days=1), updated_at=ctx.as_of - timedelta(days=5))

            if status == CommunicationCampaignStatus.SENT and event:
                order = next((o for o in ctx.orders if o.event_id == event.id and o.status == TicketOrderStatus.CONFIRMED and o.id not in campaign_orders_used), None)
                if order:
                    campaign_orders_used.add(order.id)
                    contact = next((c for c in contacts if c.user_id == order.buyer_id), contacts[0])
                    recipient = campaign.recipients.filter(contact=contact).first()
                    upsert(CampaignAttribution, f"campaign-attr-{org_index}-{j}", defaults={
                        "order": order, "campaign": campaign, "recipient": recipient, "contact": contact,
                        "status": CampaignAttributionStatus.CONFIRMED, "revenue_amount": order.total_amount,
                        "currency": order.currency, "captured_at": order.created_at, "confirmed_at": order.confirmed_at,
                        "reversed_at": None,
                    })
