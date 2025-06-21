from django.core.exceptions import ValidationError
from django.test import TestCase, TransactionTestCase
from django.utils import timezone, dateparse
from django.db.utils import IntegrityError

import pytz
import random
from typing import List
from freezegun import freeze_time

from samorzad.models import Voting, Vote, Candidate, CandidateRegistration, ElectoralProgram
from office_auth.models import AzureUser


def generate_votes(voting_id: int):
    """
    Generuje i zapisuje głosy do bazy danych dla danego głosowania i listy kandydatów.
    Nie wyłapuje błędów. Jeśli się wywali to ma się wywalić

    Args:
        voting_id (int): ID głosowania
        candidate_ids (List[int]): Lista ID kandydatów

    Returns:
        int: Liczba utworzonych głosów
    """

    candidates = CandidateRegistration.objects.filter(
        voting_id=voting_id,
        is_eligible=True
    )
    users = AzureUser.objects.all()
    voting = Voting.objects.filter(pk=voting_id).first()
    if not voting:
        raise ValueError(f"Głosowanie o ID {voting_id} nie istnieje!")
    for user in users:
            # Sprawdź ile głosów użytkownik już oddał w tym głosowaniu
            existing_votes = Vote.objects.filter(
                candidate_registration__voting=voting,
                microsoft_user=user
            ).count()
            if existing_votes >= voting.votes_per_user:
                print(f"Użytkownik {user} już oddał maksymalną liczbę głosów ({existing_votes})")
                continue
            # Oblicz ile głosów jeszcze może oddać
            remaining_votes = voting.votes_per_user - existing_votes
            votes_to_cast = min(len(candidates), remaining_votes)  # Maksymalnie tyle ile kandydatów lub ile zostało
            # Sprawdź na których kandydatów użytkownik już głosował
            already_voted_candidates = Vote.objects.filter(
                candidate_registration__voting=voting,
                microsoft_user=user
            ).values_list('candidate_registration', flat=True)
            available_candidates = candidates.exclude(pk__in=already_voted_candidates)
            if len(available_candidates) < votes_to_cast:
                votes_to_cast = len(available_candidates)
            if votes_to_cast == 0:
                print(f"Brak dostępnych kandydatów dla użytkownika {user}")
                continue
            selected_candidates = random.sample(list(available_candidates), votes_to_cast)
            # Tworzenie i zapis głosów do bazy danych
            for candidate_registration in selected_candidates:
                # Losowy czas w przedziale trwania głosowania
                total_seconds = int((voting.planned_end - voting.planned_start).total_seconds())
                random_seconds = random.randint(0, total_seconds)
                created_date = voting.planned_start + timezone.timedelta(seconds=random_seconds)
                vote = Vote.objects.create(
                    candidate_registration=candidate_registration,
                    microsoft_user=user,
                    created_at=created_date
                )



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

    def test_info_nullability(self):
        obj = ElectoralProgram.objects.all().first()
        obj.info = None
        with self.assertRaises(IntegrityError):
            obj.save()
        obj.refresh_from_db()




# TODO: Dodać testy modelu głosowania z wykorzystaniem fixtur
class VoteModelTest(TransactionTestCase):
    fixtures = ['azure_users_fixture.json']

    @freeze_time('2025-06-01 12:00:00')
    def setUp(self):
        self.base_voting = Voting.objects.create(
            planned_start=timezone.datetime(2025, 6, 2, 8, 30, 0, tzinfo=pytz.utc),
            planned_end=timezone.datetime(2025, 6, 15, 19, 30, 0, tzinfo=pytz.utc),
            votes_per_user=3
        )
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
        candidate = Candidate.objects.create(
            first_name=f"Jan_nielegal",
            last_name=f"Nowak_nielegal",
            school_class="1 TI"
        )
        registration = CandidateRegistration.objects.create(
            candidate=candidate,
            voting=self.base_voting,
            is_eligible=False
        )
        ElectoralProgram.objects.create(
            candidature=registration,
            info="Testowy program wyborczy"
        )
        self.candidature = self.base_voting.candidate_registrations.all()[2]
        self.azure_user = AzureUser.objects.first()


    @freeze_time('2025-06-02 08:31:00')
    def test_generating_valid_votes(self):
        # Nie powinno zwrócić żadnych błędów
        generate_votes(self.base_voting.id)

    @freeze_time('2025-06-02 08:29:59')
    def test_vote_before_start(self):
        with self.assertRaises(ValidationError):
            Vote.objects.create(
                candidate_registration=self.candidature,
                microsoft_user=self.azure_user
            )

    @freeze_time('2025-06-15 19:30:01')
    def test_vote_after_end(self):
        with self.assertRaises(ValidationError):
            Vote.objects.create(
                candidate_registration=self.candidature,
                microsoft_user=self.azure_user
            )

    @freeze_time('2025-06-02 08:31:00')
    def test_vote_for_not_eligible_candidature(self):
        candidature = CandidateRegistration.objects.filter(voting=self.base_voting, is_eligible=False).first()
        with self.assertRaises(ValidationError):
            Vote.objects.create(
                candidate_registration=candidature,
                microsoft_user=self.azure_user
            )

    @freeze_time('2025-06-02 08:31:00')
    def test_vote_duplicate(self):
        candidature = CandidateRegistration.objects.filter(voting=self.base_voting, is_eligible=True).first()
        Vote.objects.create(
            candidate_registration=candidature,
            microsoft_user=self.azure_user
        )
        with self.assertRaises(ValidationError):
            Vote.objects.create(
                candidate_registration=candidature,
                microsoft_user=self.azure_user
            )

    @freeze_time('2025-06-02 08:31:00')
    def test_vote_amount_per_voter(self):
        candidatures = CandidateRegistration.objects.filter(voting=self.base_voting, is_eligible=True)[:4]
        Vote.objects.create(
            candidate_registration=candidatures[0],
            microsoft_user=self.azure_user
        )
        Vote.objects.create(
            candidate_registration=candidatures[1],
            microsoft_user=self.azure_user
        )
        Vote.objects.create(
            candidate_registration=candidatures[2],
            microsoft_user=self.azure_user
        )
        with self.assertRaises(ValidationError):
            Vote.objects.create(
                candidate_registration=candidatures[3],
                microsoft_user=self.azure_user
            )

    @freeze_time('2025-06-02 08:31:00')
    def test_vote_editing(self):
        vote = Vote.objects.create(
            candidate_registration=self.candidature,
            microsoft_user=self.azure_user
        )
        new_user = AzureUser.objects.last()
        vote.microsoft_user = new_user
        with self.assertRaises(ValidationError):
            vote.save()






