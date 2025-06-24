from django.contrib import admin

from .models import AzureUser
from django.contrib.auth.admin import UserAdmin

# Register your models here.


class AzureUserAdmin(UserAdmin):
    readonly_fields = ['microsoft_user_id']

    fieldsets = UserAdmin.fieldsets + (
        ('Azure Integration', {
            'fields': ('microsoft_user_id',)
        }),
    )

admin.site.register(AzureUser, AzureUserAdmin)
