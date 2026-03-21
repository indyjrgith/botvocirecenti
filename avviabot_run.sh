#!/data/data/com.termux/files/usr/bin/bash
# avviabot_run.sh - Wrapper lanciato da cron
# Avvia il bot in una nuova finestra tmux e porta Termux in foreground

BOT_DIR="$HOME/storage/downloads/botvocirecenti"
BOT_SCRIPT="bot_voci_recenti_v30.py"
BOT_CMD="/data/data/com.termux/files/usr/bin/python3 $BOT_DIR/$BOT_SCRIPT"
TMUX_SESSION="botvoci"
WIN_NAME="bot-$(date +%H%M)"

# Crea sessione tmux se non esiste, altrimenti nuova finestra
if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
    tmux new-window -t "$TMUX_SESSION" -n "$WIN_NAME" \
        "$BOT_CMD; echo ''; echo '=== Bot terminato - premi Invio ==='; read; exit"
    tmux select-window -t "$TMUX_SESSION:$WIN_NAME"
else
    tmux new-session -d -s "$TMUX_SESSION" -n "$WIN_NAME" \
        "$BOT_CMD; echo ''; echo '=== Bot terminato - premi Invio ==='; read; exit"
fi

# Porta Termux in foreground aprendo una nuova sessione con tmux attach
sleep 1
am start --user 0 -n com.termux/.app.TermuxActivity \
    --es com.termux.app.EXTRA_ARGUMENTS "tmux attach -t botvoci" \
    > /dev/null 2>&1
