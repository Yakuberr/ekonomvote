from django.urls import path

from .views.panel import panel_login, panel_index


app_name = 'panel'

urlpatterns = [
    path('login/', panel_login, name='login'),
    path('index/', panel_index, name='index'),
]