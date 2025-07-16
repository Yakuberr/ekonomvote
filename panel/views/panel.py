from django.contrib.contenttypes.models import ContentType
from django.views.generic import TemplateView
from django.contrib.auth import login, authenticate
from django.http import HttpResponseForbidden, HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.contrib.postgres.search import SearchRank, SearchQuery, SearchVector, TrigramSimilarity
from django.shortcuts import redirect, render, reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import F
from django.apps import apps


from samorzad.models import Candidate, Vote
from ..forms import PanelLoginForm
from office_auth.auth_utils import is_opiekun, opiekun_required
from office_auth.models import AzureUser, ActionLog
from .utils import build_filter_kwargs, build_sort_list, build_redirect_urls

@login_required(login_url='office_auth:microsoft_login')
@require_http_methods(["GET", 'POST'])
def panel_login(request:HttpRequest):
    microsoft_user_id = request.session.get('microsoft_user_id')
    if microsoft_user_id is not None and is_opiekun(request.user):
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
            if not is_opiekun(user):
                messages.error(request, message='Podany użytkownik nie jest opiekunem')
                return redirect(reverse('panel:login'))
            login(request, user)
            request.session['microsoft_user_id'] = microsoft_user_id
            return redirect('panel:index')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
            return redirect(reverse('panel:login'))

@require_http_methods(["GET"])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def panel_index(request:HttpRequest):
    return render(request, 'panel/index.html')

@login_required(login_url='office_auth:microsoft_login')
@require_http_methods(['GET'])
@opiekun_required()
def actions_list_main(request: HttpRequest):
    app_labels = ['samorzad']
    banned_models = ['vote']
    models = ContentType.objects.filter(app_label__in=app_labels).exclude(model__in=banned_models)
    return render(request, 'panel/actions_list.html', context={
        'action_list': ActionLog.ActionType,
        'data_type_list': models,
    })

@login_required(login_url='office_auth:microsoft_login')
@require_http_methods(['GET'])
@opiekun_required()
def partial_actions_list_table(request: HttpRequest):
    SORT_MAP = {
        'name': ['user__username'],
        'created_at': ['created_at'],
        'id':['id'],
    }
    FILTER_MAP = {
        'f_action': {
            'field': 'action_type__in',
            'allowed_values': [ActionLog.ActionType.CREATE, ActionLog.ActionType.UPDATE, ActionLog.ActionType.DELETE],
        },
        'f_data_type': {
            'field': 'content_type__in',
            'allowed_values': ['2', '1', '4', '3']
        }
    }
    sort_data = build_sort_list(SORT_MAP, request.GET)
    query = request.GET.get('search', '')
    id_query = request.GET.get('id_search', '')
    if not id_query.isdigit():
        id_query = None
    if query:
        vector = SearchVector('user__username')
        search = SearchQuery(query, search_type='plain')
        actions = ActionLog.objects.select_related('user', 'content_type') \
            .annotate(rank=SearchRank(vector, search)) \
            .filter(rank__gte=0.03) \
            .order_by('-rank', *sort_data['sort_fields'])
    else:
        actions = ActionLog.objects.select_related('user', 'content_type').order_by(*sort_data['sort_fields'])
    if id_query is not None:
        actions = actions.filter(object_id=id_query)
    filter_kwargs = build_filter_kwargs(FILTER_MAP, request.GET)
    if filter_kwargs:
        actions = actions.filter(**filter_kwargs)
    try:
        page_number = int(request.GET.get('page', 1))
    except ValueError:
        page_number = 1
    paginator = Paginator(actions, 20)
    if page_number > paginator.num_pages:
        page_number = paginator.num_pages
    page_obj = paginator.get_page(page_number)
    params = request.GET.copy()
    params.pop('page', None)
    querystring = params.urlencode()
    return render(request, 'panel/partials/actions_list.html', context={
        'page_obj': page_obj,
        'querystring':querystring,
        'build_redirect_urls':build_redirect_urls,
    })


# TODO: Dane w panelu opiekuna mają być ładowane dynamicznie (listy na bazie filtrów)
# TODO: Stworzyć uniwersalną funkcję do aplikowania sortowania tak jak z filtrami

