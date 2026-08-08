import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


package_names = (
    "vllm_ascend",
    "vllm_ascend.distributed",
    "vllm_ascend.distributed.kv_transfer",
    "vllm_ascend.distributed.kv_transfer.kv_pool",
    "vllm_ascend.distributed.kv_transfer.kv_pool.ascend_store",
)
for package_name in package_names:
    package = ModuleType(package_name)
    package.__path__ = []
    sys.modules[package_name] = package

config_data_name = (
    "vllm_ascend.distributed.kv_transfer.kv_pool.ascend_store.config_data"
)
config_data = ModuleType(config_data_name)


def is_kv_save_role(role, consumer_is_to_put):
    return role in ("kv_producer", "kv_both") or consumer_is_to_put


config_data.is_kv_save_role = is_kv_save_role
sys.modules[config_data_name] = config_data

source = Path(
    "/vllm-workspace/vllm-ascend/vllm_ascend/distributed/kv_transfer/kv_pool/"
    "ascend_store/layerwise_config.py"
)
spec = importlib.util.spec_from_file_location("derived_layerwise_config", source)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def make_config(role: str, *, consumer_is_to_put: bool = False):
    extra = {
        "backend": "mooncake",
        "use_layerwise": True,
        "layerwise_num_shared_buffers": 3,
    }
    if consumer_is_to_put:
        extra["consumer_is_to_put"] = True
    return SimpleNamespace(
        kv_connector="AscendStoreConnector",
        kv_role=role,
        kv_connector_extra_config=extra,
    )


for role, consumer_is_to_put in (
    ("kv_producer", False),
    ("kv_both", False),
    ("kv_consumer", True),
):
    config = make_config(role, consumer_is_to_put=consumer_is_to_put)
    assert module.get_gva_layerwise_config(config) is config.kv_connector_extra_config

pure_consumer = make_config("kv_consumer")
try:
    module.get_gva_layerwise_config(pure_consumer)
except ValueError as error:
    assert "save-capable" in str(error)
else:
    raise AssertionError("pure Mooncake consumer reuse was not rejected")

layerwise = module.get_layerwise_config(27, {"layerwise_num_shared_buffers": 3})
physical_slots = module.get_layerwise_kv_cache_num_tensors(
    27, {"layerwise_num_shared_buffers": 3}
)
assert layerwise.has_layer_reuse
assert layerwise.num_shared_buffers == 3
assert layerwise.independent_layers == [0, 26]
assert physical_slots == 5
assert 27 / physical_slots == 5.4
print("roles=kv_producer,kv_both,kv_consumer+consumer_is_to_put")
print("pure_consumer=REJECTED")
print(
    f"layers=27 shared_buffers=3 physical_slots={physical_slots} "
    f"factor={27 / physical_slots:.3f}"
)
