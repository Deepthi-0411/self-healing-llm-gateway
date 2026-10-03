from app.gateway.request_logger import redact_pii


def main():
    print("\n=========================================")
    print("PII REDACTION TEST")
    print("=========================================\n")

    test_cases = [
        (
            "Email",
            "Contact john.doe@example.com for help.",
            "[REDACTED_EMAIL]",
        ),
        (
            "Phone",
            "Call +91 98765 43210.",
            "[REDACTED_PHONE]",
        ),
        (
            "IPv4",
            "Client connected from 192.168.1.100.",
            "[REDACTED_IP]",
        ),
        (
            "Bearer token",
            "Authorization: Bearer abc123secretvalue",
            "Bearer [REDACTED]",
        ),
        (
            "JWT",
            "Token: eyJhbGciOiJIUzI1NiJ9.abc.def",
            "[REDACTED_JWT]",
        ),
        (
            "Gemini API key",
            "Key: AIzaSyExampleSecretKey123",
            "[REDACTED_GEMINI_API_KEY]",
        ),
        (
            "Credit card",
            "Payment card 4111 1111 1111 1111",
            "[REDACTED_CARD]",
        ),
    ]

    all_passed = True

    # ========================================================
    # STRING REDACTION TESTS
    # ========================================================

    for name, original, expected in test_cases:

        redacted = redact_pii(original)

        passed = expected in redacted

        print(
            f"[TEST] {name}: "
            f"{'PASS' if passed else 'FAIL'}"
        )

        print(
            f"       Original: {original}"
        )

        print(
            f"       Result:   {redacted}"
        )

        if not passed:
            all_passed = False

        print()

    # ========================================================
    # ACTIVE PROVIDER SECRET FIELD TEST
    # ========================================================

    secret_payload = {
        "gemini_api_key": "AIzaSyExampleSecret",
        "cloudflare_api_token": "cloudflare-secret-value",
        "cohere_api_key": "cohere-secret-value",
        "normal_field": "this is safe",
    }

    redacted_payload = redact_pii(
        secret_payload
    )

    secret_tests = [
        (
            "Gemini secret field",
            redacted_payload["gemini_api_key"],
        ),
        (
            "Cloudflare secret field",
            redacted_payload["cloudflare_api_token"],
        ),
        (
            "Cohere secret field",
            redacted_payload["cohere_api_key"],
        ),
    ]

    for name, result in secret_tests:

        passed = result == "[REDACTED_SECRET]"

        print(
            f"[TEST] {name}: "
            f"{'PASS' if passed else 'FAIL'}"
        )

        print(
            f"       Result: {result}"
        )

        if not passed:
            all_passed = False

        print()

    # ========================================================
    # NORMAL DATA SHOULD REMAIN
    # ========================================================

    normal_payload = {
        "tenant": "learning-platform",
        "feature": "ai-tutor",
        "request_id": "req-001",
        "model": "auto",
    }

    redacted_normal = redact_pii(
        normal_payload
    )

    normal_test_passed = (
        redacted_normal == normal_payload
    )

    print(
        "[TEST] Normal metadata preservation: "
        f"{'PASS' if normal_test_passed else 'FAIL'}"
    )

    print(
        f"       Result: {redacted_normal}"
    )

    if not normal_test_passed:
        all_passed = False

    print()

    # ========================================================
    # FINAL RESULT
    # ========================================================

    print("=========================================")

    if all_passed:
        print("PII REDACTION TEST: SUCCESS")
    else:
        print("PII REDACTION TEST: FAILED")

    print("=========================================\n")

    if not all_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()