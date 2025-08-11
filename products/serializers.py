# serializers.py
from rest_framework import serializers
from decimal import Decimal
from products.models import Product, ProductImage
from common.models import Category, Tag, SEO


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = [
            'id', 'image', 'alt_text', 'is_primary',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        product = attrs.get("product") or getattr(self.instance, "product", None)
        if attrs.get("is_primary") and product:
            if ProductImage.objects.filter(product=product, is_primary=True)\
                    .exclude(pk=getattr(self.instance, "pk", None)).exists():
                raise serializers.ValidationError({
                    "is_primary": "This product already has a primary image."
                })
        return attrs


class ProductSerializer(serializers.ModelSerializer):
    vendor = serializers.HiddenField(default=serializers.CurrentUserDefault())
    categories = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Category.objects.all(), required=False
    )
    tags = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Tag.objects.all(), required=False
    )
    seo = serializers.PrimaryKeyRelatedField(
        queryset=SEO.objects.all(), required=False, allow_null=True
    )

    images = ProductImageSerializer(many=True, read_only=True)

    # Computed fields
    active_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    available_stock = serializers.IntegerField(read_only=True)
    slug = serializers.SlugField(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'vendor', 'categories', 'tags', 'seo',
            'name', 'slug', 'sku',
            'short_description', 'full_description',
            'price1', 'price2', 'price3',
            'option1', 'option2', 'option3', 'option4',
            'is_stock', 'stock_quantity',
            'home_delivery', 'pickup', 'partner_delivery', 'estimated_delivery_days',
            'status', 'featured', 'is_active',
            'active_price', 'average_rating', 'available_stock',
            'images',
            'created_at', 'updated_at', 'is_approve'
        ]
        read_only_fields = [
            'id', 'vendor', 'slug', 'status', 'featured',
            'active_price', 'average_rating', 'available_stock',
            'created_at', 'updated_at', 'is_active', 'is_approve'
        ]


    def validate(self, attrs):
        price_fields = [attrs.get("price1"), attrs.get("price2"), attrs.get("price3")]
        if not any(p is not None for p in price_fields):
            raise serializers.ValidationError({"price1": "At least one price must be set."})

        if attrs.get("is_stock", True) and attrs.get("stock_quantity", 0) < 0:
            raise serializers.ValidationError({"stock_quantity": "Stock quantity cannot be negative."})

        delivery_fields = ["home_delivery", "partner_delivery", "pickup"]
        if any(attrs.get(f) for f in delivery_fields) and attrs.get("estimated_delivery_days") is None:
            raise serializers.ValidationError({
                "estimated_delivery_days": "Must set estimated delivery days when delivery/pickup is enabled."
            })

        return attrs

    def create(self, validated_data):
        categories = validated_data.pop("categories", [])
        tags = validated_data.pop("tags", [])
        product = super().create(validated_data)
        if categories:
            product.categories.set(categories)
        if tags:
            product.tags.set(tags)
        return product

    def update(self, instance, validated_data):
        categories = validated_data.pop("categories", None)
        tags = validated_data.pop("tags", None)
        product = super().update(instance, validated_data)
        if categories is not None:
            product.categories.set(categories)
        if tags is not None:
            product.tags.set(tags)
        return product
