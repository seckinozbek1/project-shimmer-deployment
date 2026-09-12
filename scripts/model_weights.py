"""Prepare cached embedding weights for offline loading, without changing models."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


def ensure_safetensors(snapshot):
    """Return a validated safetensors file, converting a cached state dict if needed.

    Conversion requires a patched torch reader and weights_only=True. The image
    builds with an isolated CPU converter; its runtime torch stays unchanged.
    No network request belongs in this function.
    """
    from safetensors import safe_open

    snapshot = Path(snapshot)
    destination = snapshot / "model.safetensors"
    if destination.is_file():
        with safe_open(str(destination), framework="pt", device="cpu") as reader:
            if not list(reader.keys()):
                raise ValueError("cached safetensors file contains no weights")
        return destination

    import torch
    from safetensors.torch import save_file

    version = re.match(r"^(\d+)\.(\d+)", str(torch.__version__))
    if version is None or tuple(map(int, version.groups())) < (2, 6):
        raise RuntimeError("weight conversion requires torch >= 2.6; prepare "
                           "safetensors during the image build")
    source = snapshot / "pytorch_model.bin"
    state = torch.load(str(source), map_location="cpu", weights_only=True)
    if isinstance(state, dict) and isinstance(state.get("state_dict"), dict):
        state = state["state_dict"]
    if not isinstance(state, dict) or not state:
        raise ValueError("cached checkpoint contains no state dict")
    if any(not isinstance(k, str) or not isinstance(v, torch.Tensor)
           for k, v in state.items()):
        raise ValueError("cached state dict contains a non-tensor weight")
    tensors = {key: value.contiguous() for key, value in state.items()}
    temporary = destination.with_suffix(".safetensors.tmp")
    try:
        save_file(tensors, str(temporary), metadata={"format": "pt"})
        with safe_open(str(temporary), framework="pt", device="cpu") as reader:
            if set(reader.keys()) != set(tensors):
                raise ValueError("converted checkpoint lost weight names")
            for key, tensor in tensors.items():
                if reader.get_slice(key).get_shape() != list(tensor.shape):
                    raise ValueError("converted checkpoint changed a weight shape")
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="Already cached model id")
    args = parser.parse_args(argv)
    from huggingface_hub import snapshot_download
    snapshot = snapshot_download(args.model, local_files_only=True)
    result = ensure_safetensors(snapshot)
    print("Prepared offline weights: %s (%d bytes)" % (result.name, result.stat().st_size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
