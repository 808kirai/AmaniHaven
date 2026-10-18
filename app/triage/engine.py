from app.config import get_settings
from app.triage import llm
from app.triage.rules import assess, tier_rank, triage_result

# rules first, then claude as a second opinion that can only raise the tier


def combine(rules, model):
    # merges the two verdicts, the higher tier wins and a tie keeps the rules
    if model is None:
        return rules
    raised = tier_rank[model.tier] > tier_rank[rules.tier]
    tier = model.tier if raised else rules.tier
    return triage_result(
        tier=tier,
        topics=sorted(set(rules.topics) | set(model.topics)),
        signals=rules.signals,
        ask_safety_question=tier != "crisis" and (rules.ask_safety_question or model.ask_safety_question),
        reason=(model.reason if raised else rules.reason) or model.reason,
        source="rules+llm" if raised else "rules",
    )


async def triage(text, history):
    rules = assess(text)
    # crisis is already the top tier, so there is nothing for the model to add
    if rules.tier == "crisis" or not get_settings().llm_enabled:
        return rules
    return combine(rules, await llm.classify(text, history))
