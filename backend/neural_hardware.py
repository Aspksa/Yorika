"""Read-only hardware diagnostics for experimental neural execution.

Does not allocate tensors, run training, or assume a CUDA GPU exists.
"""
import platform


def hardware_report(torch_module=None):
    result = {"platform": platform.system(), "device": "cpu", "cuda_available": False,
              "gpu_name": None, "gpu_memory_bytes": None}
    if torch_module is None:
        try:
            import torch as torch_module
        except ImportError:
            return result
    if torch_module.cuda.is_available():
        props = torch_module.cuda.get_device_properties(0)
        result.update(device="cuda", cuda_available=True, gpu_name=props.name,
                      gpu_memory_bytes=props.total_memory)
    return result
