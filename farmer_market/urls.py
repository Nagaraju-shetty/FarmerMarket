from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
    path('', views.home, name='home'),
    path('market-prices/', views.market_prices, name='market_prices'),
    path('farmers/', views.farmers_list, name='farmers'),
    path('farmer/products/', views.farmer_products, name='farmer_products'),
    path('farmer/orders/', views.farmer_orders, name='farmer_orders'),
    path(
    'farmer/orders/update/<int:order_item_id>/',
    views.update_order_status,
    name='update_order_status'
),
path(
    'create-razorpay-order/<int:order_id>/',
    views.create_razorpay_order,
    name='create_razorpay_order'
),
path(
    'verify-razorpay-payment/',
    views.verify_razorpay_payment,
    name='verify_razorpay_payment'
),
path(
    'farmer/dashboard/',
    views.farmer_dashboard,
    name='farmer_dashboard'
),

    path('farmer/products/add/', views.add_product, name='add_product'),
    
path(
    'farmer/products/edit/<int:product_id>/',
    views.edit_product,
    name='edit_product'
),
path(
    'farmer/products/delete/<int:product_id>/',
    views.delete_product,
    name='delete_product'
),
path('farmer/products/add-stock/<int:product_id>/', views.add_stock, name='add_stock'),

    path('my-profile/', views.customer_profile, name='customer_profile'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),
    path('product/<int:product_id>/', views.product_detail, name='product_detail'),
    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.cart, name='cart'),
    path('cart/update/<int:item_id>/', views.update_cart, name='update_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('my-orders/', views.my_orders, name='my_orders'),
    path('my-orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('admin/', admin.site.urls),
    
path(
    'demo-payment/<int:order_id>/',
    views.demo_payment,
    name='demo_payment'
),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)