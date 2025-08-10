from rest_framework import serializers
from .models import Category, Product, ProductImage, Review, CartItem, Wishlist
from django.utils.text import slugify
import uuid


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']

    def validate(self, attrs):
        name = attrs.get('name')
        slug = attrs.get('slug')

        qs = Category.objects.all()
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if name and qs.filter(name__iexact=name).exists():
            raise serializers.ValidationError({"name": "Category with this name already exists."})

        if slug and qs.filter(slug__iexact=slug).exists():
            raise serializers.ValidationError({"slug": "Category with this slug already exists."})

        return attrs


class ProductImageSerializer(serializers.ModelSerializer):
    image = serializers.ImageField()

    class Meta:
        model = ProductImage
        fields = ['id', 'image']


class ReviewSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Review
        fields = ['id', 'user', 'rating', 'comment', 'created_at']


class ProductSerializer(serializers.ModelSerializer):
    vendor = serializers.StringRelatedField(read_only=True)

    # Expecting categories by PK only (existing categories)
    categories = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Category.objects.all()
    )

    images = ProductImageSerializer(many=True, required=False)
    reviews = ReviewSerializer(many=True, read_only=True)
    rating_info = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'title', 'slug', 'description', 'price', 'discount_price',
            'color', 'size', 'status', 'stock_status', 'stock_quantity',
            'dimensions', 'material', 'weight', 'assembly_required',
            'warranty', 'care_instructions', 'country_of_origin', 'created_at',
            'updated_at', 'vendor', 'categories', 'images', 'reviews', 'rating_info'
        ]
        read_only_fields = ['created_at', 'updated_at', 'vendor']

    def get_rating_info(self, obj):
        return obj.calculate_rating_info()

    def validate_slug(self, value):
        if not value:
            # Auto-generate slug if not provided
            value = slugify(self.initial_data.get('title', '')) + '-' + uuid.uuid4().hex[:8]
        qs = Product.objects.filter(slug=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Product with this slug already exists.")
        return value

    def create(self, validated_data):
        categories = validated_data.pop('categories', [])
        images_data = validated_data.pop('images', [])

        # Auto generate slug if missing
        if not validated_data.get('slug'):
            validated_data['slug'] = slugify(validated_data.get('title', '')) + '-' + uuid.uuid4().hex[:8]

        product = Product.objects.create(**validated_data)
        product.categories.set(categories)

        for img_data in images_data:
            # img_data must contain 'image' file
            ProductImage.objects.create(product=product, **img_data)

        return product

    def update(self, instance, validated_data):
        categories = validated_data.pop('categories', None)
        images_data = validated_data.pop('images', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if categories is not None:
            instance.categories.set(categories)

        if images_data is not None:
            instance.images.all().delete()
            for img_data in images_data:
                ProductImage.objects.create(product=instance, **img_data)

        return instance


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'quantity', 'added_at', 'user']


class WishlistSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Wishlist
        fields = ['id', 'product', 'added_at', 'user']
