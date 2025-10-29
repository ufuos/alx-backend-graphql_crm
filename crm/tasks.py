# crm/tasks.py
import os
from celery import shared_task
from django.utils import timezone
from graphene.test import Client as GrapheneClient
from crm import schema as crm_schema_module  # expects crm/schema.py exports `schema`
from django.db.models import Sum

LOG_PATH = "/tmp/crm_report_log.txt"

def _log_line(text: str):
    ts = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} - Report: {text}\n"
    # ensure directory exists (for /tmp it's usually fine)
    with open(LOG_PATH, "a") as f:
        f.write(line)

@shared_task(bind=True, name="crm.tasks.generate_crm_report")
def generate_crm_report(self):
    """
    Generates a CRM report: total customers, total orders, total revenue.
    Tries to fetch via GraphQL query first; falls back to Django ORM if necessary.
    Logs output to /tmp/crm_report_log.txt
    """
    # Build a GraphQL query that *should* exist if your schema exposes aggregate fields.
    graph_query = """
    query {
      customersCount
      ordersCount
      totalRevenue
    }
    """

    customers_count = None
    orders_count = None
    total_revenue = None

    # Try GraphQL route first (in-process)
    try:
        client = GrapheneClient(crm_schema_module.schema)
        result = client.execute(graph_query)

        if result.get("errors"):
            # GraphQL returned errors; we'll fall back below
            raise Exception(result["errors"])

        data = result.get("data", {})
        # Attempt to parse fields if they exist
        customers_count = data.get("customersCount")
        orders_count = data.get("ordersCount")
        total_revenue = data.get("totalRevenue")
    except Exception:
        # If GraphQL path doesn't work, fallback to ORM below
        pass

    # Fallback to ORM if any of the fields are None
    if customers_count is None or orders_count is None or total_revenue is None:
        try:
            # Import models lazily to avoid circular imports at module import time
            from crm.models import Customer, Order  # adjust model names if different

            customers_count = customers_count or Customer.objects.count()
            orders_count = orders_count or Order.objects.count()

            # assume Order model has 'totalamount' field (adjust name if different)
            agg = Order.objects.aggregate(total=Sum("totalamount"))
            total_revenue = total_revenue or (agg["total"] or 0)
        except Exception as ex:
            # If even the ORM fails, log an error line and re-raise for visibility
            _log_line(f"ERROR while computing report: {ex}")
            raise

    # Ensure numeric types are normalized
    try:
        customers_count = int(customers_count)
    except Exception:
        customers_count = int(customers_count or 0)

    try:
        orders_count = int(orders_count)
    except Exception:
        orders_count = int(orders_count or 0)

    try:
        # Format revenue to 2 decimal places
        total_revenue = float(total_revenue or 0)
    except Exception:
        total_revenue = 0.0

    # Build the human-readable report text
    report_text = f"{customers_count} customers, {orders_count} orders, {total_revenue:.2f} revenue"

    # Write to log
    _log_line(report_text)

    # Optionally return the report for celery task result inspection
    return {"customers": customers_count, "orders": orders_count, "revenue": total_revenue}
