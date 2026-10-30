"""Kafka in tests: sending, a listener from the current end of a topic and the kafka_listener fixture."""
import json
import logging
import threading
import uuid

import allure
import pytest
from confluent_kafka import Consumer, KafkaException, Producer, TopicPartition

from modules.allure_helper import attach_json
from modules.config import get_env
from modules.errors import EnvironmentUnavailable
from modules.waiters import wait_until

log = logging.getLogger(__name__)


def kafka_conf(cfg: dict) -> dict:
    k = cfg["kafka"]
    conf = {"bootstrap.servers": k["bootstrap_servers"], "security.protocol": k.get("security_protocol", "PLAINTEXT")}
    if k.get("username_env"):
        conf |= {"sasl.mechanism": k["sasl_mechanism"], "sasl.username": get_env(k["username_env"]),
                 "sasl.password": get_env(k["password_env"])}
    return conf


def _decode(raw: bytes | None):
    """JSON -> dict, UTF-8 text -> str, anything else (Avro, Protobuf) -> bytes as is. Never raises.

    For Avro/Protobuf pass a deserializer to KafkaListener(value_deserializer=...).
    """
    if raw is None:
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw
    try:
        return json.loads(text)
    except ValueError:
        return text


def _text(raw: bytes | None):
    """Keys and headers: UTF-8 text, or bytes as is."""
    if raw is None:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw


def kafka_send(cfg: dict, topic_key: str, value: dict, key: str | None = None, headers: dict | None = None):
    """Sends one JSON message and waits for the broker's acknowledgement."""
    topic = cfg["kafka"]["topics"][topic_key]
    errors = []
    with allure.step(f"Sending a message to {topic}"):
        attach_json(value, f"Message to {topic}")
        producer = Producer(kafka_conf(cfg))
        producer.produce(topic, key=key, value=json.dumps(value, ensure_ascii=False).encode(), headers=headers,
                         on_delivery=lambda err, msg: err and errors.append(err))
        if producer.flush(10):
            raise EnvironmentUnavailable(f"The broker did not acknowledge the message to {topic} in 10 s")
        if errors:  # flush() only counts unsent messages: a rejected message (no ACL, too large) comes here
            raise RuntimeError(f"The broker rejected the message to {topic}: {errors[0]}")


class KafkaListener:
    """Sees only messages produced after it was created; no consumer group or commits, so workers do not interfere."""

    def __init__(self, conf: dict, topic: str, value_deserializer=_decode):
        self.topic, self.messages, self.errors = topic, [], []
        self._deserialize = value_deserializer
        self._consumer = Consumer({**conf, "group.id": f"autotests-{uuid.uuid4()}", "enable.auto.commit": False})
        try:
            metadata = self._consumer.list_topics(topic, timeout=10).topics[topic]
        except KafkaException as error:
            raise EnvironmentUnavailable(f"Kafka is unreachable: {error}") from error
        if metadata.error is not None or not metadata.partitions:
            raise RuntimeError(f"Topic {topic} is not available: {metadata.error}")  # fail now, not after a timeout
        self._consumer.assign([TopicPartition(topic, p, self._consumer.get_watermark_offsets(
            TopicPartition(topic, p), timeout=10)[1]) for p in metadata.partitions])
        self._lock, self._stop = threading.Lock(), threading.Event()
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()

    def _read(self):
        while not self._stop.is_set():
            try:
                msg = self._consumer.poll(0.5)
                if msg is None:
                    continue
                if msg.error():
                    with self._lock:
                        self.errors.append(str(msg.error()))
                    continue
                message = {"key": _text(msg.key()), "value": self._deserialize(msg.value()),
                           "headers": {k: _text(v) for k, v in msg.headers() or []}}
            except Exception as error:  # noqa: BLE001 - one bad message must not stop the listener
                log.warning("Kafka listener %s: %r", self.topic, error)
                with self._lock:
                    self.errors.append(repr(error))
                continue
            with self._lock:
                self.messages.append(message)

    def wait_for(self, match, description: str, timeout: float = 30) -> dict:
        """The first message for which match(message) is true; on timeout what was read goes to an attachment."""
        def probe():
            with self._lock:
                return next((m for m in self.messages if match(m)), None)
        try:
            return wait_until(probe, description=f"a message in {self.topic}: {description}", timeout=timeout,
                              interval=0.5)
        except AssertionError:
            with self._lock:
                attach_json(self.messages[-50:], f"Read from {self.topic} (last 50)")
                if self.errors:
                    attach_json(self.errors[-20:], f"Listener errors in {self.topic}")
            raise

    def wait_for_key(self, key: str, timeout: float = 30) -> dict:
        return self.wait_for(lambda m: m["key"] == key, f"key={key}", timeout)

    def close(self):
        self._stop.set()
        self._thread.join(timeout=5)
        self._consumer.close()


@pytest.fixture
def kafka_listener(cfg):
    """kafka_listener("<key from cfg['kafka']['topics']>") creates a listener; all of them are closed after the test."""
    listeners = []

    def listen(topic_key: str, **kwargs) -> KafkaListener:
        listeners.append(KafkaListener(kafka_conf(cfg), cfg["kafka"]["topics"][topic_key], **kwargs))
        return listeners[-1]

    yield listen
    for listener in listeners:
        listener.close()
