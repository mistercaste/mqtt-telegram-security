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

# ------------------------------------------------------------------------------
# Logging configuration (Docker-friendly: stdout)
# ------------------------------------------------------------------------------

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # Prevent duplicate handlers

    logger.setLevel(LOG_LEVEL)

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.propagate = False
    return logger


logger = get_logger("telegram-mqtt-bridge")

# ------------------------------------------------------------------------------
# Environment variables
# ------------------------------------------------------------------------------

TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_USER = os.getenv('MQTT_USER')
MQTT_PASS = os.getenv('MQTT_PASS')

MQTT_TOPICS_OUTPUT = os.getenv(
    'MQTT_TOPICS_OUTPUT',
    'telegram/output/#,mt32/#'
).split(',')

MQTT_TOPIC_INPUT = os.getenv('MQTT_TOPIC_INPUT', 'telegram/input')

# ------------------------------------------------------------------------------
# Telegram bot
# ------------------------------------------------------------------------------

bot = telebot.TeleBot(TOKEN)

# Regex to match image URLs
IMAGE_URL_PATTERN = re.compile(
    r'^https?://.*\.(jpg|jpeg|png|gif|webp)(\?.*)?$',
    re.IGNORECASE
)

# ------------------------------------------------------------------------------
# MQTT callbacks
# ------------------------------------------------------------------------------

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logger.info(f"Connected to MQTT broker: {MQTT_BROKER}:{MQTT_PORT}")
        for topic in MQTT_TOPICS_OUTPUT:
            topic = topic.strip()
            client.subscribe(topic)
            logger.info(f"Subscribed to topic: {topic}")
    else:
        logger.error(f"MQTT connection failed (rc={rc})")


def on_message(client, userdata, msg):
    payload = msg.payload.decode(errors="ignore").strip()
    logger.info(f"MQTT message received | topic={msg.topic} | payload={payload}")

    try:
        match = IMAGE_URL_PATTERN.match(payload)

        if match:
            ext = match.group(1).lower()
            caption = f"Topic: {msg.topic}"

            logger.info(f"Downloading image ({ext}) from URL")

            with requests.get(payload, timeout=15, stream=True) as response:
                response.raise_for_status()

                with io.BytesIO(response.content) as photo_buffer:
                    photo_buffer.name = f"snapshot.{ext}"

                    if ext == 'gif':
                        bot.send_animation(CHAT_ID, photo_buffer, caption=caption)
                        logger.info("GIF sent to Telegram")
                    else:
                        bot.send_photo(CHAT_ID, photo_buffer, caption=caption)
                        logger.info(f"Image sent to Telegram ({photo_buffer.name})")

        else:
            message_text = f"Topic: {msg.topic}\nMessage: {payload}"
            bot.send_message(CHAT_ID, message_text, parse_mode='Markdown')
            logger.info("Text message sent to Telegram")

    except Exception:
        logger.exception("Error while processing MQTT message")


# ------------------------------------------------------------------------------
# MQTT client setup
# ------------------------------------------------------------------------------

mqtt_client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)

if MQTT_USER and MQTT_PASS:
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
    logger.info("MQTT authentication enabled")

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message


def run_mqtt():
    try:
        logger.info("Starting MQTT loop")
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_forever()
    except Exception:
        logger.exception("MQTT loop error")


# ------------------------------------------------------------------------------
# Telegram → MQTT
# ------------------------------------------------------------------------------

@bot.message_handler(func=lambda message: True)
def handle_telegram_message(message):
    if str(message.chat.id) != str(CHAT_ID):
        logger.warning(f"Ignored message from unauthorized chat_id={message.chat.id}")
        return

    payload = message.text
    result = mqtt_client.publish(MQTT_TOPIC_INPUT, payload)

    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        bot.reply_to(message, f"Sent to `{MQTT_TOPIC_INPUT}`")
        logger.info(f"Telegram message published to MQTT | topic={MQTT_TOPIC_INPUT}")
    else:
        bot.reply_to(message, "ERROR - Publishing to MQTT failed")
        logger.error("Failed to publish Telegram message to MQTT")


# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Starting Telegram ↔ MQTT bridge")

    mqtt_thread = threading.Thread(target=run_mqtt, daemon=True)
    mqtt_thread.start()

    try:
        bot.infinity_polling()
    except Exception:
        logger.exception("Telegram bot polling error")
