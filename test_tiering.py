from app.llm.tiering import (
    ModelTier,
    classify_request,
)


def run_test(
    description: str,
    messages: list[dict[str, str]]
):

    tier = classify_request(messages)

    print(
        f"{description} -> {tier.value}"
    )


def main():

    print("\n========== MODEL TIERING TEST ==========\n")

    run_test(
        "Simple question",
        [
            {
                "role": "user",
                "content": "What is Python?"
            }
        ]
    )

    run_test(
        "Normal technical question",
        [
            {
                "role": "user",
                "content": (
                    "Explain how Redis caching works "
                    "and compare it with an in-memory cache."
                )
            }
        ]
    )

    run_test(
        "Complex architecture question",
        [
            {
                "role": "user",
                "content": (
                    "Analyze this distributed architecture, "
                    "identify the root cause of failures, "
                    "design a fault-tolerant solution, "
                    "and optimize the system for scalability."
                )
            }
        ]
    )

    run_test(
        "Coding question",
        [
            {
                "role": "user",
                "content": (
                    "Debug this Python code and identify "
                    "the exception:\n"
                    "```python\n"
                    "def add(a, b):\n"
                    "    return a - b\n"
                    "```"
                )
            }
        ]
    )

    print("\n=========================================\n")


if __name__ == "__main__":
    main()