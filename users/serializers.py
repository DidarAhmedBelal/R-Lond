from rest_framework import serializers
from users.models import User, SellerApplication
from django.utils import timezone
from datetime import timedelta
from users.enums import SellerApplicationStatus
import random, string


# --------------------------
# USER SERIALIZERS
# --------------------------

class UserSerializer(serializers.ModelSerializer):
    profile_image = serializers.ImageField(allow_null=True, required=False)
    cover_image = serializers.ImageField(allow_null=True, required=False)
    phone_number = serializers.CharField(allow_null=True, required=False)
    secondary_number = serializers.CharField(allow_null=True, required=False)
    emergency_contact = serializers.CharField(allow_null=True, required=False)
    address = serializers.CharField(allow_null=True, required=False)
    gender = serializers.CharField(allow_null=True, required=False)
    date_of_birth = serializers.DateField(allow_null=True, required=False)
    national_id = serializers.CharField(allow_null=True, required=False)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'profile_image', 'cover_image',
            'phone_number', 'secondary_number', 'emergency_contact', 'address', 'gender',
            'date_of_birth', 'national_id', 'role'
        ]


class UserSignupSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(write_only=True)
    agree_to_terms = serializers.BooleanField(write_only=True)
    role = serializers.CharField(write_only=True, required=False, default='customer')

    class Meta:
        model = User
        fields = ['email', 'password', 'full_name', 'agree_to_terms', 'role']
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def validate_agree_to_terms(self, value):
        if not value:
            raise serializers.ValidationError("You must agree to the terms.")
        return value

    def create(self, validated_data):
        role = validated_data.pop('role', 'customer')
        full_name = validated_data.pop('full_name')
        first_name, *last_name = full_name.split(' ', 1)
        last_name = last_name[0] if last_name else ''
        password = validated_data.pop('password')

        user = User(
            email=validated_data['email'],
            first_name=first_name,
            last_name=last_name,
            role=role
        )
        user.set_password(password)
        user.save()
        return user


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class UserLoginResponseSerializer(serializers.Serializer):
    user = UserSerializer()
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'profile_image', 'cover_image',
            'phone_number', 'secondary_number', 'emergency_contact',
            'address', 'gender', 'date_of_birth', 'national_id'
        ]
        read_only_fields = ['email', 'role']


# --------------------------
# PASSWORD RESET SERIALIZERS
# --------------------------

class ForgotPasswordRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No user registered with this email.")
        return value

    def save(self):
        email = self.validated_data['email']
        user = User.objects.get(email=email)
        otp = user.generate_otp()
        # You might send OTP via email/SMS here
        return otp


class ForgotPasswordConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True)

    def validate(self, data):
        try:
            user = User.objects.get(email=data['email'])
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid email or OTP.")

        if user.otp_code != data['otp_code']:
            raise serializers.ValidationError("Invalid OTP code.")

        if user.otp_created_at is None or timezone.now() - user.otp_created_at > timedelta(minutes=10):
            raise serializers.ValidationError("OTP expired. Please request a new one.")

        return data

    def save(self):
        user = User.objects.get(email=self.validated_data['email'])
        user.set_password(self.validated_data['new_password'])
        user.otp_code = None
        user.otp_created_at = None
        user.save()
        return user


# --------------------------
# SELLER APPLICATION SERIALIZERS
# --------------------------

class SellerApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerApplication
        exclude = ['verification_code', 'created_at', 'updated_at', 'first_name', 'last_name', 'owner_images']
        read_only_fields = ['status', 'user']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class SellerApplicationAdminUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerApplication
        fields = ['status']

    def validate_status(self, value):
        allowed_statuses = [
            SellerApplicationStatus.APPROVED.value,
            SellerApplicationStatus.REJECTED.value,
        ]
        if value not in allowed_statuses:
            raise serializers.ValidationError(
                f"Status must be one of: {', '.join(allowed_statuses)}"
            )
        return value

    def update(self, instance, validated_data):
        old_status = instance.status
        new_status = validated_data['status']

        if old_status == new_status:
            raise serializers.ValidationError("Status is already set to this value.")

        # Generate verification code if approved
        if new_status == SellerApplicationStatus.APPROVED.value:
            instance.verification_code = ''.join(
                random.choices(string.ascii_uppercase + string.digits, k=6)
            )
            # Also change user role to vendor
            instance.user.role = "vendor"
            instance.user.save()

        instance.status = new_status
        instance.updated_at = timezone.now()
        instance.save()
        return instance