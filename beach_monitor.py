#!/usr/bin/env python3
"""
Monitor della disponibilità della spiaggia La Pelosa (Stintino).

Controlla periodicamente la pagina delle prenotazioni e, quando compaiono
posti disponibili, invia un messaggio su Telegram.

Pensato per girare 24/7 su un Raspberry Pi. Usa solo `requests` come
dipendenza esterna, così resta leggero.

Configurazione tramite variabili d'ambiente (vedi README / file .env):

  TELEGRAM_BOT_TOKEN   (obbligatorio)  token del bot creato con @BotFather
  TELEGRAM_CHAT_ID     (obbligatorio)  id della chat a cui inviare i messaggi
  BEACH_URL            url da controllare (default: La Pelosa, lang=it)
  CHECK_INTERVAL       secondi tra un controllo e l'altro (default: 120)
  WATCH_DATES          date da monitorare separate da virgola, es "15/07/2026,16/07/2026"
                       (vuoto = tutte le date mostrate nella pagina)
  MIN_SPOTS            posti minimi per far scattare l'avviso (default: 1)
  STATE_FILE           file dove salvare lo stato (default: ./state.json)
"""

import os
import re
import sys
import json
import time
import random
import logging
from datetime import datetime

import requests

# --------------------------------------------------------------------------- #
# Configurazione
# --------------------------------------------------------------------------- #

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
BEACH_URL = os.environ.get(
    "BEACH_URL", "https://app.stintinospiagge.it/prenotazioni/1/1?lang=it"
).strip()
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "120"))
MIN_SPOTS = int(os.environ.get("MIN_SPOTS", "1"))
STATE_FILE = os.environ.get("STATE_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json"))

# date da monitorare: vuoto = tutte
_watch = os.environ.get("WATCH_DATES", "").strip()
WATCH_DATES = {d.strip() for d in _watch.split(",") if d.strip()} if _watch else set()

# Ogni quante ore ripetere l'avviso se una data resta disponibile a lungo
REMIND_AFTER_HOURS = float(os.environ.get("REMIND_AFTER_HOURS", "6"))

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("beach")

# --------------------------------------------------------------------------- #
# Parsing della pagina
# --------------------------------------------------------------------------- #

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# weekday(opzionale) DD/MM  YYYY  N posti attualmente disponibili
_AVAIL_RE = re.compile(
    r"([A-Za-zàèéìòùÀÈÉÌÒÙ]+)?\s*"
    r"(\d{1,2}/\d{1,2})\s+"
    r"(\d{4})\s+"
    r"(\d+)\s+posti\s+attualmente\s+disponibili",
    re.IGNORECASE,
)


def strip_html(html: str) -> str:
    """Rimuove i tag e comprime gli spazi, così restano solo le parole."""
    text = _TAG_RE.sub(" ", html)
    # decodifica delle entità più comuni
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&egrave;", "è"),
                 ("&agrave;", "à"), ("&igrave;", "ì"), ("&ograve;", "ò"),
                 ("&ugrave;", "ù"), ("&#39;", "'")):
        text = text.replace(a, b)
    return _WS_RE.sub(" ", text).strip()


def parse_availability(html: str):
    """Restituisce una lista di dict: {weekday, date, count}."""
    text = strip_html(html)
    results = []
    for m in _AVAIL_RE.finditer(text):
        weekday, date, year, count = m.groups()
        results.append(
            {
                "weekday": (weekday or "").strip().capitalize(),
                "date": f"{date}/{year}",
                "count": int(count),
            }
        )
    return results


def fetch_page() -> str:
    resp = requests.get(
        BEACH_URL,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "it-IT,it;q=0.9"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.text


# --------------------------------------------------------------------------- #
# Stato (per non inviare avvisi duplicati)
# --------------------------------------------------------------------------- #

def load_state() -> dict:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)


# --------------------------------------------------------------------------- #
# Telegram
# --------------------------------------------------------------------------- #

def send_telegram(text: str) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        log.error("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID non configurati: "
                  "impossibile inviare il messaggio.")
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(
            url,
            json={
                "chat_id": CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=30,
        )
        r.raise_for_status()
        return True
    except requests.RequestException as e:
        log.error("Errore invio Telegram: %s", e)
        return False


# --------------------------------------------------------------------------- #
# Logica di notifica
# --------------------------------------------------------------------------- #

def should_watch(date: str) -> bool:
    return not WATCH_DATES or date in WATCH_DATES


def process(results, state) -> None:
    now = time.time()
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    for r in results:
        date = r["date"]
        count = r["count"]
        if not should_watch(date):
            continue

        key = date
        prev = state.get(key, {"available": False, "last_notified": 0})
        available_now = count >= MIN_SPOTS

        if available_now:
            time_since = now - prev.get("last_notified", 0)
            became_available = not prev.get("available", False)
            remind = time_since >= REMIND_AFTER_HOURS * 3600

            if became_available or remind:
                msg = (
                    f"🏖️ <b>Posti disponibili a La Pelosa!</b>\n\n"
                    f"📅 {r['weekday']} {date}\n"
                    f"🎫 <b>{count}</b> post{'o' if count == 1 else 'i'} disponibil"
                    f"{'e' if count == 1 else 'i'}\n"
                    f"🕒 Rilevato: {now_str}\n\n"
                    f'👉 <a href="{BEACH_URL}">Vai alla prenotazione</a>\n\n'
                    f"<i>I posti non sono riservati e possono esaurirsi "
                    f"rapidamente: prenota subito.</i>"
                )
                if send_telegram(msg):
                    log.info("Avviso inviato per %s (%d posti)", date, count)
                    prev["last_notified"] = now
            else:
                log.info("%s ancora disponibile (%d posti), avviso già inviato", date, count)
        else:
            if prev.get("available", False):
                log.info("%s tornata esaurita", date)

        prev["available"] = available_now
        prev["count"] = count
        state[key] = prev


# --------------------------------------------------------------------------- #
# Loop principale
# --------------------------------------------------------------------------- #

def check_once(state) -> None:
    html = fetch_page()
    results = parse_availability(html)
    if not results:
        log.warning("Nessuna data trovata nella pagina (struttura cambiata?).")
        return
    summary = ", ".join(f"{r['date']}:{r['count']}" for r in results)
    log.info("Disponibilità: %s", summary)
    process(results, state)
    save_state(state)


def main() -> None:
    if not BOT_TOKEN or not CHAT_ID:
        log.warning("Attenzione: token/chat_id Telegram non impostati. "
                    "Lo script girerà ma non potrà inviare avvisi.")
    log.info("Avvio monitor La Pelosa. Controllo ogni ~%ds. URL: %s",
             CHECK_INTERVAL, BEACH_URL)
    if WATCH_DATES:
        log.info("Date monitorate: %s", ", ".join(sorted(WATCH_DATES)))
    else:
        log.info("Monitoro tutte le date mostrate nella pagina.")

    state = load_state()
    while True:
        try:
            check_once(state)
        except requests.RequestException as e:
            log.error("Errore di rete: %s", e)
        except Exception as e:  # non far morire il processo per un imprevisto
            log.exception("Errore imprevisto: %s", e)

        # piccolo jitter per non colpire sempre allo stesso secondo esatto
        sleep_for = CHECK_INTERVAL + random.randint(0, max(1, CHECK_INTERVAL // 10))
        time.sleep(sleep_for)


if __name__ == "__main__":
    # modalità test: "python3 beach_monitor.py --once" fa un solo controllo
    if "--once" in sys.argv:
        st = load_state()
        check_once(st)
    elif "--test-telegram" in sys.argv:
        ok = send_telegram("✅ Test dal monitor La Pelosa: il bot funziona!")
        print("Inviato!" if ok else "Invio fallito, controlla token e chat_id.")
    else:
        try:
            main()
        except KeyboardInterrupt:
            log.info("Interrotto dall'utente. Ciao!")
