from django.contrib.auth.models import AbstractUser
from django.db import models

class AzureUser(AbstractUser):
    # null i blank w polu microsoft_user są dodane w celu zgodności z procesem tworzenia superusera w django
    # Podczas tworzenia rzeczywistych obiektów opartych na id zwracanym przez api Azure należy zawsze te id umieścić w polu microsoft_user
    microsoft_user_id = models.CharField(max_length=256, unique=True, null=True, blank=True)

    def __str__(self):
        return self.microsoft_user_id
