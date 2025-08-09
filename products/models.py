from django.db import models
from users.models import User
from products.enums import ProductStatus, StockStatus


class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True)

    def __str__(self):
        return self.name

class Product(models.Model):
    vendor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'vendor'},
        related_name='products'
    )
    categories = models.ManyToManyField('Category', related_name="products", blank=True)

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    price = models.DecimalField(max_digits=12, decimal_places=2)
    discount_price = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    color = models.CharField(max_length=50, blank=True)
    size = models.CharField(max_length=50, blank=True)

    status = models.CharField(
        max_length=20,
        choices=ProductStatus.choices(),
        default=ProductStatus.PENDING.value
    )
    stock_status = models.CharField(
        max_length=20,
        choices=StockStatus.choices(),
        default=StockStatus.IN_STOCK.value
    )
    stock_quantity = models.PositiveIntegerField(default=0)

    dimensions = models.CharField(max_length=100, blank=True, help_text="WxHxD")
    material = models.CharField(max_length=100, blank=True)
    weight = models.CharField(max_length=50, blank=True)
    assembly_required = models.BooleanField(default=False)
    warranty = models.CharField(max_length=100, blank=True)
    care_instructions = models.TextField(blank=True)
    country_of_origin = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def calculate_rating_info(self):

        reviews = self.reviews.all()
        total_reviews = reviews.count()

        if total_reviews > 0:
            average_rating = round(sum(r.rating for r in reviews) / total_reviews, 2)
        else:
            average_rating = 0

        return {
            "average_rating": average_rating,
            "total_reviews": total_reviews
        }


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/")

    def __str__(self):
        return f"Image for {self.product.title}"


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField(default=1)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review by {self.user.email} for {self.product.title}"


class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cart_items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.quantity} x {self.product.title} ({self.user.email})"


class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="wishlist")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.title} in {self.user.email}'s wishlist"
