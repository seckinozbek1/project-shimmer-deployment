"""One rule for what may stand as a claim figure: never a steering check run on the subscription
(D-S104 item 1).

A steering check of the cloud reference runs on the Claude subscription through headless Claude
Code (`cloud_reference_steering.py`). Every file it writes carries `STEERING_LABEL` and
`"claim": false`. Anything that turns runs into figures for a claim, on the page or in the report,
calls `refuse_claim` on what it reads; it raises when the label stands anywhere in it, however deep.
Its figures may be read for steering only, under the label, through `steering_view`.
"""

STEERING_LABEL = "subscription, steering only"
STEERING_KIND = "cloud-reference-steering"


class SteeringNotAClaim(ValueError):
    """A steering check offered where a claim figure is read."""


def is_steering(value):
    """True when the steering label, the steering kind or `claim: false` stands anywhere in
    `value` (dicts and lists walked; strings compared whole)."""
    if isinstance(value, dict):
        if value.get("claim") is False or value.get("kind") == STEERING_KIND or value.get("label") == STEERING_LABEL:
            return True
        return any(is_steering(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(is_steering(v) for v in value)
    return value == STEERING_LABEL


def refuse_claim(value, where="a claim figure"):
    """Raise when `value` is or holds a steering check; return it unchanged otherwise."""
    if is_steering(value):
        raise SteeringNotAClaim("A subscription steering check is never %s (D-S104 item 1)" % where)
    return value


def steering_view(result):
    """A steering pass's figures, stamped so no later reader can take them for a claim."""
    return dict(result, label=STEERING_LABEL, kind=STEERING_KIND, claim=False,
                note="steering only: never on the page, in the report or in any claim (D-S104 item 1)")
