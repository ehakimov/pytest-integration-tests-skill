"""Common helpers: unique data, model serialization, files, body mutations, value normalizers."""
import mimetypes
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from faker import Faker

from modules.config import ROOT_DIR

fake = Faker(os.getenv("FAKER_LOCALE", "en_US"))  # the project's locale: FAKER_LOCALE=de_DE in .env
FILES_DIR = ROOT_DIR / "tests" / "files"
REMOVE = object()


def unique(prefix: str = "autotest") -> str:
    """A unique string: does not collide between tests, xdist workers and parallel pipelines."""
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def iso_now(days: int = 0) -> str:
    """UTC now in ISO 8601 with milliseconds: 2026-10-30T08:41:31.123Z."""
    moment = datetime.now(timezone.utc) + timedelta(days=days)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


def as_instant(value):
    """Normalizer for comparing timestamps: any ISO 8601 form -> UTC datetime to the millisecond.

    "2026-10-30T08:41:31.123456Z" and "2026-10-30T11:41:31.123+03:00" become equal.
    """
    if not isinstance(value, str):
        return value
    moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc)
    return moment.replace(microsecond=moment.microsecond // 1000 * 1000)


def to_dict(model, drop_none: bool = True) -> dict:
    """dataclass -> dict for json=; None fields are not sent by default."""
    data = asdict(model)
    return _drop_none(data) if drop_none else data


def _drop_none(value):
    if isinstance(value, dict):
        return {k: _drop_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_drop_none(v) for v in value]
    return value


def file_for_upload(name: str, field: str = "file", content_type: str | None = None) -> dict:
    """files= for requests: a file from tests/files, read fully (no open handle), MIME type by extension."""
    path = FILES_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"No file {name} in {FILES_DIR}")
    content_type = content_type or mimetypes.guess_type(name)[0] or "application/octet-stream"
    return {field: (name, path.read_bytes(), content_type)}


@dataclass(frozen=True)
class Mutation:
    """Changes a dict body by the path "a.b.0.c": sets value or removes the key."""
    path: str
    value: object = REMOVE

    def __repr__(self):  # this is how the mutation is shown in Allure parameters
        return f"without {self.path}" if self.value is REMOVE else f"{self.path} = {self.value!r}"

    def __call__(self, body: dict) -> dict:
        *parents, last = self.path.split(".")
        node = body
        for key in parents:
            node = node[int(key)] if isinstance(node, list) else node[key]
        key = int(last) if isinstance(node, list) else last
        if self.value is REMOVE:
            del node[key]
        else:
            node[key] = self.value
        return body


def mutate(path: str, value=REMOVE) -> Mutation:
    return Mutation(path, value)
