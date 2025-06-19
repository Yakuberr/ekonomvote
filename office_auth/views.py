# views.py
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group

from urllib.parse import urlencode, parse_qs

from .auth_utils import Office365Authentication
from .models import AzureUser


#TODO: Dodać cały system z grupami dla kont opiekunów głosować oraz dla samego administratora
def microsoft_login(request: HttpRequest):
    next_url= request.GET.get('next')
    state = None
    if next_url is not None:
        state=urlencode({'next': next_url})
    if request.session.get('microsoft_user_id') is not None:
        return redirect('samorzad:index')
    auth = Office365Authentication()
    redirect_uri = request.build_absolute_uri(reverse('office_auth:microsoft_callback'))
    error_uri = request.build_absolute_uri(reverse('office_auth:microsoft_callback'))
    auth_url = auth.generate_auth_url(redirect_uri=redirect_uri, error_uri=error_uri, state=state)
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
        if created:
            Group.objects.get(name='opiekunowie').user_set.add(user)
        login(request, user)
        request.session['microsoft_user_id'] = user_info['id']
        state = request.GET.get('state')
        redirect_to = 'samorzad:index'
        if state:
            parsed_state = parse_qs(state)
            next_list = parsed_state.get('next')
            if next_list:
                redirect_to = next_list[0]
        return redirect(redirect_to)
    except Exception as e:
        return redirect('office_auth:microsoft_login')

def logout_view(request:HttpRequest):
    request.session.flush()
    redirect_uri = request.build_absolute_uri(reverse("samorzad:index"))
    logout_url = f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}/oauth2/v2.0/logout?post_logout_redirect_uri={redirect_uri}"
    return redirect(logout_url)

