from django.db import models
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone

import pytz

from office_auth.models import AzureUser


class Oscar(models.Model):
    name = models.CharField(max_length=2048, null=False)
    info = models.CharField(max_length=12000, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Oscar(name={self.name})'

class Teacher(models.Model):
    first_name = models.CharField(null=False, max_length=150)
    second_name = models.CharField(null=False, max_length=150)
    last_name = models.CharField(null=False, max_length=150)
    image = models.ImageField(upload_to='uploads/oscary/', null=True, blank=True, unique=True)
    info = models.TextField(null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Teacher(first_name={self.first_name}, last_name={self.last_name})'


class Voting(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    planned_start = models.DateTimeField(null=False, unique=True)
    planned_end = models.DateTimeField(null=False, unique=True)
    with_nominations = models.BooleanField(default=False)

    def parse_planned_start(self):
        """Zwraca planned_start w formacie polskiej strefy czasowej w postaci stringa"""
        return self.planned_start.astimezone(tz=pytz.timezone('Europe/Warsaw')).strftime('%Y.%m.%d %H:%M:%S')

    def parse_planned_end(self):
        """Zwraca planned_end w formacie polskiej strefy czasowej w postaci stringa"""
        return self.planned_end.astimezone(tz=pytz.timezone('Europe/Warsaw')).strftime('%Y.%m.%d %H:%M:%S')

    def clean(self):
        if self.planned_start <= timezone.now():
            raise ValidationError("planned_start musi być większe niż obecna data i godzina.")
        if self.planned_start >= self.planned_end:
            raise ValidationError("planned_start musi być mniejsze niż planned_end.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Voting(start={self.parse_planned_start()}, end={self.parse_planned_end()})'


class Nomination(models.Model):
    class NominationRole(models.TextChoices):
        NOMINATION = 'N', _('Nominacja')
        FINAL = 'F', _('Finał')

    voting = models.ForeignKey(Voting, on_delete=models.CASCADE, related_name='nominations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    planned_start = models.DateTimeField(null=False, unique=True)
    planned_end = models.DateTimeField(null=False, unique=True)
    max_tearchers_for_end = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1, 'Wartość musi być większa od 0')]
    )
    role = models.CharField(choices=NominationRole.choices, default=NominationRole.FINAL)

    def parse_planned_start(self):
        """Zwraca planned_start w formacie polskiej strefy czasowej w postaci stringa"""
        return self.planned_start.astimezone(tz=pytz.timezone('Europe/Warsaw')).strftime('%Y.%m.%d %H:%M:%S')

    def parse_planned_end(self):
        """Zwraca planned_end w formacie polskiej strefy czasowej w postaci stringa"""
        return self.planned_end.astimezone(tz=pytz.timezone('Europe/Warsaw')).strftime('%Y.%m.%d %H:%M:%S')

    def clean(self):
        if self.planned_start <= timezone.now():
            raise ValidationError("planned_start musi być większe niż obecna data i godzina.")
        if self.planned_start >= self.planned_end:
            raise ValidationError("planned_start musi być mniejsze niż planned_end.")
        voting = self.voting
        nominations_count = voting.nominations.count()
        # Sprawdzanie jeśli głosowanie ma WYŁĄCZONE nominacje
        if not voting.with_nominations:
            if self.role == self.NominationRole.NOMINATION:
                raise ValidationError("Głosowanie nie może zawierać nominacji")
            if nominations_count == 1:
                raise ValidationError("Głosowanie nie może składać się tylko z rundy finałowej")
        # Sprawdzanie jeśli głosowanie ma WŁĄCZONE nominacje
        elif voting.with_nominations:
            if nominations_count == 2:
                raise ValidationError('Głosowanie może mieć tylko 2 etapy: nominacje i rundę finałową')
            if nominations_count == 1 and self.role == self.NominationRole.NOMINATION:
                raise ValidationError("2 rundą głosowania może być tylko głosowanie finałowe")
            if nominations_count == 0 and self.role == self.NominationRole.FINAL:
                raise ValidationError('1 rundą głosowania może być tylko głosowanie nominacyjne')
        # Sprawdzanie zgodności pól role i max_tearchers_for_end
        if self.role == self.NominationRole.NOMINATION and self.max_tearchers_for_end < 2:
            raise ValidationError('Nominacja powinna mieć minimum 2 finałowych kandydatów')
        if self.role == self.NominationRole.FINAL and self.max_tearchers_for_end > 1:
            raise ValidationError("Finałowe głosowanie powinno mieć tylko 1 finałowego kandydata")


    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Nomination(voting={self.voting.pk}, start={self.parse_planned_start()}, end={self.parse_planned_end()})'


class Vote(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='votes')
    oscar = models.ForeignKey(Oscar, on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(AzureUser, on_delete=models.CASCADE, related_name='oscar_votes')
    voting_round = models.ForeignKey(Nomination, on_delete=models.CASCADE, related_name='votes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'oscar', 'voting_round'],
                name='unique_vote_per_user_per_oscar_per_round'
            )
        ]

    def __str__(self):
        return f'Vote(user={self.user.pk}, voting_round={self.voting_round.pk})'

    def clean(self):
        vote_count = Vote.objects.filter(user=self.user, voting_round=self.voting_round).count()
        oscar_count = Oscar.objects.all().count()
        if vote_count >= oscar_count:
            raise ValidationError(f"Można oddać tyle głosów ile jest oskarów ({oscar_count})")

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk:
            raise ValidationError("Edytowanie modelu Vote jest zabronione!")
        super().save(*args, **kwargs)



