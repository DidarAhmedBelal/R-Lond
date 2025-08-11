from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from .models import Product, ProductImage
from .serializers import ProductSerializer, ProductImageSerializer
from products.enums import ProductStatus
from products.permissions import BasePermission
from common.models import SEO

class IsVendorOrAdmin(BasePermission):

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and (
            request.user.is_staff or getattr(request.user, "role", None) == "vendor"
        )

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return (
            request.user.is_staff or
            (getattr(request.user, "role", None) == "vendor" and obj.vendor == request.user)
        )
    


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsVendorOrAdmin]

    def get_queryset(self):
        qs = Product.objects.select_related("seo", "vendor").prefetch_related(
            "categories", "tags", "images"
        )
        user = self.request.user

        if user.is_authenticated:
            if user.is_staff or user.is_superuser:
                return qs
            
            if getattr(user, "role", None) == "vendor":
                return qs.filter(vendor=user)

        return qs.filter(
            is_active=True,
            status=ProductStatus.APPROVED.value
        )


    def perform_create(self, serializer):
        user = self.request.user
        if not (user.is_staff or getattr(user, "role", None) == "vendor"):
            raise PermissionDenied("Only vendors or admins can add products.")

        seo_data = self.request.data.get('seo')
        seo_obj = None

        if isinstance(seo_data, dict):
            seo_obj = SEO.objects.create(**seo_data)
        elif seo_data:
            try:
                seo_obj = SEO.objects.get(pk=seo_data)
            except SEO.DoesNotExist:
                raise serializers.ValidationError({"seo": "SEO object not found."})

        serializer.save(vendor=user, seo=seo_obj)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def accept(self, request, pk=None):
        product = self.get_object()
        if product.status == ProductStatus.APPROVED.value:
            return Response({"detail": "Product already approved."}, status=status.HTTP_400_BAD_REQUEST)
        product.status = ProductStatus.APPROVED.value
        product.is_active = True  
        product.save()
        return Response({
            "detail": "Product approved.",
            "product": self.get_serializer(product).data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        product = self.get_object()
        if product.status == ProductStatus.REJECTED.value:
            return Response({"detail": "Product already rejected."}, status=status.HTTP_400_BAD_REQUEST)
        product.status = ProductStatus.REJECTED.value
        product.is_active = False 
        product.save()
        return Response({
            "detail": "Product rejected.",
            "product": self.get_serializer(product).data
        }, status=status.HTTP_200_OK)



class ProductImageViewSet(viewsets.ModelViewSet):
    serializer_class = ProductImageSerializer
    permission_classes = [permissions.IsAuthenticated, IsVendorOrAdmin]

    def get_queryset(self):
        qs = ProductImage.objects.select_related("product")
        product_id = self.kwargs.get("product_pk")
        if product_id:
            qs = qs.filter(product_id=product_id)
        return qs

    def create(self, request, *args, **kwargs):
        product_id = self.kwargs.get("product_pk")
        product = get_object_or_404(Product, pk=product_id)

        if not (request.user.is_staff or (getattr(request.user, "role", None) == "vendor" and product.vendor == request.user)):
            raise PermissionDenied("You do not have permission to add images to this product.")

        images = request.FILES.getlist("images")
        if not images:
            return Response({"detail": "No images uploaded."}, status=status.HTTP_400_BAD_REQUEST)

        created_images = []
        for image in images:
            img_obj = ProductImage.objects.create(product=product, image=image)
            created_images.append(ProductImageSerializer(img_obj, context={"request": request}).data)

        return Response({"images": created_images}, status=status.HTTP_201_CREATED)
