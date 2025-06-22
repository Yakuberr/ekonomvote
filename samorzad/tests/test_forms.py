from django.core.exceptions import ValidationError
from django.forms import formset_factory
from django.test import TestCase, TransactionTestCase
from django.utils import timezone, dateparse
from django.db.utils import IntegrityError

import pytz
from freezegun import freeze_time

from samorzad.models import Voting, Vote, Candidate, CandidateRegistration, ElectoralProgram
from samorzad.forms import VoteForm, BaseVoteFormSet
from office_auth.models import AzureUser

class VoteFormTest(TestCase):
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
        self.candidature = self.base_voting.candidate_registrations.first()
        self.azure_user = AzureUser.objects.first()

    def test_fields_nullability(self):
        data = {
            'candidate_registration_id':None,
        }
        form = VoteForm(data=data, voting=self.base_voting)
        self.assertFalse(form.is_valid())
        code = form.errors.get_json_data().get('candidate_registration_id')[0].get('code')
        self.assertEqual(code, 'required')
        data = {
            'candidate_registration_id':'None',
        }
        form = VoteForm(data=data, voting=self.base_voting)
        self.assertFalse(form.is_valid())
        code = form.errors.get_json_data().get('candidate_registration_id')[0].get('code')
        self.assertEqual(code, 'invalid')
        data = {
            'candidate_registration_id':'',
        }
        form = VoteForm(data=data, voting=self.base_voting)
        self.assertFalse(form.is_valid())
        code = form.errors.get_json_data().get('candidate_registration_id')[0].get('code')
        self.assertEqual(code, 'required')

    def test_registration_exists(self):
        data = {
            'candidate_registration_id':'123',
        }
        form = VoteForm(data=data, voting=self.base_voting)
        self.assertFalse(form.is_valid())
        code = form.errors.get_json_data().get('__all__')[0].get('code')
        self.assertEqual(code, 'candidature_does_not_exist')

    @freeze_time('2025-06-01 12:00:00')
    def test_registration_not_in_voting(self):
        voting = Voting.objects.create(
            planned_start=timezone.datetime(2025, 6, 2, 8, 30, 0, tzinfo=pytz.utc),
            planned_end=timezone.datetime(2025, 6, 15, 19, 30, 0, tzinfo=pytz.utc),
        )
        data = {
            'candidate_registration_id': self.candidature.id,
        }
        form = VoteForm(data=data, voting=voting)
        self.assertFalse(form.is_valid())
        code = form.errors.get_json_data().get('__all__')[0].get('code')
        self.assertEqual(code, 'candidature_not_in_voting')


class BaseVoteFormSetTest(TestCase):
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
        self.candidatures = self.base_voting.candidate_registrations.all()[:3]
        self.azure_user = AzureUser.objects.first()
        self.formset = formset_factory(VoteForm, formset=BaseVoteFormSet, extra=0)

    def test_valid_formset(self):
        data = {
            'form-TOTAL_FORMS':self.base_voting.votes_per_user,
            'form-INITIAL_FORMS':0,
            'form-0-candidate_registration_id':self.candidatures[0].id,
            'form-1-candidate_registration_id': self.candidatures[1].id,
            'form-2-candidate_registration_id': self.candidatures[2].id,
        }
        formset = self.formset(data=data, voting=self.base_voting)
        self.assertTrue(formset.is_valid())

    def test_invalid_form_count(self):
        data = {
            'form-TOTAL_FORMS':self.base_voting.votes_per_user,
            'form-INITIAL_FORMS':0,
            'form-0-candidate_registration_id':self.candidatures[0].id,
            'form-1-candidate_registration_id': self.candidatures[1].id,
        }
        formset = self.formset(data=data, voting=self.base_voting)
        self.assertFalse(formset.is_valid())
        code = formset.non_form_errors().get_json_data()[0].get('code')
        self.assertEqual(code, 'invalid_form_count')