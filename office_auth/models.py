from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _

import pytz


class AzureUser(AbstractUser):
    # null i blank w polu microsoft_user są dodane w celu zgodności z procesem tworzenia superusera w django
    # Podczas tworzenia rzeczywistych obiektów opartych na id zwracanym przez api Azure należy zawsze te id umieścić w polu microsoft_user
    microsoft_user_id = models.CharField(max_length=256, unique=True, null=True, blank=True)

    def __str__(self):
        return f'AzureUser(email={self.email}, is_superuser={self.is_superuser})'

class ActionLog(models.Model):
    class ActionType(models.TextChoices):
        CREATE = "C", _("Utworzenie")
        DELETE = "D", _("Usunięcie")
        UPDATE = "U", _("Edycja")

    user = models.ForeignKey(AzureUser, on_delete=models.CASCADE, related_name='actions')
    action_type = models.CharField(choices=ActionType, max_length=3)
    altered_fields = models.JSONField() # Przykładowa struktura {'first_name':{'old':'Jan', 'new':'Marek'}}
    created_at = models.DateTimeField(auto_now_add=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()

    def parse_created_at(self):
        return self.created_at.astimezone(tz=pytz.timezone('Europe/Warsaw'))


    def __str__(self):
        return f'ActionLog(user={self.user.id}, action={self.action_type}, object_id={self.object_id})'

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Edytowanie modelu ActionLog jest zabronione!", code='log_action_forbidden')
        super().save(*args, **kwargs)
