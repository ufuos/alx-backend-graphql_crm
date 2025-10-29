import datetime
import requests

def log_crm_heartbeat():
    """
    Logs a heartbeat message to confirm the CRM is alive.
    """
    # 1️⃣ Prepare timestamp
    now = datetime.datetime.now().strftime("%d/%m/%Y-%H:%M:%S")

    # 2️⃣ Log message format
    message = f"{now} CRM is alive\n"

    # 3️⃣ Append to /tmp/crm_heartbeat_log.txt
    with open("/tmp/crm_heartbeat_log.txt", "a") as f:
        f.write(message)

    # 4️⃣ (Optional) Test GraphQL 'hello' query
    try:
        response = requests.post(
            "http://localhost:8000/graphql/",
            json={"query": "{ hello }"}
        )
        if response.status_code == 200:
            print("GraphQL endpoint is responsive:", response.json())
        else:
            print("GraphQL check failed:", response.status_code)
    except Exception as e:
        print("GraphQL heartbeat check failed:", e)
