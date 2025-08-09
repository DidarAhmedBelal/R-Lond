# users/views.py

from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from users.serializers import (
    UserSignupSerializer,
    UserProfileUpdateSerializer,
    ForgotPasswordRequestSerializer,
    ForgotPasswordConfirmSerializer,UserSerializer,
    UserLoginResponseSerializer,
    UserLoginSerializer
)
from users.models import User
from rest_framework.views import APIView
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django_filters.rest_framework import DjangoFilterBackend




class UserListView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser] 
    queryset = User.objects.all()
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['email', 'first_name', 'last_name']
    ordering_fields = ['email', 'first_name', 'last_name', 'role']

    def get_queryset(self):
        queryset = super().get_queryset()
        role = self.request.query_params.get('role', None)
        if role in ['vendor', 'customer', 'admin']:
            queryset = queryset.filter(role=role)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                "total_users": queryset.count(),
                "users": serializer.data
            })

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "total_users": queryset.count(),
            "users": serializer.data
        })
    


class UserLoginView(generics.GenericAPIView):
    serializer_class = UserLoginSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        password = serializer.validated_data['password']

        user = authenticate(request, email=email, password=password)
        if user is None:
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)
        if not user.is_active:
            return Response({"detail": "User account is disabled."}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)
        user_data = UserSerializer(user).data

        response_data = {
            'user': user_data,
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
        }
        response_serializer = UserLoginResponseSerializer(response_data)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class BaseUserSignupView(generics.CreateAPIView):
    serializer_class = UserSignupSerializer
    permission_classes = [permissions.AllowAny]
    role = None  

    def create(self, request, *args, **kwargs):
        signup_serializer = self.get_serializer(data=request.data)
        signup_serializer.is_valid(raise_exception=True)
        
        user = signup_serializer.save(role=self.role)

        user_data = UserSerializer(user, context=self.get_serializer_context()).data

        refresh = RefreshToken.for_user(user)
        response_data = {
            'user': user_data,
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
        }
        return Response(response_data, status=status.HTTP_201_CREATED)


class CustomerSignupView(BaseUserSignupView):
    role = 'customer'


class VendorSignupView(BaseUserSignupView):
    role = 'vendor'



class UserProfileUpdateView(generics.UpdateAPIView):
    serializer_class = UserProfileUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ForgotPasswordRequestView(generics.GenericAPIView):
    serializer_class = ForgotPasswordRequestSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "OTP sent to your email."})


class ForgotPasswordConfirmView(generics.GenericAPIView):
    serializer_class = ForgotPasswordConfirmSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Password reset successful."})


