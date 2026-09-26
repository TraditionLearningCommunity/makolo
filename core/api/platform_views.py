from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authorization.constants import PLATFORM_PERMISSION_CODES, PermissionCode
from authorization.services import effective_permission_codes


def _module(key, *, capabilities, status="active", links=None):
    return {
        "key": key,
        "scope": "platform",
        "contract_status": status,
        "capabilities": capabilities,
        "links": links or {},
    }


class PlatformCapabilitiesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        effective = set(effective_permission_codes(request.user))
        if not (effective & set(PLATFORM_PERMISSION_CODES)):
            raise PermissionDenied("Autorité Platform requise.")

        modules = []
        if PermissionCode.PLATFORM_MANAGE in effective:
            modules.append(_module(
                "operations",
                capabilities=["view", "manage"],
                links={"overview": "/api/v1/operations/overview/"},
            ))
        if PermissionCode.PLATFORM_TRUST_REVIEW in effective:
            modules.append(_module(
                "trust_review",
                capabilities=["review"],
                status="owner_web_contract",
                links={"web_queue": "/trust/staff/"},
            ))

        subscription_codes = {
            PermissionCode.PLATFORM_SUBSCRIPTIONS_CATALOG_VIEW,
            PermissionCode.PLATFORM_SUBSCRIPTIONS_CATALOG_MANAGE,
            PermissionCode.PLATFORM_SUBSCRIPTIONS_VIEW,
            PermissionCode.PLATFORM_SUBSCRIPTIONS_MANAGE,
            PermissionCode.PLATFORM_SUBSCRIPTIONS_GRANTS_MANAGE,
            PermissionCode.PLATFORM_SUBSCRIPTIONS_REVIEWS_MANAGE,
        }
        if effective & subscription_codes:
            modules.append(_module(
                "subscriptions",
                capabilities=sorted(effective & subscription_codes),
                status="owner_domain",
            ))

        recognition_codes = {
            PermissionCode.PLATFORM_RECOGNITION_VIEW,
            PermissionCode.PLATFORM_RECOGNITION_POLICY_MANAGE,
            PermissionCode.PLATFORM_RECOGNITION_POLICY_PUBLISH,
            PermissionCode.PLATFORM_RECOGNITION_ECONOMY_MANAGE,
            PermissionCode.PLATFORM_RECOGNITION_ACHIEVEMENTS_MANAGE,
            PermissionCode.PLATFORM_RECOGNITION_AUDIT_VIEW,
        }
        if effective & recognition_codes:
            modules.append(_module(
                "recognition_governance",
                capabilities=sorted(effective & recognition_codes),
                status="owner_domain",
            ))

        opportunity_codes = {
            PermissionCode.OPPORTUNITIES_MANAGE,
            PermissionCode.OPPORTUNITIES_REVIEW_SUBMISSIONS,
            PermissionCode.OPPORTUNITIES_SOURCES_VERIFY,
            PermissionCode.OPPORTUNITIES_MERGE,
        }
        if effective & opportunity_codes:
            modules.append(_module(
                "opportunity_curation",
                capabilities=sorted(effective & opportunity_codes),
                status="owner_domain",
            ))

        response = Response({
            "context": "platform",
            "modules": modules,
            "space_modules_included": False,
            "personal_modules_included": False,
        })
        response["Cache-Control"] = "private, no-store"
        return response
