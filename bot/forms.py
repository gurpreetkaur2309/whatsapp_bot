from django import forms



from .models import Booking


# forms.py
from django import forms
from .models import Booking, Route

# forms.py


class BookingForm(forms.ModelForm):
    whatsapp_number = forms.CharField(max_length=15, required=True)
    class Meta:
        model = Booking
        fields = ['route', 'ticket_count','whatsapp_number']

    def __init__(self, *args, **kwargs):
        super(BookingForm, self).__init__(*args, **kwargs)
        self.fields['route'].queryset = Route.objects.all()  # Populate the route field with available routes