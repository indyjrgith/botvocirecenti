#!/data/data/com.termux/files/usr/bin/bash
# avvia_bot.sh - Launcher bot VociRecenti per Termux
# Uso:
#   ./avvia_bot.sh              -> chiede conferma e lancia subito
#   ./avvia_bot.sh 2m           -> ogni ora, a partire da +2 minuti da adesso
#   ./avvia_bot.sh 12m          -> ogni ora, al minuto (attuale+12)%60
#   ./avvia_bot.sh 0h12m        -> ogni ora, al minuto 12
#   ./avvia_bot.sh 2h15m        -> ogni 2 ore, al minuto 15

# ============================================================
# CONFIGURAZIONE
# ============================================================
BOT_DIR="$HOME/storage/downloads/botvocirecenti"
BOT_SCRIPT="bot_voci_recenti_v30.py"
BOT_CMD="/data/data/com.termux/files/usr/bin/python3 $BOT_DIR/$BOT_SCRIPT"
WRAPPER_SCRIPT="$BOT_DIR/avviabot_run.sh"
CRON_TAG="# botvocirecenti"
# ============================================================

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# ------------------------------------------------------------
# Funzione: lancia il bot (in tmux se disponibile)
# ------------------------------------------------------------
launch_bot() {
    echo -e "${CYAN}Avvio bot...${NC}"
    echo -e "  Comando: ${BOT_CMD}"

    if command -v tmux &>/dev/null; then
        # Cerca una sessione tmux esistente per il bot
        if tmux has-session -t botvoci 2>/dev/null; then
            # Sessione già esistente: crea una nuova finestra
            tmux new-window -t botvoci -n "bot-$(date +%H%M)" "$BOT_CMD; echo ''; echo '[Bot terminato - premi Invio]'; read; exit"
            tmux select-window -t botvoci
        else
            # Nuova sessione tmux
            tmux new-session -d -s botvoci -n "bot" "$BOT_CMD; echo ''; echo '[Bot terminato - premi Invio]'; read; exit"
        fi
        echo -e "${GREEN}Bot avviato in sessione tmux 'botvoci'${NC}"
        echo -e "  Per visualizzare: ${YELLOW}tmux attach -t botvoci${NC}"
        # Prova ad attaccarsi automaticamente se siamo in un terminale interattivo
        if [ -t 1 ]; then
            tmux attach -t botvoci
        fi
    else
        # Fallback: esecuzione diretta nel terminale corrente
        echo -e "${YELLOW}tmux non trovato, esecuzione diretta nel terminale corrente.${NC}"
        echo -e "${YELLOW}(installa tmux con: pkg install tmux)${NC}"
        echo ""
        $BOT_CMD
    fi
}

# ------------------------------------------------------------
# Funzione: installa crontab
# Argomenti: $1=minuto, $2=ogni_N_ore (0 o 1 = ogni ora)
# ------------------------------------------------------------
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
    echo -e "  Comando: ${BOT_CMD}"

    # Verifica crond
    if ! pgrep -x crond &>/dev/null; then
        echo -e "${YELLOW}crond non è in esecuzione. Tentativo di avvio...${NC}"
        crond 2>/dev/null
        sleep 1
        if ! pgrep -x crond &>/dev/null; then
            echo -e "${RED}ERRORE: crond non trovato o non avviabile.${NC}"
            echo -e "  Installa con: ${YELLOW}pkg install cronie${NC}"
            echo -e "  Poi avvia con: ${YELLOW}crond${NC}"
            exit 1
        fi
        echo -e "${GREEN}crond avviato.${NC}"
    else
        echo -e "${GREEN}crond è in esecuzione.${NC}"
    fi

    # Copia wrapper nella dir del bot e rendilo eseguibile
    if [ -f "$HOME/bin/avviabot_run" ]; then
        cp "$HOME/bin/avviabot_run" "$WRAPPER_SCRIPT"
    elif [ -f "$HOME/storage/downloads/botvocirecenti/avviabot_run.sh" ]; then
        cp "$HOME/storage/downloads/botvocirecenti/avviabot_run.sh" "$WRAPPER_SCRIPT"
    fi
    chmod +x "$WRAPPER_SCRIPT" 2>/dev/null

    # Rimuovi eventuali righe precedenti del bot dal crontab
    local tmpfile
    tmpfile=$(mktemp)
    crontab -l 2>/dev/null | grep -v "$CRON_TAG" > "$tmpfile"

    # Aggiungi la nuova riga
    echo "PYTHONPATH=/data/data/com.termux/files/usr/lib/python3.13/site-packages" >> "$tmpfile"
    echo "HOME=/data/data/com.termux/files/home" >> "$tmpfile"
    echo "${cron_expr} bash ${WRAPPER_SCRIPT} >> ${BOT_DIR}/bot.log 2>&1 ${CRON_TAG}" >> "$tmpfile"
    crontab "$tmpfile"
    rm -f "$tmpfile"

    echo -e "${GREEN}Crontab installato:${NC}"
    echo ""
    crontab -l | grep "$CRON_TAG"
    echo ""

    # Calcola e mostra il prossimo lancio
    local now_min
    now_min=$(date +%M | sed 's/^0//')
    local now_h
    now_h=$(date +%H | sed 's/^0//')
    local wait_min=$(( (cron_min - now_min + 60) % 60 ))
    [ "$wait_min" -eq 0 ] && wait_min=60
    echo -e "  Ora corrente:  $(date +%H:%M)"
    echo -e "  Primo lancio:  tra ${YELLOW}${wait_min} minuti${NC} (al minuto ${cron_min} dell'ora)"
    if [ "$cron_every_h" -gt 1 ]; then
        echo -e "  Frequenza:     ogni ${cron_every_h} ore"
    else
        echo -e "  Frequenza:     ogni ora"
    fi
}

# ------------------------------------------------------------
# Funzione: parsing parametro Xh Ym / Nm
# Restituisce: PARSED_MIN e PARSED_HOURS (variabili globali)
# ------------------------------------------------------------
parse_param() {
    local param="$1"
    PARSED_MIN=-1
    PARSED_HOURS=1

    # Formato XhYm
    if [[ "$param" =~ ^([0-9]+)h([0-9]+)m$ ]]; then
        PARSED_HOURS="${BASH_REMATCH[1]}"
        PARSED_MIN="${BASH_REMATCH[2]}"
        # 0h o 1h = ogni ora
        [ "$PARSED_HOURS" -eq 0 ] && PARSED_HOURS=1
        if [ "$PARSED_MIN" -lt 0 ] || [ "$PARSED_MIN" -gt 59 ]; then
            echo -e "${RED}ERRORE: i minuti devono essere tra 0 e 59.${NC}"
            exit 1
        fi
        return 0
    fi

    # Formato Nm (relativo: minuto_attuale + N)
    if [[ "$param" =~ ^([0-9]+)m$ ]]; then
        local offset="${BASH_REMATCH[1]}"
        local now_min
        now_min=$(date +%M | sed 's/^0*//')
        [ -z "$now_min" ] && now_min=0
        PARSED_MIN=$(( (now_min + offset) % 60 ))
        PARSED_HOURS=1
        return 0
    fi

    echo -e "${RED}ERRORE: formato non riconosciuto '${param}'.${NC}"
    echo -e "  Uso: ${YELLOW}./avvia_bot.sh [Nm | XhYm]${NC}"
    echo -e "  Esempi: 2m  |  0h15m  |  2h30m"
    exit 1
}

# ============================================================
# MAIN
# ============================================================

# Verifica che la directory del bot esista
if [ ! -d "$BOT_DIR" ]; then
    echo -e "${RED}ERRORE: directory bot non trovata: ${BOT_DIR}${NC}"
    exit 1
fi

if [ ! -f "$BOT_DIR/$BOT_SCRIPT" ]; then
    echo -e "${RED}ERRORE: script bot non trovato: ${BOT_DIR}/${BOT_SCRIPT}${NC}"
    exit 1
fi

# --- Nessun parametro: lancio immediato ---
if [ $# -eq 0 ]; then
    echo -e "${CYAN}=== Bot VociRecenti ===${NC}"
    echo -e "Nessun parametro — lancio immediato del bot."
    echo -n "Confermi? [s/N] "
    read -r risposta
    case "$risposta" in
        [sS]|[yY])
            launch_bot
            ;;
        *)
            echo "Annullato."
            exit 0
            ;;
    esac
    exit 0
fi

# --- Parametro presente: configura crontab ---
echo -e "${CYAN}=== Bot VociRecenti — Configurazione crontab ===${NC}"
parse_param "$1"
echo -e "  Parametro:   ${YELLOW}$1${NC}"
echo -e "  Minuto cron: ${YELLOW}${PARSED_MIN}${NC}"
echo -e "  Ogni:        ${YELLOW}${PARSED_HOURS}h${NC}"
echo ""
echo -n "Confermi l'installazione del crontab? [s/N] "
read -r risposta
case "$risposta" in
    [sS]|[yY])
        install_crontab "$PARSED_MIN" "$PARSED_HOURS"
        echo -e "${GREEN}Fatto.${NC}"
        ;;
    *)
        echo "Annullato."
        exit 0
        ;;
esac
