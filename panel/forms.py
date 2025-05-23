from django import forms
from django.core.exceptions import ValidationError

import string

class PanelLoginForm(forms.Form):
    login = forms.CharField(min_length=1, max_length=1024, empty_value='N/A')
    password = forms.CharField(min_length=8, max_length=1024, empty_value='')

    def clean(self):
        super().clean()
        password = self.cleaned_data.get('password')
        if password is None:
            password = ''
        has_lower = any(c in string.ascii_lowercase for c in password)
        has_upper = any(c in string.ascii_uppercase for c in password)
        has_digit = any(c in string.digits for c in password)
        has_special = any(c in string.punctuation for c in password)
        if not (has_lower and has_upper and has_digit and has_special):
            raise ValidationError("Hasło musi mieć minimum 8 znaków zawierać małe i duże litery, cyfrę oraz znak specjalny.")
        return self.cleaned_data
