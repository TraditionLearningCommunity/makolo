from django.urls import path
from .consumers import ConversationConsumer

websocket_urlpatterns = [path("ws/v1/conversations/", ConversationConsumer.as_asgi())]
