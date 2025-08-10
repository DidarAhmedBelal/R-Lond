from django.contrib import admin

# Register your models here.
from products.models import Wishlist, Product, ProductImage, Review, CartItem, Category
admin.site.register(Wishlist)
admin.site.register(Product)
admin.site.register(ProductImage)
admin.site.register(Review)
admin.site.register(CartItem)
admin.site.register(Category)