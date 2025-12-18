# mqtt-telegram-security
A Docker container listening to an MQTT bus, and sending notifications to Telegram when spotting items maked as vulnerable.

## Docker Compose
```
services:
  mqtt-monitor:
    build: .
    container_name: mqtt-telegram-security
    restart: unless-stopped
    environment:
      - TELEGRAM_TOKEN=your_token
      - TELEGRAM_CHAT_ID=your_chat_id
      - MQTT_BROKER=192.168.1.X
      - MQTT_TOPIC=security/#    # Monitors all sub-topics of security
```

## Testing MQTT
You can test the setup by sending a manual message to the MQTT broker:
```
mosquitto_pub -h localhost -t "security/vulnerabilities" -m "Test: Found exploit CVE-2023-XXXX"
```
