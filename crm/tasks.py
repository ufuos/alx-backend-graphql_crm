# crm/tasks.py
import os
import requests  # ✅ Added missing import
from datetime import datetime  # ✅ Added missing import
from django.utils import timezone
from graphene.test import Client as GrapheneClient
from crm import schema as crm_schema_module  # expects crm/schema.py exports schema
from django.db.models import Sum

LOG_PATH = "/tmp/crm_report_log.txt"


def _log_line(text: str):
    ts = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} - Report: {text}\n"
    with open(LOG_PATH, "a") as f:
        f.write(line)


def generate_crm_report():
    """
    Generates a CRM report: total customers, total orders, total revenue.
    Tries to fetch via GraphQL query first; falls back to Django ORM if necessary.
    Logs output to /tmp/crm_report_log.txt
    """

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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

    try:
        client = GrapheneClient(crm_schema_module.schema)
        result = client.execute(graph_query)

        if result.get("errors"):
            raise Exception(result["errors"])

        data = result.get("data", {})
        customers_count = data.get("customersCount")
        orders_count = data.get("ordersCount")
        total_revenue = data.get("totalRevenue")

    except Exception:
        # Fall back to ORM if GraphQL fails
        pass

    if customers_count is None or orders_count is None or total_revenue is None:
        try:
            from crm.models import Customer, Order

            customers_count = customers_count or Customer.objects.count()
            orders_count = orders_count or Order.objects.count()

            agg = Order.objects.aggregate(total=Sum("totalamount"))
            total_revenue = total_revenue or (agg["total"] or 0)
        except Exception as ex:
            _log_line(f"ERROR while computing report: {ex}")
            raise

    try:
        customers_count = int(customers_count)
    except Exception:
        customers_count = 0

    try:
        orders_count = int(orders_count)
    except Exception:
        orders_count = 0

    try:
        total_revenue = float(total_revenue or 0)
    except Exception:
        total_revenue = 0.0

    report_text = (
        f"[{timestamp}] {customers_count} customers, {orders_count} orders, "
        f"{total_revenue:.2f} revenue"
    )

    _log_line(report_text)

    # Example of sending report data to an external API (if needed)
    try:
        requests.post(
            "https://example.com/api/report",
            json={"customers": customers_count, "orders": orders_count, "revenue": total_revenue},
            timeout=5,
        )
    except Exception:
        _log_line("Warning: Failed to send report via HTTP.")

    return {"customers": customers_count, "orders": orders_count, "revenue": total_revenue}
