from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import generics, permissions, serializers


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ("id", "username", "password")

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class RegisterView(generics.CreateAPIView):
    """Inscription : POST {username, password}, puis /api/auth/login/ pour obtenir le JWT."""

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
