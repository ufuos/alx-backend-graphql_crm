#!/bin/bash
# crm/cron_jobs/clean_inactive_customers.sh
# Make sure script runs from project root (adjust if your repo layout is different)
cd "$(dirname "$0")/../.." || exit 1

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Run Django shell - pass a heredoc containing the Python cleanup logic.
# NOTE: this uses the related name 'orders' and a datetime field 'created_at' on orders.
DELETED_COUNT=$(python manage.py shell <<'PY'
from django.utils import timezone
from datetime import timedelta
from django.db.models import Max, Q
# adjust import path if your Customer model lives elsewhere
try:
    from crm.models import Customer
except Exception as e:
    # if import fails, print 0 so the bash side gets a safe output
    print(0)
    raise

cutoff = timezone.now() - timedelta(days=365)
# Annotate each customer with the datetime of their latest order.
# Uses related name 'orders' and expects orders to have a datetime field 'created_at'.
qs = Customer.objects.annotate(last_order=Max('orders__created_at')).filter(Q(last_order__lt=cutoff) | Q(last_order__isnull=True))

count = qs.count()
if count:
    qs.delete()
print(count)
PY
)

# Append timestamp and deleted count to log file
echo "$TIMESTAMP Deleted customers: $DELETED_COUNT" >> /tmp/customer_cleanup_log.txt
