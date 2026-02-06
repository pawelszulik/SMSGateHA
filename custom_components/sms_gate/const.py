"""Stałe konfiguracji integracji SMS Gate."""

DOMAIN = "sms_gate"

# Konfiguracja połączenia (Local)
CONF_HOST = "host"
CONF_PORT = "port"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# Domyślny port Local Server z dokumentacji SMS Gate
DEFAULT_PORT = 8080

# Options: nazwane odbiorcy i szablony (słowniki: nazwa -> wartość)
CONF_RECIPIENTS = "recipients"
CONF_TEMPLATES = "templates"

# Ścieżki API (Local Server)
PATH_MESSAGES = "/messages"
PATH_MESSAGE_LEGACY = "/message"
PATH_HEALTH = "/health"
PATH_HEALTH_READY = "/health/ready"

# Interwał odświeżania coordinatora (sekundy)
UPDATE_INTERVAL = 60

# Limit wiadomości pobieranych w jednym żądaniu
MESSAGES_LIMIT_DEFAULT = 20
