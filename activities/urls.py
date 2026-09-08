from django.urls import path

from .views import ActivityCreateView


app_name = "activities"

urlpatterns = [
    path("new/", ActivityCreateView.as_view(), name="create"),
    # Compatibility destination for the mature Home's owner-context card. The
    # current Activities bounded context has no separate owner list surface yet.
    path("mine/", ActivityCreateView.as_view(), name="mine"),
]
