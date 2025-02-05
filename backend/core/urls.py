from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(
        title="Social Media API",
        default_version='v1',
        description="API documentation for Social Media Platform",
        terms_of_service="https://www.yourapp.com/terms/",
        contact=openapi.Contact(email="contact@yourapp.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
    url=getattr(settings, 'API_URL', None),
)

api_urlpatterns = [
    path('auth/', include('authentication.urls')),
    path('users/', include('users.urls')),
    path('posts/', include('posts.urls')),
    path('chat/', include('chat.urls')),  # Note: 'chat.urls', not 'chat:urls'
    path('search/', include('search.urls')),
]

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(api_urlpatterns)),
    
    # Swagger URLs
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', 
        schema_view.without_ui(cache_timeout=0), 
        name='schema-json'
    ),
    path('swagger/', 
        schema_view.with_ui('swagger', cache_timeout=0), 
        name='schema-swagger-ui'
    ),
    path('redoc/', 
        schema_view.with_ui('redoc', cache_timeout=0), 
        name='schema-redoc'
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass