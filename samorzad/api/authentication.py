from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.models import TokenUser
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from django.utils.translation import gettext_lazy as _

class NoDbJWTAuthentication(JWTAuthentication):
    """
    Klasa uwierzytelniająca JWT, która nie odpytuje bazy danych.
    Zamiast tego zwraca obiekt TokenUser na podstawie danych z tokenu.
    """
    def get_user(self, validated_token):
        """
        Nadpisuje domyślną metodę get_user, aby uniknąć zapytania do bazy.
        Zwraca instancję TokenUser wypełnioną danymi ze zweryfikowanego tokenu.
        """
        try:
            # Pobierz identyfikator użytkownika z roszczenia w tokenie
            user_id = validated_token[api_settings.USER_ID_CLAIM]
        except KeyError:
            # To nie powinno się zdarzyć dla poprawnie zweryfikowanego tokenu,
            # ale lepiej obsłużyć defensywnie.
            raise InvalidToken(_("Token contained no recognizable user identification"))
        user = TokenUser(validated_token)
        return user