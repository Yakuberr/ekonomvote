import msal
import requests
from django.conf import settings
from django.urls import reverse


class Office365Authentication:
    def __init__(self):
        self.client_id = settings.MICROSOFT_CLIENT_ID
        self.client_secret = settings.MICROSOFT_CLIENT_SECRET
        self.tenant_id = settings.MICROSOFT_TENANT_ID
        self.authority = f'https://login.microsoftonline.com/{self.tenant_id}'
        self.app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret
        )

    def generate_auth_url(self, redirect_uri, error_uri=None, state=None):
        """Generuje URL do autoryzacji"""
        params = {
            'scopes': ['User.Read'],
            'redirect_uri': redirect_uri
        }
        extra = {}
        if error_uri:
            extra['error_uri'] = error_uri
        if state:
            params['state'] = state
        if extra:
            params['extra_query_parameters'] = extra
        return self.app.get_authorization_request_url(**params)

    def get_token(self, authorization_code, redirect_uri):
        """Wymiana kodu autoryzacyjnego na token"""
        return self.app.acquire_token_by_authorization_code(
            authorization_code,
            scopes=['User.Read'],
            redirect_uri=redirect_uri
        )

    def get_user_info(self, access_token):
        """Pobiera informacje o użytkowniku"""
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        response = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers)
        user_info = response.json()
        return {
            'id': user_info.get('id'),
        }
