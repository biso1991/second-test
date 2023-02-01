from django.conf import settings
from django.urls import path, re_path, include, reverse_lazy
from django.conf.urls.static import static
from django.contrib import admin
from django.views.generic.base import RedirectView
from rest_framework.routers import DefaultRouter

from api.qa import consumers
from .users.views import UserViewSet, UserCreateViewSet, UserAuthToken
from api.qa.urls import router_qa

# from api.qa.views import ListProjectAPIView

router = DefaultRouter()
router.register(r"users", UserViewSet)
router.register(r"users", UserCreateViewSet)
urlpatterns = (
    [
        path("admin/", admin.site.urls),
        path("api/v1/", include(router.urls)),
        path("api/v1/qa/", include(router_qa.urls)),
        path("api-token-auth/", UserAuthToken.as_view()),
        # path("api-auth/", include("rest_framework.urls", namespace="rest_framework")),
        path("api/v1/qa/", include("api.qa.urls")),
        path(
            "api/password_reset/",
            include("django_rest_passwordreset.urls", namespace="password_reset"),
        ),
        # the 'api-root' from django rest-frameworks default router
        # http://www.django-rest-framework.org/api-guide/routers/#defaultrouter
        re_path(
            r"^$", RedirectView.as_view(url=reverse_lazy("api-root"), permanent=False)
        ),
    ]
    + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
)

websocket_urlpatterns = [
    path("api/v1/monitoring/", consumers.TasksConsumer.as_asgi()),
]
