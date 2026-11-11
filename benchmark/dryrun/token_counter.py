"""The main reading agent's own tokenizer as the adapters' token counter (preregistration
section 5.3; loop plan S5 item 0.7): tokenizer files only, never the model weights.

The checkpoint is the pinned base of the producer, read from config/final_models.json
(model id and revision), resolved in the local Hugging Face cache with no network
(`local_files_only`). Every tokenizer file and config.json is checked against the pinned
`base_hashes` before use; model.safetensors is never opened (its size is read with stat
for the memory bound, never its bytes). The counts are the ones bare_model.py makes:
`count(text)` the text's tokens without special tokens, `count_prompt(system, user)` the
system and user turns through the model's own chat template with the generation prompt.

cli.load_counter imports this file and calls count and count_prompt; the tokenizer is
loaded on the first call.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ROLE = "producer"
CHECKED_FILES = ("config.json", "generation_config.json", "tokenizer.json", "tokenizer_config.json",
                 "special_tokens_map.json", "added_tokens.json", "merges.txt", "vocab.json")
NOT_READ = "model.safetensors"
_STATE = {}


class CounterRefused(RuntimeError):
    """The pinned tokenizer is not available offline, or a file differs from its pin."""


def specification(root=ROOT) -> dict:
    return json.loads((Path(root) / "config" / "final_models.json").read_text(encoding="utf-8"))[ROLE]


def _sha(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def snapshot(spec=None) -> Path:
    """The pinned snapshot folder, its tokenizer files checked against base_hashes."""
    spec = spec or specification()
    try:
        from huggingface_hub import snapshot_download
        path = Path(snapshot_download(spec["model_id"], revision=spec["revision"], local_files_only=True))
    except Exception as exc:  # not in the local cache: no download is ever attempted
        raise CounterRefused("the pinned tokenizer %s@%s is not in the local cache: %s"
                             % (spec["model_id"], spec["revision"], type(exc).__name__))
    for name in CHECKED_FILES:
        if name in spec["base_hashes"] and _sha(path / name) != spec["base_hashes"][name]:
            raise CounterRefused("pinned file differs: " + name)
    return path


def _tokenizer():
    if "tok" not in _STATE:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        path = snapshot()
        from transformers import AutoTokenizer
        _STATE["tok"] = AutoTokenizer.from_pretrained(str(path), local_files_only=True,
                                                      trust_remote_code=False)
        _STATE["path"] = path
    return _STATE["tok"]


def count(text: str) -> int:
    return len(_tokenizer()(text, add_special_tokens=False)["input_ids"])


def count_prompt(system: str, user: str) -> int:
    tok = _tokenizer()
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    rendered = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    return len(tok(rendered, add_special_tokens=False)["input_ids"])


def model_dimensions(spec=None) -> dict:
    """The model's dimensions from its own config.json (checked against its pin), and the
    size on disk of its 4-bit weights file (stat only; the file is never read)."""
    spec = spec or specification()
    path = snapshot(spec)
    config = json.loads((path / "config.json").read_text(encoding="utf-8"))
    quant = config.get("quantization_config") or {}
    weights = path / NOT_READ
    return {"model_id": spec["model_id"], "revision": spec["revision"],
            "num_hidden_layers": int(config["num_hidden_layers"]),
            "num_attention_heads": int(config["num_attention_heads"]),
            "num_key_value_heads": int(config["num_key_value_heads"]),
            "hidden_size": int(config["hidden_size"]),
            "intermediate_size": int(config["intermediate_size"]),
            "vocab_size": int(config["vocab_size"]),
            "max_position_embeddings": int(config["max_position_embeddings"]),
            "torch_dtype": config.get("torch_dtype"),
            "quant_type": quant.get("bnb_4bit_quant_type"),
            "weights_file_bytes": weights.stat().st_size if weights.exists() else None}
