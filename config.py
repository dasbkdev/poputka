import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "8480159269:AAE4sb0uharF4y9bDHEs15h5TV6tTcB2SsQ")
GROUP_ID = int(os.getenv("GROUP_ID", "-1002399165589"))
ADMINS = [int(x) for x in os.getenv("ADMINS", "984834133").split(",")]
