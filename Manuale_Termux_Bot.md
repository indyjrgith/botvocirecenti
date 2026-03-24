# Manuale: Esecuzione automatica di un bot Python su Android con Termux

Versione aggiornata per BotVociRecenti **v8.37**

## Panoramica

Questa guida descrive come configurare uno smartphone Android con Termux per eseguire automaticamente un bot Python a cadenze regolari, con monitoraggio dell'output in tempo reale tramite tmux.

### Componenti del sistema

| Componente | Funzione |
|---|---|
| **Termux** | Emulatore terminale Linux per Android |
| **Termux:Boot** | Esegue script all'avvio del telefono |
| **cronie** | Demone cron per esecuzione pianificata |
| **tmux** | Multiplexer terminale: mantiene sessioni persistenti |
| **avviabot** | Script launcher: lancia il bot o configura il crontab |
| **avviabot_run.sh** | Wrapper eseguito da cron ad ogni scadenza |

---

## 1. Installazione software

### 1.1 App Android necessarie

Installare da F-Droid (raccomandato) o Google Play:

- **Termux** — terminale Linux
- **Termux:Boot** — esecuzione automatica all'avvio

> ⚠️ Se si installa Termux da Google Play e Termux:Boot da F-Droid (o viceversa), potrebbero non comunicare correttamente. Installare entrambi dalla stessa fonte.

### 1.2 Pacchetti Termux

Aprire Termux e installare i pacchetti necessari:

```bash
pkg update && pkg upgrade
pkg install python cronie tmux git
```

### 1.3 Dipendenze Python

```bash
pip install pywikibot
```

> **Nota:** dopo un `pkg upgrade` che aggiorna Python, reinstallare i pacchetti pip con `pip install pywikibot`.

---

## 2. Struttura dei file

Creare una cartella dedicata al bot. Il percorso consigliato è nella cartella Download di Android, accessibile da Termux tramite:

```
~/storage/downloads/botvocirecenti/
```

Per abilitare l'accesso allo storage:

```bash
termux-setup-storage
```

La struttura attesa è:

```
~/storage/downloads/botvocirecenti/
├── bot_voci_recenti_v30.py   # Script principale del bot
├── PuliziaCache.py            # Script pulizia cache
├── user-config.py             # Configurazione pywikibot
├── user-password.py           # Credenziali pywikibot
├── moves_cache.json           # Cache spostamenti (aggiornata automaticamente)
├── cleanup_state.json         # Stato pulizia giornaliera
├── bot_voci_recenti.log       # Log di esecuzione (creato automaticamente)
└── avviabot_run.sh            # Wrapper per cron (copiato automaticamente da avviabot)
```

Gli script di gestione vanno in `~/bin/` per essere disponibili da qualsiasi directory:

```
~/bin/
├── avviabot            # Script launcher principale
└── avviabot_run        # Wrapper cron (copia sorgente)
```

---

## 3. Configurazione credenziali pywikibot

### user-config.py

```python
# -*- coding: utf-8 -*-
family = 'wikipedia'
mylang = 'it'
usernames['wikipedia']['it'] = 'BotVociRecenti'
put_throttle = 1
maxlag = 5
console_encoding = 'utf-8'
```

### user-password.py

```python
('BotVociRecenti', BotPassword('BotVociRecenti', 'la_tua_password_bot'))
```

> **Nota:** la password bot si ottiene da Wikipedia → Speciale:Password bot.

---

## 4. Script di gestione

### 4.1 Script launcher: `avviabot`

Salvare come `~/bin/avviabot` e renderlo eseguibile con `chmod +x ~/bin/avviabot`.

Adattare le variabili nella sezione CONFIGURAZIONE:
- `BOT_DIR`: percorso della cartella del bot
- `BOT_SCRIPT`: nome del file Python del bot
- `PYTHONPATH_VAL`: ottenibile con `python3 -c "import site; print(site.getsitepackages())"`

```bash
#!/data/data/com.termux/files/usr/bin/bash
# avviabot - Launcher bot per Termux
# Uso:
#   avviabot              -> chiede conferma e lancia subito
#   avviabot 2m           -> ogni ora, a partire da +2 minuti da adesso
#   avviabot 0h15m        -> ogni ora, al minuto 15
#   avviabot 2h30m        -> ogni 2 ore, al minuto 30

# ============================================================
# CONFIGURAZIONE — adattare a proprio ambiente
# ============================================================
BOT_DIR="$HOME/storage/downloads/botvocirecenti"
BOT_SCRIPT="bot_voci_recenti_v30.py"
PYTHON_BIN="/data/data/com.termux/files/usr/bin/python3"
PYTHONPATH_VAL="/data/data/com.termux/files/usr/lib/python3.13/site-packages"
BOT_CMD="$PYTHON_BIN $BOT_DIR/$BOT_SCRIPT"
WRAPPER_SCRIPT="$BOT_DIR/avviabot_run.sh"
CRON_TAG="# botvocirecenti"
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

launch_bot() {
    echo -e "${CYAN}Avvio bot...${NC}"
    if command -v tmux &>/dev/null; then
        if tmux has-session -t botvoci 2>/dev/null; then
            tmux new-window -t botvoci -n "bot-$(date +%H%M)" \
                "$BOT_CMD; echo ''; echo '[Bot terminato - premi Invio]'; read; exit"
        else
            tmux new-session -d -s botvoci -n "bot" \
                "$BOT_CMD; echo ''; echo '[Bot terminato - premi Invio]'; read; exit"
        fi
        echo -e "${GREEN}Bot avviato in sessione tmux 'botvoci'${NC}"
        echo -e "  Per visualizzare: ${YELLOW}tmux attach -t botvoci${NC}"
        if [ -t 1 ]; then
            tmux attach -t botvoci
        fi
    else
        echo -e "${YELLOW}tmux non trovato — esecuzione diretta.${NC}"
        $BOT_CMD
    fi
}

install_crontab() {
    local cron_min=$1
    local cron_every_h=$2
    local cron_expr
    if [ "$cron_every_h" -le 1 ]; then
        cron_expr="${cron_min} * * * *"
    else
        cron_expr="${cron_min} */${cron_every_h} * * *"
    fi

    echo -e "${CYAN}Configurazione crontab...${NC}"
    echo -e "  Espressione cron: ${YELLOW}${cron_expr}${NC}"

    if ! pgrep -x crond &>/dev/null; then
        crond 2>/dev/null; sleep 1
        if ! pgrep -x crond &>/dev/null; then
            echo -e "${RED}ERRORE: crond non avviabile. Installa con: pkg install cronie${NC}"
            exit 1
        fi
    fi
    echo -e "${GREEN}crond in esecuzione.${NC}"

    if [ -f "$HOME/bin/avviabot_run" ]; then
        cp "$HOME/bin/avviabot_run" "$WRAPPER_SCRIPT"
    fi
    chmod +x "$WRAPPER_SCRIPT" 2>/dev/null

    local tmpfile
    tmpfile=$(mktemp)
    crontab -l 2>/dev/null | grep -v "$CRON_TAG" > "$tmpfile"
    echo "PYTHONPATH=$PYTHONPATH_VAL" >> "$tmpfile"
    echo "HOME=/data/data/com.termux/files/home" >> "$tmpfile"
    echo "${cron_expr} bash ${WRAPPER_SCRIPT} >> ${BOT_DIR}/bot.log 2>&1 ${CRON_TAG}" >> "$tmpfile"
    crontab "$tmpfile"
    rm -f "$tmpfile"

    echo -e "${GREEN}Crontab installato:${NC}"
    crontab -l | grep "$CRON_TAG"

    local now_min
    now_min=$(date +%M | sed 's/^0*//')
    [ -z "$now_min" ] && now_min=0
    local wait_min=$(( (cron_min - now_min + 60) % 60 ))
    [ "$wait_min" -eq 0 ] && wait_min=60
    echo -e "  Ora corrente: $(date +%H:%M)"
    echo -e "  Primo lancio: tra ${YELLOW}${wait_min} minuti${NC}"
}

parse_param() {
    local param="$1"
    PARSED_MIN=-1; PARSED_HOURS=1
    if [[ "$param" =~ ^([0-9]+)h([0-9]+)m$ ]]; then
        PARSED_HOURS="${BASH_REMATCH[1]}"
        PARSED_MIN="${BASH_REMATCH[2]}"
        [ "$PARSED_HOURS" -eq 0 ] && PARSED_HOURS=1
        return 0
    fi
    if [[ "$param" =~ ^([0-9]+)m$ ]]; then
        local offset="${BASH_REMATCH[1]}"
        local now_min; now_min=$(date +%M | sed 's/^0*//')
        [ -z "$now_min" ] && now_min=0
        PARSED_MIN=$(( (now_min + offset) % 60 ))
        PARSED_HOURS=1; return 0
    fi
    echo -e "${RED}ERRORE: formato non valido. Esempi: 2m | 0h15m | 2h30m${NC}"
    exit 1
}

if [ ! -f "$BOT_DIR/$BOT_SCRIPT" ]; then
    echo -e "${RED}ERRORE: bot non trovato: $BOT_DIR/$BOT_SCRIPT${NC}"
    exit 1
fi

if [ $# -eq 0 ]; then
    echo -e "${CYAN}=== Bot VociRecenti ===${NC}"
    echo -n "Lancia il bot ora? [s/N] "
    read -r risposta
    case "$risposta" in [sS]|[yY]) launch_bot ;; *) echo "Annullato."; exit 0 ;; esac
    exit 0
fi

parse_param "$1"
echo -e "${CYAN}=== Configurazione crontab ===${NC}"
echo -e "  Parametro: ${YELLOW}$1${NC} → minuto ${PARSED_MIN}, ogni ${PARSED_HOURS}h"
echo -n "Confermi? [s/N] "
read -r risposta
case "$risposta" in
    [sS]|[yY]) install_crontab "$PARSED_MIN" "$PARSED_HOURS" ;;
    *) echo "Annullato."; exit 0 ;;
esac
```

### 4.2 Script wrapper cron: `avviabot_run`

Salvare come `~/bin/avviabot_run` e renderlo eseguibile con `chmod +x ~/bin/avviabot_run`.

```bash
#!/data/data/com.termux/files/usr/bin/bash
# avviabot_run - Wrapper eseguito da cron

BOT_DIR="$HOME/storage/downloads/botvocirecenti"
BOT_SCRIPT="bot_voci_recenti_v30.py"
PYTHON_BIN="/data/data/com.termux/files/usr/bin/python3"
BOT_CMD="$PYTHON_BIN $BOT_DIR/$BOT_SCRIPT"
TMUX_SESSION="botvoci"
WIN_NAME="bot-$(date +%H%M)"

if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
    tmux new-window -t "$TMUX_SESSION" -n "$WIN_NAME" \
        "$BOT_CMD; echo ''; echo '=== Bot terminato - premi Invio ==='; read"
    tmux select-window -t "$TMUX_SESSION:$WIN_NAME"
else
    tmux new-session -d -s "$TMUX_SESSION" -n "$WIN_NAME" \
        "$BOT_CMD; echo ''; echo '=== Bot terminato - premi Invio ==='; read"
fi

sleep 1
am start --user 0 -n com.termux/.app.TermuxActivity \
    --es com.termux.app.EXTRA_ARGUMENTS "tmux attach -t $TMUX_SESSION" \
    > /dev/null 2>&1
```

### 4.3 Script di avvio automatico: `~/.termux/boot/start-services.sh`

Questo script viene eseguito da Termux:Boot ad ogni riavvio del telefono.

```bash
#!/data/data/com.termux/files/usr/bin/sh
# Avvia crond
sv up crond
# Mantiene il wakelock (evita che Android sospenda Termux)
termux-wake-lock
# Pre-crea la sessione tmux
tmux new-session -d -s botvoci 2>/dev/null
```

---

## 5. Configurazione PATH

Per poter lanciare `avviabot` da qualsiasi directory, `~/bin` deve essere nel PATH:

```bash
echo 'export PATH="$HOME/bin:$PATH"' >> $PREFIX/etc/bash.bashrc
```

---

## 6. Auto-attach tmux all'apertura di Termux

Per mostrare automaticamente l'output del bot quando Termux viene aperto:

```bash
echo '[[ -z "$TMUX" ]] && tmux has-session -t botvoci 2>/dev/null && tmux attach -t botvoci' >> $PREFIX/etc/bash.bashrc
```

---

## 7. Installazione passo-passo

```bash
# 1. Abilitare accesso storage
termux-setup-storage

# 2. Installare pacchetti
pkg update && pkg upgrade
pkg install python cronie tmux git

# 3. Installare pywikibot
pip install pywikibot

# 4. Ottenere il codice dal repository GitHub
cd ~/storage/downloads
git clone https://github.com/indyjrgith/botvocirecenti.git botvocirecenti

# 5. Creare user-config.py e user-password.py (vedi sezione 3)

# 6. Creare cartella bin e copiare gli script
mkdir -p ~/bin
# copiare avviabot e avviabot_run in ~/bin (vedi sezione 4)
chmod +x ~/bin/avviabot ~/bin/avviabot_run

# 7. Aggiungere ~/bin al PATH
echo 'export PATH="$HOME/bin:$PATH"' >> $PREFIX/etc/bash.bashrc
source $PREFIX/etc/bash.bashrc

# 8. Configurare auto-attach tmux
echo '[[ -z "$TMUX" ]] && tmux has-session -t botvoci 2>/dev/null && tmux attach -t botvoci' >> $PREFIX/etc/bash.bashrc

# 9. Creare script di boot
mkdir -p ~/.termux/boot
cat > ~/.termux/boot/start-services.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/sh
sv up crond
termux-wake-lock
tmux new-session -d -s botvoci 2>/dev/null
EOF
chmod +x ~/.termux/boot/start-services.sh

# 10. Avviare crond manualmente (prima del riavvio)
crond

# 11. Configurare e installare il crontab
avviabot 5m        # avvia ogni ora, a partire da 5 minuti da adesso
```

---

## 8. Aggiornamento del codice

Per aggiornare il bot all'ultima versione dal repository GitHub:

```bash
cd ~/storage/downloads/botvocirecenti
git pull origin main
```

> **Nota:** i file `user-config.py` e `user-password.py` non sono nel repository e non vengono sovrascritti dall'aggiornamento.

---

## 9. Utilizzo di avviabot

| Comando | Effetto |
|---|---|
| `avviabot` | Chiede conferma e lancia il bot immediatamente |
| `avviabot 5m` | Configura cron: ogni ora, al minuto (attuale + 5) |
| `avviabot 0h30m` | Configura cron: ogni ora, al minuto 30 |
| `avviabot 2h15m` | Configura cron: ogni 2 ore, al minuto 15 |

---

## 10. Monitoraggio

### Vedere l'output in tempo reale

All'apertura di Termux, se il bot è in esecuzione la sessione tmux viene mostrata automaticamente.

In alternativa:

```bash
tmux attach -t botvoci
```

### Navigazione in tmux

| Tasto | Azione |
|---|---|
| `Ctrl+B` poi `D` | Esce da tmux senza chiuderlo (detach) |
| `Ctrl+B` poi `C` | Apre una nuova finestra |
| `Ctrl+B` poi `0..9` | Passa alla finestra N |
| `Ctrl+B` poi `W` | Lista finestre |

### Consultare il log

```bash
tail -f ~/storage/downloads/botvocirecenti/bot_voci_recenti.log
```

---

## 11. Comandi di diagnostica

```bash
# Verifica se crond è attivo
pgrep crond && echo "crond OK" || echo "crond NON attivo"

# Verifica se il bot è in esecuzione
pgrep -a python3

# Verifica sessioni tmux
tmux ls

# Verifica crontab installato
crontab -l

# Riavvia crond manualmente
crond

# Verifica file persistenti della cache
ls -la ~/storage/downloads/botvocirecenti/*.json
```

---

## 12. Interruzione e manutenzione

```bash
# Fermare il bot in esecuzione
pkill -f bot_voci_recenti_v30.py

# Rimuovere il crontab (stop schedulazione)
crontab -r

# Sospendere temporaneamente (commenta la riga nel crontab)
crontab -e
```

---

## 13. Risoluzione problemi comuni

### Il bot non parte da cron

**Sintomo:** `bot_voci_recenti.log` contiene `ModuleNotFoundError: No module named 'pywikibot'`

**Causa:** cron usa un ambiente minimale senza le variabili della shell interattiva.

**Soluzione:** verificare che `PYTHONPATH_VAL` nello script `avviabot` punti alla directory corretta:
```bash
python3 -c "import site; print(site.getsitepackages())"
```
Aggiornare `PYTHONPATH_VAL` in `avviabot` con il percorso restituito.

---

### Dopo pkg upgrade il bot non funziona più

**Causa:** `pkg upgrade` può aggiornare Python a una versione più recente, invalidando i pacchetti installati.

**Soluzione:**
```bash
pip install pywikibot
```

---

### Termux non si apre automaticamente quando il bot parte

**Causa:** il meccanismo `am start` non sempre funziona quando Termux è completamente chiuso.

**Soluzione:** aprire Termux manualmente — grazie all'auto-attach configurato in `bash.bashrc`, la sessione tmux con l'output del bot viene mostrata automaticamente.

---

### crond non sopravvive al riavvio

**Causa:** lo script di boot non è presente o non è eseguibile.

**Verifica:**
```bash
ls -la ~/.termux/boot/
cat ~/.termux/boot/start-services.sh
```

Assicurarsi che il file sia eseguibile:
```bash
chmod +x ~/.termux/boot/start-services.sh
```

---

### Il bot parte da zero ogni ora (moves_cache non aggiornato)

**Causa:** `moves_cache.json` viene scritto nella cartella dello script, che deve essere la stessa del bot.

**Verifica:**
```bash
ls -la ~/storage/downloads/botvocirecenti/*.json
```

I file `moves_cache.json` e `cleanup_state.json` devono esistere e avere la data dell'ultima esecuzione.

---

### La pulizia cache avviene più volte per notte

**Causa:** `cleanup_state.json` non viene trovato o non viene aggiornato.

**Verifica:**
```bash
cat ~/storage/downloads/botvocirecenti/cleanup_state.json
```

Deve contenere `"cleaned_today": true` dopo l'esecuzione nella fascia notturna (02:00-05:00).

---

## 14. Note sulla versione 8.37

La v8.37 introduce la **compatibilità multipiattaforma**:

- **Fuso orario:** `time.tzset()` è protetto con `try/except` per compatibilità Windows (su Termux e Linux funziona normalmente)
- **Percorso file:** `DATA_DIR` viene determinato automaticamente dalla variabile d'ambiente `BOT_DATA_DIR` se presente (Toolforge), altrimenti usa la cartella dello script (Termux/Windows)
- Su Termux non è necessario impostare `BOT_DATA_DIR` — il bot usa automaticamente la cartella del codice

Il bot è quindi compatibile con Termux, Windows e Toolforge senza modifiche al codice.
