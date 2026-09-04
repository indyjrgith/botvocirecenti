#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PulisciMovesCache.py

Ripulisce moves_cache.json del bot bot_voci_recenti_v30.py da entry di
rifiuto ("rejected") diventate obsolete.

BUG CORRETTO
------------
In get_moved_to_ns0_since_cutoff() (bot_voci_recenti_v30.py), una entry
'rejected' con reason 'not_exist', 'redirect' o 'ns<N>' blocca in modo
permanente (fino a scadenza naturale a 30 giorni) qualunque nuovo
spostamento legittimo verso NS0 con lo stesso titolo di destinazione,
anche quando l'evento di spostamento legittimo e' PIU' RECENTE del
rifiuto stesso. Questo script individua queste entry ancora bloccanti,
verifica se nel frattempo e' avvenuto un nuovo spostamento verso NS0
(target_ns == 0) con timestamp successivo a 'processed_at', e in tal
caso le rimuove dalla cache.

USO PRINCIPALE (da PowerShell in locale su Windows)
----------------------------------------------------
    python PulisciMovesCache.py
        Scarica moves_cache.json da Toolforge via SSH/SCP, analizza,
        mostra un report in DRY-RUN. Nessuna modifica remota.

    python PulisciMovesCache.py --apply
        Esegue la pulizia sul serio: backup remoto + locale, upload del
        file pulito su Toolforge, con conferma interattiva (Y/N) prima
        di sovrascrivere il file remoto.

USO ALTERNATIVO (direttamente su Toolforge, es. via launcher.sh)
------------------------------------------------------------------
    python PulisciMovesCache.py --toolforgeaslocal [--apply]
        Salta del tutto SSH/SCP: opera direttamente sul moves_cache.json
        locale nella cartella dello script (o BOT_DATA_DIR).

Nota tecnica sulla ricerca degli spostamenti piu' recenti: NON si puo'
usare site.logevents(page=<titolo_destinazione>), perche' il parametro
'page'/'letitle' dell'API filtra sul titolo SORGENTE del log (stessa
tecnica/limite documentato in bot_voci_recenti_v30.py, commento righe
~2942-2946). Si esegue quindi un'unica scansione globale del log
spostamenti (stessa tecnica di get_moved_to_ns0_since_cutoff), cercando
per ciascun evento se params['target_title'] corrisponde a uno dei
titoli candidati.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone

try:
    import pywikibot
except ImportError:
    print("ERRORE: il modulo 'pywikibot' non e' installato in questo Python.")
    print("Installalo con:  pip install pywikibot")
    sys.exit(1)


# ========================================
# FUSO ORARIO ITALIANO
# (replicato identico da bot_voci_recenti_v30.py, righe ~247-319)
# ========================================

import calendar as _calendar


def _last_sunday(year, month):
    last_day = _calendar.monthrange(year, month)[1]
    last_weekday = datetime(year, month, last_day).weekday()
    return last_day - (last_weekday - 6) % 7


def _it_offset_for_utc(dt_utc_naive):
    y = dt_utc_naive.year
    dst_start = datetime(y, 3, _last_sunday(y, 3), 1, 0, 0)
    dst_end = datetime(y, 10, _last_sunday(y, 10), 1, 0, 0)
    return 2 if dst_start <= dt_utc_naive < dst_end else 1


def ts_utc_to_it(ts):
    dt = ts.replace(tzinfo=None)
    return (dt + timedelta(hours=_it_offset_for_utc(dt))).strftime('%Y%m%d%H%M%S')


def now_it():
    utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
    return utc_now + timedelta(hours=_it_offset_for_utc(utc_now))


# ========================================
# CONFIGURAZIONE / DEFAULT
# ========================================

DATA_DIR = os.environ.get('BOT_DATA_DIR', os.path.dirname(os.path.abspath(__file__)))

DEFAULT_BASTION = 'login.toolforge.org'
DEFAULT_USER = 'IndyJr'
DEFAULT_TOOL_NAME = 'botvocirecenti'
DEFAULT_REMOTE_NAME = 'moves_cache.json'
DEFAULT_SLEEP = 0.3

# Reason 'rejected' da riconsiderare (vedi HANDOFF, punto 1 delle decisioni).
# Esclusi deliberatamente: 'too_old' e tutti i 'ns0_to_ns0_*' (gia' gestiti
# dalla whitelist _stale_reasons esistente nel bot, non toccare quella logica).
_CANDIDATE_REASONS_FIXED = {'not_exist', 'redirect'}
_CANDIDATE_REASON_NS_PATTERN = re.compile(r'^ns\d+$')

MAX_LOG_FETCH = 20000  # limite generoso per la scansione globale del log spostamenti


# ========================================
# ARGPARSE
# ========================================

def parse_args():
    p = argparse.ArgumentParser(
        description="Ripulisce moves_cache.json da entry 'rejected' obsolete che "
                    "bloccano spostamenti legittimi piu' recenti verso NS0.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  python PulisciMovesCache.py
      Dry-run: scarica da Toolforge, analizza, mostra report. Nessuna modifica.

  python PulisciMovesCache.py --apply
      Pulizia reale, con backup e conferma prima dell'upload su Toolforge.

  python PulisciMovesCache.py --toolforgeaslocal --apply
      Da eseguire direttamente su Toolforge: opera sul file locale, nessun SSH/SCP.
"""
    )
    p.add_argument('--apply', action='store_true',
                    help="Esegue davvero la pulizia (default: dry-run).")
    p.add_argument('--toolforgeaslocal', action='store_true',
                    help="Salta SSH/SCP, opera direttamente sul moves_cache.json locale.")
    p.add_argument('--sleep', type=float, default=DEFAULT_SLEEP,
                    help=f"Pausa (secondi) tra i controlli di progresso durante la "
                         f"scansione del log spostamenti (default: {DEFAULT_SLEEP}).")
    p.add_argument('--tool-name', default=DEFAULT_TOOL_NAME,
                    help=f"Nome breve del tool Toolforge (default: {DEFAULT_TOOL_NAME}).")
    p.add_argument('--tool-path', default=None,
                    help="Percorso remoto esplicito del tool (bypassa la risoluzione "
                         "automatica). Se omesso, si prova "
                         "/data/project/<tool-name>/<tool-name>/, poi "
                         "/data/project/<tool-name>/.")
    p.add_argument('--bastion', default=DEFAULT_BASTION,
                    help=f"Hostname del bastion SSH (default: {DEFAULT_BASTION}).")
    p.add_argument('--user', default=DEFAULT_USER,
                    help=f"Utente SSH (default: {DEFAULT_USER}).")
    p.add_argument('--remote-name', default=DEFAULT_REMOTE_NAME,
                    help=f"Nome del file remoto (default: {DEFAULT_REMOTE_NAME}).")
    p.add_argument('--cache-path', default=None,
                    help="Percorso locale esplicito di moves_cache.json. Con "
                         "--toolforgeaslocal, sovrascrive il default (DATA_DIR/"
                         "moves_cache.json). Senza --toolforgeaslocal, punta a un "
                         "file gia' scaricato manualmente (salta il download).")
    return p.parse_args()


# ========================================
# SSH / SCP (tecnica replicata da Deploy-Script.ps1)
# ========================================

def _run(cmd, **kwargs):
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def ssh_test(ssh_target, remote_path, flag):
    """flag: '-e' esiste, '-d' e' una directory."""
    r = _run(['ssh', ssh_target, f"test {flag} '{remote_path}'"])
    return r.returncode == 0


def resolve_tool_path(ssh_target, tool_name, tool_path_explicit):
    if tool_path_explicit:
        return tool_path_explicit.rstrip('/') + '/'
    candidate = f"/data/project/{tool_name}/{tool_name}/"
    if ssh_test(ssh_target, candidate, '-d'):
        return candidate
    return f"/data/project/{tool_name}/"


def scp_download(ssh_target, remote_full_path, local_path):
    print(f"Sorgente remota: {ssh_target}:{remote_full_path}")
    print(f"Destinazione locale: {local_path}")
    if not ssh_test(ssh_target, remote_full_path, '-e'):
        print(f"ERRORE: file remoto non trovato: {ssh_target}:{remote_full_path}")
        sys.exit(1)
    print("Download in corso...")
    r = _run(['scp', f"{ssh_target}:{remote_full_path}", local_path])
    if r.returncode != 0:
        print(f"ERRORE: scp fallito (exit code {r.returncode}).\n{r.stderr}")
        sys.exit(1)
    print(f"Download completato: {local_path}")


def remote_backup(ssh_target, tool_name, remote_full_path, ts):
    """Crea un backup del file remoto ORIGINALE prima di sovrascriverlo,
    solo se il file esiste gia' sul server."""
    if not ssh_test(ssh_target, remote_full_path, '-e'):
        print("  (nessun file remoto preesistente da salvare in backup)")
        return None
    backup_path = f"{remote_full_path}.bak-{ts}"
    cmd = f"become {tool_name} bash -c \"cp '{remote_full_path}' '{backup_path}'\""
    r = _run(['ssh', ssh_target, cmd])
    if r.returncode != 0:
        print(f"ERRORE: backup remoto fallito (exit code {r.returncode}).\n{r.stderr}")
        sys.exit(1)
    print(f"  Backup remoto creato: {backup_path}")
    return backup_path


def scp_upload_safe(ssh_target, tool_name, local_path, remote_full_path):
    """Upload sicuro via file temporaneo + become + chmod 644
    (tecnica identica a Deploy-Script.ps1, righe ~385-416)."""
    temp_remote_path = f"/tmp/deploy-{tool_name}-{uuid.uuid4().hex}-{os.path.basename(remote_full_path)}"

    print("Copia in corso (via temporaneo)...")
    r = _run(['scp', local_path, f"{ssh_target}:{temp_remote_path}"])
    if r.returncode != 0:
        print(f"ERRORE: scp fallito (exit code {r.returncode}).\n{r.stderr}")
        sys.exit(1)

    print(f"Attribuzione file e permessi 644 (come {tool_name})...")
    become_cmd = (
        f"become {tool_name} bash -c "
        f"\"rm -f '{remote_full_path}' && cp '{temp_remote_path}' '{remote_full_path}' "
        f"&& chmod 644 '{remote_full_path}'\""
    )
    r = _run(['ssh', ssh_target, become_cmd])
    become_rc = r.returncode
    become_err = r.stderr

    # Pulizia del temporaneo (come utente personale, che lo possiede)
    _run(['ssh', ssh_target, f"rm -f '{temp_remote_path}'"])

    if become_rc != 0:
        print(f"ERRORE: attribuzione/chmod falliti (exit code {become_rc}).\n{become_err}")
        print(f"Verifica di far parte del gruppo maintainer del tool '{tool_name}'.")
        sys.exit(1)

    r = _run(['ssh', ssh_target, f"ls -l '{remote_full_path}'"])
    print("Verifica:")
    print(r.stdout.strip())
    print(f"Upload completato: {remote_full_path}")


# ========================================
# CACHE: caricamento / scrittura / backup locale
# ========================================

def load_cache_raw(path):
    """Carica moves_cache.json senza applicare il filtro di scadenza a 30gg
    (quello e' compito esclusivo del bot in load_moves_cache): qui vogliamo
    vedere ed eventualmente correggere anche le entry 'rejected' ancora
    formalmente valide ma diventate obsolete per il bug."""
    if not os.path.exists(path):
        print(f"ERRORE: file non trovato: {path}")
        sys.exit(1)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"ERRORE: impossibile leggere {path}: {e}")
        sys.exit(1)


def save_cache(path, cache):
    """Stesso formato esatto di save_moves_cache() nel bot."""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=None, separators=(',', ':'))


def backup_local_file(path, ts):
    if os.path.exists(path):
        backup_path = f"{path}.bak-{ts}"
        shutil.copy2(path, backup_path)
        print(f"  Backup locale creato: {backup_path}")
        return backup_path
    return None


# ========================================
# LOGICA DI ANALISI
# ========================================

def is_candidate_entry(entry):
    """True se l'entry e' 'rejected' con reason tra quelle da riconsiderare
    (not_exist, redirect, ns<N>). Esclude __touched__:* (che non hanno
    'result') e i ns0_to_ns0_* (gia' gestiti dalla whitelist del bot)."""
    if not isinstance(entry, dict):
        return False
    if entry.get('result') != 'rejected':
        return False
    reason = entry.get('reason', '')
    if reason in _CANDIDATE_REASONS_FIXED:
        return True
    if _CANDIDATE_REASON_NS_PATTERN.match(reason):
        return True
    return False


def find_newer_ns0_moves(site, candidates, sleep_seconds):
    """
    Scansione UNICA e globale del log spostamenti (stessa tecnica di
    get_moved_to_ns0_since_cutoff in bot_voci_recenti_v30.py), alla ricerca,
    per ciascun titolo candidato, di un evento con target_title == titolo
    e target_ns == 0, con timestamp (IT) piu' recente di processed_at.

    candidates: dict {titolo: processed_at_str}
    Ritorna: dict {titolo: found_timestamp_str} solo per i titoli per cui
    e' stato trovato un evento piu' recente qualificante.
    """
    if not candidates:
        return {}

    oldest_processed_at = min(candidates.values())
    still_open = set(candidates.keys())
    found = {}

    checked = 0
    print(f"  Scansione log spostamenti (fino a processed_at piu' vecchio: "
          f"{oldest_processed_at})...")

    try:
        logs = site.logevents(logtype='move', total=MAX_LOG_FETCH)
        for log in logs:
            if not still_open:
                break
            checked += 1
            if checked % 200 == 0:
                print(f"    ...{checked} eventi controllati, "
                      f"{len(found)} trovati, {len(still_open)} ancora da verificare")
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)

            log_ts = log.timestamp()
            move_ts_str = ts_utc_to_it(log_ts)
            if move_ts_str < oldest_processed_at:
                # Oltre il piu' vecchio processed_at tra i candidati: da qui in
                # poi non puo' piu' esserci un evento "piu' recente" utile.
                break

            try:
                params = log.data.get('params', log.data)
                target_title = params.get('target_title', '')
                if not target_title or target_title not in still_open:
                    continue

                processed_at = candidates[target_title]
                if move_ts_str <= processed_at:
                    continue

                target_ns = int(params.get('target_ns', -1))
                if target_ns == -1:
                    # Fallback se il campo non e' presente (API piu' vecchie)
                    target_ns = int(pywikibot.Page(site, target_title).namespace())

                if target_ns == 0:
                    found[target_title] = move_ts_str
                    still_open.discard(target_title)
            except Exception:
                continue
    except Exception as e:
        print(f"  ERRORE durante la scansione del log spostamenti: {e}")

    print(f"  Scansione completata: {checked} eventi controllati, "
          f"{len(found)}/{len(candidates)} candidati risolti.")
    return found


# ========================================
# MAIN
# ========================================

def main():
    args = parse_args()
    ts = now_it().strftime('%Y%m%d%H%M%S')

    temp_dir = None
    ssh_target = None
    tool_path = None
    remote_full_path = None

    # --- Determina il percorso locale di lavoro ---
    if args.cache_path:
        local_path = args.cache_path
        if not args.toolforgeaslocal and not os.path.exists(local_path):
            print(f"ERRORE: --cache-path indicato ma il file non esiste: {local_path}")
            sys.exit(1)
    elif args.toolforgeaslocal:
        local_path = os.path.join(DATA_DIR, 'moves_cache.json')
    else:
        temp_dir = tempfile.mkdtemp(prefix='pulisci_moves_cache_')
        local_path = os.path.join(temp_dir, 'moves_cache.json')

    try:
        # --- Download da Toolforge (se applicabile) ---
        if not args.toolforgeaslocal and not (args.cache_path and os.path.exists(args.cache_path)):
            ssh_target = f"{args.user}@{args.bastion}"
            tool_path = resolve_tool_path(ssh_target, args.tool_name, args.tool_path)
            remote_full_path = f"{tool_path}{args.remote_name}"
            scp_download(ssh_target, remote_full_path, local_path)
        elif not args.toolforgeaslocal:
            # --cache-path esplicito che esiste gia': salta il download,
            # ma servono comunque ssh_target/remote_full_path per un eventuale --apply.
            ssh_target = f"{args.user}@{args.bastion}"
            tool_path = resolve_tool_path(ssh_target, args.tool_name, args.tool_path)
            remote_full_path = f"{tool_path}{args.remote_name}"

        # --- Carica e analizza ---
        cache = load_cache_raw(local_path)
        print(f"\nEntry totali in moves_cache: {len(cache)}")

        candidates = {title: entry.get('processed_at', '0')
                       for title, entry in cache.items() if is_candidate_entry(entry)}
        print(f"Entry 'rejected' candidate (not_exist / redirect / ns<N>): {len(candidates)}")

        if not candidates:
            print("\nNessuna entry candidata trovata: niente da fare.")
            return

        site = pywikibot.Site('it', 'wikipedia')
        found = find_newer_ns0_moves(site, candidates, args.sleep)

        # --- Report ---
        print("\n=== REPORT ===")
        removed_titles = []
        kept_titles = []
        for title, processed_at in candidates.items():
            reason = cache[title].get('reason', '?')
            if title in found:
                print(f"  RIMOSSA   '{title}' (reason='{reason}', processed_at={processed_at}) "
                      f"-> trovato spostamento NS0 piu' recente del {found[title]}")
                removed_titles.append(title)
            else:
                print(f"  MANTENUTA '{title}' (reason='{reason}', processed_at={processed_at}) "
                      f"-> nessun evento NS0 piu' recente trovato")
                kept_titles.append(title)

        print(f"\nTotale candidate: {len(candidates)} | da rimuovere: {len(removed_titles)} "
              f"| mantenute: {len(kept_titles)}")

        if not args.apply:
            print("\n[DRY-RUN] Nessuna modifica effettuata. Rilancia con --apply per "
                  "applicare davvero la pulizia.")
            return

        if not removed_titles:
            print("\nNessuna modifica da applicare (nessuna entry da rimuovere).")
            return

        # --- Applica le modifiche ---
        cleaned_cache = {t: v for t, v in cache.items() if t not in removed_titles}

        if args.toolforgeaslocal:
            risposta = input(f"\nConfermi la scrittura di {local_path} "
                              f"({len(removed_titles)} entry rimosse)? (S/N): ")
            if not re.match(r'^[Ss]$', risposta.strip()):
                print("Operazione annullata.")
                return
            backup_local_file(local_path, ts)
            save_cache(local_path, cleaned_cache)
            print(f"File locale aggiornato: {local_path} ({len(cleaned_cache)} entry salvate)")
        else:
            risposta = input(f"\nConfermi l'upload su {ssh_target}:{remote_full_path} "
                              f"({len(removed_titles)} entry rimosse)? (S/N): ")
            if not re.match(r'^[Ss]$', risposta.strip()):
                print("Operazione annullata.")
                return
            backup_local_file(local_path, ts)
            save_cache(local_path, cleaned_cache)
            print("\nBackup remoto del file originale...")
            remote_backup(ssh_target, args.tool_name, remote_full_path, ts)
            scp_upload_safe(ssh_target, args.tool_name, local_path, remote_full_path)

    finally:
        if temp_dir and os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == '__main__':
    main()
