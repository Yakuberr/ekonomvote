from django.db import models
from django.utils import timezone, dateparse
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from office_auth.models import AzureUser
import pytz

class Voting(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    planned_start = models.DateTimeField(null=False, unique=True)
    planned_end = models.DateTimeField(null=False, unique=True)
    votes_per_user = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1, 'Wartość musi być większa od 0')]
    )

    def parse_planned_start(self):
        return self.planned_start.astimezone(tz=pytz.timezone('Europe/Warsaw')).strftime('%Y.%m.%d %H:%M:%S')

    def parse_planned_end(self):
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

class Candidate(models.Model):
    first_name = models.CharField(null=False, max_length=150)
    second_name = models.CharField(default="", max_length=150)
    last_name = models.CharField(null=False, max_length=150)
    image = models.ImageField(upload_to='uploads/samorzad/', null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    school_class = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        return f'Candiate(first_name={self.first_name}, last_name={self.last_name})'

class ElectoralProgram(models.Model):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='electoral_programs', null=False)
    voting = models.ForeignKey(Voting, on_delete=models.CASCADE, related_name='electoral_programs', null=False)
    info = models.TextField(null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['candidate', 'voting'], name='unique_program_per_voting_per_candidate')
        ]

    def __str__(self):
        return f'ElectoralProgram(candidate={self.candidate.pk}, voting={self.voting.pk})'


class CandidateRegistration(models.Model):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='registrations')
    voting = models.ForeignKey(Voting, on_delete=models.CASCADE, related_name='candidate_registrations')
    is_eligible = models.BooleanField(default=False)  # Przeniesione z modelu Candidate
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['candidate', 'voting'], name='unique_candidate_per_voting')
        ]

    def __str__(self):
        return f'CandidateRegistration(candidate={self.candidate.pk}, voting={self.voting.pk})'

    def clean(self):
        voting = self.voting
        if voting.candidate_registrations.count() >= 50 and not voting.candidate_registrations.filter(
                pk=self.pk).exists():
            raise ValidationError("W głosowaniu nie może być więcej niż 20 kandydatów.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Vote(models.Model):
    candidate_registration = models.ForeignKey(CandidateRegistration, on_delete=models.CASCADE, related_name='votes')
    microsoft_user = models.ForeignKey(AzureUser, on_delete=models.CASCADE, related_name='votes')
    created_at = models.DateTimeField(auto_now_add=True)

    def parse_planned_end(self):
        return self.created_at.astimezone(tz=pytz.timezone('Europe/Warsaw')).strftime('%Y.%m.%d %H:%M:%S')

    def clean(self):
        voting = self.candidate_registration.voting
        if timezone.now() < voting.planned_start:
            raise ValidationError("Nie można głosować przed rozpoczęciem głosowania")
        if timezone.now() > voting.planned_end:
            raise ValidationError("Nie można głosować po zakończeniu głosowania")
        if not self.candidate_registration.is_eligible:
            raise ValidationError("Nie można oddać głosu na kandydata, który nie został dopuszczony do wyborów.")

    def save(self, *args, **kwargs):
        voting = self.candidate_registration.voting
        if Vote.objects.filter(
                candidate_registration__voting=voting,
                microsoft_user=self.microsoft_user
        ).count() == voting.votes_per_user:
            raise ValidationError("Użytkownik oddał już maksymalnie 3 głosy w głosowaniu")
        if self.pk:
            raise ValidationError("Edytowanie modelu Vote jest zabronione!")
        self.full_clean()
        super().save(*args, **kwargs)