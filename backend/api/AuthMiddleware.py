from urllib.parse import parse_qs

from channels.auth import AuthMiddleware
from channels.db import database_sync_to_async
from channels.sessions import CookieMiddleware, SessionMiddleware
from rest_framework.authtoken.models import Token


@database_sync_to_async
def get_user(scope):
    query_string = parse_qs(scope["query_string"].decode())
    token = query_string.get("token")
    if not token:
        return False
    try:
        user = Token.objects.get(key=token[0]).user
    except:
        return False
    if not user.is_active:
        return False
    return user


class TokenAuthMiddleware(AuthMiddleware):
    async def resolve_scope(self, scope):
        scope["user"]._wrapped = await get_user(scope)


def TokenAuthMiddlewareStack(inner):
    return CookieMiddleware(SessionMiddleware(TokenAuthMiddleware(inner)))
