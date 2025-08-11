# common/serializers.py
from rest_framework import serializers
from .models import Category, Tag, SEO, SavedProduct, Review, CartItem
from products.models import Product
from users.serializers import UserPublicSerializer


# -------------------
# Category
# -------------------
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']

    def validate_name(self, value):
        qs = Category.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Category with this name already exists.")
        return value


# -------------------
# Tag
# -------------------
class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug', 'created_at', 'updated_at']
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']

    def validate_name(self, value):
        qs = Tag.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Tag with this name already exists.")
        return value


# -------------------
# SEO
# -------------------
class SEOSerializer(serializers.ModelSerializer):
    class Meta:
        model = SEO
        fields = ['id', 'title', 'meta_description']


# -------------------
# Product
# -------------------
class ProductSerializer(serializers.ModelSerializer):
    vendor = UserPublicSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source='category', write_only=True
    )
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, source='tags', write_only=True
    )

    class Meta:
        model = Product
        fields = [
            'id', 'vendor', 'name', 'description', 'price',
            'is_stock', 'stock_quantity', 'category', 'category_id',
            'tags', 'tag_ids', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'vendor', 'created_at', 'updated_at']

    def create(self, validated_data):
        tags = validated_data.pop('tags', [])
        validated_data['vendor'] = self.context['request'].user
        product = super().create(validated_data)
        product.tags.set(tags)
        return product

    def update(self, instance, validated_data):
        tags = validated_data.pop('tags', None)
        instance = super().update(instance, validated_data)
        if tags is not None:
            instance.tags.set(tags)
        return instance


# -------------------
# SavedProduct
# -------------------
class SavedProductSerializer(serializers.ModelSerializer):
    vendor = UserPublicSerializer(read_only=True)

    class Meta:
        model = SavedProduct
        fields = [
            'id', 'vendor', 'name', 'data', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'vendor', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['vendor'] = self.context['request'].user
        return super().create(validated_data)


# -------------------
# Review
# -------------------
class ReviewSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = Review
        fields = [
            'id', 'product', 'product_name', 'user', 'rating', 'comment',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def validate_rating(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


# -------------------
# CartItem
# -------------------
class CartItemSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    subtotal = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = CartItem
        fields = [
            'id', 'product', 'product_name', 'user', 'quantity',
            'price_snapshot', 'subtotal', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'subtotal', 'created_at', 'updated_at']

    def validate(self, attrs):
        product = attrs.get('product')
        quantity = attrs.get('quantity')

        if product.is_stock and quantity > product.stock_quantity:
            raise serializers.ValidationError({
                'quantity': 'Requested quantity exceeds available stock.'
            })
        return attrs

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        validated_data['price_snapshot'] = validated_data['product'].price
        return super().create(validated_data)
