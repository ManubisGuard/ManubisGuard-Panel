"""Patch the Python Node bridge for the fork's additive multi-core Start field.

The published bridge may lag the forked node protocol. Keep the normal bridge
API intact and add the wire-compatible field 6 (`additive`) at image build time.
"""
from __future__ import annotations

import ast
import re
import site
from pathlib import Path

from google.protobuf import descriptor_pb2


def package_root() -> Path:
    for root in map(Path, site.getsitepackages()):
        candidate = root / "PasarGuardNodeBridge"
        if (candidate / "common" / "service_pb2.py").exists():
            return candidate
    raise RuntimeError("PasarGuardNodeBridge package not found")


def patch_descriptor(pb2_path: Path) -> None:
    source = pb2_path.read_text()
    match = re.search(r"AddSerializedFile\((b'(?:[^'\\]|\\.)*')\)", source)
    if not match:
        raise RuntimeError(f"Could not locate serialized protobuf descriptor in {pb2_path}")

    current = ast.literal_eval(match.group(1))
    descriptor = descriptor_pb2.FileDescriptorProto.FromString(current)
    backend = next((m for m in descriptor.message_type if m.name == "Backend"), None)
    if backend is None:
        raise RuntimeError("Backend message not found in Node bridge protobuf descriptor")
    if any(field.number == 6 and field.name == "additive" for field in backend.field):
        return

    field = backend.field.add()
    field.name = "additive"
    field.number = 6
    field.label = descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL
    field.type = descriptor_pb2.FieldDescriptorProto.TYPE_BOOL
    field.json_name = "additive"

    replacement = repr(descriptor.SerializeToString())
    pb2_path.write_text(source[: match.start(1)] + replacement + source[match.end(1) :])


def patch_signature_and_constructor(path: Path) -> None:
    source = path.read_text()
    source = source.replace(
        "        timeout: int | None = None,\n    ) -> service.BaseInfoResponse | None:",
        "        timeout: int | None = None,\n        additive: bool = False,\n    ) -> service.BaseInfoResponse | None:",
        1,
    )
    source = source.replace(
        "exclude_inbounds=exclude_inbounds\n        )",
        "exclude_inbounds=exclude_inbounds, additive=additive\n        )",
        1,
    )
    source = source.replace(
        "exclude_inbounds=exclude_inbounds,\n                    ),",
        "exclude_inbounds=exclude_inbounds,\n                        additive=additive,\n                    ),",
        1,
    )
    path.write_text(source)


def main() -> None:
    root = package_root()
    patch_descriptor(root / "common" / "service_pb2.py")
    patch_signature_and_constructor(root / "grpclib.py")
    patch_signature_and_constructor(root / "rest.py")
    print(f"patched Node bridge at {root}")


if __name__ == "__main__":
    main()
