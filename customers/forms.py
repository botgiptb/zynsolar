import re
from django import forms
from .models import Customer, CustomerAttachment


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            'name', 'customer_type', 'company_name', 'status',
            'phone', 'alt_phone', 'email', 'lead_source',
            'notes'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'id': 'customerNameInput', 'placeholder': 'e.g. John Doe / GreenTech Corp'}),
            'customer_type': forms.Select(attrs={'class': 'form-select', 'id': 'customerTypeSelect'}),
            'company_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company name (for business)'}),
            'status': forms.Select(attrs={'class': 'form-select', 'id': 'statusSelect'}),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'customerPhoneInput',
                'placeholder': '10-digit mobile number',
                'maxlength': '10',
                'inputmode': 'numeric',
                'data-country-phone': 'true'
            }),
            'alt_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'customerAltPhoneInput',
                'placeholder': '10-digit alternative phone',
                'maxlength': '10',
                'inputmode': 'numeric',
                'data-country-phone': 'true'
            }),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'example@domain.com'}),
            'lead_source': forms.Select(attrs={'class': 'form-select', 'id': 'id_lead_source'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Enter customer notes, preferences, or special instructions...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['lead_source'].choices = Customer.get_lead_source_choices()
        self.fields['lead_source'].required = False
        if not self.instance.pk and not self.initial.get('lead_source'):
            choices = self.fields['lead_source'].choices
            if choices:
                self.initial['lead_source'] = choices[0][0]

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        digits = re.sub(r'\D', '', phone)
        if len(digits) != 10:
            raise forms.ValidationError("Primary mobile number must be exactly 10 digits.")
        # Duplicate check excluding current instance
        existing = Customer.objects.filter(phone=digits)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError(f"A customer with phone number '{digits}' already exists ({existing.first().name}).")
        return digits

    def clean_alt_phone(self):
        alt_phone = self.cleaned_data.get('alt_phone', '').strip()
        if not alt_phone:
            return ''
        digits = re.sub(r'\D', '', alt_phone)
        if len(digits) != 10:
            raise forms.ValidationError("Alternative phone number must be exactly 10 digits.")
        return digits

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.customer_type == 'BUSINESS' and not instance.company_name:
            instance.company_name = instance.name
        if commit:
            instance.save()
        return instance


class CustomerAttachmentForm(forms.ModelForm):
    class Meta:
        model = CustomerAttachment
        fields = ['category', 'title', 'file']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Identity Proof, Electricity Bill'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
        }
