# views.py
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from .auth_utils import Office365Authentication
from .models import AzureUser


def microsoft_login(request: HttpRequest):
    if request.session.get('microsoft_user_id') is not None:
        return redirect('samorzad:index')
    auth = Office365Authentication()
    redirect_uri = request.build_absolute_uri(reverse('office_auth:microsoft_callback'))
    error_uri = request.build_absolute_uri(reverse('office_auth:microsoft_callback'))
    auth_url = auth.generate_auth_url(redirect_uri=redirect_uri, error_uri=error_uri, state=None)
    return redirect(auth_url)


def microsoft_callback(request:HttpRequest):
    auth = Office365Authentication()
    redirect_uri = request.build_absolute_uri(reverse('office_auth:microsoft_callback'))
    try:
        code = request.GET.get('code')
        token_result = auth.get_token(code, redirect_uri=redirect_uri)
        user_info = auth.get_user_info(token_result['access_token'])
        user, created = AzureUser.objects.get_or_create(
            # TODO: Zamiast chamsko pobierać wartość klucza należy użyć metody .get oraz zabezpieczyć przed możliością wsytąpienia user_info['id'] is None
            microsoft_user_id=user_info['id']
        )
        login(request, user)
        request.session['microsoft_user_id'] = user_info['id']
        return redirect('samorzad:index')
    except Exception as e:
        return redirect('office_auth:microsoft_login')

def logout_view(request:HttpRequest):
    request.session.flush()
    redirect_uri = request.build_absolute_uri(reverse("office_auth:home"))
    logout_url = f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}/oauth2/v2.0/logout?post_logout_redirect_uri={redirect_uri}"
    return redirect(logout_url)


@login_required(login_url='office_auth:microsoft_login')
def home_view(request:HttpRequest):
    microsoft_user_id = request.session.get('microsoft_user_id')
    context = {
        'microsoft_user_id': microsoft_user_id,
    }
    return render(request, 'home.html', context)