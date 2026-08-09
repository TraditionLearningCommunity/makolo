from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import FormView, TemplateView

from organizations.models import Organization, OrganizationMembership

from .forms import (
    AudienceSegmentForm,
    CommunicationCampaignForm,
    CRMContactNoteForm,
    MarketingConsentForm,
)
from .models import CommunicationCampaignStatus, CRMContact
from .permissions import CRM_VIEW_ROLES, user_can_manage_crm, user_can_view_crm
from .selectors import (
    audience_contacts,
    campaign_metrics,
    get_campaigns_visible_to,
    get_contacts_visible_to,
    get_segments_visible_to,
)
from .services import (
    add_contact_note,
    cancel_campaign,
    create_campaign,
    create_segment,
    launch_campaign,
    schedule_campaign,
    set_marketing_consent,
    sync_organization_contacts,
    unsubscribe_from_token,
)


class CRMHomeView(LoginRequiredMixin, TemplateView):
    template_name = "crm/dashboard.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_staff:
            organizations = Organization.objects.all().order_by("name")
        else:
            organization_ids = OrganizationMembership.objects.filter(
                user=self.request.user,
                is_active=True,
                role__in=CRM_VIEW_ROLES,
            ).values_list("organization_id", flat=True)
            organizations = Organization.objects.filter(pk__in=organization_ids).order_by("name")
        context["organizations"] = organizations
        context["contacts_count"] = get_contacts_visible_to(self.request.user).count()
        context["segments_count"] = get_segments_visible_to(self.request.user).filter(is_active=True).count()
        context["campaigns_count"] = get_campaigns_visible_to(self.request.user).count()
        return context


class OrganizationCRMView(LoginRequiredMixin, TemplateView):
    template_name = "crm/organization.html"
    login_url = "core:login"

    def _organization(self):
        organization = get_object_or_404(Organization, slug=self.kwargs["slug"])
        if not user_can_view_crm(self.request.user, organization):
            raise PermissionDenied("Vous n’avez pas accès au CRM de cette organisation.")
        return organization

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self._organization()
        sync_organization_contacts(organization)
        contacts = CRMContact.objects.filter(organization=organization).select_related("user")
        query = (self.request.GET.get("q") or "").strip()
        if query:
            contacts = contacts.filter(Q(name__icontains=query) | Q(email__icontains=query) | Q(phone__icontains=query))
        context.update(
            {
                "organization": organization,
                "contacts": contacts.order_by("-last_seen_at")[:100],
                "contacts_count": CRMContact.objects.filter(organization=organization).count(),
                "segments": get_segments_visible_to(self.request.user).filter(organization=organization)[:20],
                "campaigns": get_campaigns_visible_to(self.request.user).filter(organization=organization)[:20],
                "can_manage": user_can_manage_crm(self.request.user, organization),
                "query": query,
            }
        )
        return context


class ContactDetailView(LoginRequiredMixin, TemplateView):
    template_name = "crm/contact_detail.html"
    login_url = "core:login"

    def _contact(self):
        return get_object_or_404(get_contacts_visible_to(self.request.user), pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contact = self._contact()
        context.update(
            {
                "contact": contact,
                "notes": contact.notes.select_related("author").all(),
                "note_form": CRMContactNoteForm(),
                "consent_form": MarketingConsentForm(
                    initial={
                        "subscribed": contact.marketing_consent == "subscribed",
                        "source": contact.consent_source,
                    }
                ),
                "can_manage": user_can_manage_crm(self.request.user, contact.organization),
            }
        )
        return context


class ContactNoteCreateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        contact = get_object_or_404(get_contacts_visible_to(request.user), pk=pk)
        form = CRMContactNoteForm(request.POST)
        if form.is_valid():
            add_contact_note(contact=contact, actor=request.user, body=form.cleaned_data["body"])
            messages.success(request, "Note CRM ajoutée.")
        else:
            messages.error(request, "La note est invalide.")
        return redirect("crm:contact-detail", pk=contact.pk)


class ContactConsentUpdateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        contact = get_object_or_404(get_contacts_visible_to(request.user), pk=pk)
        form = MarketingConsentForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Le consentement n’a pas été modifié : vérifiez sa source.")
            return redirect("crm:contact-detail", pk=contact.pk)
        set_marketing_consent(
            contact=contact,
            actor=request.user,
            subscribed=form.cleaned_data["subscribed"],
            source=form.cleaned_data.get("source", ""),
        )
        messages.success(request, "Consentement marketing mis à jour.")
        return redirect("crm:contact-detail", pk=contact.pk)


class SegmentCreateView(LoginRequiredMixin, FormView):
    template_name = "crm/form.html"
    form_class = AudienceSegmentForm
    login_url = "core:login"

    def _organization(self):
        organization = get_object_or_404(Organization, slug=self.kwargs["slug"])
        if not user_can_manage_crm(self.request.user, organization):
            raise PermissionDenied("Vous n’avez pas le droit de créer des segments CRM.")
        return organization

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self._organization()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"organization": self._organization(), "heading": "Nouveau segment", "submit_label": "Créer le segment"})
        return context

    def form_valid(self, form):
        organization = self._organization()
        data = {name: form.cleaned_data[name] for name in form.Meta.fields}
        segment = create_segment(organization=organization, actor=self.request.user, **data)
        messages.success(self.request, "Segment CRM créé.")
        return redirect("crm:segment-detail", pk=segment.pk)


class SegmentDetailView(LoginRequiredMixin, TemplateView):
    template_name = "crm/segment_detail.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        segment = get_object_or_404(get_segments_visible_to(self.request.user), pk=self.kwargs["pk"])
        sync_organization_contacts(segment.organization)
        contacts = audience_contacts(segment)
        context.update(
            {
                "segment": segment,
                "audience_count": contacts.count(),
                "contacts": contacts[:100],
                "can_manage": user_can_manage_crm(self.request.user, segment.organization),
            }
        )
        return context


class CampaignCreateView(LoginRequiredMixin, FormView):
    template_name = "crm/form.html"
    form_class = CommunicationCampaignForm
    login_url = "core:login"

    def _organization(self):
        organization = get_object_or_404(Organization, slug=self.kwargs["slug"])
        if not user_can_manage_crm(self.request.user, organization):
            raise PermissionDenied("Vous n’avez pas le droit de créer des campagnes CRM.")
        return organization

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self._organization()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"organization": self._organization(), "heading": "Nouvelle campagne", "submit_label": "Créer la campagne"})
        return context

    def form_valid(self, form):
        organization = self._organization()
        scheduled_at = form.cleaned_data.pop("scheduled_at", None)
        data = {name: form.cleaned_data[name] for name in form.Meta.fields}
        campaign = create_campaign(organization=organization, actor=self.request.user, **data)
        if scheduled_at:
            try:
                schedule_campaign(campaign=campaign, actor=self.request.user, scheduled_at=scheduled_at)
            except ValidationError as exc:
                form.add_error("scheduled_at", exc.messages[0])
                campaign.delete()
                return self.form_invalid(form)
        messages.success(self.request, "Campagne CRM créée.")
        return redirect("crm:campaign-detail", pk=campaign.pk)


class CampaignDetailView(LoginRequiredMixin, TemplateView):
    template_name = "crm/campaign_detail.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        campaign = get_object_or_404(get_campaigns_visible_to(self.request.user), pk=self.kwargs["pk"])
        sync_organization_contacts(campaign.organization)
        audience = audience_contacts(campaign.segment)
        context.update(
            {
                "campaign": campaign,
                "metrics": campaign_metrics(campaign),
                "preview_count": audience.count(),
                "recipients": campaign.recipients.select_related("contact").all()[:100],
                "can_manage": user_can_manage_crm(self.request.user, campaign.organization),
            }
        )
        return context


class CampaignSendView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        campaign = get_object_or_404(get_campaigns_visible_to(request.user), pk=pk)
        try:
            launch_campaign(campaign=campaign, actor=request.user)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, "Campagne placée dans la file d’envoi. Autopilot assure la livraison et les retries.")
        return redirect("crm:campaign-detail", pk=campaign.pk)


class CampaignCancelView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        campaign = get_object_or_404(get_campaigns_visible_to(request.user), pk=pk)
        try:
            cancel_campaign(campaign=campaign, actor=request.user)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, "Campagne annulée.")
        return redirect("crm:campaign-detail", pk=campaign.pk)


class UnsubscribeView(TemplateView):
    template_name = "crm/unsubscribe.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            contact = unsubscribe_from_token(self.kwargs["token"])
        except ValidationError:
            context["invalid"] = True
        else:
            context["contact"] = contact
        return context
