import sys
from exchange.model import MarketOrder, COST_BASED_ORDER_EXCHANGES, STOCK_EXCHANGES
from exchange.utility import settings
from datetime import datetime, timedelta
from dhooks import Webhook, Embed
from loguru import logger
from devtools import debug, pformat
from telegram import Bot, OrderInfo
import telepot
import traceback
import os
from dotenv import load_dotenv

env_path = '/root/POA/.env'
load_dotenv(dotenv_path=env_path)

#telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
#telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
##telegram_bot_token = '6693212261:AAGu0pIV_yxxy_8qG8G4BWRLZTNkuTQqs9g'
##telegram_chat_id = '5794304967'
telegram_bot_token = '6446096063:AAEy8lNyEU6NtrDJpnM89_cNq9_7-gzLzXA'
telegram_chat_id = '1709556958'

telegram_bot = telepot.Bot(telegram_bot_token)

use_discord = 'TRUE'
use_telegram = 'TRUE'
entry_prices = {}

print(f"use_discord is set to {use_discord}")
print(f"use_telegram is set to {use_telegram}")


def send_telegram_message(message):
    if use_telegram:
        try:
            telegram_bot.sendMessage(chat_id=telegram_chat_id, text=message)
            print(f"Debug - Successfully sent message to Telegram: {message}")
        except Exception as e:
            print(f"Debug - Failed to send message to Telegram: {e}")
    else:
        pass

logger.remove(0)
logger.add(
    "./log/poa.log",
    rotation="1 days",
    retention="7 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)
logger.add(
    sys.stderr,
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <level>{message}</level>",
)

hook = None
if use_discord:
    try:
        url = settings.DISCORD_WEBHOOK_URL.replace("discordapp", "discord")
        hook = Webhook(url)
    except Exception as e:
        print("웹훅 URL이 유효하지 않습니다: ", settings.DISCORD_WEBHOOK_URL)


color_map = {
    "LONG" or "롱 진입": 0x0000FF,  # 파란색
    "SHORT" or "숏 진입": 0xFF0000,  # 빨간색
    "익절" or "롱 종료": 0x99ccff,  # 기본 색상
    "손절" or "숏 종료": 0x99ccff,  # 기본 색상
    "매수": 0x99ccff,    # 기본 색상
    "매도": 0x99ccff     # 기본 색상
}


def get_error(e):
    tb = traceback.extract_tb(e.__traceback__)
    target_folder = os.path.abspath(os.path.dirname(tb[0].filename))
    error_msg = []

    for tb_info in tb:
        # if target_folder in tb_info.filename:
        error_msg.append(f"File {tb_info.filename}, line {tb_info.lineno}, in {tb_info.name}")
        if "raise error." in tb_info.line:
            continue
        error_msg.append(f"  {tb_info.line}")

    error_msg.append(str(e))

    return "\n".join(error_msg)


def parse_time(utc_timestamp):
    timestamp = utc_timestamp + timedelta(hours=9).seconds
    date = datetime.fromtimestamp(timestamp)
    return date.strftime("%y-%m-%d %H:%M:%S")


def logger_test():
    date = parse_time(datetime.utcnow().timestamp())
    logger.info(date)


def log_message(message="None", embed: Embed = None):
    if use_discord:
        if hook:
            if embed:
                hook.send(embed=embed)
            else:
                hook.send(message)
        else:
            logger.info(message)
            print(message)


def log_order_message(exchange_name, order_result: dict, order_info: MarketOrder):
    global last_leverage  
    date = parse_time(datetime.utcnow().timestamp())
    if not order_info.is_futures and order_info.is_buy and exchange_name in COST_BASED_ORDER_EXCHANGES:
        f_name = "비용"
        if order_info.amount is not None:
            if exchange_name == "UPBIT":
                amount = str(order_result.get("cost"))
            elif exchange_name == "BITGET":
                amount = str(order_info.amount * order_info.price)
            elif exchange_name == "BYBIT":
                amount = str(order_result.get("info").get("orderQty"))
        elif order_info.percent is not None:
            f_name = "비율"
            amount = f"{order_info.percent}%"

    else:
        f_name = "수량"
        amount = None
        if exchange_name in ("KRX", "NASDAQ", "AMEX", "NYSE"):
            if order_info.amount is not None:
                amount = str(order_info.amount)
            elif order_info.percent is not None:
                f_name = "비율"
                amount = f"{order_info.percent}%"
        elif order_result.get("amount") is None:
            if order_info.amount is not None:
                if exchange_name == "OKX":
                    if order_info.is_futures:
                        f_name = "계약(수량)"
                        amount = f"{order_info.amount // order_info.contract_size}({order_info.contract_size * (order_info.amount // order_info.contract_size)})"
                    else:
                        amount = f"{order_info.amount}"
                else:
                    amount = str(order_info.amount)
            elif order_info.percent is not None:
                if order_info.amount_by_percent is not None:
                    f_name = "비율(수량)" if order_info.is_contract is None else "비율(계약)"
                    amount = f"{order_info.percent}%({order_info.amount_by_percent})"
                else:
                    f_name = "비율"
                    amount = f"{order_info.percent}%"
        elif order_result.get("amount") is not None:
            if order_info.contract_size is not None:
                f_name = "계약"
                if order_result.get("cost") is not None:
                    f_name = "계약(비용)"
                    amount = f"{order_result.get('amount')}({order_result.get('cost'):.2f})"
                else:
                    amount = f"{order_result.get('amount')}"
            else:
                if order_info.amount is not None:
                    f_name = "수량"
                    amount = f"{order_result.get('amount')}"
                elif order_info.percent is not None:
                    f_name = "비율(수량)" if order_info.is_contract is None else "비율(계약)"
                    amount = f"{order_info.percent}%({order_result.get('amount')})"

    symbol = f"{order_info.base}/{order_info.quote+'.P' if order_info.is_crypto and order_info.is_futures else order_info.quote}"

    side = ""
    side_emoji = ""
    if order_info.leverage is not None:
        last_leverage = order_info.leverage

    if order_info.is_futures:
        if order_info.is_entry:
            side = "LONG" if order_info.is_buy else "SHORT"
            side_emoji = "🟢" if order_info.is_buy else "🔴"
        else:
            side = "종료"
            side_emoji = "❗️"
    else:
        if order_info.is_buy or order_info.is_sell:
            side = "매수" if order_info.is_buy else "매도"
            side_emoji = "🟢" if order_info.is_buy else "🔴"
            entry_prices[symbol] = order_info.price
    lv_part = f"\n 레버리지 : {last_leverage}배" if last_leverage is not None else ""

    content = f"{side_emoji} {symbol} [ {side} ] \n 체결가 : {round(order_info.price, 5)}"
    content += f"\n 포지션크기 : {order_info.amount} "
    content += lv_part
    #if not order_info.is_entry:
    #    content += f"\n 종료가격 : ${round(order_info.price, 3)}"
    content += f"\n 거래소 : {exchange_name}"
    content += f"\n 시간 : {date}"

    embed = Embed(
        title=order_info.order_name,
        description=content,
        color=color_map.get(side, 0x99ccff),
    )

    log_message(content, embed)
    send_telegram_message(content)


def log_hedge_message(exchange, base, quote, exchange_amount, upbit_amount, hedge):
    date = parse_time(datetime.utcnow().timestamp())
    hedge_type = "헷지" if hedge == "ON" else "헷지 종료"
    content = f"{hedge_type}: {base} ==> {exchange}:{exchange_amount} UPBIT:{upbit_amount}"
    embed = Embed(title="헷지", description=content, color=0x0000FF)
    embed.add_field(name="일시", value=str(date), inline=False)
    embed.add_field(name="거래소", value=f"{exchange}-UPBIT", inline=False)
    embed.add_field(name="심볼", value=f"{base}/{quote}-{base}/KRW", inline=False)
    embed.add_field(name="거래유형", value=hedge_type, inline=False)
    embed.add_field(
        name="수량",
        value=f"{exchange}:{exchange_amount} UPBIT:{upbit_amount}",
        inline=False,
    )
    log_message(content, embed)


def log_error_message(error, name):
    embed = Embed(title=f"{name} 에러", description=f"[{name} 에러가 발생했습니다]\n{error}", color=0xFF0000)
    logger.error(f"{name} [에러가 발생했습니다]\n{error}")
    log_message(embed=embed)


def log_order_error_message(error: str | Exception, order_info: MarketOrder):
    if isinstance(error, Exception):
        error = get_error(error)

    if order_info is not None:
        # discord
        embed = Embed(
            title=order_info.order_name,
            description=f"[주문 오류가 발생했습니다]\n{error}",
            color=0xFF0000,
        )
        log_message(embed=embed)

        # logger
        logger.error(f"[주문 오류가 발생했습니다]\n{error}")
    else:
        # discord
        embed = Embed(
            title="오류",
            description=f"[오류가 발생했습니다]\n{error}",
            color=0xFF0000,
        )
        log_message(embed=embed)

        # logger
        logger.error(f"[오류가 발생했습니다]\n{error}")


def log_validation_error_message(msg):
    logger.error(f"검증 오류가 발생했습니다\n{msg}")
    log_message(msg)


def print_alert_message(order_info: MarketOrder, result="성공"):
    msg = pformat(order_info.dict(exclude_none=True))

    if result == "성공":
        logger.info(f"주문 {result} 웹훅메세지\n{msg}")
    else:
        logger.error(f"주문 {result} 웹훅메세지\n{msg}")


def log_alert_message(order_info: MarketOrder, result="성공"):
    # discrod
    embed = Embed(
        title=order_info.order_name,
        description="[웹훅 alert_message]",
        color=0xFF0000,
    )
    order_info_dict = order_info.dict(exclude_none=True)
    for key, value in order_info_dict.items():
        embed.add_field(name=key, value=str(value), inline=False)
    log_message(embed=embed)

    # logger
    print_alert_message(order_info, result)
