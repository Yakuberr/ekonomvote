from django.shortcuts import reverse, redirect, render
from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.contrib.messages.constants import ERROR, WARNING, SUCCESS, INFO


def get_changed_fields(form):
    if not form.instance.pk:
        raise Exception("Metody można używać tylko z formularzami edycji, nie tworzenia")
    d = {}
    for field_name in form.changed_data:
        verbose_name = form.instance._meta.get_field(field_name).verbose_name
        old_value = str(form.initial.get(field_name))
        new_value = str(form.cleaned_data.get(field_name))
        d[verbose_name] = {'old':old_value, 'new':new_value}
    return d

def build_filter_kwargs(filter_map:dict, cleaned_data:dict):
    filter_kwargs = {}
    for form_field_name in cleaned_data.keys():
        if form_field_name not in filter_map.keys(): continue
        if cleaned_data[form_field_name] is None: continue
        filter_map_key = filter_map[form_field_name]
        filter_kwargs[filter_map_key['field']] = cleaned_data[form_field_name]
    return filter_kwargs

    for filter_param in filter(lambda k: k.startswith('f_'), cleaned_data.keys()):
        field = filter_map.get(filter_param)
        if field is None: continue
        f_value = cleaned_data[filter_param].split(',')
        if len(list(filter(lambda val:val in field['allowed_values'], f_value))) != len(f_value):continue
        filter_kwargs[field['field']] = cleaned_data[filter_param].split(',')
    return filter_kwargs


def build_sort_list(sort_map:dict, form_cleaned_data:dict):
    sort_by = form_cleaned_data.get('sort_by')
    order = form_cleaned_data.get('sort_order')
    allowed_sort_fields = sort_map.keys()
    if sort_by not in allowed_sort_fields:
        sort_by = 'id'
    if order not in ['asc', 'desc']:
        order = 'asc'
    sort_fields = sort_map[sort_by]
    if order == 'desc':
        sort_fields = [f'-{field}' for field in sort_fields]
    return {
        'sort_fields':sort_fields,
        'sort_by':sort_by,
        'order':order
    }


def build_redirect_urls(model_verbose_name:str, obj_id:int):
    ID_BASED_URL_MAP = {
        'Głosowanie': reverse('panel:update_voting', kwargs={'voting_id': obj_id}),
        'Kandydat': reverse('panel:update_candidate', kwargs={'candidate_id': obj_id}),
        'Program wyborczy': reverse('panel:redirect_to_candidature', kwargs={'electoral_program_id': obj_id}),
        'Kandydatura': reverse('panel:update_candidature', kwargs={'candidature_id': obj_id}),
    }
    return ID_BASED_URL_MAP.get(model_verbose_name, '-')


def build_delete_feedback_response(request: HttpRequest, type: int, message: str, redirect_url: str, alert_template: str | None = 'alert.html') -> HttpResponse|HttpResponseRedirect|HttpResponsePermanentRedirect:
    """Funkcja która buduje alerty/wiadomości django messages w zależności od tego czy zapytanie zostało wysłane przez HTMX czy przez statyczny komponent"""
    ALERT_TYPE_MAP = {
        ERROR: 'danger',
        SUCCESS: 'success',
        WARNING: 'warning',
        INFO: 'info',
    }
    htmx = request.headers.get('HX-Request')
    if htmx and alert_template is not None:
        return render(request, alert_template, context={
            'tag': ALERT_TYPE_MAP.get(type, 'info'),
            'message': message
        })
    elif htmx and alert_template is None:
        return HttpResponse(content='', status=200)
    else:
        messages.add_message(request, level=type, message=message)
        return redirect(redirect_url)






