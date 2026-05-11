import os
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from channels.sessions import SessionMiddlewareStack
from . import django_setup

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        # "websocket": SessionMiddlewareStack(
        #     AuthMiddlewareStack(
        #         URLRouter(
        #             # All routing patterns combined
        #             # chatbot.routing.websocket_urlpatterns
        #             # + curriculum.routing.websocket_urlpatterns
        #         )
        #     )
        # ),
    }
)
