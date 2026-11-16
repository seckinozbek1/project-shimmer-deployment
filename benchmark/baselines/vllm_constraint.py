"""The DECODING-B constraint as a vLLM logits processor (#217, D-598 to D-601; a measurement only).

vLLM's Model Runner V2 calls one processor for the whole batch. This class keeps, per request
slot, the very `contract_decoding.ContractProcessor` a transformers call uses, built by
`contract_decoding.for_prompt` from the request's own rendered prompt (the compact producer's
declaration read back from its payload, or a declared envelope agent's contract). Each step it
gives that processor the request's generated token ids and its one logits row, and writes the
masked row back. The mask, the stop-token rule and the counts are the processor's own; nothing
here decides which token is admitted.

A request opts in with `SamplingParams.extra_args["shimmer_constraint"]`:
    {"prompt": <rendered prompt>, "agent": <envelope agent or None>, "prompt_tokens": <int>,
     "eos": [<stop ids>], "key": <request key>}
and the counts of every constrained request are kept in `COUNTS[key]` (this process), which
the child reads after generation (vllm_child.py).

The generated ids are followed from the step layout alone: a row whose position is before the
prompt's last token is a partial prefill row and is left as it is; at the prompt's last token
the reply is empty; each later step adds the token fed at that row (the token sampled the step
before). A row that does not fit that sequence (a resumed request) is matched against the ids
already held; anything else raises, never guesses.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parents[1] / "scripts"
for _p in (str(SCRIPTS), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import os

# The child sets this in the auxiliary environment: there, vLLM's MRV2 interface must import, and
# a failure raises (no stand-in is ever used on the instance). The laptop's proofs run without vLLM.
IN_CHILD = "VLLM_REPLAY_CHILD"
try:
    from vllm.v1.worker.gpu.sample.logits_processor import LogitsProcessor as _Base
except ImportError:
    if os.environ.get(IN_CHILD) == "1":
        raise
    class _Base:  # noqa: D401 - the laptop's stand-in, with the same constructor
        def __init__(self, vllm_config=None, req_states=None):
            pass

KEY = "shimmer_constraint"
COUNTS = {}
_TOKENIZERS = {}


def table_digest(tok):
    """The digest of the token table contract_decoding builds from a tokenizer: each token's text
    as it extends a reply. The runner's and the child's must be equal, or the constraint would
    read the reply differently in the two engines."""
    import hashlib
    import json
    import contract_decoding
    table = contract_decoding.TokenTable.of(tok)
    return hashlib.sha256(json.dumps([table.size, table.strings], ensure_ascii=False).encode("utf-8")).hexdigest()


def tokenizer(path):
    """One tokenizer per model path, loaded once from the local files only."""
    found = _TOKENIZERS.get(path)
    if found is None:
        from transformers import AutoTokenizer
        found = _TOKENIZERS[path] = AutoTokenizer.from_pretrained(path, local_files_only=True)
    return found


class Slot:
    """One constrained request: its processor and the reply's ids so far."""

    def __init__(self, args, tok):
        import contract_decoding
        self.key = args["key"]
        self.prompt_tokens = int(args["prompt_tokens"])
        self.ids = []
        self.started = False
        eos = [int(e) for e in args["eos"]]
        if args.get("agent") is not None and args.get("contract"):
            # The runner's own contract for this agent (the wrapper's, carried in the request), so both
            # engines build the very same envelope grammar (D-630 A4).
            self.constraint = contract_decoding.envelope_constraint(args["agent"], tok, 0, eos, "rendered_prompt",
                                                                    args["contract"])
        else:
            self.constraint = contract_decoding.for_prompt(args["prompt"], tok, 0, eos, agent=args.get("agent"))
        COUNTS[self.key] = self.constraint.record

    def follow(self, position, fed):
        """The reply's ids at this row, or None for a row whose logits vLLM does not sample: a
        partial prefill row, or, for a request resumed after preemption (vLLM recomputes the
        prompt and the reply so far), a row inside that recomputation. vLLM 0.33's sampler gives
        each logits row the position and the input token of the row's last fed token
        (`input_batch.positions[logits_indices]`, `input_batch.input_ids[logits_indices]`)."""
        generated = int(position) + 1 - self.prompt_tokens
        if generated == 0 and not self.started:
            self.started = True          # the prompt's last token: the reply's first step
            return self.ids
        if generated == len(self.ids) + 1 and self.started:
            self.ids.append(int(fed))    # each later step: the token sampled the step before
            return self.ids
        if generated <= len(self.ids):
            return None                  # a partial prefill row, or a row of a resumed request's recomputation
        raise RuntimeError("constraint lost its request's ids: %d held, %d at this row" % (len(self.ids), generated))


class ShimmerConstraint(_Base):
    """vLLM MRV2 custom logits processor carrying the per-request ContractProcessor."""

    tokenizer_path = None   # set by the child before the engine starts (an env var in the engine process)

    def __init__(self, vllm_config=None, req_states=None):
        super().__init__(vllm_config, req_states)
        import os
        self.path = os.environ.get("SHIMMER_CONSTRAINT_TOKENIZER") or self.tokenizer_path
        self.slots = {}
        self.by_key = {}

    @classmethod
    def validate_params(cls, sampling_params):
        args = (getattr(sampling_params, "extra_args", None) or {}).get(KEY)
        if args is not None and not {"prompt", "prompt_tokens", "eos", "key"} <= set(args):
            raise ValueError("a shimmer constraint names its prompt, prompt tokens, stop ids and key")

    def add_request(self, req_idx, sampling_params):
        """A request entering the batch. Under Model Runner V2 a preempted request comes back here,
        perhaps in another slot: it keeps its own Slot, found by its key, so the reply's ids and
        the counts carry on, and the rows of its recomputation are left alone (Slot.follow)."""
        args = (getattr(sampling_params, "extra_args", None) or {}).get(KEY)
        if args is None:
            self.slots[int(req_idx)] = None
            return False
        slot = self.by_key.get(args["key"])
        if slot is None:
            slot = self.by_key[args["key"]] = Slot(args, tokenizer(self.path))
        self.slots[int(req_idx)] = slot
        return True

    def is_argmax_invariant(self):   # the legacy interface's question: this processor changes the argmax
        return False

    def apply(self, logits, ctx):
        import torch
        rows = ctx.expanded_idx_mapping.tolist()
        if not any(self.slots.get(int(s)) is not None for s in rows):
            return logits
        positions = ctx.pos.tolist()
        fed = ctx.input_ids.tolist()
        for row, slot_index in enumerate(rows):
            slot = self.slots.get(int(slot_index))
            if slot is None:
                continue
            ids = slot.follow(positions[row], fed[row])
            if ids is None:
                continue
            masked = slot.constraint.processor(torch.tensor([ids], dtype=torch.long), logits[row:row + 1])
            logits[row] = masked[0]
        return logits
