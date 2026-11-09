from django.http import Http404
from django.utils import timezone

from rest_framework.exceptions import ValidationError

from .me_views import PersonalProjectionAPIView
from .trust_resources_projection import (
    CREDENTIAL_STATUS_VALUES,
    CREDENTIAL_TYPE_VALUES,
    PROOF_STATUS_VALUES,
    PROOF_TYPE_VALUES,
    TRUST_RESOURCE_DEFAULT_LIMIT,
    TRUST_RESOURCE_MAX_LIMIT,
    TRUST_RESOURCE_MAX_QUERY,
    TRUST_RESOURCE_SORT_VALUES,
    build_personal_proof_detail,
    build_personal_proofs_collection,
    build_personal_title_detail,
    build_personal_titles_collection,
)


def _integer_param(request, name, *, default):
    raw = request.query_params.get(name, default)
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError({name: "Valeur entière attendue."}) from exc
    if value < 0:
        raise ValidationError({name: "Valeur positive attendue."})
    return value


class PersonalProofsAPIView(PersonalProjectionAPIView):
    projection_code = "personal.proofs"

    def get(self, request):
        self._guard_personal_scope(request)
        query = (request.query_params.get("q") or "").strip()
        if len(query) > TRUST_RESOURCE_MAX_QUERY:
            raise ValidationError({"q": "Recherche trop longue."})
        status = request.query_params.get("status", "all")
        proof_type = request.query_params.get("type", "")
        sort = request.query_params.get("sort", "recent")
        if status not in PROOF_STATUS_VALUES:
            raise ValidationError({"status": "Statut de preuve inconnu."})
        if proof_type and proof_type not in PROOF_TYPE_VALUES:
            raise ValidationError({"type": "Type de preuve inconnu."})
        if sort not in TRUST_RESOURCE_SORT_VALUES:
            raise ValidationError({"sort": "Tri inconnu."})
        limit = min(
            _integer_param(request, "limit", default=TRUST_RESOURCE_DEFAULT_LIMIT),
            TRUST_RESOURCE_MAX_LIMIT,
        )
        offset = _integer_param(request, "offset", default=0)
        observed_at = timezone.now()
        return self._response(
            build_personal_proofs_collection(
                request.user,
                query=query,
                status=status,
                proof_type=proof_type,
                sort=sort,
                limit=limit,
                offset=offset,
            ),
            observed_at=observed_at,
        )


class PersonalProofDetailAPIView(PersonalProjectionAPIView):
    projection_code = "personal.proof.detail"

    def get(self, request, pk):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        data = build_personal_proof_detail(request.user, proof_id=pk)
        if data is None:
            raise Http404
        return self._response(data, observed_at=observed_at)


class PersonalTitlesAPIView(PersonalProjectionAPIView):
    projection_code = "personal.titles"

    def get(self, request):
        self._guard_personal_scope(request)
        query = (request.query_params.get("q") or "").strip()
        if len(query) > TRUST_RESOURCE_MAX_QUERY:
            raise ValidationError({"q": "Recherche trop longue."})
        status = request.query_params.get("status", "all")
        credential_type = request.query_params.get("type", "")
        sort = request.query_params.get("sort", "recent")
        if status not in CREDENTIAL_STATUS_VALUES:
            raise ValidationError({"status": "Statut de titre inconnu."})
        if credential_type and credential_type not in CREDENTIAL_TYPE_VALUES:
            raise ValidationError({"type": "Type de titre inconnu."})
        if sort not in TRUST_RESOURCE_SORT_VALUES:
            raise ValidationError({"sort": "Tri inconnu."})
        limit = min(
            _integer_param(request, "limit", default=TRUST_RESOURCE_DEFAULT_LIMIT),
            TRUST_RESOURCE_MAX_LIMIT,
        )
        offset = _integer_param(request, "offset", default=0)
        observed_at = timezone.now()
        return self._response(
            build_personal_titles_collection(
                request.user,
                query=query,
                status=status,
                credential_type=credential_type,
                sort=sort,
                limit=limit,
                offset=offset,
            ),
            observed_at=observed_at,
        )


class PersonalTitleDetailAPIView(PersonalProjectionAPIView):
    projection_code = "personal.title.detail"

    def get(self, request, pk):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        data = build_personal_title_detail(request.user, credential_id=pk)
        if data is None:
            raise Http404
        return self._response(data, observed_at=observed_at)
