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

