# Monitor spiaggia La Pelosa → avviso Telegram

Controlla ogni pochi minuti la pagina delle prenotazioni della spiaggia
**La Pelosa** (Stintino) e ti manda un messaggio su **Telegram** appena
compaiono posti disponibili.

Leggero: gira su un Raspberry Pi con la sola libreria `requests`.

---

## 1. Crea il bot Telegram

1. Su Telegram apri una chat con **@BotFather**.
2. Invia `/newbot` e segui le istruzioni (nome + username che finisce per `bot`).
3. BotFather ti dà un **token** tipo `123456789:AAxxxx...`. Tienilo da parte.

### Trovare il `chat_id`
1. Invia un messaggio qualsiasi (es. "ciao") al bot che hai appena creato.
2. Apri nel browser (mettendo il tuo token):
   `https://api.telegram.org/bot<IL_TUO_TOKEN>/getUpdates`
3. Cerca `"chat":{"id":123456789,...}`: quel numero è il tuo `chat_id`.

> In alternativa scrivi a **@userinfobot**: ti dice subito il tuo id.
> Per inviare gli avvisi a un **gruppo**, aggiungi il bot al gruppo e usa
> l'id del gruppo (di solito negativo, es. `-100...`).

---

## 2. Installazione sul Raspberry Pi

```bash
# copia la cartella "beach" sul Pi, poi:
cd ~/beach

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# configura le credenziali
cp .env.example .env
nano .env        # incolla TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID
```

### Prova subito
```bash
# carica le variabili del .env nella shell corrente
set -a; source .env; set +a

python3 beach_monitor.py --test-telegram   # verifica che il bot ti scriva
python3 beach_monitor.py --once            # fa un solo controllo e stampa i posti
```

Se `--test-telegram` ti fa arrivare un messaggio, sei a posto.

---

## 3. Farlo girare 24/7 (systemd)

Così parte da solo all'accensione del Pi e si riavvia se crasha.

```bash
# adatta i percorsi/utente nel file se non usi l'utente "pi"
sudo cp beach-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now beach-monitor

# controlla che vada e guarda i log in tempo reale
systemctl status beach-monitor
journalctl -u beach-monitor -f
```

Nel file `.service` verifica che combacino:
- `User=` → il tuo utente (es. `pi`)
- `WorkingDirectory=` e i percorsi → dove hai messo la cartella
- `venv/bin/python` → l'interprete del virtualenv creato sopra

---

## Configurazione (file `.env`)

| Variabile | Default | Cosa fa |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Token del bot (obbligatorio) |
| `TELEGRAM_CHAT_ID` | — | Chat/gruppo a cui scrivere (obbligatorio) |
| `BEACH_URL` | La Pelosa | Pagina da controllare |
| `CHECK_INTERVAL` | `120` | Secondi tra un controllo e l'altro |
| `WATCH_DATES` | (tutte) | Solo certe date, es. `15/07/2026,16/07/2026` |
| `MIN_SPOTS` | `1` | Posti minimi per far scattare l'avviso |
| `REMIND_AFTER_HOURS` | `6` | Ogni quante ore ripete l'avviso se resta disponibile |

---

## Come si comporta con gli avvisi

- Ti avvisa **quando una data passa da esaurita a disponibile**.
- **Non** ti riempie di messaggi: se resta disponibile non ripete
  (salvo un promemoria ogni `REMIND_AFTER_HOURS` ore).
- Se una data torna esaurita e poi si libera di nuovo, ti riavvisa.
- Lo stato è salvato in `state.json`, quindi non ricomincia da capo dopo un riavvio.

## Note

- Il sito dichiara che i posti mostrati sono **indicativi e non riservati**:
  l'avviso è un "corri a controllare", non una garanzia di prenotazione.
- Non impostare `CHECK_INTERVAL` troppo basso (es. sotto i 60s): eviti di
  sovraccaricare il sito e di sembrare traffico anomalo. 120–180s è un buon valore.
- Se un giorno smette di trovare le date, probabilmente il sito ha cambiato
  struttura HTML: va aggiornata la regex `_AVAIL_RE` in `beach_monitor.py`.
