#!/usr/bin/env python3
"""
send_order_reminders.py

Query the GraphQL endpoint for orders placed within the last 7 days and
append reminders (order id + customer email + timestamp) to /tmp/order_reminders_log.txt.

Requires: gql, requests
Install with: pip install gql requests
"""

from datetime import datetime, timedelta, timezone
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
import os
import sys
import traceback

GRAPHQL_URL = "http://localhost:8000/graphql"
LOG_PATH = "/tmp/order_reminders_log.txt"

def iso_utc_now():
    return datetime.now(timezone.utc).isoformat()

def seven_days_ago_iso():
    return (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

def build_client(url: str) -> Client:
    transport = RequestsHTTPTransport(url=url, verify=True, retries=3)
    return Client(transport=transport, fetch_schema_from_transport=False)

# --- GraphQL query ---
# NOTE: This query uses a common pattern: orders(since: $since) { id orderDate customer { email } }
# If your GraphQL API uses a different argument name or structure, update the query string below.
QUERY = gql(
    """
    query OrdersSince($since: DateTime!) {
      # Many GraphQL CRMs accept a 'since' argument or similar. 
      # If your API uses different name (eg. "from", "filter", or accepts a filter object),
      # replace the root field and/or arguments accordingly.
      orders(since: $since) {
        id
        orderDate
        customer {
          email
        }
      }
    }
    """
)

def process_orders(orders):
    """Write one line per order to the log with a timestamp."""
    if not orders:
        return 0

    count = 0
    # Ensure the directory exists (not needed for /tmp but safe)
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

    with open(LOG_PATH, "a", encoding="utf-8") as f:
        for o in orders:
            # The structure returned may vary: ensure safe lookups
            order_id = o.get("id") if isinstance(o, dict) else str(o)
            # try nested customer email
            email = None
            if isinstance(o, dict):
                cust = o.get("customer") or {}
                email = cust.get("email") if isinstance(cust, dict) else None
            if not email:
                email = "<no-email>"

            timestamp = iso_utc_now()
            line = f"{timestamp} - Order ID: {order_id} - Email: {email}\n"
            f.write(line)
            count += 1
    return count

def main():
    try:
        client = build_client(GRAPHQL_URL)
        since_iso = seven_days_ago_iso()
        variables = {"since": since_iso}

        # Execute query
        result = client.execute(QUERY, variable_values=variables)

        # The exact place orders appear depends on the API:
        # Common patterns:
        #  - result['orders'] is a list
        #  - result['data']['orders'] (if fetch_schema_from_transport True and your client wraps it)
        # We try a few reasonable fallbacks below.
        orders = None
        if isinstance(result, dict):
            # common: result['orders']
            orders = result.get("orders")
            # some servers might wrap under 'data' (uncommon with gql lib), try it
            if orders is None and "data" in result:
                orders = result["data"].get("orders")
        # If still None, try to find any list-looking value in result
        if orders is None:
            for v in result.values() if isinstance(result, dict) else []:
                if isinstance(v, list):
                    orders = v
                    break

        # If still None, set to empty list
        if orders is None:
            orders = []

        count = process_orders(orders)
        print("Order reminders processed!")
        print(f"{count} order(s) logged to {LOG_PATH}")
        return 0
    except Exception as e:
        print("Error while sending order reminders:", file=sys.stderr)
        traceback.print_exc()
        return 2

if __name__ == "__main__":
    sys.exit(main())
