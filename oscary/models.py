from datetime import datetime

from django.db import models
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone

import pytz

from office_auth.models import AzureUser

WARSAW_TZ = pytz.timezone('Europe/Warsaw')

class Oscar(models.Model):
    name = models.CharField(max_length=2048, null=False)
    info = models.CharField(max_length=12000, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Oskar'
        verbose_name_plural = 'Oskary'

    @staticmethod
    def localize_dt(dt:datetime):
        return dt.astimezone(tz=WARSAW_TZ)

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

    class Meta:
        verbose_name = 'Nauczyciel'
        verbose_name_plural = 'Nauczyciele'

    @staticmethod
    def localize_dt(dt:datetime):
        return dt.astimezone(tz=WARSAW_TZ)

    def __str__(self):
        return f'Teacher(first_name={self.first_name}, last_name={self.last_name})'


class Candidature (models.Model):
    """Model reprezentujący pojedyńczą rywalizację w kontekście: nauczyciel-oscar-nominacja"""
    oscar = models.ForeignKey(Oscar, on_delete=models.CASCADE, related_name='candidatures')
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='candidatures')
    voting_round = models.ForeignKey('VotingRound', on_delete=models.CASCADE, related_name='candidatures')
    created_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['teacher', 'oscar', 'voting_round'],
                name='unique_comp_per_teacher_per_oscar_per_round',
                violation_error_message="Nauczyciel w ramach pojedyńczej rywalizacji może istnieć tylko raz w ramach całego kontekstu rundy głosowania"
            )
        ]
        verbose_name = "Kandydatura"
        verbose_name_plural = "Kandydatury"

    def __str__(self):
        return f'Candidature(voting_round={self.voting_round}, oscar={self.oscar}, teacher={self.teacher})'

    @staticmethod
    def localize_dt(dt:datetime):
        return dt.astimezone(tz=WARSAW_TZ)

class VotingEvent(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    with_nominations = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Głosowanie'
        verbose_name_plural = 'Głosowania'

    @staticmethod
    def localize_dt(dt:datetime):
        return dt.astimezone(tz=WARSAW_TZ)

    def clean(self):
        if self.planned_start <= timezone.now():
            raise ValidationError("planned_start musi być większe niż obecna data i godzina.")
        if self.planned_start >= self.planned_end:
            raise ValidationError("planned_start musi być mniejsze niż planned_end.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'VotingEvent(start={self.localize_dt(self.planned_start.strftime('%Y.%m.%d %H:%M:%S'))}, end={self.localize_dt(self.planned_end.strftime('%Y.%m.%d %H:%M:%S'))})'


class VotingRound(models.Model):
    class VotingRoundType(models.TextChoices):
        NOMINATION = 'N', _('Nominacja')
        FINAL = 'F', _('Finał')

    voting_event = models.ForeignKey(VotingEvent, on_delete=models.CASCADE, related_name='voting_rounds')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    planned_start = models.DateTimeField(null=False, unique=True)
    planned_end = models.DateTimeField(null=False, unique=True)
    max_tearchers_for_end = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1, 'Wartość musi być większa od 0')]
    )
    round_type = models.CharField(choices=VotingRoundType.choices, default=VotingRoundType.FINAL)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['voting_event', 'round_type'],
                name='unique_round_type_per_event',
                violation_error_message="Typ rundy głosowania nie może się powtarzać w kontekście wydarzenia",
            )
        ]
        verbose_name = "Runda głosowania"
        verbose_name_plural = "Rundy głosowań"

    @staticmethod
    def localize_dt(dt:datetime):
        return dt.astimezone(tz=WARSAW_TZ)

    def clean(self):
        if self.planned_start <= timezone.now():
            raise ValidationError("Początek głosowania musi być w przyszłości")
        if self.planned_start >= self.planned_end:
            raise ValidationError("Początek musi być wcześniejszy niż koniec")

        # Sprawdzenie logiki nominacji/finału
        if self.round_type == self.RoundType.NOMINATION and self.max_winners < 2:
            raise ValidationError('Nominacja musi mieć minimum 2 zwycięzców')
        if self.round_type == self.RoundType.FINAL and self.max_winners != 1:
            raise ValidationError('Finał może mieć tylko 1 zwycięzcę')


    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'VotingRound(voting_event={self.voting_event.pk}, start={self.localize_dt(self.planned_start.strftime('%Y.%m.%d %H:%M:%S'))}, end={self.localize_dt(self.planned_end.strftime('%Y.%m.%d %H:%M:%S'))})'


class Vote(models.Model):
    candidature = models.ForeignKey(Candidature, on_delete=models.CASCADE, related_name='votes', null=True)
    microsoft_user = models.ForeignKey(AzureUser, on_delete=models.CASCADE, related_name='oscar_votes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # Ograniczenie: użytkownik może głosować tylko raz na daną rywalizację
            models.UniqueConstraint(
                fields=['microsoft_user', 'candidature'],
                name='unique_vote_per_candidature',
                violation_error_message="Użytkownik może zagłosować tylko raz na daną rywalizację"
            )
        ]
        verbose_name = "Głos"
        verbose_name_plural = "Głosy"

    @staticmethod
    def localize_dt(dt:datetime):
        return dt.astimezone(tz=WARSAW_TZ)

    def __str__(self):
        return f'Vote(user={self.user.pk}, voting_round={self.voting_round.pk})'

    def clean(self):
        existing = Vote.objects.filter(
            microsoft_user=self.microsoft_user,
            candidature__oscar=self.candidature.oscar,
            candidature__voting_round=self.candidature.voting_round
        )
        if self.pk:
            existing = existing.exclude(pk=self.pk)

        if existing.exists():
            raise ValidationError(
                "Użytkownik może głosować tylko raz na tego samego oscara w tej samej rundzie."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.pk:
            raise ValidationError("Edytowanie modelu Vote jest zabronione!")
        super().save(*args, **kwargs)



