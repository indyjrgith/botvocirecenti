#!/bin/bash
# avvia_bot_toolforge.sh - Launcher bot VociRecenti per Toolforge
# Uso:
#   ./avvia_bot_toolforge.sh              -> chiede conferma e lancia subito (one-off)
#   ./avvia_bot_toolforge.sh 2m           -> ogni ora, a partire da +2 minuti da adesso
#   ./avvia_bot_toolforge.sh 12m          -> ogni ora, al minuto (attuale+12)%60
#   ./avvia_bot_toolforge.sh 0h12m        -> ogni ora, al minuto 12
#   ./avvia_bot_toolforge.sh 2h15m        -> ogni 2 ore, al minuto 15
#   ./avvia_bot_toolforge.sh stop         -> ferma il bot in modo sicuro (attende fine scrittura cache)
#   ./avvia_bot_toolforge.sh logs         -> monitora i log in tempo reale

# ============================================================
# CONFIGURAZIONE
# ============================================================
BOT_SCRIPT="bot_voci_recenti_v30.py"
BOT_IMAGE="tool-botvocirecenti/tool-botvocirecenti:latest"
JOB_NAME="botvocirecenti"
JOB_NAME_ONEOFF="bot-oneoff"
CACHE_PAGE="Modulo:VociRecenti/Dati1"
WIKI_API="https://it.wikipedia.org/w/api.php"
SAFE_STOP_THRESHOLD=300   # secondi: se Dati1 è stato modificato meno di 5 minuti fa, il bot sta scrivendo
SAFE_STOP_POLL=30         # secondi: intervallo di controllo
# ============================================================

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# ------------------------------------------------------------
# Funzione: lancia il bot una volta sola
# ------------------------------------------------------------
launch_bot() {
    echo -e "${CYAN}Avvio bot (esecuzione singola)...${NC}"

    # Rimuovi eventuale job one-off precedente
    toolforge jobs delete "$JOB_NAME_ONEOFF" 2>/dev/null

    toolforge jobs run "$JOB_NAME_ONEOFF" \
        --command "python3 $BOT_SCRIPT" \
        --image "$BOT_IMAGE" \
        --mount all \
        --filelog

    echo -e "${GREEN}Bot avviato come job one-off '${JOB_NAME_ONEOFF}'.${NC}"
    echo -e "  Stato:  ${YELLOW}toolforge jobs show ${JOB_NAME_ONEOFF}${NC}"
    echo -e "  Log:    ${YELLOW}tail -f ~/${JOB_NAME_ONEOFF}.out${NC}"
    echo -e "  Ferma:  ${YELLOW}toolforge jobs delete ${JOB_NAME_ONEOFF}${NC}"
}

# ------------------------------------------------------------
# Funzione: installa job schedulato
# Argomenti: $1=minuto, $2=ogni_N_ore
# ------------------------------------------------------------
install_schedule() {
    local cron_min=$1
    local cron_every_h=$2
    local cron_expr

    if [ "$cron_every_h" -le 1 ]; then
        cron_expr="${cron_min} * * * *"
    else
        cron_expr="${cron_min} */${cron_every_h} * * *"
    fi

    echo -e "${CYAN}Configurazione job schedulato...${NC}"
    echo -e "  Espressione cron: ${YELLOW}${cron_expr}${NC}"

    # Rimuovi job schedulato esistente
    if toolforge jobs show "$JOB_NAME" &>/dev/null; then
        echo -e "  Rimozione job esistente '${JOB_NAME}'..."
        toolforge jobs delete "$JOB_NAME"
        sleep 2
    fi

    # Crea nuovo job schedulato
    toolforge jobs run "$JOB_NAME" \
        --command "python3 $BOT_SCRIPT" \
        --image "$BOT_IMAGE" \
        --mount all \
        --filelog \
        --schedule "$cron_expr"

    echo -e "${GREEN}Job schedulato installato:${NC}"
    echo ""
    toolforge jobs show "$JOB_NAME"
    echo ""

    # Calcola e mostra il prossimo lancio
    local now_min
    now_min=$(date +%M | sed 's/^0*//')
    [ -z "$now_min" ] && now_min=0
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
# Funzione: mostra i log in tempo reale
# ------------------------------------------------------------
show_logs() {
    local log_scheduled=~/"${JOB_NAME}.out"
    local log_oneoff=~/"${JOB_NAME_ONEOFF}.out"

    if [ -f "$log_scheduled" ]; then
        echo -e "${CYAN}Monitoraggio log job schedulato '${JOB_NAME}'...${NC}"
        echo -e "  File: ${YELLOW}${log_scheduled}${NC}"
        echo -e "  (Ctrl+C per uscire)"
        echo ""
        tail -f "$log_scheduled"
    elif [ -f "$log_oneoff" ]; then
        echo -e "${CYAN}Monitoraggio log job one-off '${JOB_NAME_ONEOFF}'...${NC}"
        echo -e "  File: ${YELLOW}${log_oneoff}${NC}"
        echo -e "  (Ctrl+C per uscire)"
        echo ""
        tail -f "$log_oneoff"
    else
        echo -e "${YELLOW}Nessun file di log trovato.${NC}"
        echo -e "  Assicurati che il bot sia stato avviato con questo script."
    fi
}

# ------------------------------------------------------------
# Funzione: attende che il bot abbia finito di scrivere la cache
# Controlla il timestamp dell'ultima modifica di Dati1 su Wikipedia
# ------------------------------------------------------------
wait_for_safe_stop() {
    echo -e "${CYAN}Controllo stato scrittura cache...${NC}"
    echo -e "  Pagina monitorata: ${YELLOW}${CACHE_PAGE}${NC}"

    while true; do
        # Recupera il timestamp dell'ultima modifica di Dati1 (in UTC ISO 8601)
        local api_response
        api_response=$(curl -s "${WIKI_API}?action=query&titles=$(python3 -c "import urllib.parse; print(urllib.parse.quote('${CACHE_PAGE}'))")&prop=revisions&rvprop=timestamp&format=json" 2>/dev/null)

        local last_edit
        last_edit=$(echo "$api_response" | grep -o '"timestamp":"[^"]*"' | head -1 | cut -d'"' -f4)

        if [ -z "$last_edit" ]; then
            echo -e "  ${YELLOW}Impossibile recuperare il timestamp da Wikipedia, procedo con lo stop.${NC}"
            break
        fi

        # Converti il timestamp Wikipedia (UTC) in secondi Unix
        local ts_wiki
        ts_wiki=$(date -u -d "$last_edit" +%s 2>/dev/null)
        if [ -z "$ts_wiki" ]; then
            # Fallback per sistemi che non supportano -d
            ts_wiki=$(python3 -c "from datetime import datetime; print(int(datetime.strptime('${last_edit}', '%Y-%m-%dT%H:%M:%SZ').timestamp()))" 2>/dev/null)
        fi

        local ts_now
        ts_now=$(date -u +%s)

        local diff=$(( ts_now - ts_wiki ))

        if [ "$diff" -lt "$SAFE_STOP_THRESHOLD" ]; then
            echo -e "  ${YELLOW}Bot probabilmente in scrittura cache (ultima modifica: ${diff}s fa). Attendo ${SAFE_STOP_POLL}s...${NC}"
            sleep "$SAFE_STOP_POLL"
        else
            echo -e "  ${GREEN}Cache ferma da ${diff}s — sicuro procedere con lo stop.${NC}"
            break
        fi
    done
}

# ------------------------------------------------------------
# Funzione: ferma il bot in modo sicuro
# ------------------------------------------------------------
stop_schedule() {
    echo -e "${CYAN}Arresto job schedulato '${JOB_NAME}'...${NC}"

    # Attendi che il bot finisca di scrivere la cache
    wait_for_safe_stop

    # Elimina il job schedulato
    if toolforge jobs show "$JOB_NAME" &>/dev/null; then
        toolforge jobs delete "$JOB_NAME"
        echo -e "${GREEN}Job schedulato '${JOB_NAME}' eliminato.${NC}"
    else
        echo -e "${YELLOW}Nessun job schedulato '${JOB_NAME}' trovato.${NC}"
    fi

    # Elimina anche eventuale job one-off in esecuzione
    if toolforge jobs show "$JOB_NAME_ONEOFF" &>/dev/null; then
        echo -e "${CYAN}Trovato job one-off '${JOB_NAME_ONEOFF}' in esecuzione, eliminazione...${NC}"
        toolforge jobs delete "$JOB_NAME_ONEOFF"
        echo -e "${GREEN}Job one-off '${JOB_NAME_ONEOFF}' eliminato.${NC}"
    fi

    echo -e "${GREEN}Bot fermato.${NC}"
}

# ------------------------------------------------------------
# Funzione: parsing parametro Xh Ym / Nm
# ------------------------------------------------------------
parse_param() {
    local param="$1"
    PARSED_MIN=-1
    PARSED_HOURS=1

    # Formato XhYm
    if [[ "$param" =~ ^([0-9]+)h([0-9]+)m$ ]]; then
        PARSED_HOURS="${BASH_REMATCH[1]}"
        PARSED_MIN="${BASH_REMATCH[2]}"
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
    echo -e "  Uso: ${YELLOW}./avvia_bot_toolforge.sh [Nm | XhYm | stop]${NC}"
    echo -e "  Esempi: 2m  |  0h15m  |  2h30m  |  stop"
    exit 1
}

# ============================================================
# MAIN
# ============================================================

# --- logs: mostra i log in tempo reale ---
if [ "$1" = "logs" ]; then
    show_logs
    exit 0
fi

# --- stop: ferma il job schedulato ---
if [ "$1" = "stop" ]; then
    echo -e "${CYAN}=== Bot VociRecenti — Arresto ===${NC}"
    echo -n "Confermi l'arresto del job schedulato? [s/N] "
    read -r risposta
    case "$risposta" in
        [sS]|[yY])
            stop_schedule
            ;;
        *)
            echo "Annullato."
            exit 0
            ;;
    esac
    exit 0
fi

# --- Nessun parametro: lancio immediato ---
if [ $# -eq 0 ]; then
    echo -e "${CYAN}=== Bot VociRecenti ===${NC}"
    echo -e "Nessun parametro — lancio immediato (esecuzione singola)."
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

# --- Parametro presente: configura job schedulato ---
echo -e "${CYAN}=== Bot VociRecenti — Configurazione schedulazione ===${NC}"
parse_param "$1"
echo -e "  Parametro:   ${YELLOW}$1${NC}"
echo -e "  Minuto cron: ${YELLOW}${PARSED_MIN}${NC}"
echo -e "  Ogni:        ${YELLOW}${PARSED_HOURS}h${NC}"
echo ""
echo -n "Confermi l'installazione della schedulazione? [s/N] "
read -r risposta
case "$risposta" in
    [sS]|[yY])
        install_schedule "$PARSED_MIN" "$PARSED_HOURS"
        echo -e "${GREEN}Fatto.${NC}"
        ;;
    *)
        echo "Annullato."
        exit 0
        ;;
esac
