import re
from decimal import Decimal
from django import forms
from django.contrib.auth.models import User
from .models import UserProfile, TeamMember, Team


class RegistrationForm(forms.Form):
    first_name = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter first name',
            'autocomplete': 'given-name'
        })
    )
    last_name = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter last name',
            'autocomplete': 'family-name'
        })
    )
    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Choose username',
            'autocomplete': 'username'
        })
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'name@company.com',
            'autocomplete': 'email'
        })
    )
    phone = forms.CharField(
        max_length=10,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '10-digit mobile number',
            'autocomplete': 'tel',
            'maxlength': '10',
            'inputmode': 'numeric',
            'data-country-phone': 'true'
        })
    )
    role = forms.ChoiceField(
        choices=UserProfile.ROLE_CHOICES,
        initial='SALES',
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Create password (min 6 characters)',
            'autocomplete': 'new-password'
        })
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm password',
            'autocomplete': 'new-password'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].choices = UserProfile.get_role_choices()

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken. Please choose another.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email address already exists.")
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if not phone:
            return ''
        digits = re.sub(r'\D', '', phone)
        if len(digits) != 10:
            raise forms.ValidationError("Phone number must be exactly 10 digits.")
        return digits

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and len(password) < 6:
            self.add_error('password', "Password must be at least 6 characters long.")

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")

        return cleaned_data

    def save(self):
        first_name = self.cleaned_data['first_name']
        last_name = self.cleaned_data['last_name']
        username = self.cleaned_data['username']
        email = self.cleaned_data['email']
        phone = self.cleaned_data.get('phone', '')
        role = self.cleaned_data.get('role', 'SALES')
        password = self.cleaned_data['password']

        # Created inactive pending administrator approval
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_active=False
        )

        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.phone = phone
        profile.role = role
        profile.status = UserProfile.STATUS_PENDING
        profile.save()

        return user


class TeamMemberForm(forms.ModelForm):
    class Meta:
        model = TeamMember
        fields = [
            'name', 'designation', 'phone', 'email',
            'is_active', 'notes'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name or Crew Identifier'}),
            'designation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Senior Solar Advisor, Technical Lead, Field Operations'}),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '10-digit phone number',
                'maxlength': '10',
                'inputmode': 'numeric',
                'data-country-phone': 'true'
            }),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'member@company.com'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Internal notes, certifications, vehicle registration, etc.'}),
        }

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if not phone:
            return ''
        digits = re.sub(r'\D', '', phone)
        if len(digits) != 10:
            raise forms.ValidationError("Phone number must be exactly 10 digits.")
        return digits


class StaffUserModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        name = obj.get_full_name().strip()
        prof = getattr(obj, 'profile', None)
        role = prof.get_role_display() if prof else ''
        if name:
            if role:
                return f"{name} • {role} (@{obj.username})"
            return f"{name} (@{obj.username})"
        return f"@{obj.username}"


class TeamForm(forms.ModelForm):
    leader = StaffUserModelChoiceField(
        queryset=User.objects.filter(is_active=True).select_related('profile').order_by('first_name', 'username'),
        required=False,
        empty_label="-- Select Team Leader (Optional) --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    members = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True).select_related('profile').order_by('first_name', 'username'),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': 5})
    )

    class Meta:
        model = Team
        fields = ['name', 'description', 'leader', 'members', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Alpha, Beta, Omega, South Installation Crew'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Team operational scope, coverage zone, or specialization'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class AdminUserCreateForm(forms.ModelForm):
    first_name = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}))
    last_name = forms.CharField(max_length=50, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'user@solarpro.in'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}), required=True)
    phone = forms.CharField(
        max_length=10,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '10-digit mobile number',
            'maxlength': '10',
            'inputmode': 'numeric',
            'data-country-phone': 'true'
        })
    )
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].choices = UserProfile.get_role_choices()

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if not phone:
            return ''
        digits = re.sub(r'\D', '', phone)
        if len(digits) != 10:
            raise forms.ValidationError("Phone number must be exactly 10 digits.")
        return digits

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Unique Username'}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        user.is_active = True
        user.is_staff = self.cleaned_data['role'] in [UserProfile.ROLE_ADMIN, UserProfile.ROLE_MANAGER]
        if commit:
            user.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = self.cleaned_data['role']
            profile.phone = self.cleaned_data.get('phone', '')
            profile.status = UserProfile.STATUS_APPROVED
            profile.save()
        return user
