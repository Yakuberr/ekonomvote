from django.core.exceptions import ValidationError
from django.forms import formset_factory
from django.test import TestCase, TransactionTestCase
from django.utils import timezone, dateparse
from django.db.utils import IntegrityError

import pytz
from freezegun import freeze_time

from oscary.models import VotingEvent,VotingRound
from panel.forms import OscaryAddWholeVotingEventForm

class WholeVotingEventFormTest(TestCase):
    def setUp(self):
        self.valid_data = {
            'with_nominations': True,
            'f_round_t_count': 5,
            'f_round_start': '2024-01-01 10:00:00',
            'f_round_end': '2024-01-01 15:00:00',
            'l_round_start': '2024-01-02 10:00:00',
            'l_round_end': '2024-01-02 15:00:00'
        }

    def test_fields_nullability_without_nomination(self):
        """Sprawdza poprawność walidacji formularza
        w przypadku kiedy poszczególne pola są puste"""
        d = {
            'with_nominations': False,
            'l_round_start': '2024-01-02 10:00:00',
            'l_round_end': '2024-01-02 15:00:00'
        }
        form = OscaryAddWholeVotingEventForm(data=d)
        self.assertEqual(form.is_valid(), True)
        self.assertEqual(len(form.errors), 0)
        d = {
            'with_nominations': False,
        }
        form = OscaryAddWholeVotingEventForm(data=d)
        self.assertEqual(form.is_valid(), False)
        for field, errors in form.errors.as_data().items():
            self.assertEqual(errors[0].code, 'required')

    def test_field_nullability_with_nominations(self):
        d = {
            'with_nominations': True,
            'l_round_start': '2024-01-02 10:00:00',
            'l_round_end': '2024-01-02 15:00:00'
        }
        form = OscaryAddWholeVotingEventForm(data=d)
        self.assertEqual(form.is_valid(), False)
        for field, errors in form.errors.as_data().items():
            self.assertEqual(errors[0].code, 'fields_required')

    def  test_invalid_data_types(self):
        d = {
            'with_nominations': "Kałamarnica",
            'f_round_t_count': '',
            'f_round_start': "Kałamarnica",
            'f_round_end': "Kałamarnica",
            'l_round_start': "True",
            'l_round_end': "1234"
        }
        form = OscaryAddWholeVotingEventForm(data=d)
        self.assertFalse(form.is_valid())
        for field, errors in list(form.errors.as_data().items())[1:]:
            self.assertEqual(errors[0].code, 'invalid')

