from django.utils.timezone import datetime

from django.db import models
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone

import pytz

from office_auth.models import AzureUser

WARSAW_TZ = pytz.timezone('Europe/Warsaw')

class Oscar(models.Model):
    name = models.CharField(max_length=2048, null=False,unique=True,  error_messages={
        'max_length':"Nazwa oscara nie może przekraczać 2048 znaków",
        'null':"Nazwa oscara nie może być pusta",
        'blank':"Nazwa oscara jest wymagana",
        'unique':"Ta nazwa oscara już istnieje"
    }, verbose_name='Nazwa')
    info = models.CharField(max_length=12000, null=False, error_messages={
        'max_length':"Opis oscara nie może przekraczać 12000 znaków",
        'null':"Opis oscara nie może być pusty",
        'blank':"Opis oscara jest wymagany"
    }, verbose_name='Opis')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Oscar'
        verbose_name_plural = 'Oscary'

    @staticmethod
    def localize_dt(dt:datetime):
        return dt.astimezone(tz=WARSAW_TZ)

    def __str__(self):
        return f'Oscar(name={self.name})'

class Teacher(models.Model):
    first_name = models.CharField(null=False, max_length=150, verbose_name='Imię')
    second_name = models.CharField(default='', max_length=150, blank=True, verbose_name='Drugie imię')
    last_name = models.CharField(null=False, max_length=150, verbose_name='Nazwisko')
    image = models.ImageField(upload_to='uploads/oscary/', null=True, blank=True, unique=False, verbose_name='Zdjęcie')
    info = models.TextField(null=False, verbose_name='Opis')
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
    # TODO: Kandydatury powinny być tworzone automatycznie dla danego wydarzenia
    """Model reprezentujący pojedyńczą rywalizację w kontekście: nauczyciel-oscar-nominacja"""
    oscar = models.ForeignKey(Oscar, on_delete=models.CASCADE, related_name='candidatures', error_messages={
        'invalid_choice':"Nieprawidłowa wartość dla pola oscarów",
        'null':"Pole oscarów nie może być puste",
        "blank":"Pole oscarów jest wymagane"
    }, verbose_name='Oscar')
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='candidatures', error_messages={
        'invalid_choice':"Nieprawidłowa wartość dla pola nauczycieli",
        'null':"Pole nauczycieli nie może być puste",
        "blank":"Pole nauczycieli jest wymagane"
    }, verbose_name='Nauczyciel')
    voting_round = models.ForeignKey('VotingRound', on_delete=models.CASCADE, related_name='candidatures', error_messages={
        'invalid_choice':"Nieprawidłowa wartość dla pola rund",
        'null':"Pole rund nie może być puste",
        "blank":"Pole rund jest wymagane"
    }, verbose_name="Runda głosowania")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['teacher', 'oscar', 'voting_round'],
                name='unique_comp_per_teacher_per_oscar_per_round',
                violation_error_message="Nauczyciel w ramach pojedyńczej rywalizacji może istnieć tylko raz w ramach całego kontekstu rundy głosowania",
                violation_error_code='constraint_violation'
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
    """Uwaga: finał musi być stworzony przed nominacją"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    with_nominations = models.BooleanField(default=False, verbose_name="Zawiera nominacje")

    class Meta:
        verbose_name = 'Wydarzenie głosowanie'
        verbose_name_plural = 'Wydarzenia głosowań'

    @staticmethod
    def localize_dt(dt:datetime):
        return dt.astimezone(tz=WARSAW_TZ)

    def clean(self):
        if self.pk:
            old_instance = self.__class__.objects.get(pk=self.pk)
            if self.with_nominations != old_instance.with_nominations:
                raise ValidationError("Nie można zmienić statusu posiadania nominacji", code='cant_modify')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_event_status(self, now: datetime):
        """Określa status wydarzenia używając tylko pól z anotacji, bez query. UWAGA funkcja używana tylko w widoku panel.views.oscary.partial_list_voting_events"""
        # Jeśli są nominacje
        if self.with_nominations:
            if now < self.first_round_start:
                return "Zaplanowane"
            if self.first_round_start <= now <= self.last_round_end:
                return "Aktywne"
            return "Zakończone"
        # Bez nominacji
        if now < self.last_round_start:
            return "Zaplanowane"
        if self.last_round_start <= now <= self.last_round_end:
            return "Aktywne"
        return "Zakończone"

    def populate_first_round(self, first_round):
        if first_round.candidatures.count() > 0:
            raise Exception(f"Nie można wypełnić pierwszej rundy danymi (id: {first_round.id}), ponieważ już zawiera kandydatury")
        for o in Oscar.objects.all():
            for t in Teacher.objects.all():
                Candidature.objects.create(
                    teacher=t,
                    oscar=o,
                    voting_round=first_round
                )


    def __str__(self):
        return f'VotingEvent(created_at={self.localize_dt(self.created_at).strftime('%Y.%m.%d %H:%M:%S')}, with_nominations={self.with_nominations})'


class VotingRound(models.Model):
    """Uwaga: finał musi być stworzony przed nominacją"""
    # TODO: Po utworzeniu obiektu musi być utworzony cron jon który wypełni ostateczną rundę danymi
    class VotingRoundType(models.TextChoices):
        NOMINATION = 'N', _('Nominacja')
        FINAL = 'F', _('Finał')

    voting_event = models.ForeignKey(VotingEvent, on_delete=models.CASCADE, related_name='voting_rounds', verbose_name="Wydarzenie głosowania")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    planned_start = models.DateTimeField(null=False, verbose_name='Start rundy')
    planned_end = models.DateTimeField(null=False, verbose_name="Koniec rundy")
    max_tearchers_for_end = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1, 'Wartość musi być większa od 0')],
        verbose_name="Ilość nominacji/oscara"
    )
    round_type = models.CharField(choices=VotingRoundType.choices, default=VotingRoundType.FINAL, verbose_name="Rodzaj rundy")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['voting_event', 'round_type'],
                name='unique_round_type_per_event',
                violation_error_message="Typ rundy głosowania nie może się powtarzać w kontekście wydarzenia",
                violation_error_code='constraint_violation'
            )
        ]
        verbose_name = "Runda głosowania"
        verbose_name_plural = "Rundy głosowań"

    @staticmethod
    def localize_dt(dt:datetime):
        return dt.astimezone(tz=WARSAW_TZ)

    def clean(self):
        if self.planned_start <= timezone.now():
            raise ValidationError("Początek głosowania musi być w przyszłości", code='invalid_date')
        if self.planned_start >= self.planned_end:
            raise ValidationError("Początek musi być wcześniejszy niż koniec", code='invalid_date')

        if self.round_type == VotingRound.VotingRoundType.NOMINATION:
            final = VotingRound.objects.filter(round_type=VotingRound.VotingRoundType.FINAL, voting_event=self.voting_event).first()
            if self.planned_start >= final.planned_start:
                raise ValidationError('Runda nominacji musi być wcześniej niż runda finałowa', code='invalid_date_round_type')

        # Sprawdzenie logiki nominacji/finału
        if self.round_type == VotingRound.VotingRoundType.NOMINATION and self.max_tearchers_for_end < 2:
            raise ValidationError('Nominacja musi mieć minimum 2 zwycięzców', code='invalid_max_tearchers_for_end')
        if self.round_type == VotingRound.VotingRoundType.FINAL and self.max_tearchers_for_end != 1:
            raise ValidationError('Finał może mieć tylko 1 zwycięzcę', code='invalid_max_tearchers_for_end')


    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'VotingRound(voting_event={self.voting_event.pk}, start={self.localize_dt(self.planned_start).strftime('%Y.%m.%d %H:%M:%S')}, end={self.localize_dt(self.planned_end).strftime('%Y.%m.%d %H:%M:%S')}, type={self.round_type})'


class Vote(models.Model):
    candidature = models.ForeignKey(Candidature, on_delete=models.CASCADE, related_name='votes', null=True, verbose_name="Kandydatura")
    microsoft_user = models.ForeignKey(AzureUser, on_delete=models.CASCADE, related_name='oscar_votes', verbose_name="Użytkownik")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # Ograniczenie: użytkownik może głosować tylko raz na daną rywalizację
            models.UniqueConstraint(
                fields=['microsoft_user', 'candidature'],
                name='unique_vote_per_candidature',
                violation_error_message="Użytkownik może zagłosować tylko raz na daną rywalizację",
                violation_error_code='constraint_violation'
            )
        ]
        verbose_name = "Głos"
        verbose_name_plural = "Głosy"

    @staticmethod
    def localize_dt(dt:datetime):
        return dt.astimezone(tz=WARSAW_TZ)

    def __str__(self):
        return f'Vote(user={self.microsoft_user.pk}, candidature={self.candidature.pk})'

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



