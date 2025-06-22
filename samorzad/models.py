from django.db import models
from django.utils import timezone, dateparse
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.core.exceptions import ObjectDoesNotExist
from office_auth.models import AzureUser
import pytz

class Voting(models.Model):
    """
    Model reprezentujący głosowanie, pola:

    - created_at: Czas utworzenia obiektu (strefa UTC)
    - updated_at: Czas aktualizacji obiektu (strefa UTC)
    - planned_start: Czas rozpoczęcia głosowania (UTC)
    - planned_end: Czas zakończenia głosowania (UTC)
    - votes_per_user: Dodatnia liczba, która reprezentuje liczbę głosów które można oddać na poszczególnych kandydatów
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    planned_start = models.DateTimeField(null=False)
    planned_end = models.DateTimeField(null=False)
    votes_per_user = models.SmallIntegerField(
        default=1,
        validators=[MinValueValidator(1, 'Ilość głosów musi być większa od 0')]
    )

    def parse_planned_start(self):
        """Zwraca planned_start w formacie polskiej strefy czasowej w postaci stringa"""
        return self.planned_start.astimezone(tz=pytz.timezone('Europe/Warsaw'))

    def parse_planned_end(self):
        """Zwraca planned_end w formacie polskiej strefy czasowej w postaci stringa"""
        return self.planned_end.astimezone(tz=pytz.timezone('Europe/Warsaw'))

    def parse_created_at(self):
        return self.created_at.astimezone(tz=pytz.timezone('Europe/Warsaw'))

    def parse_updated_at(self):
        return self.updated_at.astimezone(tz=pytz.timezone('Europe/Warsaw'))

    def clean(self):
        if self.planned_start <= timezone.now():
            raise ValidationError("Głosowanie musi zaczynać się później niż obecna data.", code='invalid_planned_start_value')
        if self.planned_start >= self.planned_end:
            raise ValidationError("Głosowanie musi kończyć się później niż jego data rozpoczęcia.", code='invalid_planned_end_value')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Voting(start={self.parse_planned_start()}, end={self.parse_planned_end()})'

class Candidate(models.Model):
    """Model reprezentujący kandydata na wybory do samorządu, pola:

    - first_name: Imię kandydata
    - second_name: Drugie imię kandydata, domyślnie pusty string
    - last_name: Nazwisko kandydata
    - image: Zdjęcie kandydata, może być null
    - created_at: Czas utworzenia obiektu (strefa UTC)
    - updated_at: Czas aktualizacji obiektu (strefa UTC)
    - school_class: Klasa kandydata w obecnych wyborach, może być null ale nie powinna
    """
    first_name = models.CharField(null=False, max_length=150)
    second_name = models.CharField(default="", max_length=150, blank=True)
    last_name = models.CharField(null=False, max_length=150)
    image = models.ImageField(upload_to='uploads/samorzad/', null=True, blank=True, unique=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    school_class = models.CharField(max_length=20)


    def parse_created_at(self):
        return self.created_at.astimezone(tz=pytz.timezone('Europe/Warsaw'))

    def parse_updated_at(self):
        return self.updated_at.astimezone(tz=pytz.timezone('Europe/Warsaw'))

    def __str__(self):
        return f'Candiate(first_name={self.first_name}, last_name={self.last_name})'

class ElectoralProgram(models.Model):
    """
    Model reprezentujący program wyborczy kandydata w wyborach. Każdy kandydat może mieć różne programy wyborcze w różnych głosowaniach
    ALE może mieć tylko 1 program wyborczy w konkretnym głosowaniu (class Meta), pola:

    - candidate: Klucz obcy kandydata
    - voting: Klucz obcy głosowania
    - info: Tekst programu wyborczego
    - created_at: Czas utworzenia obiektu (strefa UTC)
    - updated_at: Czas aktualizacji obiektu (strefa UTC)
    """
    candidature = models.OneToOneField('CandidateRegistration', on_delete=models.CASCADE, related_name='electoral_program')
    info = models.TextField(null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def __str__(self):
        return f'ElectoralProgram(candidature={self.candidature.pk})'


class CandidateRegistration(models.Model):
    """Model n..n łączący modele kandydata i głosowania, pola:

    - candidate: Klucz obcy modelu kandydata
    - voting: Klucz obcy modelu głosowania
    - is_eligible: Boolean określający czy kandydat jest dopuszczony go głosowania
    - created_at: Czas utworzenia obiektu (strefa UTC)
    """
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='registrations')
    voting = models.ForeignKey(Voting, on_delete=models.CASCADE, related_name='candidate_registrations')
    is_eligible = models.BooleanField(default=False)  # Przeniesione z modelu Candidate
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def parse_created_at(self):
        return self.created_at.astimezone(tz=pytz.timezone('Europe/Warsaw'))

    def parse_updated_at(self):
        return self.updated_at.astimezone(tz=pytz.timezone('Europe/Warsaw'))

    class Meta:
        # Zapobiega duplikatom
        constraints = [
            models.UniqueConstraint(fields=['candidate', 'voting'], name='unique_candidate_per_voting',
            violation_error_message="Kandydatura dla tego kandydata już istnieje w tym głosowaniu")
        ]

    def __str__(self):
        return f'CandidateRegistration(candidate={self.candidate.pk}, voting={self.voting.pk})'

    def clean(self):
        try:
            voting = self.voting
        except ObjectDoesNotExist:
            raise ValidationError("Podane głosowanie nie istnieje w systemie.", code='voting_does_not_exist')
        # TODO: O tą zmienną trzeba się pytać lecha
        if voting.candidate_registrations.count() >= 15 and not voting.candidate_registrations.filter(
                pk=self.pk).exists():
            raise ValidationError("W głosowaniu nie może być więcej niż 15 kandydatów.", code='voting_candidatures_limit_reached')
        now = timezone.now()
        if now >= voting.planned_start:
            raise ValidationError("Nie można dodawać nowych kandydatur do głosowania które już się zaczęło.", code="voting_is_live")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class Vote(models.Model):
    """Model reprezentujący oddany głos w głosowaniu na samorząd, pola

    - candidate_registration: klucz obcy zarejestrowanego kandydata
    - microsoft_user: klucz obcy poświadczonego użytkownika aplikacji
    - created_at: Czas utworzenia obiektu (strefa UTC)

    UWAGA: Nie da się edytować obiektów
    """
    candidate_registration = models.ForeignKey(CandidateRegistration, on_delete=models.CASCADE, related_name='votes')
    microsoft_user = models.ForeignKey(AzureUser, on_delete=models.CASCADE, related_name='samorzad_votes')
    created_at = models.DateTimeField(auto_now_add=True)

    def parse_created_at(self):
        return self.created_at.astimezone(tz=pytz.timezone('Europe/Warsaw')).strftime('%Y.%m.%d %H:%M:%S')

    def clean(self):
        voting = self.candidate_registration.voting
        # Walidacja czasu oddanego głosu
        if timezone.now() < voting.planned_start:
            raise ValidationError("Nie można głosować przed rozpoczęciem głosowania", code='voting_not_started')
        if timezone.now() > voting.planned_end:
            raise ValidationError("Nie można głosować po zakończeniu głosowania", code='voting_gone')
        # Walidacja kandydatury
        if not self.candidate_registration.is_eligible:
            raise ValidationError("Nie można oddać głosu na kandydata, który nie został dopuszczony do wyborów.", code='illegal_candidature')
        # Walidacja ilości głosów/głosowanie i ilości głosów/kandydatura
        if Vote.objects.filter(candidate_registration=self.candidate_registration, microsoft_user=self.microsoft_user).exists():
            raise ValidationError("Już zagłosowałeś na tego kandydata.", code='vote_dupliaction')
        voting = self.candidate_registration.voting
        if Vote.objects.filter(
                candidate_registration__voting=voting,
                microsoft_user=self.microsoft_user
        ).count() == voting.votes_per_user:
            raise ValidationError("Użytkownik oddał już maksymalną ilość głosów w głosowaniu", code='vote_limit_reached')
        if self.pk:
            raise ValidationError("Edytowanie modelu Vote jest zabronione!", code='vote_action_forbidden')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)