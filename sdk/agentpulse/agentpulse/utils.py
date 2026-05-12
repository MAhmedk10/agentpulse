MODEL_PRICING = {
    "gpt-4o":                          (0.0025,   0.01),
    "gpt-4o-mini":                     (0.00015,  0.0006),
    "claude-sonnet-4":                 (0.003,    0.015),
    "claude-haiku":                    (0.00025,  0.00125),
    "meta-llama/llama-3.3-70b-instruct:free": (0.0, 0.0),
    "openai/gpt-oss-20b:free":         (0.0,      0.0),
}

def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    p = MODEL_PRICING.get(model, (0.001, 0.002))
    return round((input_tokens / 1000) * p[0] + (output_tokens / 1000) * p[1], 8)