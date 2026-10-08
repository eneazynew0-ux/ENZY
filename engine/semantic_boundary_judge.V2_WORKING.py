import json

from mlx_lm import generate

from engine.semantic_boundary_validator import build_boundary_context


SYSTEM_PROMPT = """
You are a conservative Semantic Visual Boundary Judge.

You receive ONLY immutable MASTER narration words immediately before and
after one proposed visual-beat boundary.

Your only task is to decide whether the proposed boundary represents a
real change in what should naturally be visible on screen.

APPROVE only when the narration genuinely changes one or more of:
- visible subject
- visible object
- visible action
- visible location
- visible state
- visible time/state of the same object
- concrete visual focus

REJECT when the boundary is caused only by:
- grammar
- punctuation
- conjunction
- rhetorical continuation
- emphasis
- negation
- comparison
- abstract commentary
- the same visual idea continuing naturally

Be conservative.
A new beat must materially improve synchronization between narration and picture.

CONTINUITY PRESUMPTION:
- Default to REJECT when the words on both sides continue describing the same visible subject or object.
- A change in wording is NOT a visual change.
- A new adjective, property, direction, material, location phrase, relative clause, or additional description of the same object is NOT enough for a new beat.
- Do not split one noun phrase, object description, action phrase, or tightly connected clause into separate visual beats.
- If the right side merely completes or specifies the meaning started on the left side, REJECT.
- APPROVE only when a viewer would naturally need a materially different shot because a genuinely new visible subject, object, action, location, time/state, or concrete visual focus begins.
- The burden of proof is on APPROVE. If uncertain, REJECT.
- Keep "reason" extremely short: maximum 12 words.
- Do not explain your reasoning step by step.
- Return the JSON object immediately and stop generating after it.

Example:
"church carved downward | into a single rock" = REJECT because both sides continue describing the same church.

Example:
"church carved into rock | pilgrims walk around it on their knees" = APPROVE because the visible focus changes from the church itself to people performing a new visible action.

Do not invent facts.
Do not use outside knowledge.
Do not infer Story Map information.
Do not move the boundary.
Do not propose another boundary.
Do not output timestamps.

Return JSON only:

{
  "approve": true,
  "reason": "brief explanation based only on MASTER words"
}
"""


def build_judge_prompt(
    scene,
    boundary_index,
    timed_words,
    radius=8,
):
    context = build_boundary_context(
        scene,
        boundary_index,
        timed_words,
        radius=radius,
    )

    return (
        SYSTEM_PROMPT
        + "\n\nMASTER BOUNDARY CONTEXT:\n"
        + json.dumps(context, ensure_ascii=False)
    )


def parse_judge_json(raw):
    if isinstance(raw, dict):
        data = raw
    else:
        text = str(raw).strip()

        if text.startswith("```"):
            text = text.replace("```json", "", 1)
            text = text.replace("```", "").strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            left = text.find("{")
            right = text.rfind("}")

            if left < 0 or right <= left:
                raise ValueError(
                    "SEMANTIC_BOUNDARY_JUDGE_INVALID_JSON"
                )

            try:
                data = json.loads(text[left:right + 1])
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "SEMANTIC_BOUNDARY_JUDGE_INVALID_JSON: "
                    + str(exc)
                ) from exc

    if not isinstance(data, dict):
        raise ValueError(
            "SEMANTIC_BOUNDARY_JUDGE_NOT_OBJECT"
        )

    if not isinstance(data.get("approve"), bool):
        raise ValueError(
            "SEMANTIC_BOUNDARY_JUDGE_MISSING_APPROVE"
        )

    return {
        "approve": data["approve"],
        "reason": str(data.get("reason", "")).strip(),
    }


def judge_semantic_boundary(
    scene,
    boundary_index,
    timed_words,
    model,
    tokenizer,
    radius=8,
    max_tokens=320,
):
    prompt = build_judge_prompt(
        scene,
        boundary_index,
        timed_words,
        radius=radius,
    )

    messages = [
        {
            "role": "user",
            "content": prompt,
        }
    ]

    formatted = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    raw = generate(
        model,
        tokenizer,
        prompt=formatted,
        max_tokens=max_tokens,
        verbose=False,
    )

    decision = parse_judge_json(raw)

    return {
        "boundary_index": int(boundary_index),
        "approve": decision["approve"],
        "reason": decision["reason"],
        "raw": raw,
    }
