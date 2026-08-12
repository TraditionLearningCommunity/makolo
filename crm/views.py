from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import FormView, TemplateView

from authorization.constants import PermissionCode
from authorization.services import space_ids_with_permission
from organizations.models import Organization

from .forms import (
    AudienceSegmentForm,
    CampaignTemplateForm,
    CommunicationCampaignForm,
    ContactTagForm,
    CRMContactNoteForm,
    CRMCustomFieldForm,
    CRMTagForm,
    MarketingConsentForm,
)
from .models import (
    CampaignTemplate,
    CommunicationCampaignStatus,
    CRMContact,
    CRMContactFieldValue,
    CRMCustomField,
    CRMTag,
)
from .permissions import user_can_manage_crm, user_can_view_crm
from .selectors import (
    audience_contacts,
    campaign_metrics,
    get_campaigns_visible_to,
    get_contacts_visible_to,
    get_segments_visible_to,
)
from .services import (
    add_contact_note,
    assign_contact_tag,
    cancel_campaign,
    capture_campaign_click,
    create_campaign,
    create_campaign_template,
    create_custom_field,
    create_segment,
    create_tag,
    launch_campaign,
    remove_contact_tag,
    schedule_campaign,
    set_contact_custom_value,
    set_marketing_consent,
    sync_organization_contacts,
    unsubscribe_from_token,
)


class CRMHomeView(LoginRequiredMixin, TemplateView):
    template_name = "crm/dashboard.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization_ids = space_ids_with_permission(self.request.user, PermissionCode.CRM_VIEW)
        organizations = Organization.objects.all().order_by("name")
        if organization_ids is not None:
            organizations = organizations.filter(pk__in=organization_ids)
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
            raise PermissionDenied("Vous n’avez pas accès au CRM de cet Espace.")
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
                "templates": CampaignTemplate.objects.filter(organization=organization).order_by("name")[:20],
                "tags": CRMTag.objects.filter(organization=organization).order_by("name")[:30],
                "custom_fields": CRMCustomField.objects.filter(organization=organization).order_by("label")[:30],
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
        values_by_field = {
            record.field_id: record
            for record in contact.custom_values.select_related("field", "updated_by").all()
        }
        field_rows = []
        for field in CRMCustomField.objects.filter(organization=contact.organization, is_active=True).order_by("label"):
            field_rows.append({"field": field, "record": values_by_field.get(field.pk)})
        context.update(
            {
                "contact": contact,
                "notes": contact.notes.select_related("author").all(),
                "tag_links": contact.tag_links.select_related("tag", "assigned_by").all(),
                "tag_form": ContactTagForm(organization=contact.organization),
                "custom_field_rows": field_rows,
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


class ContactTagAssignView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        contact = get_object_or_404(get_contacts_visible_to(request.user), pk=pk)
        form = ContactTagForm(request.POST, organization=contact.organization)
        if form.is_valid():
            assign_contact_tag(contact=contact, tag=form.cleaned_data["tag"], actor=request.user)
            messages.success(request, "Tag ajouté au contact.")
        else:
            messages.error(request, "Tag invalide.")
        return redirect("crm:contact-detail", pk=contact.pk)


class ContactTagRemoveView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk, tag_id):
        contact = get_object_or_404(get_contacts_visible_to(request.user), pk=pk)
        tag = get_object_or_404(CRMTag, pk=tag_id, organization=contact.organization)
        remove_contact_tag(contact=contact, tag=tag, actor=request.user)
        messages.success(request, "Tag retiré du contact.")
        return redirect("crm:contact-detail", pk=contact.pk)


class ContactCustomValueUpdateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk, field_id):
        contact = get_object_or_404(get_contacts_visible_to(request.user), pk=pk)
        field = get_object_or_404(CRMCustomField, pk=field_id, organization=contact.organization, is_active=True)
        try:
            set_contact_custom_value(contact=contact, field=field, actor=request.user, value=request.POST.get("value"))
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, f"Champ « {field.label} » mis à jour.")
        return redirect("crm:contact-detail", pk=contact.pk)


class CRMTagCreateView(LoginRequiredMixin, FormView):
    template_name = "crm/form.html"
    form_class = CRMTagForm
    login_url = "core:login"

    def _organization(self):
        organization = get_object_or_404(Organization, slug=self.kwargs["slug"])
        if not user_can_manage_crm(self.request.user, organization):
            raise PermissionDenied("Vous n’avez pas le droit de créer des tags CRM.")
        return organization

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"organization": self._organization(), "heading": "Nouveau tag CRM", "submit_label": "Créer le tag"})
        return context

    def form_valid(self, form):
        tag = create_tag(organization=self._organization(), actor=self.request.user, **form.cleaned_data)
        messages.success(self.request, "Tag CRM créé.")
        return redirect("crm:organization", slug=tag.organization.slug)


class CRMCustomFieldCreateView(LoginRequiredMixin, FormView):
    template_name = "crm/form.html"
    form_class = CRMCustomFieldForm
    login_url = "core:login"

    def _organization(self):
        organization = get_object_or_404(Organization, slug=self.kwargs["slug"])
        if not user_can_manage_crm(self.request.user, organization):
            raise PermissionDenied("Vous n’avez pas le droit de créer des champs CRM.")
        return organization

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"organization": self._organization(), "heading": "Nouveau champ CRM", "submit_label": "Créer le champ"})
        return context

    def form_valid(self, form):
        field = create_custom_field(
            organization=self._organization(),
            actor=self.request.user,
            key=form.cleaned_data["key"],
            label=form.cleaned_data["label"],
            field_type=form.cleaned_data["field_type"],
            options=form.cleaned_data.get("options", []),
        )
        messages.success(self.request, "Champ CRM créé.")
        return redirect("crm:organization", slug=field.organization.slug)


class CampaignTemplateCreateView(LoginRequiredMixin, FormView):
    template_name = "crm/form.html"
    form_class = CampaignTemplateForm
    login_url = "core:login"

    def _organization(self):
        organization = get_object_or_404(Organization, slug=self.kwargs["slug"])
        if not user_can_manage_crm(self.request.user, organization):
            raise PermissionDenied("Vous n’avez pas le droit de créer des modèles de campagne.")
        return organization

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"organization": self._organization(), "heading": "Nouveau modèle de campagne", "submit_label": "Enregistrer le modèle"})
        return context

    def form_valid(self, form):
        template = create_campaign_template(organization=self._organization(), actor=self.request.user, **form.cleaned_data)
        messages.success(self.request, "Modèle de campagne créé.")
        return redirect("crm:organization", slug=template.organization.slug)


class CampaignTemplateEditView(LoginRequiredMixin, View):
    template_name = "crm/form.html"
    login_url = "core:login"

    def _template(self, request, pk):
        template = get_object_or_404(CampaignTemplate.objects.select_related("organization"), pk=pk)
        if not user_can_manage_crm(request.user, template.organization):
            raise PermissionDenied("Vous n’avez pas le droit de modifier ce modèle.")
        return template

    def get(self, request, pk):
        template = self._template(request, pk)
        return render(request, self.template_name, {"organization": template.organization, "heading": "Modifier le modèle", "submit_label": "Enregistrer", "form": CampaignTemplateForm(instance=template)})

    def post(self, request, pk):
        template = self._template(request, pk)
        form = CampaignTemplateForm(request.POST, instance=template)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.full_clean()
            obj.save()
            messages.success(request, "Modèle de campagne mis à jour.")
            return redirect("crm:organization", slug=template.organization.slug)
        return render(request, self.template_name, {"organization": template.organization, "heading": "Modifier le modèle", "submit_label": "Enregistrer", "form": form}, status=400)


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

    def get_initial(self):
        initial = super().get_initial()
        template_id = self.request.GET.get("template")
        if template_id:
            template = CampaignTemplate.objects.filter(pk=template_id, organization=self._organization(), is_active=True).first()
            if template:
                initial.update({
                    "template": template,
                    "kind": template.kind,
                    "subject": template.subject,
                    "preview_text": template.preview_text,
                    "body": template.body,
                    "cta_label": template.cta_label,
                    "cta_url": template.cta_url,
                })
        return initial

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


class CampaignClickView(View):
    def get(self, request, token):
        try:
            recipient = capture_campaign_click(request=request, token=token)
        except ValidationError as exc:
            raise Http404("Lien de campagne invalide ou expiré.") from exc
        return redirect(recipient.campaign.cta_url)


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
