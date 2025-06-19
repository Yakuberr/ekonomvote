from django.urls import path
from . import views

app_name = 'office_auth'

urlpatterns = [
    path('', views.microsoft_login, name='microsoft_login'),
    path('microsoft-callback/', views.microsoft_callback, name='microsoft_callback'),
    path('logout/', views.logout_view, name='logout'),
]