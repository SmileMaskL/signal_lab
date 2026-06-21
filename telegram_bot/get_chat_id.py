"""Telegram Bot Chat ID 조회 유틸리티.

봇에게 메시지를 보내면 Chat ID를 콘솔과 Telegram 채팅창에 출력합니다.
개인 채팅, 그룹, 슈퍼그룹, 채널(봇이 관리자인 경우) 모두 지원합니다.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def _resolve_token(cli_token: str | None) -> str:
    token = cli_token or os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print(
            "오류: Bot Token이 필요합니다.\n"
            "  1) .env 파일에 TELEGRAM_TOKEN=your_token 설정\n"
            "  2) python telegram/get_chat_id.py --token your_token",
            file=sys.stderr,
        )
        sys.exit(1)
    return token


def _format_chat_info(update: Update) -> str:
    chat = update.effective_chat
    user = update.effective_user

    lines = [
        "Chat ID 정보",
        f"Chat ID: {chat.id}",
        f"Chat Type: {chat.type}",
    ]
    if chat.title:
        lines.append(f"Chat Title: {chat.title}")
    if chat.username:
        lines.append(f"Chat Username: @{chat.username}")
    if user:
        lines.append(f"User ID: {user.id}")
        display_name = user.full_name or user.username or "Unknown"
        lines.append(f"User: {display_name}")
        if user.username:
            lines.append(f"Username: @{user.username}")

    return "\n".join(lines)


async def _send_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.effective_message is None:
        return

    info = _format_chat_info(update)
    logger.info(info.replace("\n", " | "))
    await update.effective_message.reply_text(info)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "안녕하세요! Chat ID 조회 봇입니다.\n\n"
        "아무 메시지를 보내거나 /chatid 를 입력하면 Chat ID를 알려드립니다.\n\n"
        "그룹 Chat ID가 필요하면:\n"
        "1) 봇을 그룹에 추가\n"
        "2) 그룹에서 메시지 전송 (또는 /chatid)\n"
        "3) Privacy Mode가 켜져 있으면 @BotFather 에서 /setprivacy → Disable"
    )
    await _send_chat_id(update, context)


async def cmd_chatid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_chat_id(update, context)


def main() -> None:
    parser = argparse.ArgumentParser(description="Telegram Bot Chat ID 조회")
    parser.add_argument(
        "--token",
        help="Telegram Bot Token (.env의 TELEGRAM_BOT_TOKEN 대신 사용)",
    )
    args = parser.parse_args()

    token = _resolve_token(args.token)

    print("봇을 시작합니다. Telegram에서 봇에게 메시지를 보내세요.")
    print("종료: Ctrl+C\n")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("chatid", cmd_chatid))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, _send_chat_id))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
