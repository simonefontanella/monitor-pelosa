# Hosting gratuito con GitHub Actions

Fa girare il monitor **gratis**, senza server: GitHub esegue lo script ogni
~5 minuti secondo lo schedule. Ogni esecuzione fa un solo controllo e termina.

## Cosa contiene il repo

```
beach_monitor.py                 # lo script (con modalità --once)
requirements.txt                 # dipendenze (requests)
state.json                       # creato in automatico, tiene traccia degli avvisi
.gitignore
.github/workflows/check-beach.yml  # lo schedule ogni 5 minuti
```

---

## Passo 1 — Prepara il bot Telegram

Come già visto: crea il bot con **@BotFather** e recupera:
- `TELEGRAM_BOT_TOKEN` (il token tipo `123456:AA...`)
- `TELEGRAM_CHAT_ID` (il tuo id, da @userinfobot o da `getUpdates`)

---

## Passo 2 — Crea il repository

1. Vai su https://github.com e crea un nuovo repository (può essere **privato**;
   i 2.000 minuti/mese gratis bastano abbondantemente per un controllo ogni 5 min).
2. Carica questi file **mantenendo le cartelle** (in particolare
   `.github/workflows/check-beach.yml` deve stare esattamente in quel percorso).

   Da web: "Add file" → "Upload files" e trascina tutto. Attenzione: la cartella
   `.github` è nascosta, quindi da web crea prima il file con
   "Add file → Create new file" e digita come nome:
   `.github/workflows/check-beach.yml`, poi incolla il contenuto.

   Oppure da terminale:
   ```bash
   git init
   git add .
   git commit -m "primo commit: monitor spiaggia"
   git branch -M main
   git remote add origin https://github.com/TUO_UTENTE/TUO_REPO.git
   git push -u origin main
   ```

---

## Passo 3 — Inserisci i segreti (token e chat_id)

Nel repository su GitHub:
1. **Settings** → **Secrets and variables** → **Actions**.
2. Bottone **New repository secret** e aggiungi (uno alla volta):
   - Nome: `TELEGRAM_BOT_TOKEN` → valore: il tuo token
   - Nome: `TELEGRAM_CHAT_ID` → valore: il tuo chat id

> I segreti non sono visibili nei log: è il modo sicuro per non mettere il
> token dentro al codice.

---

## Passo 4 — (Opzionale) scegli le date e i posti minimi

Apri `.github/workflows/check-beach.yml` e modifica queste due righe:

```yaml
WATCH_DATES: ''      # es '15/07/2026,16/07/2026'  (vuoto = tutte le date)
MIN_SPOTS: '1'       # posti minimi per l'avviso
```

Per cambiare la frequenza modifica il cron (il minimo è 5 minuti):
```yaml
- cron: '*/5 * * * *'    # ogni 5 min   →  '*/15 * * * *' per ogni 15 min
```

---

## Passo 5 — Attiva e prova

1. Vai nella tab **Actions** del repo. Se richiesto, conferma l'abilitazione
   dei workflow.
2. Seleziona **"Controllo spiaggia La Pelosa"** → **Run workflow** per lanciarlo
   subito a mano (senza aspettare i 5 minuti) e verificare che tutto funzioni.
3. Apri l'esecuzione e controlla i log dello step "Controllo disponibilità":
   vedrai la disponibilità rilevata. Se un giorno ha posti, ti arriva il
   messaggio su Telegram.

Da qui in poi parte da solo ogni ~5 minuti.

---

## Note utili

- **Ritardi**: nei momenti di carico GitHub può posticipare i cron, quindi a
  volte l'intervallo reale è di 5-15 minuti. Normale.
- **Repo inattivo**: GitHub disabilita i cron sui repo senza attività da 60
  giorni. Lo script committa `state.json` quando cambia qualcosa, il che tiene
  vivo il repo; in caso, basta un commit qualsiasi per riattivarlo.
- **Avvisi duplicati**: gestiti da `state.json`, che il workflow ricommitta
  dopo ogni esecuzione. Per questo NON va messo nel `.gitignore`.
- **Costi**: repo privato = 2.000 min/mese gratis; una run dura ~20-40 secondi,
  quindi con un controllo ogni 5 min resti ampiamente nel free. Repo pubblico =
  minuti illimitati.
- **Fermarlo**: disattiva il workflow dalla tab Actions (menu "···" → Disable),
  oppure elimina/commenta la sezione `schedule` nel file yml.
