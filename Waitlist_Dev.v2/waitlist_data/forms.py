from django import forms
from .models import DoctrineFit

class XUpForm(forms.Form):
    # Users select a character they own
    character_id = forms.IntegerField(widget=forms.HiddenInput())
    
    # Users select a fit from the doctrine
    fit = forms.ModelChoiceField(
        queryset=DoctrineFit.objects.filter(is_doctrinal=True),
        empty_label="Select a Doctrine Fit",
        widget=forms.Select(attrs={'class': 'w-full bg-slate-900 border border-slate-600 rounded p-2 text-white'})
    )