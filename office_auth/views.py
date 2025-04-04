# views.py
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from .auth_utils import Office365Authentication

def azure_login_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.session.get('is_authenticated'):
            return redirect('office_auth:microsoft_login')
        return view_func(request, *args, **kwargs)
    return wrapper


def microsoft_login(request: HttpRequest):
    auth = Office365Authentication()
    redirect_uri = request.build_absolute_uri(reverse('office_auth:microsoft_callback'))
    error_uri = request.build_absolute_uri(reverse('office_auth:microsoft_callback'))
    auth_url = auth.generate_auth_url(redirect_uri=redirect_uri, error_uri=error_uri)
    print(auth_url)
    return redirect(auth_url)


def microsoft_callback(request:HttpRequest):
    auth = Office365Authentication()
    redirect_uri = request.build_absolute_uri(reverse('office_auth:microsoft_callback'))
    try:
        code = request.GET.get('code')
        token_result = auth.get_token(code, redirect_uri=redirect_uri)
        user_info = auth.get_user_info(token_result['access_token'])
        print(user_info)
        request.session['microsoft_user_id'] = user_info['id']
        request.session['is_authenticated'] = True
        return redirect('samorzad:index')
    except Exception as e:
        return redirect('office_auth:microsoft_login')

def logout_view(request:HttpRequest):
    request.session.flush()
    return redirect('office_auth:microsoft_login')


@azure_login_required
def home_view(request:HttpRequest):
    microsoft_user_id = request.session.get('microsoft_user_id')
    context = {
        'microsoft_user_id': microsoft_user_id,
    }
    return render(request, 'home.html', context)