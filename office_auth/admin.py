from django.contrib import admin

from .models import AzureUser

# Register your models here.


class AzureUserAdmin(admin.ModelAdmin):
    exclude = ['microsoft_user_id']

admin.site.register(AzureUser, AzureUserAdmin)
