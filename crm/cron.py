# crm/cron.py
import os
import datetime
import requests
import json
from django.utils import timezone
from crm.schema import schema  # import the graphene schema object we exported in crm/schema.py

# ✅ Log paths
HEARTBEAT_LOG_PATH = "/tmp/crm_heartbeat_log.txt"
LOW_STOCK_LOG_PATH = "/tmp/low_stock_updates_log.txt"


# ---------------------- HEARTBEAT LOGGER ----------------------
def log_crm_heartbeat():
    """
    Logs a heartbeat message every 5 minutes to confirm the CRM is alive
    and optionally checks the GraphQL endpoint responsiveness.
    """
    now = datetime.datetime.now().strftime("%d/%m/%Y-%H:%M:%S")
    message = f"{now} CRM is alive\n"

    # Append heartbeat to log file
    with open(HEARTBEAT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(message)

    # Optional GraphQL endpoint test
    try:
        response = requests.post(
            "http://localhost:8000/graphql/",
            json={"query": "{ hello }"},
        )
        if response.status_code == 200:
            print("GraphQL endpoint is responsive:", response.json())
        else:
            print("GraphQL check failed:", response.status_code)
    except Exception as e:
        print("GraphQL heartbeat check failed:", e)


# ---------------------- LOW STOCK UPDATER ----------------------
def _log_line(text):
    """Helper to write timestamped log lines for low-stock updates."""
    timestamp = timezone.now().astimezone().isoformat()
    line = f"[{timestamp}] {text}\n"
    with open(LOW_STOCK_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line)


def update_low_stock():
    """
    Cron job that executes the UpdateLowStockProducts GraphQL mutation via the schema object,
    then logs updated product names and new stock levels to /tmp/low_stock_updates_log.txt
    """
    mutation = """
    mutation {
      updateLowStockProducts {
        success
        message
        updatedProducts {
          id
          name
          stock
        }
      }
    }
    """

    try:
        result = schema.execute(mutation)

        if result.errors:
            _log_line(f"GraphQL errors: {result.errors}")
            return

        data = result.data.get("updateLowStockProducts")
        if not data:
            _log_line("No data returned from UpdateLowStockProducts mutation.")
            return

        success = data.get("success")
        message = data.get("message")
        products = data.get("updatedProducts") or []

        if success and products:
            for p in products:
                _log_line(f"Updated product '{p.get('name')}' (id={p.get('id')}) new stock: {p.get('stock')}")
            _log_line(f"Mutation result: {message}")
        else:
            _log_line(f"Mutation run: success={success} message='{message}' Updated count: {len(products)}")

    except Exception as exc:
        _log_line(f"Exception during update_low_stock: {str(exc)}")
