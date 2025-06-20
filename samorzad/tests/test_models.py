from django.core.exceptions import ValidationError
from django.test import TestCase, TransactionTestCase
from django.utils import timezone, dateparse
from django.db.utils import IntegrityError

import pytz
from freezegun import freeze_time

from samorzad.models import Voting, Vote, Candidate, CandidateRegistration, ElectoralProgram
from office_auth.models import AzureUser


class VotingModelTest(TestCase):
    @freeze_time("2025-06-01 12:00:00")
    def setUp(self):
        self.base_voting = Voting.objects.create(
            planned_start=timezone.datetime(2025, 6, 2, 8, 30, 0, tzinfo=pytz.utc),
            planned_end = timezone.datetime(2025, 6, 4, 19, 30, 0, tzinfo=pytz.utc),
        )
        self.base_voting: Voting

    @freeze_time("2025-06-01 12:00:00")
    def test_votes_per_user(self):
        self.base_voting.votes_per_user = 0
        with self.assertRaises(ValidationError) as context:
            self.base_voting.save()
            error_dict = context.exception.error_dict
            self.assertIn('votes_per_user', error_dict,
                msg=f"Błąd nie dotyczy `votes_per_user`, tylko: {error_dict}"
            )
        self.base_voting.votes_per_user = -1
        with self.assertRaises(ValidationError) as context:
            self.base_voting.save()
            error_dict = context.exception.error_dict
            self.assertIn('votes_per_user', error_dict,
                msg=f"Błąd nie dotyczy `votes_per_user`, tylko: {error_dict}"
            )

    @freeze_time("2025-06-03 12:00:00")
    def test_edit_voting_after_start(self):
        with self.assertRaises(ValidationError):
            self.base_voting.save()

    @freeze_time("2025-06-03 12:00:00")
    def test_creating_not_in_future(self):
        with self.assertRaises(ValidationError):
            voting = Voting.objects.create(
                planned_start=timezone.datetime(2025, 6, 3, 12, 0, 0, tzinfo=pytz.utc),
                planned_end=timezone.datetime(2025, 6, 15, 8, 30, 0, tzinfo=pytz.utc),
            )

    @freeze_time("2025-06-01 12:00:00")
    def test_planned_end_after_start(self):
        with self.assertRaises(ValidationError):
            self.base_voting.planned_end = timezone.datetime(2025, 6, 2, 8, 30, 0, tzinfo=pytz.utc)
            self.base_voting.save()
            self.base_voting.planned_end = timezone.datetime(2025, 6, 2, 8, 29, 0, tzinfo=pytz.utc)
            self.base_voting.save()

class CandidateModelTest(TransactionTestCase):
    def setUp(self):
        self.candidate = Candidate.objects.create(
            first_name="Jan",
            second_name='Krzysztof',
            last_name='Nowak',
            image=None,
            school_class='3 TI'
        )

    def test_fields_nullability(self):
        self.candidate.first_name = None
        with self.assertRaises(IntegrityError):
            self.candidate.save()
        self.candidate.refresh_from_db()
        self.candidate.last_name = None
        with self.assertRaises(IntegrityError):
            self.candidate.save()
        self.candidate.refresh_from_db()
        self.candidate.school_class = None
        with self.assertRaises(IntegrityError):
            self.candidate.save()

class CandidateRegistrationModelTest(TestCase):
    @freeze_time('2025-06-01 12:00:00')
    def setUp(self):
        self.base_voting = Voting.objects.create(
            planned_start=timezone.datetime(2025, 6, 2, 8, 30, 0, tzinfo=pytz.utc),
            planned_end = timezone.datetime(2025, 6, 4, 19, 30, 0, tzinfo=pytz.utc),
        )
        self.base_voting:Voting
        for i in range(8):
            candidate = Candidate.objects.create(
                first_name=f"Jan{i}",
                last_name=f"Nowak{i}",
                school_class="1 TI"
            )
            registration = CandidateRegistration.objects.create(
                candidate=candidate,
                voting=self.base_voting,
                is_eligible=True
            )
            ElectoralProgram.objects.create(
                candidature=registration,
                info="Testowy program wyborczy"
            )

    @freeze_time('2025-06-01 12:00:00')
    def test_more_than_15_candidates(self):
        for i in range(7):
            candidate = Candidate.objects.create(
                first_name=f"Jan1{i}",
                last_name=f"Nowak1{i}",
                school_class="1 TI"
            )
            registration = CandidateRegistration.objects.create(
                candidate=candidate,
                voting=self.base_voting,
                is_eligible=True
            )
            ElectoralProgram.objects.create(
                candidature=registration,
                info="Testowy program wyborczy"
            )
        candidate = Candidate.objects.create(
            first_name=f"Jan1{i}",
            last_name=f"Nowak1{i}",
            school_class="1 TI"
        )
        with self.assertRaises(ValidationError):
            registration = CandidateRegistration.objects.create(
                candidate=candidate,
                voting=self.base_voting,
                is_eligible=True
            )
            ElectoralProgram.objects.create(
                candidature=registration,
                info="Testowy program wyborczy"
            )

    @freeze_time('2025-06-01 12:00:00')
    def test_candidature_duplicate(self):
        registration = Voting.objects.prefetch_related('candidate_registrations').filter(id=self.base_voting.id).first().candidate_registrations.first()
        with self.assertRaises(ValidationError):
            duplicated_registration = CandidateRegistration.objects.create(
                candidate=registration.candidate,
                voting=self.base_voting
            )

    @freeze_time('2025-06-02 08:30:00')
    def test_candidature_add_aftertime(self):
        candidate = Candidate.objects.create(
            first_name=f"Jan24",
            last_name=f"Nowak24",
            school_class="1 TI"
        )
        with self.assertRaises(ValidationError):
            registration = CandidateRegistration.objects.create(
                candidate=candidate,
                voting=self.base_voting,
                is_eligible=True
            )
            ElectoralProgram.objects.create(
                candidature=registration,
                info="Testowy program wyborczy"
            )

class ElectoralProgramModelTest(TransactionTestCase):
    @freeze_time('2025-06-01 12:00:00')
    def setUp(self):
        self.base_voting = Voting.objects.create(
            planned_start=timezone.datetime(2025, 6, 2, 8, 30, 0, tzinfo=pytz.utc),
            planned_end = timezone.datetime(2025, 6, 4, 19, 30, 0, tzinfo=pytz.utc),
        )
        self.base_voting:Voting
        for i in range(8):
            candidate = Candidate.objects.create(
                first_name=f"Jan{i}",
                last_name=f"Nowak{i}",
                school_class="1 TI"
            )
            registration = CandidateRegistration.objects.create(
                candidate=candidate,
                voting=self.base_voting,
                is_eligible=True
            )
            ElectoralProgram.objects.create(
                candidature=registration,
                info="Testowy program wyborczy"
            )
    def test_one_to_one_relation(self):
        registration = Voting.objects.prefetch_related('candidate_registrations').filter(
            id=self.base_voting.id).first().candidate_registrations.first()
        with self.assertRaises(IntegrityError):
            ElectoralProgram.objects.create(
                candidature=registration,
                info="Testowy program wyborczy"
            )

# TODO: Dodać testy modelu głosowania z wykorzystaniem fixtur







