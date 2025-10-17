# GraphQL CRM - Models, Schema, and Seeder

This document contains the updated files required by the task: `models.py`, `crm/schema.py`, `graphql_crm/schema.py`, and `seed_db.py`.

> **Instructions**: Save each code block into the corresponding file in your repository (`alx-backend-graphql_crm`). Run `python manage.py makemigrations` and `python manage.py migrate` before using the seed script. You can test GraphQL at `/graphql` after running the server.

---

## `models.py`

```python
from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal

class Customer(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=32, blank=True, null=True)

    def __str__(self):
        return f"{self.name} <{self.email}>"

class Product(models.Model):
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    stock = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.name} (${self.price})"

class Order(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='orders')
    products = models.ManyToManyField(Product, related_name='orders')
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    order_date = models.DateTimeField(auto_now_add=True)

    def recalc_total(self):
        total = Decimal('0.00')
        for p in self.products.all():
            total += p.price
        self.total_amount = total
        self.save()

    def __str__(self):
        return f"Order {self.id} - {self.customer.name} - {self.total_amount}"
```

---

## `crm/schema.py`

```python
import re
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
import graphene
from graphene_django import DjangoObjectType
from .models import Customer, Product, Order

# ---------- Types ----------
class CustomerType(DjangoObjectType):
    class Meta:
        model = Customer
        fields = ("id", "name", "email", "phone")

class ProductType(DjangoObjectType):
    class Meta:
        model = Product
        fields = ("id", "name", "price", "stock")

class OrderType(DjangoObjectType):
    class Meta:
        model = Order
        fields = ("id", "customer", "products", "total_amount", "order_date")

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

        # Use a transaction but allow per-record savepoints to support partial success
        with transaction.atomic():
            for idx, data in enumerate(customers):
                name = data.get('name')
                email = data.get('email')
                phone = data.get('phone', None)

                # Start a savepoint for this record
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
        # Validate customer
        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            errors.append("Invalid customer ID")
            return CreateOrder(order=None, errors=errors)

        if not product_ids or len(product_ids) == 0:
            errors.append("At least one product must be selected")
            return CreateOrder(order=None, errors=errors)

        # Validate and collect products
        products = []
        for pid in product_ids:
            try:
                p = Product.objects.get(pk=pid)
                products.append(p)
            except Product.DoesNotExist:
                errors.append(f"Invalid product ID: {pid}")

        if errors:
            return CreateOrder(order=None, errors=errors)

        # Create order and associate products in a transaction
        with transaction.atomic():
            if order_date:
                od = order_date
            else:
                od = timezone.now()

            order = Order.objects.create(customer=customer, order_date=od)
            order.products.set(products)

            # Ensure total is accurate by summing the product prices (use Decimal)
            total = Decimal('0.00')
            for p in products:
                total += p.price
            order.total_amount = total
            order.save()

        return CreateOrder(order=order, errors=None)

# ---------- Schema exports ----------
class Mutation(graphene.ObjectType):
    create_customer = CreateCustomer.Field()
    bulk_create_customers = BulkCreateCustomers.Field()
    create_product = CreateProduct.Field()
    create_order = CreateOrder.Field()

class Query(graphene.ObjectType):
    customers = graphene.List(CustomerType)
    products = graphene.List(ProductType)
    orders = graphene.List(OrderType)

    def resolve_customers(root, info):
        return Customer.objects.all()

    def resolve_products(root, info):
        return Product.objects.all()

    def resolve_orders(root, info):
        return Order.objects.all()
```

---

## `graphql_crm/schema.py`

```python
import graphene
from crm.schema import Query as CRMQuery, Mutation as CRMMutation

class Query(CRMQuery, graphene.ObjectType):
    pass

class Mutation(CRMMutation, graphene.ObjectType):
    pass

schema = graphene.Schema(query=Query, mutation=Mutation)
```

---

## `seed_db.py`

```python
# Run this script with: python manage.py shell < seed_db.py
# or import and run the `run()` function from a Django shell

from decimal import Decimal
from crm.models import Customer, Product


def run():
    # Create some products
    products_data = [
        {"name": "Laptop", "price": Decimal('999.99'), "stock": 10},
        {"name": "Mouse", "price": Decimal('25.50'), "stock": 100},
        {"name": "Keyboard", "price": Decimal('45.00'), "stock": 50},
    ]

    for p in products_data:
        obj, created = Product.objects.get_or_create(name=p['name'], defaults={
            'price': p['price'], 'stock': p['stock']
        })
        if created:
            print(f"Created product: {obj}")

    # Create some customers
    customers_data = [
        {"name": "Alice", "email": "alice@example.com", "phone": "+1234567890"},
        {"name": "Bob", "email": "bob@example.com", "phone": "123-456-7890"},
    ]

    for c in customers_data:
        obj, created = Customer.objects.get_or_create(email=c['email'], defaults={
            'name': c['name'], 'phone': c.get('phone')
        })
        if created:
            print(f"Created customer: {obj}")


if __name__ == '__main__':
    run()
```

---

## Quick testing examples (GraphQL queries)

> Use these directly at `/graphql` after starting the dev server.

* Create single customer

```graphql
mutation {
  createCustomer(name: "Alice", email: "alice@example.com", phone: "+1234567890") {
    customer { id name email phone }
    message
    errors
  }
}
```

* Bulk create customers

```graphql
mutation {
  bulkCreateCustomers(customers: [
    {name: "Sam", email: "sam@example.com", phone: "123-456-7890"},
    {name: "Eve", email: "alice@example.com"}  # intentionally duplicate
  ]) {
    customers { id name email }
    errors
  }
}
```

* Create product

```graphql
mutation {
  createProduct(name: "Tablet", price: 199.99, stock: 5) {
    product { id name price stock }
    errors
  }
}
```

* Create order

```graphql
mutation {
  createOrder(customerId: "1", productIds:["1","2"]) {
    order { id totalAmount orderDate customer { name } products { name price } }
    errors
  }
}
```

---

If you want, I can also open a small checklist of commands to run locally (migrations, running server, running seed) or produce unit tests for these mutations.
