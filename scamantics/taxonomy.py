"""Fixed tactic taxonomy used for classification, prompting, highlighting and evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Tactic:
    label: str
    name: str
    definition: str
    examples: tuple[str, ...]
    color: str
    advice: str
    extra: dict = field(default_factory=dict)


TACTICS: tuple[Tactic, ...] = (
    Tactic(
        label="urgency",
        name="Urgency",
        definition=(
            "Pressures the reader to act immediately, with deadlines, countdowns or warnings "
            "that delay will cause loss, so they do not stop to think or verify."
        ),
        examples=(
            "Your account will be suspended within 24 hours unless you verify now.",
            "Only 2 hours left to claim this before it expires!",
        ),
        color="#f97316",
        advice="Real organisations rarely demand action within minutes. Slow down and verify first.",
    ),
    Tactic(
        label="impersonation",
        name="Impersonation / Authority",
        definition=(
            "Claims to be, or borrows the authority of, a trusted organisation, official body, "
            "well-known company, or a person the reader knows, to make the request seem legitimate."
        ),
        examples=(
            "This is the IRS. A warrant has been issued in your name.",
            "Hi Mum, it's me, I lost my phone, this is my new number.",
        ),
        color="#3b82f6",
        advice="Contact the organisation or person through a number or website you already trust, not one in the message.",
    ),
    Tactic(
        label="isolation",
        name="Isolation / Secrecy",
        definition=(
            "Asks the reader to keep the matter private, not tell family, friends, their bank or "
            "the police, or to communicate only through a specific channel, cutting off outside advice."
        ),
        examples=(
            "Do not discuss this with anyone, including bank staff, as they may be involved.",
            "Keep this between us for now.",
        ),
        color="#a855f7",
        advice="Secrecy benefits the sender, not you. Talk to someone you trust before doing anything.",
    ),
    Tactic(
        label="reward",
        name="Reward / Incentive",
        definition=(
            "Offers money, prizes, refunds, jobs, investment returns or other benefits that seem "
            "too good to be true, to motivate the reader to engage or pay a small fee first."
        ),
        examples=(
            "Congratulations! You have been selected to receive a $1,000 gift card.",
            "Guaranteed 30% monthly return with zero risk.",
        ),
        color="#22c55e",
        advice="Legitimate prizes and refunds never require an upfront payment or your card details.",
    ),
    Tactic(
        label="threat",
        name="Threat / Penalty",
        definition=(
            "Warns of arrest, fines, legal action, account closure, exposure of private material or "
            "other harm if the reader does not comply."
        ),
        examples=(
            "Failure to pay will result in your immediate arrest.",
            "We will release your private videos to all your contacts.",
        ),
        color="#ef4444",
        advice="Threats are designed to cause panic. Authorities do not demand payment or threaten arrest by text message.",
    ),
)

LABELS: tuple[str, ...] = tuple(t.label for t in TACTICS)
TACTIC_BY_LABEL: dict[str, Tactic] = {t.label: t for t in TACTICS}
COLOR_MAP: dict[str, str] = {t.label: t.color for t in TACTICS}

# Accept common alternative spellings coming back from an LLM and map them to canonical labels.
_ALIASES: dict[str, str] = {
    "urgency": "urgency",
    "urgent": "urgency",
    "time pressure": "urgency",
    "scarcity": "urgency",
    "impersonation": "impersonation",
    "authority": "impersonation",
    "impersonation or authority": "impersonation",
    "impersonation/authority": "impersonation",
    "impersonation / authority": "impersonation",
    "isolation": "isolation",
    "secrecy": "isolation",
    "isolation or secrecy": "isolation",
    "isolation/secrecy": "isolation",
    "isolation / secrecy": "isolation",
    "reward": "reward",
    "incentive": "reward",
    "reward or incentive": "reward",
    "reward/incentive": "reward",
    "reward / incentive": "reward",
    "threat": "threat",
    "penalty": "threat",
    "threat or penalty": "threat",
    "threat/penalty": "threat",
    "threat / penalty": "threat",
    "intimidation": "threat",
}


def normalise_label(raw: str) -> str | None:
    """Map a free-form label string to a canonical taxonomy label, or None if unknown."""
    key = raw.strip().lower().replace("_", " ").replace("-", " ")
    key = " ".join(key.split())
    return _ALIASES.get(key)
