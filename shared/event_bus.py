"""
Event bus simulation using Redis pub/sub.
Simulates Kafka-style event-driven communication between services.
Services publish events; subscribers react asynchronously.
"""
import json
import logging
import redis
from shared.config import REDIS_HOST, REDIS_PORT

logger = logging.getLogger(__name__)

_client = None

def get_redis():
    global _client
    if _client is None:
        try:
            _client = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT,
                decode_responses=True,
                socket_connect_timeout=1,   # fail fast — don't block requests
                socket_timeout=1,
            )
            _client.ping()
        except Exception as e:
            logger.warning(f"Redis unavailable, events will be logged only: {e}")
            _client = None
    return _client


def publish_event(channel: str, event_type: str, payload: dict):
    """
    Publish an event to a Redis channel.
    Falls back to logging if Redis is unavailable.
    """
    message = json.dumps({"event": event_type, "payload": payload})
    r = get_redis()
    if r:
        try:
            r.publish(channel, message)
            logger.info(f"[EVENT BUS] Published '{event_type}' to '{channel}'")
        except Exception as e:
            logger.error(f"[EVENT BUS] Publish failed: {e}")
    else:
        logger.info(f"[EVENT BUS FALLBACK] {channel}::{event_type} → {payload}")


def subscribe_and_handle(channel: str, handler_map: dict):
    """
    Subscribe to a Redis channel and dispatch events to handlers.
    handler_map: { "event_type": callable }
    Runs in a blocking loop — call from a background thread.
    """
    r = get_redis()
    if not r:
        logger.warning(f"[EVENT BUS] Cannot subscribe to '{channel}' — Redis unavailable")
        return
    pubsub = r.pubsub()
    pubsub.subscribe(channel)
    logger.info(f"[EVENT BUS] Subscribed to '{channel}'")
    for raw in pubsub.listen():
        if raw["type"] != "message":
            continue
        try:
            msg = json.loads(raw["data"])
            event_type = msg.get("event")
            if event_type in handler_map:
                handler_map[event_type](msg["payload"])
        except Exception as e:
            logger.error(f"[EVENT BUS] Handler error on '{channel}': {e}")
