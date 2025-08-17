from django.test import TestCase
from django.urls import reverse
from django.http import HttpResponse
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone
from django.contrib.messages import get_messages
from datetime import timedelta
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

import pytz
from freezegun import freeze_time

from oscary.models import VotingEvent, VotingRound
from office_auth.models import AzureUser, ActionLog


class CreateVotingEventTest(TestCase):
    """
    Testy widoku tworzenia wydarzenia głosowania.
    Sprawdzają zarówno poprawne utworzenie obiektów, jak i obsługę błędów walidacji.
    """
    fixtures = ['auth_groups.json']

    def setUp(self):
        self.valid_user = AzureUser.objects.create(
            username='admin',
            password="ZAQ!2wsx",
            is_superuser=True,
        )
        self.invalid_user = AzureUser.objects.create(
            username='user',
            password="ZAQ!2wsx",
            is_superuser=False
        )
        opiekun_group = Group.objects.filter(name='opiekunowie').first()
        wyborcy_group = Group.objects.filter(name='wyborcy').first()
        self.valid_user.groups.add(opiekun_group)
        self.invalid_user.groups.add(wyborcy_group)
        self.url = reverse('panel:create_voting_event')

    def _login_valid_user(self):
        """Loguje poprawnego użytkownika do sesji testowej."""
        session = self.client.session
        session['microsoft_user_id'] = '11223344'
        session.save()
        self.client.force_login(self.valid_user)

    def _future_datetime(self, days_ahead):
        """Zwraca datę w przyszłości przesuniętą o days_ahead dni."""
        return timezone.now() + timedelta(days=days_ahead)

    def test_post_valid_data_creates_event_and_rounds(self):
        """
        Testuje, że wysłanie poprawnych danych w formularzu:
        - tworzy jeden obiekt VotingEvent,
        - tworzy jedną rundę typu FINAL,
        - zapisuje odpowiednie wpisy w ActionLog,
        - przekierowuje użytkownika po utworzeniu obiektów.
        """
        self._login_valid_user()

        l_start = timezone.now() + timedelta(days=2)
        l_end = timezone.now() + timedelta(days=3)

        data = {
            "with_nominations": False,
            "l_round_start": l_start,
            "l_round_end": l_end,
        }

        response = self.client.post(reverse('panel:create_voting_event'), data)
        self.assertEqual(response.status_code, 302)

        self.assertEqual(VotingEvent.objects.count(), 1)
        self.assertEqual(VotingRound.objects.count(), 1)

        event = VotingEvent.objects.first()
        round_final = VotingRound.objects.first()

        self.assertEqual(round_final.round_type, VotingRound.VotingRoundType.FINAL)
        self.assertEqual(round_final.voting_event, event)

        logs_event = ActionLog.objects.filter(
            content_type=ContentType.objects.get_for_model(VotingEvent)
        )
        logs_round = ActionLog.objects.filter(
            content_type=ContentType.objects.get_for_model(VotingRound)
        )
        self.assertEqual(logs_event.count(), 1)
        self.assertEqual(logs_round.count(), 1)

    def test_post_invalid_data_shows_messages_and_no_objects(self):
        """
        Testuje, że wysłanie niepoprawnych danych:
        - wyświetla komunikaty o błędach walidacji w systemie messages,
        - nie tworzy żadnych obiektów VotingEvent ani VotingRound,
        - zwraca kod odpowiedzi 200 (strona formularza z błędami).
        """
        self._login_valid_user()

        data = {
            "with_nominations": False,
            "l_round_start": "",
            "l_round_end": "",
        }

        response = self.client.post(reverse('panel:create_voting_event'), data, follow=True)
        self.assertEqual(response.status_code, 200)

        storage = list(get_messages(response.wsgi_request))
        self.assertGreater(len(storage), 0)
        messages_text = [m.message for m in storage]
        self.assertTrue(any("musi być podana" in msg for msg in messages_text))

        self.assertEqual(VotingEvent.objects.count(), 0)
        self.assertEqual(VotingRound.objects.count(), 0)

    def test_post_without_nominations_creates_final_round(self):
        """POST z poprawnymi danymi i without_nominations=False tworzy VotingEvent + 1 rundę FINAL."""
        self._login_valid_user()
        payload = {
            'with_nominations': False,
            'l_round_start': self._future_datetime(10),
            'l_round_end': self._future_datetime(20)
        }
        response = self.client.post(self.url, data=payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(VotingEvent.objects.count(), 1)
        self.assertEqual(VotingRound.objects.count(), 1)
        round_obj = VotingRound.objects.first()
        self.assertEqual(round_obj.round_type, VotingRound.VotingRoundType.FINAL)

    def test_post_with_nominations_creates_two_rounds(self):
        """POST z with_nominations=True i kompletem danych tworzy VotingEvent + 2 rundy."""
        self._login_valid_user()
        payload = {
            'with_nominations': True,
            'f_round_t_count': 2,
            'f_round_start': self._future_datetime(10).strftime('%Y-%m-%d %H:%M:%S'),
            'f_round_end': self._future_datetime(20).strftime('%Y-%m-%d %H:%M:%S'),
            'l_round_start': self._future_datetime(30).strftime('%Y-%m-%d %H:%M:%S'),
            'l_round_end': self._future_datetime(40).strftime('%Y-%m-%d %H:%M:%S')
        }
        response = self.client.post(self.url, data=payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(VotingEvent.objects.count(), 1)
        self.assertEqual(VotingRound.objects.count(), 2)
        self.assertEqual(ActionLog.objects.count(), 3)

    def test_post_invalid_dates_returns_error_and_no_db_changes(self):
        """POST z planned_start >= planned_end powoduje błąd walidacji i brak wpisów w DB."""
        self._login_valid_user()
        bad_start = self._future_datetime(10)
        bad_end = self._future_datetime(5)
        payload = {
            'with_nominations': False,
            'l_round_start': bad_start,
            'l_round_end': bad_end
        }
        response = self.client.post(self.url, data=payload, follow=True)
        self.assertEqual(VotingEvent.objects.count(), 0)
        self.assertEqual(VotingRound.objects.count(), 0)
        storage = get_messages(response.wsgi_request)
        for m in storage:
            self.assertEqual(m.message, 'Nie udało się dodać głosowań')

    def test_nomination_after_final_returns_error(self):
        """POST z rundą nominacji po dacie startu finału powoduje błąd i brak wpisów w DB."""
        self._login_valid_user()
        payload = {
            'with_nominations': True,
            'f_round_t_count': 2,
            'f_round_start': self._future_datetime(40),
            'f_round_end': self._future_datetime(50),
            'l_round_start': self._future_datetime(10),
            'l_round_end': self._future_datetime(20)
        }
        response = self.client.post(self.url, data=payload, follow=True)
        self.assertEqual(VotingEvent.objects.count(), 0)
        self.assertEqual(VotingRound.objects.count(), 0)
        storage = get_messages(response.wsgi_request)
        for m in storage:
            self.assertEqual(m.message, 'Nie udało się dodać głosowań')


class UpdateVotingEventTest(TestCase):
    """
    Testy widoku edycji wydarzenia głosowania.
    Sprawdzają zarówno poprawne utworzenie obiektów, jak i obsługę błędów walidacji.
    """
    fixtures = ['auth_groups.json']

    @freeze_time('2025-01-01 10:00:00')
    def setUp(self):
        self.valid_user = AzureUser.objects.create(
            username='admin',
            password="ZAQ!2wsx",
            is_superuser=True,
        )
        self.invalid_user = AzureUser.objects.create(
            username='user',
            password="ZAQ!2wsx",
            is_superuser=False
        )
        opiekun_group = Group.objects.filter(name='opiekunowie').first()
        wyborcy_group = Group.objects.filter(name='wyborcy').first()
        self.valid_user.groups.add(opiekun_group)
        self.invalid_user.groups.add(wyborcy_group)
        self.voting_event = VotingEvent.objects.create(
            with_nominations=True
        )
        self.voting_final = VotingRound.objects.create(
            planned_start = timezone.datetime(2025, 1, 5, 10, 0, 0, tzinfo=pytz.utc),
            planned_end=timezone.datetime(2025, 1, 6, 10, 0, 0, tzinfo=pytz.utc),
            voting_event=self.voting_event,
            round_type=VotingRound.VotingRoundType.FINAL
        )
        self.voting_nomination = VotingRound.objects.create(
            planned_start = timezone.datetime(2025, 1, 2, 10, 0, 0, tzinfo=pytz.utc),
            planned_end=timezone.datetime(2025, 1, 3, 10, 0, 0, tzinfo=pytz.utc),
            max_tearchers_for_end = 4,
            voting_event=self.voting_event,
            round_type=VotingRound.VotingRoundType.NOMINATION
        )

    def _login_valid_user(self):
        """Loguje poprawnego użytkownika do sesji testowej."""
        session = self.client.session
        session['microsoft_user_id'] = '11223344'
        session.save()
        self.client.force_login(self.valid_user)

    @freeze_time('2025-01-01 10:00:00')
    def test_valid_request_context(self):
        self._login_valid_user()
        post_data = {

        }
        response = self.client.post(reverse('panel:update_voting_event', kwargs={'voting_event_id':self.voting_event.id}))
        print(response.context)
        print(response.status_code)
        print(response.context_data)





