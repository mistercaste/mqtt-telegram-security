import os
import telebot
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
import threading
import re
import requests
import io

# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Telegram USER ID(s) allowed to interact with the bot
# Example: TELEGRAM_USER_IDS="123456789,987654321"
AUTHORIZED_USER_IDS = {
    int(uid.strip())
    for uid in os.getenv("TELEGRAM_USER_IDS", "").split(",")
    if uid.strip().isdigit()
}

# Telegram CHAT ID used ONLY as destination for outbound messages
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASS")
MQTT_TOPICS_OUTPUT = os.getenv(
    "MQTT_TOPICS_OUTPUT", "telegram/output/#,mt32/#"
).split(",")
MQTT_TOPIC_INPUT = os.getenv("MQTT_TOPIC_INPUT", "telegram/input")

# ============================================================
# TELEGRAM BOT INITIALIZATION
# ============================================================

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ============================================================
# SECURITY UTILITIES
# ============================================================

def is_authorized(message) -> bool:
    """
    Allow access ONLY if:
    - message comes from a private chat
    - sender exists
    - sender Telegram USER ID is explicitly whitelisted
    """
    return (
        message.chat.type == "private"
        and message.from_user is not None
        and message.from_user.id in AUTHORIZED_USER_IDS
    )

# ============================================================
# IMAGE URL REGEX
# Supports:
# - http / https
# - hostname or IP
# - optional port
# - path
# - query string
# ============================================================

IMAGE_URL_PATTERN = re.compile(
    r"""
    ^https?://
    [^/\s:]+            # hostname or IP
    (?::\d+)?           # optional port
    /.+?
    \.(jpg|jpeg|png|gif|webp)
    (?:\?.*)?$
    """,
    re.IGNORECASE | re.VERBOSE,
)

# ============================================================
# MQTT CALLBACKS
# ============================================================

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"INFO - Connected to MQTT broker: {MQTT_BROKER}")
        for topic in MQTT_TOPICS_OUTPUT:
            topic = topic.strip()
            client.subscribe(topic)
            print(f"INFO - Subscribed to topic: {topic}")
    else:
        print(f"ERROR - MQTT connection failed (rc={rc})")

def on_message(client, userdata, msg):
    """
    Forward MQTT messages to Telegram.
    This path is NOT exposed to Telegram users.
    """
    payload = msg.payload.decode(errors="ignore").strip()
    print(f"INFO - MQTT [{msg.topic}] -> {payload}")

    try:
        match = IMAGE_URL_PATTERN.match(payload)

        if match:
            ext = match.group(1).lower()
            caption = f"Topic: {msg.topic}"

            print(f"INFO - Downloading image ({ext})")

            with requests.get(payload, timeout=15) as response:
                response.raise_for_status()

                with io.BytesIO(response.content) as buffer:
                    buffer.name = f"snapshot.{ext}"

                    if ext == "gif":
                        bot.send_animation(
                            TELEGRAM_CHAT_ID,
                            buffer,
                            caption=caption,
                        )
                    else:
                        bot.send_photo(
                            TELEGRAM_CHAT_ID,
                            buffer,
                            caption=caption,
                        )

            print("INFO - Image sent to Telegram")

        else:
            text = f"Topic: {msg.topic}\nMessage: {payload}"
            bot.send_message(
                TELEGRAM_CHAT_ID,
                text,
                parse_mode=None,  # safer: avoid Markdown injection
            )
            print("INFO - Text message sent to Telegram")

    except Exception as e:
        print(f"ERROR - MQTT -> Telegram failed: {e}")

# ============================================================
# MQTT CLIENT INITIALIZATION
# ============================================================

mqtt_client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)

if MQTT_USER and MQTT_PASS:
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# ============================================================
# TELEGRAM -> MQTT (SECURED)
# ============================================================

@bot.message_handler(func=lambda message: True)
def handle_telegram_message(message):
    # SECURITY GATE: nothing happens before this check
    if not is_authorized(message):
        print(
            f"SECURITY - Unauthorized access attempt from "
            f"{message.from_user.id if message.from_user else 'UNKNOWN'}"
        )
        return

    payload = message.text or ""
    result = mqtt_client.publish(MQTT_TOPIC_INPUT, payload)

    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        bot.reply_to(message, f"Sent to `{MQTT_TOPIC_INPUT}`")
    else:
        bot.reply_to(message, "ERROR - MQTT publish failed")

# ============================================================
# MQTT THREAD
# ============================================================

def run_mqtt():
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_forever()
    except Exception as e:
        print(f"ERROR - MQTT loop error: {e}")

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("INFO - Starting secure Telegram ↔ MQTT bridge")

    mqtt_thread = threading.Thread(target=run_mqtt, daemon=True)
    mqtt_thread.start()

    try:
        bot.infinity_polling(skip_pending=True)
    except Exception as e:
        print(f"ERROR - Telegram polling error: {e}")
