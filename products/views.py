from rest_framework import viewsets, permissions, serializers
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from .models import Category, Product, ProductImage, Review, CartItem, Wishlist
from .serializers import (
    CategorySerializer,
    ProductSerializer,
    ProductImageSerializer,
    ReviewSerializer,
    CartItemSerializer,
    WishlistSerializer
)
from users.enums import UserRole


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            getattr(request.user, "role", None) == UserRole.ADMIN.value
        )


class IsVendorUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            getattr(request.user, "role", None) == UserRole.VENDOR.value
        )


class IsCustomerUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            getattr(request.user, "role", None) == UserRole.CUSTOMER.value
        )


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and getattr(user, "role", None) == UserRole.ADMIN.value:
            return Category.objects.all()
        return Category.objects.none()


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, "role", None)
        if role == UserRole.ADMIN.value:
            return Product.objects.all()
        elif role == UserRole.VENDOR.value:
            return Product.objects.filter(vendor=user)
        else:
            return Product.objects.filter(status="available")

    def perform_create(self, serializer):
        user = self.request.user
        if getattr(user, "role", None) == UserRole.VENDOR.value:
            serializer.save(vendor=user)
        else:
            raise permissions.PermissionDenied("Only vendors can create products.")

    @action(detail=False, methods=["GET"], permission_classes=[permissions.IsAuthenticated])
    def available_categories(self, request):
        categories = Category.objects.all()
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)


class ProductImageViewSet(viewsets.ModelViewSet):
    queryset = ProductImage.objects.all()
    serializer_class = ProductImageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, "role", None)
        if role == UserRole.ADMIN.value:
            return ProductImage.objects.all()
        elif role == UserRole.VENDOR.value:
            return ProductImage.objects.filter(product__vendor=user)
        return ProductImage.objects.none()

    def perform_create(self, serializer):
        product_id = self.request.data.get('product')
        if not product_id:
            raise serializers.ValidationError({"product": "Product ID is required."})

        product = get_object_or_404(Product, id=product_id)
        user = self.request.user
        role = getattr(user, "role", None)

        if product.vendor == user or role == UserRole.ADMIN.value:
            serializer.save(product=product)
        else:
            raise permissions.PermissionDenied("You cannot upload images for this product.")


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [IsCustomerUser]

    def get_queryset(self):
        product_id = self.request.query_params.get('product')
        if product_id:
            return Review.objects.filter(product_id=product_id)
        return Review.objects.none()

    def perform_create(self, serializer):
        product_id = self.request.data.get('product')
        if not product_id:
            raise serializers.ValidationError({"product": "Product ID is required."})

        product = get_object_or_404(Product, id=product_id)
        serializer.save(user=self.request.user, product=product)


class CartItemViewSet(viewsets.ModelViewSet):
    queryset = CartItem.objects.all()
    serializer_class = CartItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CartItem.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class WishlistViewSet(viewsets.ModelViewSet):
    queryset = Wishlist.objects.all()
    serializer_class = WishlistSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
