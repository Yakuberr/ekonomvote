from django.contrib import admin
from .models import Voting, Vote, Candidate, ElectoralProgram
from django.utils import timezone
import pytz
# Register your models here.

# class TimeZoneConvertAdmin(admin.ModelAdmin):
#     def get_object(self, request, object_id, from_field=None):
#         obj = super().get_object(request, object_id, from_field)
#         if obj:
#             target_timezone = pytz.timezone('Europe/Warsaw')
#             for field in self.model._meta.fields:
#                 if field.get_internal_type() == 'DateTimeField':
#                     field_name = field.name
#                     value = getattr(obj, field_name)
#                     if value and timezone.is_aware(value):
#                         converted_value = value.astimezone(target_timezone)
#                         setattr(obj, field_name, converted_value)
#         return obj
#
#     def get_form(self, request, obj=None, **kwargs):
#         form = super().get_form(request, obj, **kwargs)
#         if obj:
#             target_timezone = pytz.timezone('Europe/Warsaw')
#             original_init = form.__init__
#             def new_init(self, *args, **kwargs):
#                 original_init(self, *args, **kwargs)
#                 for field_name, field in self.fields.items():
#                     model_field = obj.__class__._meta.get_field(field_name)
#                     if model_field.get_internal_type() == 'DateTimeField':
#                         value = getattr(obj, field_name, None)
#                         if value and timezone.is_aware(value):
#                             converted_value = value.astimezone(target_timezone)
#                             self.initial[field_name] = converted_value
#             form.__init__ = new_init
#             print(form)
#         return form
#
#     def save_model(self, request, obj, form, change):
#         for field in obj._meta.fields:
#             if field.get_internal_type() == 'DateTimeField':
#                 field_name = field.name
#                 value = getattr(obj, field_name)
#                 if value and timezone.is_aware(value):
#                     utc_value = value.astimezone(pytz.UTC)
#                     setattr(obj, field_name, utc_value)
#         super().save_model(request, obj, form, change)


# @admin.register(Voting)
# class VotingAdmin(TimeZoneConvertAdmin):
#     list_display = ['pk', 'planned_start', 'planned_end']

admin.site.register(Voting)
admin.site.register(Vote)
admin.site.register(Candidate)
admin.site.register(ElectoralProgram)


