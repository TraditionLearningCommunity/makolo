"""Minimal public Profile projection derived from the canonical Passeport.

This endpoint neither grants authority nor exposes the private Profile.
"""
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.projections import projection_envelope
from sharing.passport import PASSPORT_PUBLIC, build_profile_passport


class PublicProfileAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, profile_id):
        user = get_object_or_404(
            get_user_model().objects.filter(
                is_active=True,
                profile__public_profile=True,
            ),
            pk=profile_id,
        )
        # The public Passeport remains the owner of this representation.
        identity = build_profile_passport(
            user, variant=PASSPORT_PUBLIC,
        ).identity
        response = Response(projection_envelope(
            projection="accounts.public-profile",
            scope="public",
            data={
                "profile": {
                    "kind": "profile",
                    "id": str(user.pk),
                    "name": identity["name"],
                    "avatar_url": identity["avatar_url"],
                    "headline": identity["headline"],
                    "bio": identity["bio"],
                    "location": identity["location"],
                },
            },
        ))
        response["Cache-Control"] = "private, no-store"
        return response
