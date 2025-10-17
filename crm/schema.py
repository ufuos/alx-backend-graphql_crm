import re
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
import graphene
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField

from .models import Customer, Product, Order
from .filters import CustomerFilter, ProductFilter, OrderFilter


# ------------------ GraphQL Types (Relay-Compatible) ------------------
class CustomerType(DjangoObjectType):
    class Meta:
        model = Customer
        filter_fields = ["name", "email", "phone"]
        interfaces = (graphene.relay.Node,)


class ProductType(DjangoObjectType):
    class Meta:
        model = Product
        filter_fields = ["name", "price", "stock"]
        interfaces = (graphene.relay.Node,)


class OrderType(DjangoObjectType):
    class Meta:
        model = Order
        filter_fields = ["customer__name", "total_amount"]
        interfaces = (graphene.relay.Node,)


# ------------------ Queries ------------------
class Query(graphene.ObjectType):
    # Individual node access
    customer = graphene.relay.Node.Field(CustomerType)
    product = graphene.relay.Node.Field(ProductType)
    order = graphene.relay.Node.Field(OrderType)

    # List queries with filters
    all_customers = DjangoFilterConnectionField(CustomerType, filterset_class=CustomerFilter)
    all_products = DjangoFilterConnectionField(ProductType, filterset_class=ProductFilter)
    all_orders = DjangoFilterConnectionField(OrderType, filterset_class=OrderFilter)

    def resolve_all_customers(self, info, **kwargs):
        return Customer.objects.all()

    def resolve_all_products(self, info, **kwargs):
        return Product.objects.all()

    def resolve_all_orders(self, info, **kwargs):
        return Order.objects.all()


# ------------------ Mutations ------------------
class CreateCustomer(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        email = graphene.String(required=True)
        phone = graphene.String()

    customer = graphene.Field(CustomerType)
    message = graphene.String()

    def mutate(self, info, name, email, phone=None):
        if Customer.objects.filter(email=email).exists():
            raise ValidationError("Email already exists.")
        if phone and not re.match(r'^(\+?\d{1,3}[- ]?)?\d{10}$', phone):
            raise ValidationError("Invalid phone format.")
        customer = Customer.objects.create(name=name, email=email, phone=phone)
        return CreateCustomer(customer=customer, message="Customer created successfully!")


class BulkCreateCustomers(graphene.Mutation):
    class Arguments:
        customers = graphene.List(graphene.JSONString, required=True)

    customers = graphene.List(CustomerType)
    errors = graphene.List(graphene.String)

    def mutate(self, info, customers):
        created, errors = [], []
        with transaction.atomic():
            for c in customers:
                try:
                    if Customer.objects.filter(email=c["email"]).exists():
                        raise ValidationError("Duplicate email")
                    customer = Customer.objects.create(**c)
                    created.append(customer)
                except Exception as e:
                    errors.append(str(e))
        return BulkCreateCustomers(customers=created, errors=errors)


class CreateProduct(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        price = graphene.Float(required=True)
        stock = graphene.Int(default_value=0)

    product = graphene.Field(ProductType)

    def mutate(self, info, name, price, stock):
        if price <= 0:
            raise ValidationError("Price must be positive")
        if stock < 0:
            raise ValidationError("Stock cannot be negative")
        product = Product.objects.create(name=name, price=Decimal(price), stock=stock)
        return CreateProduct(product=product)


class CreateOrder(graphene.Mutation):
    class Arguments:
        customer_id = graphene.ID(required=True)
        product_ids = graphene.List(graphene.ID, required=True)

    order = graphene.Field(OrderType)

    def mutate(self, info, customer_id, product_ids):
        try:
            customer = Customer.objects.get(id=customer_id)
            products = Product.objects.filter(id__in=product_ids)
            if not products.exists():
                raise ValidationError("Invalid product IDs.")
            total_amount = sum([p.price for p in products])
            order = Order.objects.create(customer=customer, total_amount=total_amount)
            order.products.set(products)
            return CreateOrder(order=order)
        except Exception as e:
            raise ValidationError(str(e))


# ------------------ Root Mutation ------------------
class Mutation(graphene.ObjectType):
    create_customer = CreateCustomer.Field()
    bulk_create_customers = BulkCreateCustomers.Field()
    create_product = CreateProduct.Field()
    create_order = CreateOrder.Field()


# ------------------ Schema ------------------
schema = graphene.Schema(query=Query, mutation=Mutation)
