from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import FormView, TemplateView

from organizations.models import Organization

from .customer360 import customer_360, customer_timeline, segment_behavior_filters
from .customer_forms import BehavioralSegmentForm
from .forms import ContactTagForm, CRMContactNoteForm, MarketingConsentForm
from .models import CRMCustomField
from .permissions import (
    user_can_manage_crm,
    user_can_view_customer_360_financials,
    user_can_view_crm,
)
from .selectors import audience_contacts, get_contacts_visible_to, get_segments_visible_to
from .services import create_segment, sync_organization_contacts


class Contact360DetailView(LoginRequiredMixin, TemplateView):
    template_name = "crm/contact_360.html"
    login_url = "core:login"

    def _contact(self):
        return get_object_or_404(get_contacts_visible_to(self.request.user), pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contact = self._contact()
        include_financials = user_can_view_customer_360_financials(
            self.request.user,
            contact.organization,
        )
        values_by_field = {
            record.field_id: record
            for record in contact.custom_values.select_related("field", "updated_by").all()
        }
        field_rows = []
        for field in CRMCustomField.objects.filter(
            organization=contact.organization,
            is_active=True,
        ).order_by("label"):
            field_rows.append({"field": field, "record": values_by_field.get(field.pk)})

        context.update(
            {
                "contact": contact,
                "customer360": customer_360(contact, include_financials=include_financials),
                "timeline": customer_timeline(contact, include_financials=include_financials, limit=120),
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
                "can_view_financials": include_financials,
            }
        )
        return context


class Segment360CreateView(LoginRequiredMixin, FormView):
    template_name = "crm/segment_form.html"
    form_class = BehavioralSegmentForm
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
        context.update(
            {
                "organization": self._organization(),
                "heading": "Nouveau segment dynamique",
                "submit_label": "Créer le segment",
                "editing": False,
            }
        )
        return context

    def form_valid(self, form):
        organization = self._organization()
        data = {name: form.cleaned_data[name] for name in form.Meta.fields}
        segment = create_segment(
            organization=organization,
            actor=self.request.user,
            **data,
        )
        messages.success(self.request, "Segment CRM comportemental créé.")
        return redirect("crm:segment-detail", pk=segment.pk)


class Segment360EditView(LoginRequiredMixin, FormView):
    template_name = "crm/segment_form.html"
    form_class = BehavioralSegmentForm
    login_url = "core:login"

    def _segment(self):
        segment = get_object_or_404(get_segments_visible_to(self.request.user), pk=self.kwargs["pk"])
        if not user_can_manage_crm(self.request.user, segment.organization):
            raise PermissionDenied("Vous n’avez pas le droit de modifier ce segment CRM.")
        return segment

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        self.segment = self._segment()
        kwargs["organization"] = self.segment.organization
        kwargs["instance"] = self.segment
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        segment = getattr(self, "segment", None) or self._segment()
        context.update(
            {
                "organization": segment.organization,
                "segment": segment,
                "heading": f"Modifier {segment.name}",
                "submit_label": "Enregistrer",
                "editing": True,
            }
        )
        return context

    def form_valid(self, form):
        segment = form.save(commit=False)
        if not user_can_manage_crm(self.request.user, segment.organization):
            raise PermissionDenied("Vous n’avez pas le droit de modifier ce segment CRM.")
        segment.full_clean()
        segment.save()
        form.save_m2m()
        messages.success(self.request, "Segment CRM mis à jour.")
        return redirect("crm:segment-detail", pk=segment.pk)


class Segment360DetailView(LoginRequiredMixin, TemplateView):
    template_name = "crm/segment_360.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        segment = get_object_or_404(get_segments_visible_to(self.request.user), pk=self.kwargs["pk"])
        if not user_can_view_crm(self.request.user, segment.organization):
            raise PermissionDenied("Vous n’avez pas accès à ce segment CRM.")
        sync_organization_contacts(segment.organization)
        contacts = audience_contacts(segment)
        context.update(
            {
                "segment": segment,
                "behavior_filters": segment_behavior_filters(segment),
                "audience_count": contacts.count(),
                "contacts": contacts[:100],
                "can_manage": user_can_manage_crm(self.request.user, segment.organization),
            }
        )
        return context
