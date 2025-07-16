from django.shortcuts import reverse

def get_changed_fields(form):
    if not form.instance.pk:
        raise Exception("Metody można używać tylko z formularzami edycji, nie tworzenia")
    d = {}
    for field_name in form.changed_data:
        verbose_name = form.instance._meta.get_field(field_name).verbose_name
        old_value = form.initial.get(field_name)
        new_value = form.cleaned_data.get(field_name)
        d[verbose_name] = {'old':old_value, 'new':new_value}
    return d

def build_filter_kwargs(filter_map:dict, request_params:dict):
    filter_kwargs = {}
    for filter_param in filter(lambda k: k.startswith('f_'), request_params.keys()):
        field = filter_map.get(filter_param)
        if field is None: continue
        f_value = request_params[filter_param].split(',')
        if len(list(filter(lambda val:val in field['allowed_values'], f_value))) != len(f_value):continue
        filter_kwargs[field['field']] = request_params[filter_param].split(',')
    return filter_kwargs


def build_sort_list(sort_map:dict, request_params:dict):
    sort_by = request_params.get('sort', 'id')
    order = request_params.get('order', 'asc')
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




