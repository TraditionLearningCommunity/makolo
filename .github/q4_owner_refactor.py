from pathlib import Path


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write(path, content):
    Path(path).write_text(content, encoding="utf-8")


req_models = read("requirements/models.py")
policy_start = req_models.index("class RequirementReusePolicy(models.Model):")
app_start = req_models.index("class RequirementReuseApplication(models.Model):")
policy_block = req_models[policy_start:app_start].rstrip()
application_block = req_models[app_start:].rstrip()

# Horizontal Requirements keeps only pure contracts/enums and no domain persistence.
trusted = read("requirements/trusted_reuse.py")
if "class RequirementReuseSource(str, Enum):" not in trusted:
    source_enum = '''class RequirementReuseSource(str, Enum):\n    LIBRARY = "library"\n    JOURNEY_ARTIFACT = "journey_artifact"\n    PROOF = "proof"\n\n\n'''
    trusted = trusted.replace("class TrustedReuseDecisionCode(str, Enum):\n", source_enum + "class TrustedReuseDecisionCode(str, Enum):\n")
write("requirements/trusted_reuse.py", trusted)

write(
    "requirements/apps.py",
    '''from django.apps import AppConfig\n\n\nclass RequirementsConfig(AppConfig):\n    default_auto_field = "django.db.models.BigAutoField"\n    name = "requirements"\n    verbose_name = "Requirements"\n''',
)

for name in [
    "requirements/models.py",
    "requirements/admin.py",
    "requirements/signals.py",
    "requirements/migrations/0001_trusted_reuse_policy.py",
    "requirements/migrations/0002_trusted_reuse_application.py",
    "requirements/migrations/__init__.py",
]:
    path = Path(name)
    if path.exists():
        path.unlink()
path = Path("requirements/migrations")
if path.exists() and not any(path.iterdir()):
    path.rmdir()

# Policy belongs to Opportunities: it is explicitly scoped to OpportunityRequirement.
policy_block = policy_block.replace(
    'requirement = models.ForeignKey(\n        "opportunities.OpportunityRequirement",',
    'requirement = models.ForeignKey(\n        OpportunityRequirement,',
)
policy_block = policy_block.replace(
    'source_type = models.CharField(max_length=24, choices=RequirementReuseSource.choices)',
    'source_type = models.CharField(\n        max_length=24,\n        choices=[\n            (RequirementReuseSource.LIBRARY.value, "Ma Bibliothèque"),\n            (RequirementReuseSource.JOURNEY_ARTIFACT.value, "JourneyArtifact historique"),\n            (RequirementReuseSource.PROOF.value, "Proof Trust"),\n        ],\n    )',
)
policy_block = policy_block.replace(
    'artifact_kind = models.CharField(max_length=32, choices=JourneyArtifactKind.choices, blank=True)',
    'artifact_kind = models.CharField(max_length=32, blank=True)',
)
policy_block = policy_block.replace(
    'proof_type = models.CharField(max_length=32, choices=ProofType.choices, blank=True)',
    'proof_type = models.CharField(max_length=32, blank=True)',
)
policy_block = policy_block.replace("RequirementReuseSource.PROOF", "RequirementReuseSource.PROOF.value")
policy_block = policy_block.replace('name="req_reuse_policy_key_unique"', 'name="opp_req_reuse_policy_key_unique"')
policy_block = policy_block.replace('name="req_reuse_policy_src_idx"', 'name="opp_req_reuse_policy_src_idx"')
queryset_code = '''class RequirementReusePolicyQuerySet(models.QuerySet):\n    def delete(self):\n        if self.filter(requirement__revision__published_at__isnull=False).exists():\n            raise ValidationError("La policy d’un Requirement publié ne peut pas être supprimée.")\n        return super().delete()\n\n\n'''
policy_block = queryset_code + policy_block
policy_block = policy_block.replace(
    '    class Meta:\n',
    '    objects = RequirementReusePolicyQuerySet.as_manager()\n\n    class Meta:\n',
    1,
)

opp = read("opportunities/models.py")
if "from requirements.trusted_reuse import RequirementReuseSource" not in opp:
    opp = opp.replace(
        "from geography.validators import validate_timezone_name\n",
        "from geography.validators import validate_timezone_name\nfrom requirements.trusted_reuse import RequirementReuseSource\n",
    )
if "class RequirementReusePolicy(models.Model):" not in opp:
    opp = opp.replace("\n\nclass OpportunitySave(models.Model):", "\n\n" + policy_block + "\n\nclass OpportunitySave(models.Model):")
write("opportunities/models.py", opp)

# Application audit belongs to Services: it records application to Assessment/Evidence.
application_block = application_block.replace(
    'policy = models.ForeignKey(\n        RequirementReusePolicy,',
    'policy = models.ForeignKey(\n        "opportunities.RequirementReusePolicy",',
)
application_block = application_block.replace(
    'source_type = models.CharField(max_length=24, choices=RequirementReuseSource.choices)',
    'source_type = models.CharField(\n        max_length=24,\n        choices=[\n            (RequirementReuseSource.LIBRARY.value, "Ma Bibliothèque"),\n            (RequirementReuseSource.JOURNEY_ARTIFACT.value, "JourneyArtifact historique"),\n            (RequirementReuseSource.PROOF.value, "Proof Trust"),\n        ],\n    )',
)
application_block = application_block.replace("RequirementReuseSource.LIBRARY:", "RequirementReuseSource.LIBRARY.value:")
application_block = application_block.replace("RequirementReuseSource.JOURNEY_ARTIFACT:", "RequirementReuseSource.JOURNEY_ARTIFACT.value:")
application_block = application_block.replace("RequirementReuseSource.PROOF:", "RequirementReuseSource.PROOF.value:")
application_block = application_block.replace("RequirementReuseSource.PROOF and", "RequirementReuseSource.PROOF.value and")
for old, new in [
    ("req_reuse_app_one_source", "svc_reuse_app_one_source"),
    ("req_reuse_app_asset_unique", "svc_reuse_app_asset_unique"),
    ("req_reuse_app_art_unique", "svc_reuse_app_art_unique"),
    ("req_reuse_app_proof_unique", "svc_reuse_app_proof_unique"),
    ("req_reuse_app_assess_idx", "svc_reuse_app_assess_idx"),
    ("req_reuse_app_policy_idx", "svc_reuse_app_policy_idx"),
]:
    application_block = application_block.replace(old, new)

svc = read("services/models.py")
if "from requirements.trusted_reuse import RequirementReuseSource" not in svc:
    svc = svc.replace(
        "from requirements.contracts import RequirementAssessmentState\n",
        "from requirements.contracts import RequirementAssessmentState\nfrom requirements.trusted_reuse import RequirementReuseSource\n",
    )
if "class RequirementReuseApplication(models.Model):" not in svc:
    svc = svc.rstrip() + "\n\n\n" + application_block + "\n"
write("services/models.py", svc)

runtime = read("services/trusted_reuse.py")
runtime = runtime.replace(
    "from requirements.models import RequirementReuseApplication, RequirementReusePolicy, RequirementReuseSource\nfrom requirements.trusted_reuse import TrustedReuseDecision, TrustedReuseDecisionCode, TrustedReuseReasonCode\n",
    "from opportunities.models import RequirementReusePolicy\nfrom requirements.trusted_reuse import RequirementReuseSource, TrustedReuseDecision, TrustedReuseDecisionCode, TrustedReuseReasonCode\n",
)
runtime = runtime.replace(
    "from .models import ServiceRequirementAssessment\n",
    "from .models import RequirementReuseApplication, ServiceRequirementAssessment\n",
)
write("services/trusted_reuse.py", runtime)

# Move policy tests to their owner domain; keep horizontal boundary tests strict.
old_test = Path("requirements/test_q4_trusted_reuse_policy.py")
if old_test.exists():
    test = old_test.read_text(encoding="utf-8")
    test = test.replace(
        "from requirements.models import RequirementReusePolicy, RequirementReuseSource\n",
        "from opportunities.models import RequirementReusePolicy\nfrom requirements.trusted_reuse import RequirementReuseSource\n",
    )
    write("opportunities/test_q4_trusted_reuse_policy.py", test)
    old_test.unlink()

# Move admin surfaces to their owners.
opp_admin = read("opportunities/admin.py")
if "    RequirementReusePolicy,\n" not in opp_admin:
    opp_admin = opp_admin.replace("    OpportunityRequirement,\n", "    OpportunityRequirement,\n    RequirementReusePolicy,\n")
if "@admin.register(RequirementReusePolicy)" not in opp_admin:
    opp_admin += '''\n\n@admin.register(RequirementReusePolicy)\nclass RequirementReusePolicyAdmin(admin.ModelAdmin):\n    list_display = ("requirement", "key", "source_type", "artifact_kind", "proof_type", "human_review_required", "created_at")\n    list_filter = ("source_type", "human_review_required", "require_not_expired")\n    search_fields = ("key", "requirement__title")\n    readonly_fields = ("created_at",)\n\n    def has_change_permission(self, request, obj=None):\n        if obj is not None:\n            return False\n        return super().has_change_permission(request, obj=obj)\n\n    def has_delete_permission(self, request, obj=None):\n        if obj is not None and obj.requirement.revision.published_at is not None:\n            return False\n        return super().has_delete_permission(request, obj=obj)\n'''
write("opportunities/admin.py", opp_admin)

svc_admin = read("services/admin.py")
if "    RequirementReuseApplication,\n" not in svc_admin:
    svc_admin = svc_admin.replace("    ServiceRequirementAssessment,\n", "    RequirementReuseApplication,\n    ServiceRequirementAssessment,\n")
if "@admin.register(RequirementReuseApplication)" not in svc_admin:
    svc_admin += '''\n\n@admin.register(RequirementReuseApplication)\nclass RequirementReuseApplicationAdmin(admin.ModelAdmin):\n    list_display = ("assessment", "source_type", "policy", "decision", "applied_by", "applied_at")\n    list_filter = ("source_type", "decision", "confirmation_confirmed")\n    search_fields = ("policy__key",)\n    readonly_fields = [field.name for field in RequirementReuseApplication._meta.fields]\n\n    def has_add_permission(self, request):\n        return False\n\n    def has_change_permission(self, request, obj=None):\n        return False\n\n    def has_delete_permission(self, request, obj=None):\n        return False\n'''
write("services/admin.py", svc_admin)

for wf_name in [".github/workflows/q4-trusted-reuse-validation.yml", ".github/workflows/q4-checkpoint-validation.yml"]:
    wf = Path(wf_name)
    if wf.exists():
        write(wf, read(wf_name).replace("requirements.test_q4_trusted_reuse_policy", "opportunities.test_q4_trusted_reuse_policy"))
