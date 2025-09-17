"""
Token Masking Utility - Säker hantering av JWT-tokens i loggar

KRITISKT: Denna modul förhindrar att JWT-tokens exponeras i loggar eller konsol.
"""

import re
from typing import Any, Dict, List, Union


def mask_token(token: str | None) -> str:
    """
    Maskera JWT-token för säker loggning.

    Args:
        token: JWT-token att maskera

    Returns:
        Maskerad token (första 8 tecken + "***masked***")
    """
    if not token or not isinstance(token, str):
        return "***no_token***"

    # JWT-tokens börjar med "eyJ" och är minst 20 tecken
    if len(token) < 20 or not token.startswith("eyJ"):
        return "***invalid_token***"

    # Visa första 8 tecken + maskerad rest
    return f"{token[:8]}***masked***"


def mask_tokens_in_dict(data: dict[str, Any]) -> dict[str, Any]:
    """
    Maskera alla tokens i en dictionary rekursivt.

    Args:
        data: Dictionary som kan innehålla tokens

    Returns:
        Dictionary med maskerade tokens
    """
    if not isinstance(data, dict):
        return data

    masked_data = {}
    for key, value in data.items():
        if isinstance(value, str) and _is_jwt_token(value):
            masked_data[key] = mask_token(value)
        elif isinstance(value, dict):
            masked_data[key] = mask_tokens_in_dict(value)
        elif isinstance(value, list):
            masked_data[key] = mask_tokens_in_list(value)
        else:
            masked_data[key] = value

    return masked_data


def mask_tokens_in_list(data: list[Any]) -> list[Any]:
    """
    Maskera alla tokens i en lista rekursivt.

    Args:
        data: Lista som kan innehålla tokens

    Returns:
        Lista med maskerade tokens
    """
    if not isinstance(data, list):
        return data

    masked_list = []
    for item in data:
        if isinstance(item, str) and _is_jwt_token(item):
            masked_list.append(mask_token(item))
        elif isinstance(item, dict):
            masked_list.append(mask_tokens_in_dict(item))
        elif isinstance(item, list):
            masked_list.append(mask_tokens_in_list(item))
        else:
            masked_list.append(item)

    return masked_list


def mask_tokens_in_string(text: str) -> str:
    """
    Maskera alla JWT-tokens i en sträng.

    Args:
        text: Text som kan innehålla tokens

    Returns:
        Text med maskerade tokens
    """
    if not isinstance(text, str):
        return str(text)

    # Regex för JWT-tokens (eyJ + base64-encoded data)
    jwt_pattern = r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"

    def replace_token(match):
        token = match.group(0)
        return mask_token(token)

    return re.sub(jwt_pattern, replace_token, text)


def _is_jwt_token(value: str) -> bool:
    """
    Kontrollera om en sträng är en JWT-token.

    Args:
        value: Sträng att kontrollera

    Returns:
        True om det är en JWT-token
    """
    if not isinstance(value, str) or len(value) < 20:
        return False

    # JWT-tokens börjar med "eyJ" och har 3 delar separerade med "."
    return value.startswith("eyJ") and value.count(".") == 2


def safe_log_data(data: Any, message: str = "") -> str:
    """
    Säker loggning av data med automatisk token-masking.

    Args:
        data: Data att logga
        message: Meddelande att inkludera

    Returns:
        Säker sträng för loggning
    """
    if isinstance(data, dict):
        masked_data = mask_tokens_in_dict(data)
        data_str = str(masked_data)
    elif isinstance(data, list):
        masked_data = mask_tokens_in_list(data)
        data_str = str(masked_data)
    elif isinstance(data, str):
        data_str = mask_tokens_in_string(data)
    else:
        data_str = str(data)

    if message:
        return f"{message}: {data_str}"
    else:
        return data_str


# Exempel på användning:
if __name__ == "__main__":
    # Test token-masking
    test_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJmcm9udGVuZF91c2VyIiwic2NvcGUiOiJyZWFkIiwidHlwZSI6ImFjY2VzcyIsImp0aSI6IjAyNTM2Yzk1LWZkODMtNGQ3NS05ZTYzLTViZjVkNzAxNGIyMyIsImlhdCI6MTc1NzQwODc3OCwiZXhwIjoxNzU3NDEyMzc4fQ.Ww1tueGu"  # nosec B105: test token for masking demo

    print(f"Original token: {test_token}")
    print(f"Masked token: {mask_token(test_token)}")

    # Test i dictionary
    test_data = {
        "user_id": "test_user",
        "access_token": test_token,
        "nested": {"token": test_token, "other_data": "safe"},
    }

    print(f"Original data: {test_data}")
    print(f"Masked data: {mask_tokens_in_dict(test_data)}")
