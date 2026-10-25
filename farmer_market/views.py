import razorpay
from django.conf import settings
import qrcode
from io import BytesIO
from base64 import b64encode
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from fallback_mandi_prices import FALLBACK_MANDI_PRICES
from django.db.models import F
from django.contrib.auth.models import User
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from products.models import Product, Category, MarketPrice
from accounts.models import Consumer
from orders.models import CartItem, Order, OrderItem
from farmers.models import Farmer
from decimal import Decimal
def home(request):
    category = request.GET.get('category')
    search_query = request.GET.get('q', '').strip()
    products = Product.objects.all()
    if category:
        products = products.filter(category__name=category)
    if search_query:
        products = products.filter(name__icontains=search_query)
    return render(request, 'home.html', {
        'products': products,
        'selected_category': category,
        'search_query': search_query,
    })
def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    return render(
        request,
        'product_detail.html',
        {'product': product}
    )
@login_required(login_url='login')
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    consumer = Consumer.objects.filter(
        user=request.user
    ).first()
    if consumer is None:
        return render(
        request,
        'home.html',
        {
            'products': Product.objects.all(),
            'selected_category': None,
            'error': 'No Consumer profile is linked to this login.'
        }
    )
    cart_item, created = CartItem.objects.get_or_create(
        consumer=consumer,
        product=product,
        defaults={'quantity': 1}
    )
    if not created:
        cart_item.quantity += 1
        cart_item.save()
    return redirect('cart')
@login_required(login_url='login')

@login_required(login_url='login')
def cart(request):
    consumer = Consumer.objects.filter(
        user=request.user
    ).first()

    if consumer is None:
        return redirect('home')

    cart_items = CartItem.objects.filter(
        consumer=consumer
    ).select_related('product')

    for item in cart_items:
        price = get_official_mandi_price_per_kg(
            item.product.name
        )

        item.mandi_price_per_kg = price

        if price is None:
            item.total = None
        else:
            item.total = price * item.quantity

    return render(
        request,
        'cart.html',
        {'cart_items': cart_items}
    )

def checkout(request):
    consumer = Consumer.objects.filter(user=request.user).first()

    if consumer is None:
        return redirect('home')

    cart_items = list(
        CartItem.objects.filter(
            consumer=consumer
        ).select_related('product')
    )

    if not cart_items:
        return redirect('cart')

    official_prices = {}

    for item in cart_items:
        price = get_official_mandi_price_per_kg(
            item.product.name
        )

        if price is None:
            messages.error(
                request,
                f"No official mandi price is available for "
                f"{item.product.name}. Please try again later."
            )
            return redirect('cart')

        official_prices[item.product_id] = price

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')

        if payment_method not in ['UPI', 'COD', 'RAZORPAY']:
            return redirect('checkout')

        with transaction.atomic():
            cart_items = list(
                CartItem.objects.filter(
                    consumer=consumer
                ).select_related('product')
            )

            if not cart_items:
                return redirect('cart')

            products = {}
            total_amount = Decimal('0.00')

            for item in cart_items:
                product = Product.objects.select_for_update().filter(
                    id=item.product_id
                ).first()

                if (
                    product is None
                    or not product.available
                    or item.quantity <= 0
                    or product.quantity < item.quantity
                ):
                    return redirect('cart')

                price = get_official_mandi_price_per_kg(
                    product.name
                )

                if price is None:
                    messages.error(
                        request,
                        f"No official mandi price is available for "
                        f"{product.name}. Please try again later."
                    )
                    return redirect('cart')

                products[product.id] = (product, price)
                total_amount += price * item.quantity

            order = Order.objects.create(
                consumer=consumer,
                total_amount=total_amount,
                status='Pending',
                payment_method=payment_method,
                payment_status='Pending'
            )

            for item in cart_items:
                product, price = products[item.product_id]

                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=item.quantity,
                    price=price
                )

                Product.objects.filter(
                    id=product.id
                ).update(
                    quantity=F('quantity') - item.quantity
                )

                product.refresh_from_db()

                if product.quantity == 0:
                    product.available = False
                    product.save(update_fields=['available'])

        if payment_method == 'UPI':
            return redirect('demo_payment', order_id=order.id)

        if payment_method == 'RAZORPAY':
            return redirect(
                'create_razorpay_order',
                order_id=order.id
            )

        if payment_method == 'COD':
            CartItem.objects.filter(
                consumer=consumer
            ).delete()

            return render(
                request,
                'order_confirmed.html',
                {'order': order}
            )

        return redirect('home')

    total_amount = Decimal('0.00')

    for item in cart_items:
        item.mandi_price_per_kg = official_prices[item.product_id]
        item.total = item.mandi_price_per_kg * item.quantity
        total_amount += item.total

    return render(
        request,
        'checkout.html',
        {
            'cart_items': cart_items,
            'total_amount': total_amount
        }
    )
def register(request):
    if request.method == 'POST':
        name = request.POST['name'].strip()
        phone = request.POST['phone'].strip()
        address = request.POST['address'].strip()
        city = request.POST['city'].strip()
        username = request.POST['username'].strip()
        password = request.POST['password']
        if User.objects.filter(username=username).exists():
            return render(
                request,
                'register.html',
                {
                    'error': (
                        'This username already exists. '
                        'Please choose another.'
                    )
                }
            )
        user = User.objects.create_user(
            username=username,
            password=password
        )
        Consumer.objects.create(
            user=user,
            name=name,
            phone=phone,
            address=address,
            city=city
        )
        login(request, user)
        return redirect('home')
    return render(request, 'register.html')
def login_view(request):
    if request.method == 'POST':
        username = request.POST['username'].strip()
        password = request.POST['password']
        user = authenticate(
            request,
            username=username,
            password=password
        )
        if user is not None:
            login(request, user)
            return redirect('home')
        return render(
            request,
            'login.html',
            {'error': 'Invalid username or password.'}
        )
    return render(request, 'login.html')
def logout_view(request):
    logout(request)
    return redirect('home')
@login_required(login_url='login')
def my_orders(request):
    consumer = Consumer.objects.filter(
        user=request.user
    ).first()
    if consumer is None:
        return redirect('home')
    orders = Order.objects.filter(
        consumer=consumer
    ).order_by('-order_date')
    return render(
        request,
        'my_orders.html',
        {'orders': orders}
    )
@login_required(login_url='login')
def order_detail(request, order_id):
    consumer = Consumer.objects.filter(
        user=request.user
    ).first()
    if consumer is None:
        return redirect('home')
    order = get_object_or_404(
        Order,
        id=order_id,
        consumer=consumer
    )
    order_items = OrderItem.objects.filter(
        order=order
    ).select_related('product')
    return render(
        request,
        'order_detail.html',
        {
            'order': order,
            'order_items': order_items
        }
    )
@login_required(login_url='login')
def update_cart(request, item_id):
    if request.method != 'POST':
        return redirect('cart')
    consumer = Consumer.objects.filter(
        user=request.user
    ).first()
    if consumer is None:
        return redirect('home')
    cart_item = get_object_or_404(
        CartItem,
        id=item_id,
        consumer=consumer
    )
    try:
        quantity = int(request.POST.get('quantity', 1))
    except (ValueError, TypeError):
        return redirect('cart')
    if quantity < 1:
        return redirect('cart')
    cart_item.quantity = quantity
    cart_item.save()
    return redirect('cart')
@login_required(login_url='login')
def remove_from_cart(request, item_id):
    if request.method != 'POST':
        return redirect('cart')
    consumer = Consumer.objects.filter(
        user=request.user
    ).first()
    if consumer is None:
        return redirect('home')
    cart_item = get_object_or_404(
        CartItem,
        id=item_id,
        consumer=consumer
    )
    cart_item.delete()
    return redirect('cart')
def farmers_list(request):
    farmers = Farmer.objects.all()
    return render(request, 'farmers.html', {'farmers': farmers})
@login_required(login_url='login')
def customer_profile(request):
    consumer = Consumer.objects.filter(user=request.user).first()
    if consumer is None:
        return redirect('home')
    return render(request, 'customer_profile.html', {
        'consumer': consumer
    })
@login_required(login_url='login')
def edit_profile(request):
    consumer = Consumer.objects.filter(user=request.user).first()
    if consumer is None:
        return redirect('home')
    if request.method == 'POST':
        consumer.name = request.POST.get('name', '').strip()
        consumer.phone = request.POST.get('phone', '').strip()
        consumer.city = request.POST.get('city', '').strip()
        consumer.address = request.POST.get('address', '').strip()
        if not all([
            consumer.name,
            consumer.phone,
            consumer.city,
            consumer.address
        ]):
            return render(request, 'edit_profile.html', {
                'consumer': consumer,
                'error': 'Please fill in all fields.'
            })
        consumer.save()
        return redirect('customer_profile')
    return render(request, 'edit_profile.html', {
        'consumer': consumer
    })
@login_required(login_url='login')
def farmer_products(request):
    farmer = Farmer.objects.filter(user=request.user).first()
    if farmer is None:
        return render(request, 'farmer_products.html', {
            'products': [],
            'error': 'No farmer profile is linked to this account.'
        })
    products = Product.objects.filter(farmer=farmer)
    return render(request, 'farmer_products.html', {
        'products': products
    })
@login_required(login_url='login')
def add_product(request):
    print("Logged-in username:", request.user.username)
    print("Is authenticated:", request.user.is_authenticated)

    farmer = Farmer.objects.filter(user=request.user).first()
    print("Farmer profile found:", farmer)

    if farmer is None:
        return render(request, 'farmer_products.html', {
            'products': [],
            'error': 'No farmer profile is linked to this account.'
        })

    categories = Category.objects.all()

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category')
        price = request.POST.get('price')
        quantity = request.POST.get('quantity')
        image = request.FILES.get('image')
        available = request.POST.get('available') == 'on'

        if not all([name, description, category_id, price, quantity]):
            return render(request, 'add_product.html', {
                'categories': categories,
                'error': 'Please fill in all required fields.'
            })

        try:
            category = Category.objects.get(id=category_id)
            price = float(price)
            quantity = int(quantity)
            if price < 0 or quantity < 0:
                raise ValueError
        except (Category.DoesNotExist, ValueError, TypeError):
            return render(request, 'add_product.html', {
                'categories': categories,
                'error': 'Please enter a valid category, price, and quantity.'
            })

        Product.objects.create(
            farmer=farmer,
            category=category,
            name=name,
            description=description,
            price=price,
            quantity=quantity,
            available=available,
            image=image
        )
        return redirect('farmer_products')

    return render(request, 'add_product.html', {
        'categories': categories
    })

@login_required(login_url='login')
def farmer_orders(request):
    print("Farmer orders username:", request.user.username)

    farmer = Farmer.objects.filter(user=request.user).first()
    print("Farmer profile:", farmer)

    if farmer is None:
        return render(request, 'farmer_products.html', {
            'products': [],
            'error': 'No farmer profile is linked to this account.'
        })

    order_items = OrderItem.objects.filter(
        product__farmer=farmer
    ).select_related(
        'order',
        'order__consumer',
        'product'
    ).order_by('-order__order_date')

    return render(request, 'farmer_orders.html', {
        'order_items': order_items
    })

    order_items = OrderItem.objects.filter(
        product__farmer=farmer
    ).select_related(
        'order',
        'order__consumer',
        'product'
    ).order_by('-order__order_date')

    return render(request, 'farmer_orders.html', {
        'order_items': order_items
    })

@login_required(login_url='login')
def update_order_status(request, order_item_id):
    if request.method != 'POST':
        return redirect('farmer_orders')

    farmer = Farmer.objects.filter(user=request.user).first()

    if farmer is None:
        return redirect('home')

    order_item = get_object_or_404(
        OrderItem,
        id=order_item_id,
        product__farmer=farmer
    )

    new_status = request.POST.get('status')

    allowed_statuses = [
        'Pending',
        'Confirmed',
        'Shipped',
        'Delivered',
        'Cancelled',
    ]

    if new_status in allowed_statuses:
        order_item.order.status = new_status
        order_item.order.save(update_fields=['status'])

    return redirect('farmer_orders')

@login_required(login_url='login')
def edit_product(request, product_id):
    farmer = Farmer.objects.filter(user=request.user).first()

    if farmer is None:
        return redirect('home')

    product = get_object_or_404(
        Product,
        id=product_id,
        farmer=farmer
    )

    categories = Category.objects.all()

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category')
        price = request.POST.get('price')
        quantity = request.POST.get('quantity')
        image = request.FILES.get('image')

        try:
            category = Category.objects.get(id=category_id)
            price = float(price)
            quantity = int(quantity)

            if not name or not description or price < 0 or quantity < 0:
                raise ValueError

        except (Category.DoesNotExist, ValueError, TypeError):
            return render(request, 'edit_product.html', {
                'product': product,
                'categories': categories,
                'error': 'Please enter valid product details.'
            })

        product.name = name
        product.description = description
        product.category = category
        product.price = price
        product.quantity = quantity
        product.available = quantity > 0

        if image:
            product.image = image

        product.save()

        return redirect('farmer_products')


    return render(request, 'edit_product.html', {
        'product': product,
        'categories': categories
    })


@login_required(login_url='login')
def delete_product(request, product_id):
    farmer = Farmer.objects.filter(user=request.user).first()

    if farmer is None:
        return redirect('home')

    product = get_object_or_404(
        Product,
        id=product_id,
        farmer=farmer
    )

    if request.method == 'POST':
        product.delete()
        return redirect('farmer_products')

    return render(request, 'delete_product.html', {
        'product': product
        
        
    })
    
    
@login_required(login_url='login')
def add_stock(request, product_id):
    farmer = Farmer.objects.filter(user=request.user).first()

    if farmer is None:
        return redirect('home')

    product = get_object_or_404(
        Product,
        id=product_id,
        farmer=farmer
    )

    if request.method == 'POST':
        try:
            quantity_to_add = int(request.POST.get('quantity', 0))

            if quantity_to_add <= 0:
                messages.error(
                    request,
                    'Enter a quantity greater than zero.'
                )
            else:
                product.quantity += quantity_to_add
                product.available = True
                product.save(
                    update_fields=['quantity', 'available']
                )

                messages.success(
                    request,
                    'Stock added successfully!'
                )
                return redirect('farmer_products')

        except (ValueError, TypeError):
            messages.error(
                request,
                'Enter a valid whole number.'
            )

    return render(
        request,
        'add_stock.html',
        {'product': product}
    )

from django.db import models
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.db.models import F
from django.contrib.auth.models import User
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from products.models import Product, Category
from accounts.models import Consumer
from orders.models import CartItem, Order, OrderItem
from farmers.models import Farmer


def get_official_mandi_price_per_kg(product_name):
    latest_date = MarketPrice.objects.filter(
        product_name__iexact=product_name
    ).order_by(
        '-recorded_date'
    ).values_list(
        'recorded_date', flat=True
    ).first()

    if latest_date is None:
        return None

    prices = MarketPrice.objects.filter(
        product_name__iexact=product_name,
        recorded_date=latest_date
    )

    average_price = prices.aggregate(
        avg_price=models.Avg('modal_price')
    )['avg_price']

    if average_price is None:
        return None

    return (
        Decimal(str(average_price)) / Decimal('100')
    ).quantize(Decimal('0.01'))
def home(request):
    from decimal import Decimal
    from django.db import models
    from django.shortcuts import render

    category = request.GET.get('category')
    search_query = request.GET.get('q', '').strip()

    products = Product.objects.filter(available=True)

    if category:
        products = products.filter(category__name=category)

    if search_query:
        products = products.filter(name__icontains=search_query)

    cart_count = 0

    if request.user.is_authenticated:
        consumer = Consumer.objects.filter(
            user=request.user
        ).first()

        if consumer:
            cart_count = CartItem.objects.filter(
                consumer=consumer
            ).aggregate(
                total=models.Sum('quantity')
            )['total'] or 0

    product_list = []

    for product in products:
        latest_date = MarketPrice.objects.filter(
            product_name__iexact=product.name
        ).order_by(
            '-recorded_date'
        ).values_list(
            'recorded_date', flat=True
        ).first()

        mandi_price_per_kg = None
        fallback_price = FALLBACK_MANDI_PRICES.get(product.name)

        if latest_date:
            prices = MarketPrice.objects.filter(
                product_name__iexact=product.name,
                recorded_date=latest_date
            )

            average_price = prices.aggregate(
                avg_price=models.Avg('modal_price')
            )['avg_price']

            if average_price is not None:
                mandi_price_per_kg = (
                    average_price / Decimal('100')
                ).quantize(Decimal('0.01'))

        product_list.append({
            'product': product,
            'mandi_price_per_kg': (
                fallback_price['price_per_kg']
                if fallback_price
                else mandi_price_per_kg
            ),
            'mandi_price_source': (
                fallback_price['source_type']
                if fallback_price
                else 'Official API'
                if mandi_price_per_kg is not None
                else None
            ),
            'mandi_price_date': (
                fallback_price['recorded_date']
                if fallback_price
                else latest_date
            ),
        })

    return render(request, 'home.html', {
        'product_list': product_list,
        'cart_count': cart_count,
        'category': category,
        'q': search_query,
    })
def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    return render(
        request,
        'product_detail.html',
        {'product': product}
    )
@login_required(login_url='login')
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    consumer = Consumer.objects.filter(
        user=request.user
    ).first()
    if consumer is None:
        return render(
        request,
        'home.html',
        {
            'products': Product.objects.all(),
            'selected_category': None,
            'error': 'No Consumer profile is linked to this login.'
        }
    )
    cart_item, created = CartItem.objects.get_or_create(
        consumer=consumer,
        product=product,
        defaults={'quantity': 1}
    )
    if not created:
        cart_item.quantity += 1
        cart_item.save()
    return redirect('product_detail', product_id=product.id)
@login_required(login_url='login')

@login_required(login_url='login')
def cart(request):
    consumer = Consumer.objects.filter(
        user=request.user
    ).first()

    if consumer is None:
        return redirect('home')

    cart_items = CartItem.objects.filter(
        consumer=consumer
    ).select_related('product')

    for item in cart_items:
        price = get_official_mandi_price_per_kg(
            item.product.name
        )

        item.mandi_price_per_kg = price

        if price is None:
            item.total = None
        else:
            item.total = price * item.quantity

    return render(
        request,
        'cart.html',
        {'cart_items': cart_items}
    )
def register(request):
    if request.method == 'POST':
        name = request.POST['name'].strip()
        phone = request.POST['phone'].strip()
        address = request.POST['address'].strip()
        city = request.POST['city'].strip()
        username = request.POST['username'].strip()
        password = request.POST['password']
        if User.objects.filter(username=username).exists():
            return render(
                request,
                'register.html',
                {
                    'error': (
                        'This username already exists. '
                        'Please choose another.'
                    )
                }
            )
        user = User.objects.create_user(
            username=username,
            password=password
        )
        Consumer.objects.create(
            user=user,
            name=name,
            phone=phone,
            address=address,
            city=city
        )
        login(request, user)
        return redirect('home')
    return render(request, 'register.html')
def login_view(request):
    if request.method == 'POST':
        username = request.POST['username'].strip()
        password = request.POST['password']
        user = authenticate(
            request,
            username=username,
            password=password
        )
        if user is not None:
            login(request, user)
            return redirect('home')
        return render(
            request,
            'login.html',
            {'error': 'Invalid username or password.'}
        )
    return render(request, 'login.html')
def logout_view(request):
    logout(request)
    return redirect('home')
@login_required(login_url='login')
def my_orders(request):
    consumer = Consumer.objects.filter(
        user=request.user
    ).first()
    if consumer is None:
        return redirect('home')
    orders = Order.objects.filter(
        consumer=consumer
    ).order_by('-order_date')
    return render(
        request,
        'my_orders.html',
        {'orders': orders}
    )
@login_required(login_url='login')
def order_detail(request, order_id):
    consumer = Consumer.objects.filter(
        user=request.user
    ).first()
    if consumer is None:
        return redirect('home')
    order = get_object_or_404(
        Order,
        id=order_id,
        consumer=consumer
    )
    order_items = OrderItem.objects.filter(
        order=order
    ).select_related('product')
    return render(
        request,
        'order_detail.html',
        {
            'order': order,
            'order_items': order_items
        }
    )
@login_required(login_url='login')
def update_cart(request, item_id):
    if request.method != 'POST':
        return redirect('cart')
    consumer = Consumer.objects.filter(
        user=request.user
    ).first()
    if consumer is None:
        return redirect('home')
    cart_item = get_object_or_404(
        CartItem,
        id=item_id,
        consumer=consumer
    )
    try:
        quantity = int(request.POST.get('quantity', 1))
    except (ValueError, TypeError):
        return redirect('cart')
    if quantity < 1:
        return redirect('cart')
    cart_item.quantity = quantity
    cart_item.save()
    return redirect('cart')
@login_required(login_url='login')
def remove_from_cart(request, item_id):
    if request.method != 'POST':
        return redirect('cart')
    consumer = Consumer.objects.filter(
        user=request.user
    ).first()
    if consumer is None:
        return redirect('home')
    cart_item = get_object_or_404(
        CartItem,
        id=item_id,
        consumer=consumer
    )
    cart_item.delete()
    return redirect('cart')
def farmers_list(request):
    farmers = Farmer.objects.all()
    return render(request, 'farmers.html', {'farmers': farmers})
@login_required(login_url='login')
def customer_profile(request):
    consumer = Consumer.objects.filter(user=request.user).first()
    if consumer is None:
        return redirect('home')
    return render(request, 'customer_profile.html', {
        'consumer': consumer
    })
@login_required(login_url='login')
def edit_profile(request):
    consumer = Consumer.objects.filter(user=request.user).first()
    if consumer is None:
        return redirect('home')
    if request.method == 'POST':
        consumer.name = request.POST.get('name', '').strip()
        consumer.phone = request.POST.get('phone', '').strip()
        consumer.city = request.POST.get('city', '').strip()
        consumer.address = request.POST.get('address', '').strip()
        if not all([
            consumer.name,
            consumer.phone,
            consumer.city,
            consumer.address
        ]):
            return render(request, 'edit_profile.html', {
                'consumer': consumer,
                'error': 'Please fill in all fields.'
            })
        consumer.save()
        return redirect('customer_profile')
    return render(request, 'edit_profile.html', {
        'consumer': consumer
    })
@login_required(login_url='login')
def farmer_products(request):
    farmer = Farmer.objects.filter(user=request.user).first()
    if farmer is None:
        return render(request, 'farmer_products.html', {
            'products': [],
            'error': 'No farmer profile is linked to this account.'
        })
    products = Product.objects.filter(farmer=farmer)
    return render(request, 'farmer_products.html', {
        'products': products
    })
@login_required(login_url='login')
def add_product(request):
    print("Logged-in username:", request.user.username)
    print("Is authenticated:", request.user.is_authenticated)

    farmer = Farmer.objects.filter(user=request.user).first()
    print("Farmer profile found:", farmer)

    if farmer is None:
        return render(request, 'farmer_products.html', {
            'products': [],
            'error': 'No farmer profile is linked to this account.'
        })

    categories = Category.objects.all()

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category')
        price = request.POST.get('price')
        quantity = request.POST.get('quantity')
        image = request.FILES.get('image')
        available = request.POST.get('available') == 'on'

        if not all([name, description, category_id, price, quantity]):
            return render(request, 'add_product.html', {
                'categories': categories,
                'error': 'Please fill in all required fields.'
            })

        try:
            category = Category.objects.get(id=category_id)
            price = float(price)
            quantity = int(quantity)
            if price < 0 or quantity < 0:
                raise ValueError
        except (Category.DoesNotExist, ValueError, TypeError):
            return render(request, 'add_product.html', {
                'categories': categories,
                'error': 'Please enter a valid category, price, and quantity.'
            })

        Product.objects.create(
            farmer=farmer,
            category=category,
            name=name,
            description=description,
            price=price,
            quantity=quantity,
            available=available,
            image=image
        )
        return redirect('farmer_products')

    return render(request, 'add_product.html', {
        'categories': categories
    })

@login_required(login_url='login')
def farmer_orders(request):
    print("Farmer orders username:", request.user.username)

    farmer = Farmer.objects.filter(user=request.user).first()
    print("Farmer profile:", farmer)

    if farmer is None:
        return render(request, 'farmer_products.html', {
            'products': [],
            'error': 'No farmer profile is linked to this account.'
        })

    order_items = OrderItem.objects.filter(
        product__farmer=farmer
    ).select_related(
        'order',
        'order__consumer',
        'product'
    ).order_by('-order__order_date')

    return render(request, 'farmer_orders.html', {
        'order_items': order_items
    })

    order_items = OrderItem.objects.filter(
        product__farmer=farmer
    ).select_related(
        'order',
        'order__consumer',
        'product'
    ).order_by('-order__order_date')

    return render(request, 'farmer_orders.html', {
        'order_items': order_items
    })

@login_required(login_url='login')
def update_order_status(request, order_item_id):
    if request.method != 'POST':
        return redirect('farmer_orders')

    farmer = Farmer.objects.filter(user=request.user).first()

    if farmer is None:
        return redirect('home')

    order_item = get_object_or_404(
        OrderItem,
        id=order_item_id,
        product__farmer=farmer
    )

    new_status = request.POST.get('status')

    allowed_statuses = [
        'Pending',
        'Confirmed',
        'Shipped',
        'Delivered',
        'Cancelled',
    ]

    if new_status in allowed_statuses:
        order_item.order.status = new_status
        order_item.order.save(update_fields=['status'])

    return redirect('farmer_orders')

@login_required(login_url='login')
def edit_product(request, product_id):
    farmer = Farmer.objects.filter(user=request.user).first()

    if farmer is None:
        return redirect('home')

    product = get_object_or_404(
        Product,
        id=product_id,
        farmer=farmer
    )

    categories = Category.objects.all()

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category')
        price = request.POST.get('price')
        quantity = request.POST.get('quantity')
        image = request.FILES.get('image')

        try:
            category = Category.objects.get(id=category_id)
            price = float(price)
            quantity = int(quantity)

            if not name or not description or price < 0 or quantity < 0:
                raise ValueError

        except (Category.DoesNotExist, ValueError, TypeError):
            return render(request, 'edit_product.html', {
                'product': product,
                'categories': categories,
                'error': 'Please enter valid product details.'
            })

        product.name = name
        product.description = description
        product.category = category
        product.price = price
        product.quantity = quantity
        product.available = quantity > 0

        if image:
            product.image = image

        product.save()

        return redirect('farmer_products')


    return render(request, 'edit_product.html', {
        'product': product,
        'categories': categories
    })


@login_required(login_url='login')
def delete_product(request, product_id):
    farmer = Farmer.objects.filter(user=request.user).first()

    if farmer is None:
        return redirect('home')

    product = get_object_or_404(
        Product,
        id=product_id,
        farmer=farmer
    )

    if request.method == 'POST':
        product.delete()
        return redirect('farmer_products')

    return render(request, 'delete_product.html', {
        'product': product
        
        
    })

@login_required(login_url='login')
def farmer_dashboard(request):
    farmer = Farmer.objects.filter(user=request.user).first()

    if farmer is None:
        return redirect('home')

    # Count products belonging to this farmer.
    total_products = Product.objects.filter(
        farmer=farmer
    ).count()
    low_stock_products = Product.objects.filter(
    farmer=farmer,
    quantity__lte=5
).order_by('quantity')

    # Get orders containing this farmer's products.
    order_items = OrderItem.objects.filter(
        product__farmer=farmer
    ).select_related('order', 'product')

    # Count distinct orders, not individual product rows.
    total_orders = order_items.values(
        'order_id'
    ).distinct().count()

    pending_orders = order_items.filter(
        order__status='Pending'
    ).values('order_id').distinct().count()

    # Calculate the value of ordered items.
    total_sales = sum(
        item.price * item.quantity
        for item in order_items.exclude(
            order__status='Cancelled'
        )
    )

    return render(request, 'farmer_dashboard.html', {
        'total_products': total_products,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'total_sales': total_sales,
        'low_stock_products': low_stock_products,
    })


@login_required(login_url='login')
def farmer_dashboard(request):
    farmer = Farmer.objects.filter(user=request.user).first()

    if farmer is None:
        return redirect('home')

    # Count products belonging to this farmer.
    total_products = Product.objects.filter(
        farmer=farmer
    ).count()
    low_stock_products = Product.objects.filter(
    farmer=farmer,
    quantity__lte=5
).order_by('quantity')

    # Get orders containing this farmer's products.
    order_items = OrderItem.objects.filter(
        product__farmer=farmer
    ).select_related('order', 'product')

    # Count distinct orders, not individual product rows.
    total_orders = order_items.values(
        'order_id'
    ).distinct().count()

    pending_orders = order_items.filter(
        order__status='Pending'
    ).values('order_id').distinct().count()

    # Calculate the value of ordered items.
    total_sales = sum(
        item.price * item.quantity
        for item in order_items.exclude(
            order__status='Cancelled'
        )
    )

    return render(request, 'farmer_dashboard.html', {
        'total_products': total_products,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'total_sales': total_sales,
        'low_stock_products': low_stock_products,
    })

@login_required(login_url='login')

@login_required(login_url='login')
def demo_payment(request, order_id):
    order = get_object_or_404(
        Order,
        id=order_id,
        consumer__user=request.user
    )

    upi_id = '9945463812@kotakbank'

    # Build UPI payment details using this order's amount.
    payment_amount = f'{order.total_amount:.2f}'

    upi_string = (
        f'upi://pay?pa={upi_id}'
        f'&pn=FarmerMarket'
        f'&am={payment_amount}'
        f'&cu=INR'
        f'&tn=Order%20{order.id}'
    )

    # Generate a new QR code for this order.
    qr = qrcode.make(upi_string)

    # Convert the QR image into a Base64 string.
    buffer = BytesIO()
    qr.save(buffer, format='PNG')
    qr_base64 = b64encode(buffer.getvalue()).decode('utf-8')

    if request.method == 'POST':
        # Do not mark an unverified payment as paid.
        messages.info(
            request,
            'Demo confirmation received. '
            'Actual payment has not been verified.'
        )
        return redirect('home')

    return render(
        request,
        'demo_payment.html',
        {
            'order': order,
            'upi_id': upi_id,
            'qr_base64': qr_base64,
        }
    )

@login_required(login_url='login')
def create_razorpay_order(request, order_id):
    order = get_object_or_404(
        Order,
        id=order_id,
        consumer__user=request.user,
        payment_method='RAZORPAY'
    )

    if order.payment_status == 'Paid':
        return redirect('home')

    client = razorpay.Client(
        auth=(
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY_KEY_SECRET
        )
    )

    try:
        razorpay_order = client.order.create({
            'amount': int(order.total_amount * 100),
            'currency': 'INR',
            'receipt': f'order_{order.id}',
        })
    
    except Exception as e:
        print("Razorpay order creation failed:", repr(e))
        messages.error(
            request,
            'Unable to start Razorpay payment. Please check your Test API keys and try again.'
        )
        return redirect('home')


    order.razorpay_order_id = razorpay_order['id']
    order.save(update_fields=['razorpay_order_id'])

    return render(
        request,
        'razorpay_checkout.html',
        {
            'order': order,
            'razorpay_order_id': razorpay_order['id'],
            'razorpay_key_id': settings.RAZORPAY_KEY_ID,
            'razorpay_amount': int(order.total_amount * 100),
        }
    )

@login_required(login_url='login')
def verify_razorpay_payment(request):
    if request.method != 'POST':
        return redirect('home')

    payment_id = request.POST.get('razorpay_payment_id')
    razorpay_order_id = request.POST.get('razorpay_order_id')
    signature = request.POST.get('razorpay_signature')

    if not all([payment_id, razorpay_order_id, signature]):
        messages.error(request, 'Payment details are incomplete.')
        return redirect('home')

    order = get_object_or_404(
        Order,
        consumer__user=request.user,
        payment_method='RAZORPAY',
        razorpay_order_id=razorpay_order_id
    )
    print("DEBUG: Entered verify_razorpay_payment")
    client = razorpay.Client(
        auth=(
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY_KEY_SECRET
        )
    )

    try:
        client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        })

        payment = client.payment.fetch(payment_id)

        if (
            payment.get('order_id') != razorpay_order_id
            or payment.get('status') != 'captured'
        ):
            messages.error(
                request,
                'Payment has not been confirmed as captured.'
            )
            return redirect('home')

        order.razorpay_payment_id = payment_id
        order.payment_status = 'Paid'
        order.save(update_fields=[
            'razorpay_payment_id',
            'payment_status'
        ])

        messages.success(request, 'Payment verified successfully!')

    except razorpay.errors.SignatureVerificationError:
        messages.error(request, 'Payment verification failed.')

    except Exception as e:
        print("Razorpay payment verification error:", repr(e))
    messages.error(
        request,
        'Unable to verify payment. Please try again.'
    )

    return redirect('home')

from products.models import MarketPrice


def market_prices(request):
    prices = MarketPrice.objects.order_by(
        "location",
        "product_name"
    )

    return render(
        request,
        "market_prices.html",
        {"prices": prices}
    )
