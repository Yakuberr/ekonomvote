from django.views.generic import TemplateView
from django.contrib.auth import login, authenticate
from django.http import HttpResponseForbidden, HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import redirect, render, reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from ..forms import PanelLoginForm

@login_required(login_url='office_auth:microsoft_login')
def panel_login(request:HttpRequest):
    microsoft_user_id = request.session.get('microsoft_user_id')
    if microsoft_user_id is not None and request.user.is_superuser:
        return redirect(reverse('panel:index'))
    if request.method == 'GET':
        form = PanelLoginForm()
        return render(request, 'panel/login.html', context={'form':form})
    if request.method == 'POST':
        form = PanelLoginForm(request.POST)
        if form.is_valid():
            cleaned_data = form.cleaned_data
            user = authenticate(username=cleaned_data.get('login'), password=cleaned_data.get('password'))
            if user is None:
                messages.error(request, 'Nie ma takiego użytkownika')
                return redirect(reverse('panel:login'))
            if not user.is_superuser:
                messages.error(request, message='Podany użytkownik nie jest administratorem')
                return redirect(reverse('panel:login'))
            login(request, user)
            request.session['microsoft_user_id'] = microsoft_user_id
            return redirect('panel:index')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
            return redirect(reverse('panel:login'))


@login_required(login_url='office_auth:microsoft_login')
def panel_index(request:HttpRequest):
    if request.method != 'GET':
        return HttpResponseNotAllowed(permitted_methods=['GET'])
    if not request.user.is_superuser:
        return redirect(reverse('panel:login'))
    return render(request, 'panel/index.html')

