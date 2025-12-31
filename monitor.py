import os
import telebot
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
import threading
import re
import requests
import io
import logging
import sys
import time

# ------------------------------------------------------------------------------
# Logging (Docker-friendly)
# ------------------------------------------------------------------------------

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(LOG_LEVEL)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


logger = get_logger("telegram-mqtt-bridge")

# ------------------------------------------------------------------------------
# Environment variables
# ------------------------------------------------------------------------------

TOKEN = os.getenv("TELEGRAM_TOKEN")

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASS")

MQTT_TOPICS_OUTPUT = os.getenv(
    "MQTT_TOPICS_OUTPUT", "telegram/output/#"
).split(",")

MQTT_TOPIC_INPUT = os.getenv("MQTT_TOPIC_INPUT", "telegram/input")

ALLOWED_USER_IDS = {
    int(uid.strip())
    for uid in os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").split(",")
    if uid.strip().isdigit()
}

# Rate limit config
RATE_LIMIT_MESSAGES = int(os.getenv("RATE_LIMIT_MESSAGES", 5))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", 10))

logger.info(f"Authorized Telegram users: {sorted(ALLOWED_USER_IDS)}")
logger.info(
    f"Rate limit: {RATE_LIMIT_MESSAGES} messages / {RATE_LIMIT_WINDOW}s per user"
)

# ------------------------------------------------------------------------------
# Safety checks
# ------------------------------------------------------------------------------

if not TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN not set")

if not ALLOWED_USER_IDS:
    logger.warning("No authorized Telegram users configured — bot will be silent")

# ------------------------------------------------------------------------------
# Telegram bot
# ------------------------------------------------------------------------------

bot = telebot.TeleBot(TOKEN)

IMAGE_URL_PATTERN = re.compile(
    r"^https?://.*\.(jpg|jpeg|png|gif|webp)(\?.*)?$",
    re.IGNORECASE
)

# ------------------------------------------------------------------------------
# Authorization + Rate limit
# ------------------------------------------------------------------------------

rate_limit_state = {}  # user_id -> {count, window_start}

def is_rate_limited(user_id: int) -> bool:
    now = time.time()
    state = rate_limit_state.get(user_id)

    if not state:
        rate_limit_state[user_id] = {
            "count": 1,
            "window_start": now
        }
        return False

    elapsed = now - state["window_start"]

    if elapsed > RATE_LIMIT_WINDOW:
        # reset window
        rate_limit_state[user_id] = {
            "count": 1,
            "window_start": now
        }
        return False

    if state["count"] >= RATE_LIMIT_MESSAGES:
        return True

    state["count"] += 1
    return False


def is_user_allowed(message) -> bool:
    if message.chat.type != "private":
        logger.warning(f"Blocked non-private chat | chat_type={message.chat.type}")
        return False

    user_id = message.from_user.id

    if user_id not in ALLOWED_USER_IDS:
        logger.warning(f"Unauthorized Telegram user blocked | user_id={user_id}")
        return False

    if is_rate_limited(user_id):
        logger.warning(f"Rate limit exceeded | user_id={user_id}")
        return False

    return True


def send_to_allowed_users(send_func, *args, **kwargs):
    for user_id in ALLOWED_USER_IDS:
        try:
            send_func(user_id, *args, **kwargs)
        except Exception:
            logger.exception(f"Failed sending Telegram message | user_id={user_id}")

# ------------------------------------------------------------------------------
# MQTT callbacks
# ------------------------------------------------------------------------------

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logger.info(f"Connected to MQTT broker {MQTT_BROKER}:{MQTT_PORT}")
        for topic in MQTT_TOPICS_OUTPUT:
            topic = topic.strip()
            client.subscribe(topic)
            logger.info(f"Subscribed to MQTT topic: {topic}")
    else:
        logger.error(f"MQTT connection failed (rc={rc})")


def on_message(client, userdata, msg):
    payload = msg.payload.decode(errors="ignore").strip()
    logger.info(f"MQTT → Telegram | topic={msg.topic} | payload={payload}")

    try:
        match = IMAGE_URL_PATTERN.match(payload)

        if match:
            ext = match.group(1).lower()
            caption = f"Topic: {msg.topic}"

            with requests.get(payload, timeout=15) as response:
                response.raise_for_status()

                with io.BytesIO(response.content) as photo_buffer:
                    photo_buffer.name = f"snapshot.{ext}"

                    if ext == "gif":
                        send_to_allowed_users(
                            bot.send_animation,
                            photo_buffer,
                            caption=caption
                        )
                    else:
                        send_to_allowed_users(
                            bot.send_photo,
                            photo_buffer,
                            caption=caption
                        )
        else:
            message_text = f"Topic: {msg.topic}\nMessage: {payload}"
            send_to_allowed_users(
                bot.send_message,
                message_text,
                parse_mode="Markdown"
            )

    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error while downloading image: {e}")
    except requests.exceptions.Timeout:
        logger.error("Timeout while downloading image")
    except Exception:
        logger.exception("Unexpected error while processing MQTT message")

# ------------------------------------------------------------------------------
# MQTT client
# ------------------------------------------------------------------------------

mqtt_client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)

if MQTT_USER and MQTT_PASS:
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message


def run_mqtt():
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_forever()
    except Exception:
        logger.exception("MQTT loop error")

# ------------------------------------------------------------------------------
# Telegram → MQTT
# ------------------------------------------------------------------------------

@bot.message_handler(func=lambda message: True)
def handle_telegram_message(message):
    if not is_user_allowed(message):
        return

    payload = message.text
    result = mqtt_client.publish(MQTT_TOPIC_INPUT, payload)

    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        bot.reply_to(message, f"Sent to `{MQTT_TOPIC_INPUT}`")
        logger.info(
            f"Telegram → MQTT | user_id={message.from_user.id} | topic={MQTT_TOPIC_INPUT}"
        )
    else:
        bot.reply_to(message, "ERROR - Publishing to MQTT failed")
        logger.error(
            f"MQTT publish failed | user_id={message.from_user.id}"
        )

# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Starting Telegram ↔ MQTT secure bridge with rate limiting")

    mqtt_thread = threading.Thread(target=run_mqtt, daemon=True)
    mqtt_thread.start()

    try:
        bot.infinity_polling()
    except Exception:
        logger.exception("Telegram bot polling error")
