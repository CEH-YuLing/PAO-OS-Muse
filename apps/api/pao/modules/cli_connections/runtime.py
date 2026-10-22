"""Operator-pinned Docker runtime. No device/profile provisioning by customer input."""
from pathlib import Path
import json
from ...config import ROOT
from ...config import settings
from ..engines.contract import EngineFailure


def host_digest():
    from pao_cli_runtime.source_pin import library_digest
    try:
        return library_digest()
    except Exception:
        raise EngineFailure('cli_runtime_pin_invalid') from None


def device_config():
    from pao_cli_runtime.docker_transport import ImagePin, canonical
    path = ROOT / '.runtime/cli-device.json'
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 16384:
        raise EngineFailure('cli_runtime_not_provisioned')
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        if (set(value) != {'version','device_id','image_id','binary_sha256','binary_version','host_runtime_sha256'}
                or value['version'] != 2 or canonical(value['device_id']) != value['device_id']
                or value['host_runtime_sha256'] != host_digest()
                or (settings().cli_device_id and settings().cli_device_id != value['device_id'])):
            raise ValueError()
        ImagePin(value['image_id'], value['binary_sha256'], value['binary_version'])
        return value
    except Exception:
        raise EngineFailure('cli_runtime_pin_invalid') from None


def configured_device():
    return settings().cli_device_id or device_config()['device_id']


def resolve(pin):
    from pao_cli_runtime.docker_transport import DockerTransport, ImagePin
    value = device_config()
    if (not isinstance(pin, dict) or value['device_id'] != pin.get('device_id')
            or value['image_id'] != pin.get('runtime_image_id')
            or value['binary_sha256'] != pin.get('binary_sha256') or value['binary_version'] != pin.get('binary_version')
            or value['host_runtime_sha256'] != pin.get('host_runtime_sha256')):
        raise EngineFailure('cli_runtime_pin_invalid')
    return DockerTransport(ImagePin(value['image_id'], value['binary_sha256'], value['binary_version']))
