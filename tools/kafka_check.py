"""
Checks modules/kafka_client.py of the example against a real broker (CI service apache/kafka on localhost:9092).

    python tools/kafka_check.py [bootstrap_servers]

1. A missing topic fails at once instead of after a waiting timeout.
2. The listener sees a message sent after it was created and finds it by key.
3. A message that is not UTF-8 (like Avro) does not stop the listener: it is kept as bytes, the next one is found.
4. kafka_send waits for the acknowledgement.
"""
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "example"))

from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic
from modules.kafka_client import KafkaListener, kafka_conf, kafka_send

SERVERS = sys.argv[1] if len(sys.argv) > 1 else "localhost:9092"
TOPIC = f"autotests.check.{uuid.uuid4().hex[:8]}"
CFG = {"kafka": {"bootstrap_servers": SERVERS, "topics": {"events": TOPIC}}}


def create_topic():
    admin = AdminClient({"bootstrap.servers": SERVERS})
    for attempt in range(30):  # the broker container may still be starting
        try:
            admin.create_topics([NewTopic(TOPIC, num_partitions=2, replication_factor=1)])[TOPIC].result(10)
            return
        except Exception as error:  # noqa: BLE001
            print(f"waiting for the broker ({attempt}): {error}")
            time.sleep(2)
    raise SystemExit("The broker did not come up")


def main() -> int:
    create_topic()
    conf = kafka_conf(CFG)
    try:
        KafkaListener(conf, f"{TOPIC}.missing")
        raise SystemExit("1. a missing topic did not fail")
    except RuntimeError as error:
        print(f"1. OK: {error}")

    listener = KafkaListener(conf, TOPIC)
    try:
        time.sleep(1)
        raw = Producer(conf)
        raw.produce(TOPIC, key=b"binary", value=b"\x00\x00\x00\x00\x01\xff\xfe avro-like")
        raw.flush(10)
        key = uuid.uuid4().hex
        kafka_send(CFG, "events", {"id": key, "status": "SUBMITTED"}, key=key)
        print("4. OK: kafka_send acknowledged")
        message = listener.wait_for_key(key, timeout=20)
        assert message["value"] == {"id": key, "status": "SUBMITTED"}, message
        print("2. OK: found by key", message)
        binary = listener.wait_for_key("binary", timeout=5)
        assert isinstance(binary["value"], bytes), binary
        print("3. OK: the non-UTF-8 message is kept as bytes, the listener kept running")
    finally:
        listener.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
