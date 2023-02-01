import os
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from api.AuthMiddleware import TokenAuthMiddlewareStack
from . import urls

# import api.routing
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")

application_Asgi = ProtocolTypeRouter(
    {
        "websocket": AllowedHostsOriginValidator(
            TokenAuthMiddlewareStack(URLRouter(urls.websocket_urlpatterns))
        ),
    }
)
