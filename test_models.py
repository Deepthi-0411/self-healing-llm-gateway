from app.llm.models import (
    get_model_for_tier,
    get_fallback_model_for_tier,
)
from app.llm.tiering import ModelTier


def main():

    print("\n========== MODEL RESOLUTION TEST ==========\n")

    for tier in ModelTier:

        primary = get_model_for_tier(tier)

        fallback = get_fallback_model_for_tier(tier)

        print(
            f"{tier.value.upper()}"
        )

        print(
            f"  Primary  -> "
            f"Provider: {primary['provider']} | "
            f"Model: {primary['model']}"
        )

        print(
            f"  Fallback -> "
            f"Provider: {fallback['provider']} | "
            f"Model: {fallback['model']}"
        )

        print()

    print("============================================\n")


if __name__ == "__main__":
    main()