# ALX Backend GraphQL CRM

## 🧠 Overview
This project introduces **GraphQL with Django** using **Graphene-Django**.  
It demonstrates how to build and query a CRM (Customer Relationship Management) system with Customers, Products, and Orders.

---

## 🚀 Features
- GraphQL endpoint with GraphiQL interface
- Create customers, products, and orders via mutations
- Bulk customer creation with validation
- Filter and search using django-filter
- Modular schema for easy scalability

---

## ⚙️ Setup

### 1️⃣ Install dependencies
```bash
pip install django graphene-django django-filter
1) crm/README.md (complete instructions)

Create crm/README.md with this content (drop into your repo):

# CRM Celery Weekly Report Setup

This file describes how to set up Celery + Celery Beat for weekly CRM reporting.

## Requirements
- Redis running at `redis://localhost:6379/0`
- Python packages: `celery`, `django-celery-beat`

## Install
1. Add to requirements.txt:


celery>=5.2
django-celery-beat>=2.5

2. Install:
```bash
pip install -r requirements.txt

Django setup

Add 'django_celery_beat' to INSTALLED_APPS in crm/settings.py.

Run migrations:

python manage.py migrate

Celery files

crm/celery.py - initializes the Celery app (uses redis://localhost:6379/0).

crm/__init__.py - loads Celery app on Django startup.

crm/tasks.py - contains the generate_crm_report Celery task and logging.

Celery Beat schedule

crm/settings.py contains CELERY_BEAT_SCHEDULE with the generate-crm-report job:

Runs every Monday at 06:00 (server timezone).

Start services (development)

Start Redis (or docker run -d -p 6379:6379 redis:7).

Start Django server if needed:

python manage.py runserver


Start a Celery worker:

celery -A crm worker -l info


Start Celery Beat:

celery -A crm beat -l info

Verify

The report is logged to /tmp/crm_report_log.txt.

Each run appends a line formatted like:

YYYY-MM-DD HH:MM:SS - Report: X customers, Y orders, Z revenue

Troubleshooting

If the GraphQL query used by the task fails, the task falls back to using Django ORM to compute counts and revenue.

Make sure model field names match (e.g., Order.totalamount). Edit crm/tasks.py if your field names differ.


---

# 12) Quick checklist to test everything (step-by-step)

1. Add packages to `requirements.txt` and `pip install`.
2. Add `django_celery_beat` to `INSTALLED_APPS`.
3. Create `crm/celery.py` and update `crm/__init__.py`.
4. Add Celery settings in `crm/settings.py` (broker URL + beat schedule).
5. Add `crm/tasks.py` (task code above).
6. (Optional but recommended) Add aggregates to `crm/schema.py` as described.
7. Run `python manage.py migrate`.
8. Start Redis locally (or via Docker).
9. Start `celery -A crm worker -l info` in one terminal.
10. Start `celery -A crm beat -l info` in another terminal.
11. Check `/tmp/crm_report_log.txt` for output.

---
