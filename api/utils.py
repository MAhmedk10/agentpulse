import re

# Pricing per 1K tokens: (input_price, output_price) in USD
MODEL_PRICING = {
    "google/gemini-flash-1.5":        (0.000075, 0.0003),
    "google/gemini-pro-1.5":          (0.00125,  0.005),
    "openai/gpt-4o":                  (0.0025,   0.010),
    "openai/gpt-4o-mini":             (0.00015,  0.0006),
    "anthropic/claude-3-haiku":       (0.00025,  0.00125),
    "anthropic/claude-3.5-sonnet":    (0.003,    0.015),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = MODEL_PRICING.get(model, (0.001, 0.002))
    cost = (input_tokens / 1000 * pricing[0]) + (output_tokens / 1000 * pricing[1])
    return round(cost, 6)


def redact_pii(text: str) -> str:
    if not text:
        return text
    # Remove emails
    text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]", text)
    # Remove phone numbers
    text = re.sub(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", "[PHONE]", text)
    # Remove passwords/tokens in key=value format
    text = re.sub(r"(?i)(password|secret|token|api_key)\s*[:=]\s*\S+", "[REDACTED]", text)
    return text