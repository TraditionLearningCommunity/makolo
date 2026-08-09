from django import forms

from promotions.models import Promotion

from .models import LoyaltyProgram, LoyaltyReward, LoyaltyTier, MembershipPlan


INPUT = "w-full rounded-2xl border border-zinc-300 bg-white px-4 py-3 dark:border-zinc-700 dark:bg-zinc-900"


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "h-5 w-5 rounded border-zinc-300"
            else:
                field.widget.attrs["class"] = INPUT


class LoyaltyProgramForm(StyledModelForm):
    class Meta:
        model = LoyaltyProgram
        fields = ["name", "description", "points_name", "points_per_order", "points_per_ticket", "points_per_checkin", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class LoyaltyTierForm(StyledModelForm):
    class Meta:
        model = LoyaltyTier
        fields = ["name", "code", "threshold_points", "points_multiplier", "benefits", "is_active"]
        widgets = {"benefits": forms.Textarea(attrs={"rows": 3})}


class MembershipPlanForm(StyledModelForm):
    class Meta:
        model = MembershipPlan
        fields = ["name", "code", "description", "price", "currency", "duration_days", "points_multiplier", "join_bonus_points", "benefit_promotion", "benefits", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3}), "benefits": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["benefit_promotion"].queryset = Promotion.objects.filter(organization=organization).order_by("name")


class LoyaltyRewardForm(StyledModelForm):
    class Meta:
        model = LoyaltyReward
        fields = ["name", "description", "points_cost", "promotion", "fulfillment_instructions", "max_redemptions_per_member", "starts_at", "ends_at", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "fulfillment_instructions": forms.Textarea(attrs={"rows": 3}),
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["starts_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["ends_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        if organization:
            self.fields["promotion"].queryset = Promotion.objects.filter(organization=organization).order_by("name")


class PointsAdjustmentForm(forms.Form):
    points = forms.IntegerField(widget=forms.NumberInput(attrs={"class": INPUT}))
    reason = forms.CharField(max_length=255, widget=forms.TextInput(attrs={"class": INPUT}))
