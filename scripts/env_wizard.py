from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        print(".env file already exists. Skipping wizard.")
        sys.exit(0)

    print("=" * 50)
    print("  ED Capital Quant Engine - Environment Wizard")
    print("=" * 50)
    print("Leave Telegram fields blank to run in offline notification mode.\n")

    bot_token = input("1. Telegram Bot Token (optional): ").strip()
    chat_id = input("2. Telegram Admin Chat ID (optional): ").strip()

    lines = []
    if bot_token:
        lines.append(f"TELEGRAM_BOT_TOKEN={bot_token}")
    if chat_id:
        lines.append(f"ADMIN_CHAT_ID={chat_id}")
    lines.append("ENVIRONMENT=production")

    try:
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("Successfully created .env file.")
    except Exception as exc:
        print(f"Error writing .env file: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
