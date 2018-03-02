from django import forms

SERVER_OPTIONS = [
    ('xbrivas0', 'Campo Grande'),
    ('xbrivas1', 'Minas Gerais'),
]

class ServerForm(forms.Form):
    remoteserver = forms.CharField(widget=forms.Select(choices=SERVER_OPTIONS), label='Choose the Remote Server')
    textaread = forms.Textarea()