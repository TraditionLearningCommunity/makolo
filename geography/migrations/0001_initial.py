import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import geography.validators


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0003_team_teammembership"),
    ]

    operations = [
        migrations.CreateModel(
            name="Place",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=180)),
                ("address_line", models.CharField(blank=True, max_length=255)),
                ("locality", models.CharField(blank=True, max_length=120)),
                ("administrative_area", models.CharField(blank=True, max_length=120)),
                ("postal_code", models.CharField(blank=True, max_length=32)),
                ("country_code", models.CharField(blank=True, max_length=2, validators=[geography.validators.validate_country_code])),
                ("latitude", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("longitude", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("timezone", models.CharField(blank=True, max_length=100, validators=[geography.validators.validate_timezone_name])),
                ("access_instructions", models.CharField(blank=True, max_length=320)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_places", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "lieu", "verbose_name_plural": "lieux", "ordering": ["name", "locality"]},
        ),
        migrations.CreateModel(
            name="Zone",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=180)),
                ("zone_type", models.CharField(choices=[("administrative", "Administrative"), ("radius", "Rayon")], default="administrative", max_length=20)),
                ("country_code", models.CharField(blank=True, max_length=2, validators=[geography.validators.validate_country_code])),
                ("administrative_area", models.CharField(blank=True, max_length=120)),
                ("locality", models.CharField(blank=True, max_length=120)),
                ("radius_m", models.PositiveIntegerField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("center_place", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="radius_zones", to="geography.place")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_zones", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "zone", "verbose_name_plural": "zones", "ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="SpacePlace",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("role", models.CharField(choices=[("headquarters", "Siège"), ("office", "Bureau"), ("branch", "Agence / succursale"), ("service_point", "Point de service"), ("other", "Autre")], default="other", max_length=24)),
                ("public_label", models.CharField(blank=True, max_length=160)),
                ("is_primary", models.BooleanField(default=False)),
                ("is_public", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("position", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="space_places", to="organizations.organization")),
                ("place", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="space_relations", to="geography.place")),
            ],
            options={"verbose_name": "lieu d'Espace", "verbose_name_plural": "lieux d'Espace", "ordering": ["position", "role", "place__name"]},
        ),
        migrations.AddConstraint(model_name="place", constraint=models.CheckConstraint(condition=models.Q(models.Q(("latitude__isnull", True), ("longitude__isnull", True)), models.Q(("latitude__isnull", False), ("longitude__isnull", False)), _connector="OR"), name="geo_place_coordinates_pair")),
        migrations.AddConstraint(model_name="place", constraint=models.CheckConstraint(condition=models.Q(("latitude__isnull", True), models.Q(("latitude__gte", -90), ("latitude__lte", 90)), _connector="OR"), name="geo_place_latitude_range")),
        migrations.AddConstraint(model_name="place", constraint=models.CheckConstraint(condition=models.Q(("longitude__isnull", True), models.Q(("longitude__gte", -180), ("longitude__lte", 180)), _connector="OR"), name="geo_place_longitude_range")),
        migrations.AddIndex(model_name="place", index=models.Index(fields=["country_code", "locality", "is_active"], name="geo_place_country_local_idx")),
        migrations.AddIndex(model_name="place", index=models.Index(fields=["latitude", "longitude"], name="geo_place_lat_lon_idx")),
        migrations.AddConstraint(model_name="zone", constraint=models.CheckConstraint(condition=models.Q(models.Q(("center_place__isnull", True), ("radius_m__isnull", True), ("zone_type", "administrative")), models.Q(("center_place__isnull", False), ("radius_m__gt", 0), ("zone_type", "radius")), _connector="OR"), name="geo_zone_shape_valid")),
        migrations.AddIndex(model_name="zone", index=models.Index(fields=["zone_type", "is_active"], name="geo_zone_type_active_idx")),
        migrations.AddIndex(model_name="zone", index=models.Index(fields=["country_code", "is_active"], name="geo_zone_country_active_idx")),
        migrations.AddConstraint(model_name="spaceplace", constraint=models.UniqueConstraint(fields=("organization", "place", "role"), name="geo_space_place_role_unique")),
        migrations.AddConstraint(model_name="spaceplace", constraint=models.UniqueConstraint(condition=models.Q(("is_active", True), ("is_primary", True)), fields=("organization", "role"), name="geo_space_place_primary_role")),
        migrations.AddConstraint(model_name="spaceplace", constraint=models.CheckConstraint(condition=models.Q(("is_primary", False), ("is_active", True), _connector="OR"), name="geo_space_primary_is_active")),
        migrations.AddIndex(model_name="spaceplace", index=models.Index(fields=["organization", "is_active"], name="geo_space_place_org_active_idx")),
        migrations.AddIndex(model_name="spaceplace", index=models.Index(fields=["place", "is_active"], name="geo_space_place_active_idx")),
    ]
