from django.contrib import admin

from .models import TransportDeparture, TransportRoute, TransportRouteStop, TransportService, Vehicle

admin.site.register([TransportRoute, TransportRouteStop, TransportService, TransportDeparture, Vehicle])
