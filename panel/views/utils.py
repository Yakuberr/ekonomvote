def get_changed_fields(form):
    if not form.instance.pk:
        raise Exception("Metody można używać tylko z formularzami edycji, nie tworzenia")
    d = {}
    for field_name in form.changed_data:
        old_value = form.initial.get(field_name)
        new_value = form.cleaned_data.get(field_name)
        d[field_name] = {'old':old_value, 'new':new_value}
    return d

