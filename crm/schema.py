import re
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
import graphene
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField  # ✅ required for filtering and relay
from .models import Customer, Product, Order

# ---------- Types ----------
class CustomerType(DjangoObjectType):
    class Meta:
        model = Customer
        filter_fields = ["name", "email", "phone"]  # ✅ enable filters
        interfaces = (graphene.relay.Node,)          # ✅ make Relay-compatible

class ProductType(DjangoObjectType):
    class Meta:
        model = Product
        filter_fields = ["name", "price", "stock"]
        interfaces = (graphene.relay.Node,)

class OrderType(DjangoObjectType):
    class Meta:
        model = Order
        filter_fields = ["customer__name", "total_amount", "order_date"]
        interfaces = (graphene.relay.Node,)

# ---------- Utility validations ----------
PHONE_REGEX = re.compile(r"^(\+\d{7,15}|\d{3}-\d{3}-\d{4})$")

def validate_phone(phone: str) -> bool:
    if not phone:
        return True
    return bool(PHONE_REGEX.match(phone))

# ---------- Mutations ----------
class CreateCustomer(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        email = graphene.String(required=True)
        phone = graphene.String(required=False)

    customer = graphene.Field(CustomerType)
    message = graphene.String()
    errors = graphene.List(graphene.String)

    @classmethod
    def mutate(cls, root, info, name, email, phone=None):
        errors = []
        email = email.strip().lower()
        if Customer.objects.filter(email=email).exists():
            errors.append("Email already exists")
            return CreateCustomer(customer=None, message="Failed", errors=errors)

        if phone and not validate_phone(phone):
            errors.append("Invalid phone format. Use +1234567890 or 123-456-7890")
            return CreateCustomer(customer=None, message="Failed", errors=errors)

        customer = Customer.objects.create(name=name.strip(), email=email, phone=phone)
        return CreateCustomer(customer=customer, message="Customer created successfully", errors=None)

class CustomerInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    email = graphene.String(required=True)
    phone = graphene.String(required=False)

class BulkCreateCustomers(graphene.Mutation):
    class Arguments:
        customers = graphene.List(graphene.NonNull(CustomerInput), required=True)

    customers = graphene.List(CustomerType)
    errors = graphene.List(graphene.String)

    @classmethod
    def mutate(cls, root, info, customers):
        created = []
        errors = []

        with transaction.atomic():
            for idx, data in enumerate(customers):
                name = data.get('name')
                email = data.get('email')
                phone = data.get('phone', None)

                sid = transaction.savepoint()
                try:
                    if not name or not email:
                        errors.append(f"Record {idx}: name and email are required")
                        transaction.savepoint_rollback(sid)
                        continue

                    email_norm = email.strip().lower()
                    if Customer.objects.filter(email=email_norm).exists():
                        errors.append(f"Record {idx}: Email already exists ({email})")
                        transaction.savepoint_rollback(sid)
                        continue

                    if phone and not validate_phone(phone):
                        errors.append(f"Record {idx}: Invalid phone format ({phone})")
                        transaction.savepoint_rollback(sid)
                        continue

                    c = Customer.objects.create(name=name.strip(), email=email_norm, phone=phone)
                    created.append(c)
                    transaction.savepoint_commit(sid)
                except Exception as exc:
                    transaction.savepoint_rollback(sid)
                    errors.append(f"Record {idx}: Unexpected error: {str(exc)}")

        return BulkCreateCustomers(customers=created, errors=errors if errors else None)

class CreateProduct(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        price = graphene.Decimal(required=True)
        stock = graphene.Int(required=False)

    product = graphene.Field(ProductType)
    errors = graphene.List(graphene.String)

    @classmethod
    def mutate(cls, root, info, name, price, stock=0):
        errors = []
        try:
            price = Decimal(price)
        except Exception:
            errors.append("Price must be a valid decimal number")
            return CreateProduct(product=None, errors=errors)

        if price <= 0:
            errors.append("Price must be positive")
        if stock is None:
            stock = 0
        if stock < 0:
            errors.append("Stock cannot be negative")

        if errors:
            return CreateProduct(product=None, errors=errors)

        product = Product.objects.create(name=name.strip(), price=price, stock=stock)
        return CreateProduct(product=product, errors=None)

class CreateOrder(graphene.Mutation):
    class Arguments:
        customer_id = graphene.ID(required=True)
        product_ids = graphene.List(graphene.ID, required=True)
        order_date = graphene.DateTime(required=False)

    order = graphene.Field(OrderType)
    errors = graphene.List(graphene.String)

    @classmethod
    def mutate(cls, root, info, customer_id, product_ids, order_date=None):
        errors = []
        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            errors.append("Invalid customer ID")
            return CreateOrder(order=None, errors=errors)

        if not product_ids:
            errors.append("At least one product must be selected")
            return CreateOrder(order=None, errors=errors)

        products = []
        for pid in product_ids:
            try:
                p = Product.objects.get(pk=pid)
                products.append(p)
            except Product.DoesNotExist:
                errors.append(f"Invalid product ID: {pid}")

        if errors:
            return CreateOrder(order=None, errors=errors)

        with transaction.atomic():
            order = Order.objects.create(
                customer=customer,
                order_date=order_date or timezone.now()
            )
            order.products.set(products)
            total = sum((p.price for p in products), Decimal('0.00'))
            order.total_amount = total
            order.save()

        return CreateOrder(order=order, errors=None)

# ---------- Schema exports ----------
class Query(graphene.ObjectType):
    # ✅ Relay-compatible filter fields
    all_customers = DjangoFilterConnectionField(CustomerType)
    all_products = DjangoFilterConnectionField(ProductType)
    all_orders = DjangoFilterConnectionField(OrderType)

    def resolve_all_customers(root, info, **kwargs):
        return Customer.objects.all()

    def resolve_all_products(root, info, **kwargs):
        return Product.objects.all()

    def resolve_all_orders(root, info, **kwargs):
        return Order.objects.all()

class Mutation(graphene.ObjectType):
    create_customer = CreateCustomer.Field()
    bulk_create_customers = BulkCreateCustomers.Field()
    create_product = CreateProduct.Field()
    create_order = CreateOrder.Field()
