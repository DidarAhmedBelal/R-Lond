# common/views.py
from rest_framework import viewsets, permissions, filters, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError
from django.shortcuts import get_object_or_404
from django.db import transaction

from common.models import Category, Tag, SEO, SavedProduct, Review, CartItem
from common.serializers import (
    CategorySerializer, TagSerializer, SEOSerializer,
    SavedProductSerializer, ReviewSerializer, CartItemSerializer
)
from products.models import Product 
from products.enums import ProductStatus


# -------------------
# Permissions
# -------------------
class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)


class IsVendorOrAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        user = request.user
        return user and user.is_authenticated and (user.is_staff or getattr(user, "role", None) == "vendor")


class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return getattr(obj, 'vendor', None) == request.user or getattr(obj, 'user', None) == request.user


# -------------------
# Category
# -------------------
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]  
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['name']


# -------------------
# Tag
# -------------------
class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [IsVendorOrAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['name']

    def create(self, request, *args, **kwargs):
        """
        If tag with same name exists (case-insensitive), reuse it.
        Else create new.
        """
        name = (request.data.get('name') or "").strip()
        if not name:
            raise DRFValidationError({"name": "This field is required."})

        tag = Tag.objects.filter(name__iexact=name).first()
        if tag:
            serializer = self.get_serializer(tag)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = self.get_serializer(data={"name": name})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# -------------------
# SEO
# -------------------
class SEOViewSet(viewsets.ModelViewSet):
    queryset = SEO.objects.all()
    serializer_class = SEOSerializer
    permission_classes = [IsVendorOrAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'meta_description']
    ordering_fields = ['id']

    def create(self, request, *args, **kwargs):

        title = (request.data.get('title') or "").strip()
        if not title:
            raise DRFValidationError({"title": "This field is required."})

        seo = SEO.objects.filter(title__iexact=title).first()
        if seo:
            serializer = self.get_serializer(seo)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# -------------------
# SavedProduct
# -------------------
# class SavedProductViewSet(viewsets.ModelViewSet):
#     serializer_class = SavedProductSerializer
#     permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
#     filter_backends = [filters.SearchFilter, filters.OrderingFilter]
#     search_fields = ['name', 'status']
#     ordering_fields = ['created_at', 'updated_at']
#     ordering = ['-created_at']

#     def get_queryset(self):
#         return SavedProduct.objects.filter(vendor=self.request.user)

#     def perform_create(self, serializer):
#         if getattr(self.request.user, "role", None) != "vendor":
#             raise PermissionDenied("Only vendors can save products.")
#         serializer.save(vendor=self.request.user)

#     def create(self, request, *args, **kwargs):
#         product_id = request.data.get('product_id')
#         action_type = request.data.get('action', 'save')  # "save" or "submit"

#         if not product_id:
#             raise DRFValidationError({"product_id": "This field is required."})

#         product = get_object_or_404(Product, pk=product_id)

#         snapshot = {
#             "id": product.id,
#             "name": product.name,
#             "slug": product.slug,
#             "price": str(product.active_price),
#             "is_active": product.is_active,
#             "status": product.status,
#         }

#         existing = SavedProduct.objects.filter(vendor=request.user, data__id=product.id).first()
#         if existing:
#             if action_type == "submit":
#                 existing.status = "submitted"
#                 existing.save()
#             serializer = self.get_serializer(existing)
#             return Response(serializer.data, status=status.HTTP_200_OK)

#         saved_status = "submitted" if action_type == "submit" else "draft"
#         obj = SavedProduct.objects.create(
#             vendor=request.user,
#             name=product.name,
#             data=snapshot,
#             status=saved_status
#         )
#         serializer = self.get_serializer(obj)
#         return Response(serializer.data, status=status.HTTP_201_CREATED)



class SavedProductViewSet(viewsets.ModelViewSet):
    serializer_class = SavedProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        return SavedProduct.objects.filter(vendor=self.request.user)

    def perform_create(self, serializer):
        if getattr(self.request.user, "role", None) != "vendor":
            raise PermissionDenied("Only vendors can save products.")
        serializer.save(vendor=self.request.user)

    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)


# -------------------
# Review
# -------------------

class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [
        permissions.IsAuthenticatedOrReadOnly,
        IsOwnerOrReadOnly
    ]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['product__name', 'comment']
    ordering_fields = ['created_at', 'updated_at', 'rating']
    ordering = ['-created_at']

    def get_queryset(self):

        return Review.objects.select_related('product', 'user').filter(
            product__status=ProductStatus.APPROVED.value
        )

    def perform_create(self, serializer):

        user = self.request.user

        # Only customers can create reviews
        if getattr(user, 'role', None) != 'customer':
            raise PermissionDenied("Only customers can create reviews.")

        product = serializer.validated_data.get('product')

        # Product must be approved
        if product.status != ProductStatus.APPROVED.value:
            raise PermissionDenied("Cannot review a product that is not approved.")

        serializer.save(user=user)



# -------------------
# CartItem
# -------------------
class CartItemViewSet(viewsets.ModelViewSet):
    serializer_class = CartItemSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['product__name']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    def get_queryset(self):
        return CartItem.objects.select_related('product', 'user').filter(user=self.request.user)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Expect payload: {"product_id": <int>, "quantity": <int>}
        If same product in cart -> increment quantity (but check stock).
        price_snapshot = current active price of product.
        """
        product_id = request.data.get('product_id')
        quantity = int(request.data.get('quantity', 1))

        if not product_id:
            raise DRFValidationError({"product_id": "This field is required."})
        if quantity < 1:
            raise DRFValidationError({"quantity": "Quantity must be >= 1."})

        product = get_object_or_404(Product, pk=product_id)

        # check stock if product uses stock
        if product.is_stock and quantity > product.stock_quantity:
            raise DRFValidationError({"quantity": "Requested quantity exceeds available stock."})

        # if item exists, increase quantity (but don't exceed stock)
        cart_item = CartItem.objects.filter(user=request.user, product=product).first()
        if cart_item:
            new_qty = cart_item.quantity + quantity
            if product.is_stock and new_qty > product.stock_quantity:
                raise DRFValidationError({"quantity": "Resulting quantity exceeds available stock."})
            cart_item.quantity = new_qty
            cart_item.price_snapshot = product.active_price
            cart_item.save()
            serializer = self.get_serializer(cart_item)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # create new cart item
        cart_item = CartItem.objects.create(
            user=request.user,
            product=product,
            quantity=quantity,
            price_snapshot=product.active_price
        )
        serializer = self.get_serializer(cart_item)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def checkout(self, request):
        """
        Simple checkout endpoint: returns cart items and total.
        (Integrate real payment gateway here.)
        """
        items = self.get_queryset()
        total = sum((item.price_snapshot * item.quantity) for item in items)
        serialized = self.get_serializer(items, many=True).data
        return Response({
            "items": serialized,
            "total": str(total)
        }, status=status.HTTP_200_OK)
