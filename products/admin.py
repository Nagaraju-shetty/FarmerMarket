
from django.contrib import admin
from .models import Category, Product, MarketPrice


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'category', 'price', 'quantity', 'available')
    list_filter = ('category', 'available')
    search_fields = ('name',)


@admin.register(MarketPrice)
class MarketPriceAdmin(admin.ModelAdmin):
    list_display = (
        'product_name',
        'market_name',
        'location',
        'min_price',
        'max_price',
        'modal_price',
        'recorded_date',
    )
    list_filter = ('location', 'recorded_date')
    search_fields = ('product_name', 'market_name', 'location')
    ordering = ('-recorded_date',)
