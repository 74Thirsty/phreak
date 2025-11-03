import datetime

def timestamp() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"
