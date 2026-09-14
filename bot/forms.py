"""Web forms. Django's own auth forms are used wherever they fit — the previous
hand-rolled versions skipped password validation and duplicate checks entirely.
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)
    email = forms.EmailField(required=False)
    whatsapp_number = forms.CharField(
        max_length=20,
        required=False,
        help_text="With country code, e.g. +919876543210. Links your chat bookings.",
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "whatsapp_number")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean_whatsapp_number(self):
        number = (self.cleaned_data.get("whatsapp_number") or "").strip()
        if not number:
            return ""
        digits = number.replace(" ", "").replace("-", "")
        if not digits.startswith("+"):
            digits = "+91" + digits.lstrip("0")
        if not digits[1:].isdigit() or not (10 <= len(digits[1:]) <= 15):
            raise forms.ValidationError("Enter a valid number with country code.")
        return digits


class SearchForm(forms.Form):
    origin = forms.IntegerField(widget=forms.HiddenInput)
    destination = forms.IntegerField(widget=forms.HiddenInput)
    service_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )
    seats = forms.IntegerField(min_value=1, max_value=6, initial=1)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("origin") and cleaned.get("origin") == cleaned.get("destination"):
            raise forms.ValidationError("Origin and destination must be different stops.")
        return cleaned


class CheckoutForm(forms.Form):
    trip_id = forms.IntegerField(widget=forms.HiddenInput)
    origin = forms.IntegerField(widget=forms.HiddenInput)
    destination = forms.IntegerField(widget=forms.HiddenInput)
    seats = forms.IntegerField(min_value=1, max_value=6, widget=forms.HiddenInput)
    passenger_name = forms.CharField(
        max_length=80, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    whatsapp_number = forms.CharField(
        max_length=20, widget=forms.TextInput(attrs={"class": "form-control"})
    )

    def clean_whatsapp_number(self):
        number = (self.cleaned_data.get("whatsapp_number") or "").strip()
        digits = number.replace(" ", "").replace("-", "")
        if not digits.startswith("+"):
            digits = "+91" + digits.lstrip("0")
        if not digits[1:].isdigit() or not (10 <= len(digits[1:]) <= 15):
            raise forms.ValidationError("Enter a valid number with country code.")
        return digits


class PNRLookupForm(forms.Form):
    pnr = forms.CharField(
        max_length=10,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "IB7K4Q2M", "autocapitalize": "characters"}
        ),
    )
