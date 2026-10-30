# Asynchronous events (Kafka)

Read this when a scenario publishes or consumes Kafka events. The `kafka_listener` fixture, `KafkaListener` and
`kafka_send` come from the core (`modules/kafka_client.py`, the pytest-integration-bootstrap skill). Hosts and topics
are in the config, the login and password in environment variables.

```python
def test_submission_sends_event(cfg, kafka_listener, f_cleanup):
    """After the submission an event with the contract number goes to the contract events topic."""
    events = kafka_listener("contract_events")   # subscribe BEFORE the action that publishes the event
    contract = ContractSteps(cfg).create().attach_document("document.pdf")
    f_cleanup(contract)

    assert_submit_success(contract.try_submit())

    assert_contract_event(events.wait_for_key(contract.id), number=contract.number)  # a domain assertion
```

## Rules

- A listener sees only messages produced after it was created (it starts at the current end of every partition,
  with no consumer group or commits, so parallel workers do not interfere). Create it before the action.
- Find a message with `wait_for_key(key)` or `wait_for(match, description)`; check its content in an `assert_*`.
  On a timeout the last messages read and the listener's errors go to attachments.
- A topic that does not exist or a broker that is down fails at once, not after the waiting timeout.
- Values: JSON becomes a dict, UTF-8 text a str, anything else stays bytes. For Avro or Protobuf pass a
  deserializer: `kafka_listener("events", value_deserializer=my_avro_decode)`.
- To start a scenario with an event, call `kafka_send(cfg, "<topic key>", value, key=...)` inside a domain step;
  it fails if the broker rejects the message.
