#!/usr/bin/env python3
"""
Bot VociRecenti v8.35

Changelog:
- v8.36: FIX check_deleted_pages: rimosso redirects=True dalla query API batch.
         Con redirects=True MediaWiki seguiva i redirect restituendo la pagina
         di destinazione, nascondendo il flag 'redirect' e impedendo la rimozione
         delle voci diventate redirect dalla cache.
- v8.35: STEP 6: filtra cached_pages rimuovendo voci con eta' > MAX_AGE_DAYS.
         Usa move_timestamp se presente (voci da sandbox spostate di recente),
         altrimenti timestamp di creazione. Impedisce che voci vecchie rimangano
         in cache indefinitamente senza dover eseguire PuliziaCache.
         format_lua_row: aggiunto 6° campo move_timestamp (stringa vuota se assente),
         ignorato dal modulo Lua (retrocompatibile).
         download_page_data: salva move_timestamp nel record se disponibile.
- v8.34: FIX validate_ns_or_manual_page: le voci da NS2/NS118 venivano sempre
         accettate indipendentemente dalla data di creazione NS0 (ref_date=now()
         era sempre > cutoff_date). Ora usa la data di creazione della voce NS0,
         coerentemente con download_page_data. MAX_PAGES aggiornato a 3500.
- v8.33: STEP 7: ottimizzata validate_lua_longstrings — usa re.finditer
         invece del loop carattere per carattere, eliminando il lag prima
         di ogni salvataggio file.
- v8.32: STEP 6: dedup esplicito dopo il filtro remove_set: in caso di titoli
         duplicati, viene mantenuto il record presente in pages_to_update
         (aggiornato da Aggiorna:) invece del record vecchio dalla cache.
- v8.31: Aggiorna: esegue purge della pagina prima di rileggere i metadati,
         garantendo categorie aggiornate anche se l'indice Wikipedia e' in ritardo.
- v8.30: STEP 3b: controllo voci cancellate/redirect via API batch (CheckDeleted)
- v8.29: FIX STEP 6: Aggiorna: non eliminava il record aggiornato (bug remove_set)
- v8.28: CacheMoved: accetta URL Wikipedia come input
         (es. https://it.wikipedia.org/wiki/Titolo o link con ?action=edit&redlink=1).
         Funziona anche nei comandi Aggiorna: e Rimuovi:.
- v8.27: AGGIUNTO timer per split_pages_into_files, format_lua_data e
         blank_old_data_files per identificare il tempo nascosto in STEP 7.
- v8.26: FIX blank_old_data_files: range di controllo ridotto da +10 a +2,
         elimina ~5 minuti di attesa su chiamate API per pagine inesistenti.
- v8.25: AGGIUNTO timer per ogni singolo salvataggio file in STEP 7.
- v8.24: AGGIUNTO timer per ogni STEP nel main(): durata stampata a fine
         di ogni step e tempo totale nel riepilogo finale.
- v8.23: CacheMoved: aggiunto comando 'Aggiorna: Titolo' per forzare il
         refresh dei metadati (categorie, template, preview) di una voce gia'
         in cache. Se la pagina non esiste piu', la rimuove automaticamente.
         Se non era in cache, la aggiunge.
- v8.22: FIX voci lavorate in bozza/sandbox per mesi e poi spostate in NS0:
         download_page_data ora usa il timestamp dello spostamento (non la data
         di creazione) per il controllo eta', accettando voci vecchie spostate
         di recente. Per voci da NS2/NS118 e CacheMoved il controllo eta' usa
         la data odierna, poiche' per definizione sono state trovate oggi.
- v8.21: moves_cache salvato su disco ogni 200 voci processate (checkpoint)
         invece che solo alla fine, per resistere a interruzioni del bot.
- v8.20: ESTESO moves_cache a scan_and_load_ns_pages e validate_ns_or_manual_page:
         le voci NS0 derivate gia' rifiutate (no_ns0, redirect, too_old) vengono
         saltate senza chiamate API nei run successivi, eliminando il collo di
         bottiglia con migliaia di titoli NS2/NS118 da rivalidare ogni run.
         FIX validate_ns_or_manual_page: ora restituisce formato nuovo con
         templates e preview invece di contenuto grezzo.
- v8.19: AGGIUNTO moves_cache.json: cache locale degli spostamenti gia' processati.
         Le voci rifiutate (non NS0, non esistenti, ecc.) vengono saltate senza
         chiamate API nei run successivi. Le voci accettate vengono sempre
         riverificate per gestire spostamenti inversi o uscite da NS0.
         ESTESO moves_cache a download_page_data: registra anche i rifiuti per
         too_old, not_exist e redirect, cosi' le voci spostate ma antiche non
         vengono riverificate via API ad ogni run.
- v8.17: FIX parse_templates_from_wikitext: rimuove graffe residue {{ }}
         da nomi e valori dei parametri template (es. 'zucchero}}' -> 'zucchero').
- v8.16: Invertito ordine ricerca: NS0 (RecentChanges) prima, NS2/NS118 dopo.
         NS0 e' la fonte principale, gli altri namespace sono casi speciali.
- v8.15: FIX parse_lua_to_json: ora riconosce sia il nuovo formato (d={...})
         che il vecchio (voci={...}). Il bot leggeva 0 voci dalla cache
         nel nuovo formato causando ricostruzione completa ad ogni run.
         FIX parse_lua_to_json: il nuovo formato usa parsing veloce per righe
         (ogni voce e' su una riga) invece di iterare carattere per carattere
         su 2MB, evitando blocco del processo durante la lettura della cache.
- v8.14: AGGIUNTA validate_lua_longstrings per individuare voci con long string
         non bilanciati prima del salvataggio.
- v8.13: FIX change['title'] e change['timestamp'] in scansione NS0 e NS2/NS118:
         ora usa .get() con skip esplicito se title e' vuoto.
- v8.12: FIX split_pages_into_files: dimensione calcolata sul Lua reale (format_lua_row)
         invece di stima, evita superamento limite 2MB di Wikipedia.
         Estratta funzione format_lua_row riutilizzata da split e format_lua_data.
- v8.11: NUOVO formato cache compatto (array posizionale) al posto del formato
         con keyword ripetute: {titolo,timestamp,{cat},{{tmpl,{params}}},preview}
         RIMOSSO campo contenuto completo: sostituito con template estratti
         dal wikitesto (nome + nomi parametri valorizzati) e preview 100 char.
         AGGIUNTO parse_templates_from_wikitext: estrae template di primo
         livello, conserva parametri posizionali valorizzati, scarta parametri
         named vuoti.
         COMPATIBILITA' RETROATTIVA: parse_single_voce rileva automaticamente
         il vecchio formato (keyword) e lo legge tramite parse_single_voce_legacy,
         permettendo la transizione senza reset della cache.
- v8.10: STEP 5 riscritto: scorre RecentChanges NS0 dall'inizio fino al
         cutoff_date raccogliendo TUTTE le voci non in cache nell'arco.
         Stesso approccio per il log degli spostamenti in NS0 (ora cattura
         anche ridenominazioni e inversioni di redirect NS0->NS0).
         Il troncamento a MAX_PAGES avviene solo nello STEP 6 dopo l'unione.
- v8.8:  FIX logica spostamenti: log.page() e' la sorgente, target_title la
         destinazione (erano invertiti in v8.7).
- v8.7:  CacheMoved torna ad essere cache MANUALE (input), non output del bot.
         Supporto RIMOZIONE: righe che iniziano con "Rimuovi:" rimuovono la
         voce dalla cache. CacheParsed controlla SOLO CacheMoved.
         Scansione NS2/NS118 eseguita ad ogni run indipendentemente.
- v8.6:  SOSTITUITA cache manuale CacheMoved con scansione automatica.
         (versione intermedia, sostituita da v8.7)
- v8.5:  Fix logica RecentChanges: raccoglie TUTTE le voci nuove fino al
         timestamp di riferimento, troncamento a MAX_PAGES solo alla fine.
- v8.4:  AGGIUNTO sistema AutoClean per eseguire PuliziaCache.py automaticamente
         una volta per fascia oraria configurata.
         AutoClean = 'Once'  → pulizia eseguita una sola volta per fascia oraria.
         AutoClean = 'Every' → pulizia eseguita ad ogni run del bot.
         AutoClean = 'None'  → pulizia mai eseguita.
- v8.3:  FIX parser Lua: il conteggio delle graffe ora salta correttamente
         il contenuto dei long string Lua [[ ]], [=[ ]=], ecc.
- v8.2:  FIX parser Lua: rimossa regex fragile per trovare sezione voci,
         sostituita con conteggio bilanciato delle graffe.
- v8.1:  AGGIUNTO filtro data creazione: scarta voci piu' vecchie del limite.
         Limite = max(30 giorni fa, timestamp voce piu' vecchia in cache).
         Filtro applicato sia su RecentChanges che su cache manuale.
- v8.0:  RIMOSSA logica di pulizia cache interna (affidata a PuliziaCache.py).
         AGGIUNTO flag RUN_CLEANUP per eseguire PuliziaCache.py all'avvio.
         AGGIUNTO sistema CacheParsed per evitare di riprocessare la cache manuale.
         AGGIUNTO controllo duplicati in tutti i punti di aggiunta voci.
"""

import pywikibot
import pywikibot.config as config
from datetime import datetime, timedelta
import re
from urllib.parse import unquote
import json
import os
import subprocess
import sys
import logging

# ========================================
# CONFIGURAZIONE
# ========================================
MAX_PAGES = 3000                            # Totale voci da mantenere
MAX_CHARS_PER_FILE = 1500000               # ~1.5MB per file
DATA_PAGE_PREFIX = 'Modulo:VociRecenti/Dati'
NAMESPACE = 0
MAX_ITERATIONS = 100
TIMEOUT = 300
VERSION = '8.36'
MAX_AGE_DAYS = 30       
config.put_throttle = 1
config.minthrottle = 0
config.maxthrottle = 2
# Scarta voci create piu' di N giorni fa

# --- Configurazione pulizia automatica ---
# 'Once'  = una volta per fascia oraria (comportamento default)
# 'Every' = ad ogni esecuzione del bot
# 'None'  = mai
AutoClean = 'Once'

# Fascia oraria in cui eseguire la pulizia (formato 'HH:MM')
# La fascia puo' attraversare la mezzanotte (es. '23:00' - '01:00')
AutoCleanTimeBegin = '02:00'
AutoCleanTimeEnd   = '05:00'

# File di stato per AutoClean = 'Once'
# Viene creato nella stessa cartella del bot
CLEANUP_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cleanup_state.json')

# File di cache locale per gli spostamenti già processati
# Evita di riverificare via API gli spostamenti rifiutati nei run precedenti
MOVES_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'moves_cache.json')
MOVES_CACHE_MAX_AGE_DAYS = 30  # Rimuovi entry più vecchie di N giorni

# Script di pulizia (nella stessa cartella del bot)
PULIZIA_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'PuliziaCache.py')

# Versione minima richiesta di PuliziaCache.py
# Il bot rifiuta di eseguire PuliziaCache se la versione presente è inferiore
REQUIRED_PULIZIA_VERSION = 'PC-2.0'

# File di log (nella stessa cartella del bot)
# L'output viene scritto sia a video che nel file di log
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bot_voci_recenti.log')
LOG_MAX_BYTES = 2 * 1024 * 1024  # 2 MB: se superato, viene troncato tenendo la parte finale

# Controllo voci cancellate/redirect ad ogni run del bot
# True  = controlla tutte le voci in cache via API batch (50 titoli per chiamata)
# False = skip (le voci cancellate vengono rimosse solo dalla PuliziaCache notturna)
CheckDeleted = True
BATCH_SIZE_CHECK = 50   # Titoli per chiamata API (max 50 per account bot)

# Namespace da scansionare per voci spostate in NS0
# NS2 = Utente, NS118 = Bozze
NS_SCAN = [2, 118]

# Cache voci da altri namespace (aggiornata automaticamente dal bot)
CACHE_MOVED_PAGE = 'Utente:BotVociRecenti/CacheMoved'
CACHE_PARSED_PAGE = 'Utente:BotVociRecenti/CacheParsed'
# ========================================


SITE = pywikibot.Site('it', 'wikipedia')


# ========================================
# LOGICA AUTOCLEAN
# ========================================

def _parse_hhmm(s):
    """Converte una stringa 'HH:MM' in un oggetto time."""
    h, m = s.strip().split(':')
    return datetime.now().replace(hour=int(h), minute=int(m), second=0, microsecond=0)


def _in_time_window(begin_str, end_str):
    """
    Restituisce True se l'ora corrente e' nella fascia [begin, end).
    Gestisce correttamente le fasce che attraversano la mezzanotte.
    """
    now = datetime.now()
    begin = _parse_hhmm(begin_str)
    end   = _parse_hhmm(end_str)

    now_t   = (now.hour,   now.minute)
    begin_t = (begin.hour, begin.minute)
    end_t   = (end.hour,   end.minute)

    if begin_t <= end_t:
        # Fascia normale (es. 03:00 - 05:00)
        return begin_t <= now_t < end_t
    else:
        # Fascia a cavallo della mezzanotte (es. 23:00 - 01:00)
        return now_t >= begin_t or now_t < end_t


def _load_cleanup_state():
    """Carica lo stato di pulizia dal file JSON. Restituisce un dict."""
    if not os.path.exists(CLEANUP_STATE_FILE):
        return {'cleaned_today': False}
    try:
        with open(CLEANUP_STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'cleaned_today': False}


def _save_cleanup_state(state):
    """Salva lo stato di pulizia nel file JSON."""
    try:
        with open(CLEANUP_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"  WARNING: impossibile salvare cleanup_state.json: {e}")


def load_moves_cache():
    """
    Carica il file moves_cache.json e rimuove le entry più vecchie di
    MOVES_CACHE_MAX_AGE_DAYS giorni. Restituisce un dict:
      {titolo: {'processed_at': 'YYYYMMDDHHMMSS', 'result': 'accepted'|'rejected', 'reason': str}}
    """
    cache = {}
    if os.path.exists(MOVES_CACHE_FILE):
        try:
            with open(MOVES_CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
        except Exception as e:
            print(f"  WARNING: impossibile leggere moves_cache.json: {e}")
            cache = {}

    # Rimuovi entry troppo vecchie
    cutoff = (datetime.now() - timedelta(days=MOVES_CACHE_MAX_AGE_DAYS)).strftime('%Y%m%d%H%M%S')
    before = len(cache)
    cache = {t: v for t, v in cache.items() if v.get('processed_at', '0') >= cutoff}
    removed = before - len(cache)
    if removed > 0:
        print(f"  moves_cache: {len(cache)} entry ({removed} scadute rimosse)")
    else:
        print(f"  moves_cache: {len(cache)} entry")
    return cache


def save_moves_cache(cache):
    """Salva il dict moves_cache nel file JSON."""
    try:
        with open(MOVES_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=None, separators=(',', ':'))
        print(f"  moves_cache: salvate {len(cache)} entry")
    except Exception as e:
        print(f"  WARNING: impossibile salvare moves_cache.json: {e}")


def checkpoint_moves_cache(cache, counter, interval=200):
    """Salva moves_cache ogni 'interval' chiamate. Chiamare passando il contatore
    incrementato ad ogni voce processata. Restituisce il contatore aggiornato."""
    if counter % interval == 0:
        save_moves_cache(cache)
    return counter


def should_run_cleanup():
    """
    Determina se PuliziaCache.py deve essere eseguito in questo run.

    AutoClean = 'Every' → sempre True
    AutoClean = 'None'  → sempre False
    AutoClean = 'Once'  →
        - Se siamo nella fascia oraria E la pulizia non e' ancora
          stata fatta in questa fascia → True, poi setta il flag.
        - Se siamo nella fascia oraria E la pulizia e' gia' stata
          fatta → False.
        - Se siamo fuori fascia oraria → False, e resetta il flag
          in modo che alla prossima fascia la pulizia venga rieseguita.
    """
    if AutoClean == 'Every':
        print(f"  AutoClean=Every -> pulizia sempre eseguita")
        return True

    if AutoClean == 'None':
        print(f"  AutoClean=None -> pulizia mai eseguita")
        return False

    # AutoClean == 'Once'
    in_window = _in_time_window(AutoCleanTimeBegin, AutoCleanTimeEnd)
    state = _load_cleanup_state()

    if not in_window:
        # Fuori fascia: resetta il flag se era True
        if state.get('cleaned_today', False):
            state['cleaned_today'] = False
            _save_cleanup_state(state)
            print(f"  AutoClean=Once, fuori fascia ({AutoCleanTimeBegin}-{AutoCleanTimeEnd}) -> flag resettato")
        else:
            print(f"  AutoClean=Once, fuori fascia ({AutoCleanTimeBegin}-{AutoCleanTimeEnd}) -> skip")
        return False

    # Siamo in fascia
    if state.get('cleaned_today', False):
        print(f"  AutoClean=Once, in fascia ({AutoCleanTimeBegin}-{AutoCleanTimeEnd}) -> pulizia gia' eseguita, skip")
        return False

    # In fascia e non ancora eseguita
    print(f"  AutoClean=Once, in fascia ({AutoCleanTimeBegin}-{AutoCleanTimeEnd}) -> eseguo pulizia")
    state['cleaned_today'] = True
    _save_cleanup_state(state)
    return True

def run_cleanup():
    """Esegue PuliziaCache.py con output in tempo reale."""
    if not os.path.exists(PULIZIA_SCRIPT):
        print(f"  ERRORE: script non trovato: {PULIZIA_SCRIPT}")
        return False

    print(f"  Esecuzione: {PULIZIA_SCRIPT}")
    result = subprocess.run(
        [sys.executable, PULIZIA_SCRIPT]
    )

    if result.returncode != 0:
        print(f"  ERRORE pulizia (exit {result.returncode})")
        return False

    print("  OK Pulizia completata")
    return True


# ========================================
# LOG SU FILE + CONTROLLO VERSIONE PULIZIA
# ========================================

class _Tee:
    """
    Sostituisce sys.stdout reindirizzando ogni write() sia al terminale
    che al file di log, senza buffering aggiuntivo.
    """
    def __init__(self, stream, log_path):
        self._stream = stream
        self._log_path = log_path
        self._file = None
        try:
            self._file = open(log_path, 'a', encoding='utf-8')
        except Exception as e:
            print(f"WARNING: impossibile aprire il file di log {log_path}: {e}", file=stream)

    def write(self, data):
        self._stream.write(data)
        if self._file:
            try:
                self._file.write(data)
                self._file.flush()
            except Exception:
                pass

    def flush(self):
        self._stream.flush()
        if self._file:
            try:
                self._file.flush()
            except Exception:
                pass

    def close(self):
        if self._file:
            try:
                self._file.close()
            except Exception:
                pass
        self._file = None

    def __getattr__(self, name):
        return getattr(self._stream, name)


def setup_log():
    """
    Attiva il logging su file affiancato all'output a video.
    Se il file di log supera LOG_MAX_BYTES, viene troncato tenendo
    la parte finale (i messaggi piu' recenti).
    Restituisce l'oggetto _Tee per poterlo chiudere a fine run.
    """
    if os.path.exists(LOG_FILE):
        try:
            size = os.path.getsize(LOG_FILE)
            if size > LOG_MAX_BYTES:
                with open(LOG_FILE, 'rb') as f:
                    f.seek(-LOG_MAX_BYTES, 2)
                    tail = f.read()
                nl = tail.find(b'\n')
                if nl != -1:
                    tail = tail[nl + 1:]
                with open(LOG_FILE, 'wb') as f:
                    f.write(b'[... log troncato ...]\n')
                    f.write(tail)
        except Exception as e:
            print(f"WARNING: impossibile troncare il log: {e}")

    tee = _Tee(sys.stdout, LOG_FILE)
    sys.stdout = tee
    return tee


def check_pulizia_version():
    """
    Legge la versione di PuliziaCache.py e la confronta con REQUIRED_PULIZIA_VERSION.
    Stampa un messaggio di stato e restituisce True se la versione e' quella richiesta,
    False altrimenti (in tal caso run_cleanup non verra' eseguita).
    """
    if not os.path.exists(PULIZIA_SCRIPT):
        print(f"  WARNING: PuliziaCache.py non trovato: {PULIZIA_SCRIPT}")
        return False

    present_version = None
    try:
        with open(PULIZIA_SCRIPT, 'r', encoding='utf-8') as f:
            for line in f:
                m = re.match(r"^\s*VERSION\s*=\s*['\"](.+?)['\"]", line)
                if m:
                    present_version = m.group(1)
                    break
    except Exception as e:
        print(f"  WARNING: impossibile leggere PuliziaCache.py: {e}")
        return False

    if present_version is None:
        print(f"  WARNING: VERSION non trovata in PuliziaCache.py")
        return False

    if present_version == REQUIRED_PULIZIA_VERSION:
        print(f"  PuliziaCache.py versione richiesta {REQUIRED_PULIZIA_VERSION} "
              f"versione presente {present_version}, OK")
        return True
    else:
        print(f"  === ATTENZIONE === PuliziaCache.py non valida, "
              f"versione richiesta {REQUIRED_PULIZIA_VERSION} "
              f"versione presente {present_version}, non verra' caricata")
        return False

# ========================================
# CALCOLO DATA LIMITE
# ========================================

def compute_cutoff_date(cached_pages):
    """
    Calcola la data limite per accettare nuove voci.
    E' il MASSIMO tra:
    - 30 giorni fa (MAX_AGE_DAYS)
    - timestamp della voce piu' VECCHIA gia' in cache
    """
    cutoff_30 = datetime.now() - timedelta(days=MAX_AGE_DAYS)

    if not cached_pages:
        print(f"  Limite data: {cutoff_30.strftime('%d/%m/%Y')} (30 giorni fa, cache vuota)")
        return cutoff_30

    oldest_in_cache = min(cached_pages, key=lambda x: x.get('timestamp', '99999999999999'))
    oldest_ts_str = oldest_in_cache.get('timestamp', '')

    try:
        oldest_dt = datetime.strptime(oldest_ts_str, '%Y%m%d%H%M%S')
    except Exception:
        print(f"  Limite data: {cutoff_30.strftime('%d/%m/%Y')} (fallback 30 giorni)")
        return cutoff_30

    cutoff = max(cutoff_30, oldest_dt)

    if cutoff == oldest_dt:
        print(f"  Limite data: {cutoff.strftime('%d/%m/%Y')} "
              f"(voce piu' vecchia in cache: '{oldest_in_cache.get('titolo', 'N/A')}')")
    else:
        print(f"  Limite data: {cutoff.strftime('%d/%m/%Y')} (30 giorni fa)")

    return cutoff


# ========================================
# CACHE PARSED
# ========================================

def check_should_load_manual_cache():
    """
    Verifica se caricare la cache manuale.
    Returns True se deve essere caricata, False se gia' processata.
    """
    try:
        page = pywikibot.Page(SITE, CACHE_PARSED_PAGE)
        if not page.exists():
            return True
        content = page.text.strip()
        if content != "True":
            return True
        return False
    except Exception:
        return True


def mark_manual_cache_as_parsed():
    """Marca la cache manuale come gia' processata scrivendo 'True' in CacheParsed."""
    try:
        page = pywikibot.Page(SITE, CACHE_PARSED_PAGE)
        page.text = "True"
        page.save(summary="Bot: Cache manuale processata", minor=True)
        print(f"  OK Marcata cache manuale come processata")
    except Exception as e:
        print(f"  ERRORE marcatura CacheParsed: {e}")


# ========================================
# CARICAMENTO CACHE
# ========================================

def get_all_data_pages():
    """Trova tutti i file Dati esistenti (Dati1, Dati2, Dati3, ...)"""
    data_pages = []
    i = 1
    while True:
        page_name = f"{DATA_PAGE_PREFIX}{i}"
        page = pywikibot.Page(SITE, page_name)
        if page.exists():
            data_pages.append(page_name)
            i += 1
        else:
            break
    return data_pages


def skip_lua_longstring(text, pos):
    """
    Se in posizione pos inizia un long string Lua [=*[, restituisce
    la posizione subito dopo la chiusura corrispondente ]=*].
    Altrimenti restituisce None.
    """
    ls_match = re.match(r'\[=*\[', text[pos:])
    if not ls_match:
        return None
    open_delim = ls_match.group(0)
    eq_count = open_delim.count('=')
    close_delim = ']' + '=' * eq_count + ']'
    close_pos = text.find(close_delim, pos + len(open_delim))
    if close_pos == -1:
        return None
    return close_pos + len(close_delim)


def find_balanced_braces(text, start):
    """
    Partendo da start (che deve essere la posizione di una '{'),
    trova la '}' di chiusura bilanciata ignorando le graffe
    dentro i long string Lua.
    Restituisce l'indice della '}' di chiusura, o None se non trovata.
    """
    level = 0
    i = start

    while i < len(text):
        char = text[i]

        next_pos = skip_lua_longstring(text, i)
        if next_pos is not None:
            i = next_pos
            continue

        if char == '{':
            level += 1
        elif char == '}':
            level -= 1
            if level == 0:
                return i

        i += 1

    return None


def parse_lua_to_json(lua_content):
    """
    Converte contenuto Lua in struttura Python.
    Rileva il formato automaticamente:
    - Nuovo formato (d={...}): ogni voce è su una riga -> parsing veloce per righe
    - Vecchio formato (voci={...}): parsing bilanciato delle graffe (lento ma raro)
    """
    voci = []

    # Rileva quale chiave contiene l'array voci
    m_new = re.search(r'(?<![a-zA-Z_])d\s*=\s*\{', lua_content)
    m_old = re.search(r'voci\s*=\s*\{', lua_content)

    if m_new:
        # NUOVO FORMATO: ogni voce è su una riga che inizia con "    {[["
        # Parsing veloce: riga per riga invece di iterare carattere per carattere
        brace_start = lua_content.find('{', m_new.start())
        if brace_start == -1:
            return voci
        # Trova la fine dell'array d={} cercando la riga che contiene solo "  }"
        # In alternativa, estrae le righe tra d={ e la chiusura
        section = lua_content[brace_start:]
        for line in section.splitlines():
            stripped = line.strip()
            # Ogni voce inizia con {[[ nel nuovo formato
            if stripped.startswith('{[['):
                # Rimuovi virgola finale se presente
                if stripped.endswith(','):
                    stripped = stripped[:-1]
                voce = parse_single_voce(stripped)
                if voce:
                    voci.append(voce)
        return voci

    elif m_old:
        # VECCHIO FORMATO: parsing bilanciato delle graffe
        brace_start = lua_content.find('{', m_old.start())
        if brace_start == -1:
            return voci

        voci_content_end = find_balanced_braces(lua_content, brace_start)
        if voci_content_end is None:
            return voci

        voci_content = lua_content[brace_start + 1:voci_content_end]

        i = 0
        while i < len(voci_content):
            char = voci_content[i]

            next_pos = skip_lua_longstring(voci_content, i)
            if next_pos is not None:
                i = next_pos
                continue

            if char == '{':
                block_end = find_balanced_braces(voci_content, i)
                if block_end is not None:
                    block = voci_content[i:block_end + 1]
                    voce = parse_single_voce(block)
                    if voce:
                        voci.append(voce)
                    i = block_end + 1
                    continue

            i += 1

    return voci


def extract_lua_longstring(text, pos):
    """
    Estrae il contenuto di un long string Lua che inizia a pos.
    Restituisce (contenuto, pos_dopo_chiusura) oppure (None, pos).
    """
    m = re.match(r'\[(?P<eq>=*)\[', text[pos:])
    if not m:
        return None, pos
    eq = m.group('eq')
    close = f']{eq}]'
    start = pos + len(m.group(0))
    end = text.find(close, start)
    if end == -1:
        return None, pos
    return text[start:end], end + len(close)


def parse_single_voce_legacy(block):
    """
    Parsa un singolo blocco voce nel VECCHIO formato con keyword:
      {titolo=[[...]], timestamp='...', categorie={...}, contenuto=...}
    """
    try:
        titolo_match = re.search(r'titolo\s*=\s*\[\[(.+?)\]\]', block)
        if not titolo_match:
            return None
        titolo = titolo_match.group(1)

        timestamp_match = re.search(r"timestamp\s*=\s*['\"](\d{14})['\"]", block)
        if not timestamp_match:
            return None
        timestamp = timestamp_match.group(1)

        categorie = []
        cat_section_match = re.search(r'categorie\s*=\s*\{(.+?)\}(?:,|\s*contenuto)', block, re.DOTALL)
        if cat_section_match:
            cat_content = cat_section_match.group(1)
            categorie = re.findall(r'\[\[(.+?)\]\]', cat_content)

        # Vecchio formato non ha templates: li lasciamo vuoti
        # preview: prendi i primi 100 char del contenuto se presente
        preview = ""
        cont_match = re.search(r'contenuto\s*=\s*(\[=*\[)', block)
        if cont_match:
            open_bracket = cont_match.group(1)
            lv = open_bracket.count('=')
            close_bracket = ']' + ('=' * lv) + ']'
            cont_start = cont_match.end()
            close_pos = block.find(close_bracket, cont_start)
            if close_pos != -1:
                preview = block[cont_start:cont_start+100].replace('\n', ' ').strip()

        return {
            'titolo': titolo,
            'timestamp': timestamp,
            'categorie': categorie,
            'templates': [],
            'preview': preview
        }
    except Exception:
        return None


def parse_single_voce(block):
    """
    Parsa un singolo blocco voce rilevando automaticamente il formato:
    - Nuovo formato (array posizionale): {[[titolo]],[[timestamp]],{cat},{tmpl},preview}
    - Vecchio formato (keyword):         {titolo=[[...]], timestamp='...', ...}
    Il rilevamento è O(1): controlla se il primo token dopo '{' è un long string.
    """
    # Rileva formato: salta spazi e cerca il primo token significativo
    stripped = block.lstrip('{ \t\n\r')
    if stripped.startswith('['):
        # Nuovo formato array posizionale
        pass  # continua sotto
    else:
        # Vecchio formato con keyword
        return parse_single_voce_legacy(block)

    """
    Nuovo formato array posizionale:
      {titolo, timestamp, {categorie}, {{nome,{params}}, ...}, preview}
    """
    try:
        pos = 0
        # Salta la { iniziale
        ob = block.find('{')
        if ob == -1:
            return None
        pos = ob + 1

        def next_longstring(p):
            # Salta spazi e virgole
            while p < len(block) and block[p] in ' \t\n\r,':
                p += 1
            return extract_lua_longstring(block, p)

        # Campo 1: titolo
        titolo, pos = next_longstring(pos)
        if titolo is None:
            return None

        # Campo 2: timestamp
        timestamp, pos = next_longstring(pos)
        if timestamp is None:
            return None

        # Campo 3: array categorie { ls, ls, ... }
        while pos < len(block) and block[pos] in ' \t\n\r,':
            pos += 1
        if pos >= len(block) or block[pos] != '{':
            return None
        cat_end = find_balanced_braces(block, pos)
        if cat_end is None:
            return None
        cat_block = block[pos+1:cat_end]
        categorie = []
        cp = 0
        while cp < len(cat_block):
            val, new_cp = extract_lua_longstring(cat_block, cp)
            if val is not None:
                categorie.append(val)
                cp = new_cp
            else:
                cp += 1
        pos = cat_end + 1

        # Campo 4: array template { {ls,{ls,...}}, ... }
        while pos < len(block) and block[pos] in ' \t\n\r,':
            pos += 1
        if pos >= len(block) or block[pos] != '{':
            return None
        tmpl_arr_end = find_balanced_braces(block, pos)
        if tmpl_arr_end is None:
            return None
        tmpl_block = block[pos+1:tmpl_arr_end]
        templates = []
        tp = 0
        while tp < len(tmpl_block):
            while tp < len(tmpl_block) and tmpl_block[tp] in ' \t\n\r,':
                tp += 1
            if tp >= len(tmpl_block):
                break
            if tmpl_block[tp] == '{':
                t_end = find_balanced_braces(tmpl_block, tp)
                if t_end is None:
                    break
                t_inner = tmpl_block[tp+1:t_end]
                # nome
                t_nome, t_pos = extract_lua_longstring(t_inner, 0)
                # params array
                while t_pos < len(t_inner) and t_inner[t_pos] in ' \t\n\r,':
                    t_pos += 1
                t_params = []
                if t_pos < len(t_inner) and t_inner[t_pos] == '{':
                    p_end = find_balanced_braces(t_inner, t_pos)
                    if p_end is not None:
                        p_block = t_inner[t_pos+1:p_end]
                        pp = 0
                        while pp < len(p_block):
                            pval, new_pp = extract_lua_longstring(p_block, pp)
                            if pval is not None:
                                t_params.append(pval)
                                pp = new_pp
                            else:
                                pp += 1
                if t_nome:
                    templates.append({'nome': t_nome, 'params': t_params})
                tp = t_end + 1
            else:
                tp += 1
        pos = tmpl_arr_end + 1

        # Campo 5: preview
        preview, pos = next_longstring(pos)
        if preview is None:
            preview = ""

        return {
            'titolo': titolo,
            'timestamp': timestamp,
            'categorie': categorie,
            'templates': templates,
            'preview': preview
        }
    except Exception:
        return None


def load_existing_cache_from_all_files():
    """Carica cache da TUTTI i file esistenti, ignorando duplicati"""
    print("Caricamento cache esistente da tutti i file...")

    existing_pages = []
    existing_titles = set()

    data_pages = get_all_data_pages()

    if not data_pages:
        print("  Nessun file cache esistente\n")
        return existing_pages, existing_titles

    print(f"  Trovati {len(data_pages)} file cache")

    for page_name in data_pages:
        try:
            page = pywikibot.Page(SITE, page_name)
            print(f"  Lettura {page_name}...")
            content = page.text
            voci = parse_lua_to_json(content)

            added = 0
            duplicates = []
            for voce in voci:
                if voce['titolo'] not in existing_titles:
                    existing_pages.append(voce)
                    existing_titles.add(voce['titolo'])
                    added += 1
                else:
                    duplicates.append(voce['titolo'])

            msg = f"    OK {added} voci caricate"
            if duplicates:
                msg += f" ({len(duplicates)} duplicate ignorate)"
            print(msg)
            for dup in duplicates:
                print(f"      DUPLICATA: {dup}")
        except Exception as e:
            print(f"    ERRORE: {e}")

    print(f"\nOK Cache totale: {len(existing_pages)} voci da {len(data_pages)} file\n")
    return existing_pages, existing_titles


# ========================================
# CACHE MANUALE E SCANSIONE ALTRI NS (CacheMoved)
# ========================================

def scan_other_namespaces(cutoff_date):
    """
    Interroga RecentChanges per i namespace in NS_SCAN (NS2 Utente, NS118 Bozze)
    cercando voci nell'arco di tempo coperto dalla cache.
    Restituisce una lista di titoli (con prefisso ns), senza scaricare dati completi.
    La scansione si ferma quando il timestamp scende sotto cutoff_date.
    """
    site = SITE
    ns_label = ', '.join(f'NS{n}' for n in NS_SCAN)
    print(f"  Scansione RecentChanges per {ns_label}...")

    found_titles = []
    seen = set()
    cutoff_str = cutoff_date.strftime('%Y%m%d%H%M%S')
    request_size = 500
    iteration = 0

    for ns in NS_SCAN:
        print(f"  Namespace {ns}...")
        ns_found = 0
        continue_param = None

        params = {
            'action': 'query',
            'list': 'recentchanges',
            'rcnamespace': ns,
            'rcshow': '!redirect|!bot',
            'rclimit': request_size,
            'rcprop': 'title|timestamp',
            'rcdir': 'older',
            'format': 'json'
        }

        while iteration < MAX_ITERATIONS:
            iteration += 1
            if continue_param:
                params['rccontinue'] = continue_param

            try:
                request = site.simple_request(**params)
                data = request.submit()

                if 'query' not in data or 'recentchanges' not in data['query']:
                    break

                changes = data['query']['recentchanges']
                stop = False

                for change in changes:
                    title = change.get('title', '')
                    if not title:
                        continue
                    rc_ts = change.get('timestamp', '').replace('-','').replace('T','').replace(':','').replace('Z','')
                    if rc_ts and rc_ts < cutoff_str:
                        stop = True
                        break
                    if title not in seen:
                        seen.add(title)
                        found_titles.append(title)
                        ns_found += 1

                if stop:
                    break

                if 'continue' in data and 'rccontinue' in data['continue']:
                    continue_param = data['continue']['rccontinue']
                else:
                    break

            except Exception as e:
                print(f"    Errore API NS{ns}: {e}")
                break

        print(f"    Trovati {ns_found} titoli in NS{ns}")

    print(f"  Totale titoli da altri NS: {len(found_titles)}")
    return found_titles


def validate_ns_or_manual_page(title, existing_titles, cutoff_date, moves_cache=None, mc_counter_ref=None):
    """
    Valida un singolo titolo (da NS non-0 o da CacheMoved manuale):
    - Se il titolo e' in NS0: lo usa direttamente
    - Altrimenti: estrae il nome base e cerca la controparte in NS0
    - Verifica esistenza, non-redirect, eta'
    - Scarica categorie, templates e preview solo se la voce passa la validazione
    Se moves_cache e' fornito:
    - Skippa subito le voci NS0 gia' rifiutate in precedenza (result=rejected)
    - Le voci accettate vengono sempre riverificate
    La chiave del cache e' sempre il titolo NS0 derivato.
    mc_counter_ref: lista a un elemento [int] usata come contatore condiviso
    per i checkpoint periodici del moves_cache.
    Restituisce il dict voce se valida, None altrimenti (con motivo).
    """
    now_str = datetime.now().strftime('%Y%m%d%H%M%S')
    try:
        temp_page = pywikibot.Page(SITE, title)
        original_ns = temp_page.namespace()

        if original_ns == 0:
            voce_page = temp_page
        else:
            base_name = temp_page.title(with_ns=False)
            if '/' in base_name:
                base_name = base_name.split('/')[-1]
            voce_page = pywikibot.Page(SITE, base_name, ns=0)

        ns0_title = voce_page.title()

        if ns0_title in existing_titles:
            return None, 'duplicate'

        # Skip da moves_cache: solo voci NS0 rifiutate in precedenza
        if moves_cache is not None:
            cached = moves_cache.get(ns0_title)
            if cached and cached.get('result') == 'rejected':
                return None, 'cached_rejected'

        def _mc_update(key, result, reason):
            if moves_cache is not None:
                moves_cache[key] = {'processed_at': now_str, 'result': result, 'reason': reason}
                if mc_counter_ref is not None:
                    mc_counter_ref[0] = checkpoint_moves_cache(moves_cache, mc_counter_ref[0] + 1)

        if not voce_page.exists():
            _mc_update(ns0_title, 'rejected', 'no_ns0')
            return None, 'no_ns0'
        if voce_page.isRedirectPage():
            _mc_update(ns0_title, 'rejected', 'redirect')
            return None, 'redirect'

        oldest = voce_page.oldest_revision
        created = oldest.timestamp
        # Controllo eta': usa la data di creazione della voce NS0.
        # Una pagina utente modificata di recente non e' sufficiente per
        # accettare una voce NS0 creata anni fa.
        ref_date = created.replace(tzinfo=None)
        if ref_date < cutoff_date:
            _mc_update(ns0_title, 'rejected', 'too_old')
            return None, f'old ({created.strftime("%d/%m/%Y")})'

        timestamp = created.strftime('%Y%m%d%H%M%S')

        categories = []
        try:
            for cat in voce_page.categories():
                categories.append(cat.title(with_ns=False))
        except Exception:
            pass

        wikitext = ""
        try:
            wikitext = voce_page.text
        except Exception:
            pass

        templates = parse_templates_from_wikitext(wikitext)
        preview = wikitext[:100].replace("\n", " ").strip() if wikitext else ""

        _mc_update(ns0_title, 'accepted', 'ns0')

        return {
            'titolo': ns0_title,
            'timestamp': timestamp,
            'categorie': categories,
            'templates': templates,
            'preview': preview
        }, 'ok'

    except Exception as e:
        return None, f'error: {e}'



def extract_title_from_wiki_url(line):
    """
    Se la riga e' un URL Wikipedia (it.wikipedia.org/wiki/...), estrae
    il titolo della pagina decodificando percent-encoding e sostituendo
    underscore con spazi. Rimuove eventuali parametri query.
    Restituisce il titolo estratto, o None se la riga non e' un URL wiki.
    """
    m = re.search(r'it\.wikipedia\.org/wiki/([^?#\s]+)', line)
    if not m:
        return None
    raw = m.group(1)
    # Decodifica percent-encoding e sostituisci underscore con spazi
    title = unquote(raw).replace('_', ' ').strip()
    return title if title else None

def read_cache_moved(existing_titles, cutoff_date, cached_pages_by_title=None):
    """
    Legge CacheMoved (lista manuale).
    - Righe normali: aggiunge la voce se valida in NS0
    - Righe "Rimuovi: Titolo": rimuove dalla cache principale
    - Righe "Aggiorna: Titolo": rilegge metadati dalla pagina Wikipedia e
      aggiorna il record in cache (o lo aggiunge se non c'era, o lo rimuove
      se la pagina non esiste piu')
    Restituisce (pages_to_add, titles_to_remove, pages_to_update).
    cached_pages_by_title: dict {titolo: record} per lookup O(1) su Aggiorna:.
    Chiamata solo quando CacheParsed != 'True'.
    """
    pages_to_add = []
    titles_to_remove = []
    pages_to_update = []   # lista di record aggiornati (stesso titolo, nuovi metadati)

    if cached_pages_by_title is None:
        cached_pages_by_title = {}

    print(f"Lettura: {CACHE_MOVED_PAGE}")
    try:
        cm_page = pywikibot.Page(SITE, CACHE_MOVED_PAGE)
        if not cm_page.exists() or not cm_page.text.strip():
            print("  CacheMoved assente o vuota - skip")
            return pages_to_add, titles_to_remove, pages_to_update

        lines = cm_page.text.strip().split('\n')
        add_titles = []
        remove_titles = []
        update_titles = []

        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # Aggiorna: (case-insensitive) - priorita' su Rimuovi:
            if line.lower().startswith('aggiorna:'):
                update_title = line[len('aggiorna:'):].strip()
                update_title = extract_title_from_wiki_url(update_title) or update_title.replace('_', ' ')
                if update_title:
                    update_titles.append(update_title)
                continue
            # Rimuovi: (case-insensitive)
            if line.lower().startswith('rimuovi:'):
                remove_title = line[len('rimuovi:'):].strip()
                remove_title = extract_title_from_wiki_url(remove_title) or remove_title.replace('_', ' ')
                if remove_title:
                    remove_titles.append(remove_title)
                continue
            # URL Wikipedia (es. https://it.wikipedia.org/wiki/Titolo)
            wiki_title = extract_title_from_wiki_url(line)
            if wiki_title:
                add_titles.append(wiki_title)
                continue
            # Formato dump Speciale:PagineRecenti
            m = re.search(r'\d{2}:\d{2}, \d{1,2} \w+ \d{4} (.+?) \(cron \|', line)
            add_titles.append(m.group(1).strip() if m else line)

        print(f"  Da aggiungere: {len(add_titles)}, Da rimuovere: {len(remove_titles)}, Da aggiornare: {len(update_titles)}")

        for rt in remove_titles:
            titles_to_remove.append(rt)
            print(f"  Rimuovi: {rt}")

        # Gestione Aggiorna:
        for title in update_titles:
            print(f"  Aggiorna: {title}")
            try:
                page_obj = pywikibot.Page(SITE, title, ns=0)

                if not page_obj.exists() or page_obj.isRedirectPage():
                    # Pagina sparita o diventata redirect: rimuovi dalla cache
                    titles_to_remove.append(title)
                    reason = "cancellata" if not page_obj.exists() else "redirect"
                    print(f"    RIMUOVI ({reason}): {title}")
                    continue

                # Rileggi metadati freschi
                # Purge forzato: aggiorna l'indice Wikipedia (categorie da template,
                # link, ecc.) prima di rileggere, evitando dati stale dalla cache
                try:
                    page_obj.purge()
                except Exception:
                    pass  # purge non critico: prosegui comunque
                try:
                    new_cats = [cat.title(with_ns=False) for cat in page_obj.categories()]
                except Exception:
                    new_cats = []
                try:
                    wikitext = page_obj.text
                    new_templates = parse_templates_from_wikitext(wikitext)
                    new_preview = wikitext[:100].replace('\n', ' ').strip() if wikitext else ''
                except Exception:
                    new_templates = []
                    new_preview = ''

                if title in cached_pages_by_title:
                    # Voce gia' in cache: aggiorna i metadati mantenendo il timestamp
                    record = dict(cached_pages_by_title[title])
                    record['categorie'] = new_cats
                    record['templates'] = new_templates
                    record['preview'] = new_preview
                    pages_to_update.append(record)
                    # Segnala anche per rimozione del vecchio record prima dell'unione
                    titles_to_remove.append(title)
                    print(f"    OK Metadati aggiornati: {title}")
                else:
                    # Voce non in cache: aggiungila come nuova
                    try:
                        oldest = page_obj.oldest_revision
                        timestamp = oldest.timestamp.strftime('%Y%m%d%H%M%S')
                    except Exception:
                        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                    record = {
                        'titolo': title,
                        'timestamp': timestamp,
                        'categorie': new_cats,
                        'templates': new_templates,
                        'preview': new_preview
                    }
                    pages_to_add.append(record)
                    existing_titles.add(title)
                    print(f"    OK Aggiunta (non era in cache): {title}")

            except Exception as e:
                print(f"    ERRORE Aggiorna {title}: {e}")

        skipped = {}
        for i, title in enumerate(add_titles, 1):
            print(f"  [{i}/{len(add_titles)}] {title}")
            voce, reason = validate_ns_or_manual_page(title, existing_titles, cutoff_date, moves_cache=None)
            if voce:
                pages_to_add.append(voce)
                existing_titles.add(voce['titolo'])
                print(f"      OK Aggiunta: {voce['titolo']}")
            else:
                skipped[reason] = skipped.get(reason, 0) + 1
                print(f"      SKIP: {reason}")

        if skipped:
            print(f"  Skippate da CacheMoved: {skipped}")

    except Exception as e:
        print(f"  ERRORE lettura CacheMoved: {e}")

    return pages_to_add, titles_to_remove, pages_to_update


def scan_and_load_ns_pages(existing_titles, cutoff_date, moves_cache):
    """
    Interroga RecentChanges per i namespace in NS_SCAN (NS2, NS118),
    valida le voci trovate cercando la controparte in NS0.
    Eseguita ad ogni run del bot, indipendentemente da CacheParsed.
    moves_cache: le voci NS0 rifiutate in precedenza vengono saltate senza API.
    Restituisce la lista di voci valide da aggiungere alla cache.
    """
    ns_titles = scan_other_namespaces(cutoff_date)

    if not ns_titles:
        print("  Nessun titolo trovato da altri NS")
        return []

    print(f"  Validazione {len(ns_titles)} titoli da NS{NS_SCAN}...")
    pages_to_add = []
    skipped = {}

    mc_counter_ref = [0]  # lista a un elemento per passaggio per riferimento
    for i, title in enumerate(ns_titles, 1):
        if i % 50 == 0:
            print(f"    [{i}/{len(ns_titles)}] Validazione...")
        voce, reason = validate_ns_or_manual_page(title, existing_titles, cutoff_date, moves_cache, mc_counter_ref)
        if voce:
            pages_to_add.append(voce)
            existing_titles.add(voce['titolo'])
            print(f"    OK {voce['titolo']}")
        else:
            skipped[reason] = skipped.get(reason, 0) + 1

    if skipped:
        print(f"  Skippate da NS: {skipped}")

    print(f"  Aggiunte da altri NS: {len(pages_to_add)}")
    return pages_to_add


# ========================================
# SCARICAMENTO NUOVE VOCI
# ========================================

def get_new_pages_only(existing_titles, cutoff_date, moves_cache):
    """
    Raccoglie TUTTE le voci nuove in NS0 nell'arco del cutoff.
    Scorre RecentChanges dal piu' recente fino al cutoff_date,
    raccogliendo tutti i titoli non gia' in existing_titles.
    Nessun limite numerico: il troncamento avviene nello STEP 6.
    Include sia creazioni dirette che spostamenti da altri NS in NS0.
    moves_cache: passato a get_moved_to_ns0_since_cutoff per skip intelligente.
    """
    print(f"Ricerca nuove voci in NS0 (dal cutoff {cutoff_date.strftime('%d/%m/%Y')})...")
    print(f"Cache esistente: {len(existing_titles)} voci")

    candidate_titles = set()
    cutoff_str = cutoff_date.strftime('%Y%m%d%H%M%S')

    # Fonte 1: creazioni dirette in NS0
    print("\nFonte 1: Creazioni dirette NS0...")
    direct = get_new_creations_since_cutoff(existing_titles, cutoff_str)
    candidate_titles.update(direct)
    print(f"  Trovate: {len(direct)} voci candidate")

    # Fonte 2: spostamenti nel log NS0 (da altri NS)
    print("\nFonte 2: Spostamenti in NS0 dal log...")
    moved = get_moved_to_ns0_since_cutoff(existing_titles, cutoff_date, moves_cache)
    # moved e' un dict {titolo: move_timestamp}; aggiorna candidate_titles (set)
    # e costruisce move_timestamps per propagare il ts a download_page_data
    candidate_titles.update(moved.keys())
    move_timestamps = moved  # {titolo: move_ts_str}
    print(f"  Trovate: {len(moved)} voci spostate")

    print(f"\nTotale candidate NS0: {len(candidate_titles)}")
    print(f"Scaricamento dati completi...")
    new_pages = download_page_data(list(candidate_titles), existing_titles, cutoff_date, moves_cache, move_timestamps)

    print(f"\nOK Nuove voci da NS0: {len(new_pages)}\n")
    return new_pages


def get_new_creations_since_cutoff(existing_titles, cutoff_str):
    """
    Scorre RecentChanges NS0 (solo nuove creazioni) dal piu' recente
    fino a quando il timestamp scende sotto cutoff_str.
    Raccoglie tutti i titoli non in existing_titles senza limite numerico.
    """
    site = SITE
    found_titles = set()
    iteration = 0
    total_checked = 0

    params = {
        'action': 'query',
        'list': 'recentchanges',
        'rctype': 'new',
        'rcnamespace': NAMESPACE,
        'rcshow': '!redirect|!bot',
        'rclimit': 500,
        'rcprop': 'title|timestamp',
        'rcdir': 'older',
        'format': 'json'
    }

    continue_param = None

    while iteration < MAX_ITERATIONS:
        iteration += 1
        if continue_param:
            params['rccontinue'] = continue_param

        try:
            request = site.simple_request(**params)
            data = request.submit()

            if 'query' not in data or 'recentchanges' not in data['query']:
                break

            changes = data['query']['recentchanges']
            stop = False

            for change in changes:
                total_checked += 1
                title = change.get('title', '')
                if not title:
                    continue
                rc_ts = change.get('timestamp', '').replace('-','').replace('T','').replace(':','').replace('Z','')
                if rc_ts and rc_ts < cutoff_str:
                    stop = True
                    break
                if title not in existing_titles:
                    found_titles.add(title)

            if iteration % 5 == 0:
                print(f"    [{iteration}] Trovate: {len(found_titles)}, Controllate: {total_checked}")

            if stop:
                break

            if 'continue' in data and 'rccontinue' in data['continue']:
                continue_param = data['continue']['rccontinue']
            else:
                break

        except Exception as e:
            print(f"    Errore API: {e}")
            break

    print(f"    Totale controllate: {total_checked}, nuove trovate: {len(found_titles)}")
    return found_titles


def get_moved_to_ns0_since_cutoff(existing_titles, cutoff_date, moves_cache):
    """
    Scorre il log degli spostamenti fino al cutoff_date.
    Raccoglie tutti i titoli destinazione in NS0 non gia' in existing_titles,
    indipendentemente dal namespace sorgente. Questo cattura:
    - spostamenti da sandbox/bozze/utente (NS!=0 -> NS0)
    - ridenominazioni e inversioni di redirect interne (NS0 -> NS0)
    La verifica del cutoff sulla data di creazione avviene in download_page_data.

    moves_cache: dict persistente tra i run. Le voci rifiutate (not NS0, non
    esistenti, ecc.) vengono saltate senza chiamate API. Le voci accettate in
    passato vengono sempre riverificate perché potrebbero aver subito spostamenti
    successivi (redirect inverso, uscita da NS0, ecc.).
    """
    site = SITE
    # Dict {titolo_ns0: move_timestamp_str} per propagare il timestamp
    # dello spostamento a download_page_data, che lo usa come data di
    # riferimento per il controllo eta' al posto della data di creazione.
    found_titles = {}
    checked = 0
    skipped_cached = 0
    now_str = datetime.now().strftime('%Y%m%d%H%M%S')

    try:
        logs = site.logevents(logtype='move', total=MAX_ITERATIONS * 500)

        for log in logs:
            checked += 1
            if checked % 200 == 0:
                print(f"    Log spostamenti: {checked} controllati, "
                      f"{len(found_titles)} trovati, {skipped_cached} skip da cache")

            # Ferma quando lo spostamento e' piu' vecchio del cutoff
            log_ts = log.timestamp()
            if log_ts.replace(tzinfo=None) < cutoff_date:
                break

            # Timestamp dello spostamento (usato come riferimento eta')
            move_ts_str = log_ts.strftime('%Y%m%d%H%M%S')

            try:
                params = log.data.get('params', log.data)
                target_title = params.get('target_title', '')
                if not target_title:
                    continue

                # Se gia' in existing_titles, skip immediato senza toccare il cache
                if target_title in existing_titles:
                    continue

                # Controlla moves_cache: skip solo se rifiutata in precedenza
                # Le voci accettate vengono sempre riverificate
                cached = moves_cache.get(target_title)
                if cached and cached.get('result') == 'rejected':
                    skipped_cached += 1
                    continue

                # Verifica namespace via API
                target_page = pywikibot.Page(site, target_title)
                if int(target_page.namespace()) != 0:
                    moves_cache[target_title] = {
                        'processed_at': now_str,
                        'result': 'rejected',
                        'reason': f"ns{target_page.namespace()}"
                    }
                    continue

                # Voce accettata: aggiorna cache e aggiungi ai candidati
                # con il timestamp dello spostamento
                moves_cache[target_title] = {
                    'processed_at': now_str,
                    'result': 'accepted',
                    'reason': 'ns0'
                }
                found_titles[target_title] = move_ts_str
                source_title = log.page().title()
                print(f"    Spostamento -> NS0: '{source_title}' -> '{target_title}'")

            except Exception:
                continue

    except Exception as e:
        print(f"    Errore log spostamenti: {e}")

    print(f"    Log spostamenti: {checked} controllati, "
          f"{len(found_titles)} trovati, {skipped_cached} skip da cache")
    return found_titles



def parse_templates_from_wikitext(text):
    """
    Estrae template di primo livello dal wikitesto.
    Per ogni template restituisce nome e lista dei nomi di parametri valorizzati.
    Ignora: template annidati, parser functions (#if, #switch, ecc.),
    template con nome vuoto o che inizia con caratteri speciali.
    I parametri senza valore (nome= senza testo dopo) vengono scartati.
    """
    templates = []
    i = 0
    n = len(text)

    while i < n - 1:
        if text[i] == '{' and text[i+1] == '{':
            depth = 1
            j = i + 2
            while j < n - 1 and depth > 0:
                if text[j] == '{' and text[j+1] == '{':
                    depth += 1
                    j += 2
                elif text[j] == '}' and text[j+1] == '}':
                    depth -= 1
                    if depth == 0:
                        break
                    j += 2
                else:
                    j += 1

            if depth == 0:
                inner = text[i+2:j]
                parts = inner.split('|')
                raw_name = parts[0].strip()

                # Salta parser functions e nomi vuoti/speciali
                if raw_name and not raw_name.startswith('#') and not raw_name.startswith(':'):
                    name = raw_name.replace('_', ' ').strip()
                    params = []
                    for part in parts[1:]:
                        if '=' in part:
                            pname, _, pval = part.partition('=')
                            pname = pname.strip()
                            # Rimuove eventuali graffe residue dal nome parametro
                            pname = pname.replace('{', '').replace('}', '').strip()
                            pval = pval.strip()
                            if pname and pval:
                                # Parametro named valorizzato: salva il nome
                                params.append(pname)
                        else:
                            pval = part.strip()
                            # Rimuove eventuali graffe residue dal valore
                            pval = pval.replace('{', '').replace('}', '').strip()
                            # Parametro posizionale: salva il valore solo se
                            # semplice (no parentesi quadre che rompono lua_str)
                            if pval and '[' not in pval and ']' not in pval:
                                params.append(pval[:100])
                    templates.append({'nome': name, 'params': params})

                i = j + 2
                continue
        i += 1

    return templates


def download_page_data(titles, existing_titles, cutoff_date, moves_cache=None, move_timestamps=None):
    """
    Scarica i dati completi di una lista di titoli.
    Salta: duplicati, non esistenti, redirect, voci create prima di cutoff_date.
    Aggiorna existing_titles dopo ogni aggiunta per prevenire duplicati successivi.
    Se moves_cache e' fornito, registra i rifiuti (too_old, not_exist, redirect)
    cosi' i run successivi possono skippare queste voci senza chiamate API.
    Il cache viene salvato su disco ogni 200 voci per resistere a interruzioni.
    move_timestamps: dict {titolo: move_ts_str} con il timestamp dello spostamento
    in NS0. Se presente per un titolo, viene usato al posto della data di creazione
    per il controllo eta', permettendo di accettare voci vecchie spostate di recente
    da sandbox/bozze senza aprire la porta a rinominazioni di voci antiche.
    """
    site = SITE
    pages_data = []
    skipped_duplicate = 0
    skipped_cached = 0
    skipped_old = []
    skipped_notexist = []
    skipped_redirect = []
    skipped_error = []
    now_str = datetime.now().strftime('%Y%m%d%H%M%S')
    mc_counter = 0  # contatore per checkpoint moves_cache

    for i, title in enumerate(titles):
        if i % 50 == 0:
            print(f"  [{i}/{len(titles)}] Scaricamento...")

        if title in existing_titles:
            skipped_duplicate += 1
            continue

        # Skip da moves_cache: solo voci rifiutate in precedenza
        if moves_cache is not None:
            cached = moves_cache.get(title)
            if cached and cached.get('result') == 'rejected':
                skipped_cached += 1
                continue

        try:
            page = pywikibot.Page(site, title)

            if not page.exists():
                skipped_notexist.append(title)
                if moves_cache is not None:
                    moves_cache[title] = {'processed_at': now_str, 'result': 'rejected', 'reason': 'not_exist'}
                    mc_counter = checkpoint_moves_cache(moves_cache, mc_counter + 1)
                continue
            if page.isRedirectPage():
                skipped_redirect.append(title)
                if moves_cache is not None:
                    moves_cache[title] = {'processed_at': now_str, 'result': 'rejected', 'reason': 'redirect'}
                    mc_counter = checkpoint_moves_cache(moves_cache, mc_counter + 1)
                continue

            try:
                oldest = page.oldest_revision
                created = oldest.timestamp
                timestamp = created.strftime('%Y%m%d%H%M%S')
            except Exception as e:
                skipped_error.append((title, f"timestamp: {e}"))
                continue

            # Controllo eta': usa il timestamp dello spostamento in NS0 se disponibile
            # (voci lavorate in bozza/sandbox per mesi e poi spostate in NS0)
            # altrimenti usa la data di creazione originale
            move_ts_str = move_timestamps.get(title) if move_timestamps else None
            if move_ts_str:
                try:
                    ref_date = datetime.strptime(move_ts_str, '%Y%m%d%H%M%S')
                except Exception:
                    ref_date = created.replace(tzinfo=None)
            else:
                ref_date = created.replace(tzinfo=None)

            if ref_date < cutoff_date:
                skipped_old.append(title)
                age_info = f"spostata {ref_date.strftime('%d/%m/%Y')}" if move_ts_str else f"creata {created.strftime('%d/%m/%Y')}"
                print(f"    SKIP (troppo vecchia, {age_info}): {title}")
                if moves_cache is not None:
                    moves_cache[title] = {'processed_at': now_str, 'result': 'rejected', 'reason': 'too_old'}
                    mc_counter = checkpoint_moves_cache(moves_cache, mc_counter + 1)
                continue

            categories = []
            try:
                for cat in page.categories():
                    categories.append(cat.title(with_ns=False))
            except Exception:
                pass

            wikitext = ""
            try:
                wikitext = page.text
            except Exception:
                pass

            templates = parse_templates_from_wikitext(wikitext)
            preview = wikitext[:100].replace("\n", " ").strip() if wikitext else ""

            record = {
                'titolo': title,
                'timestamp': timestamp,
                'categorie': categories,
                'templates': templates,
                'preview': preview
            }
            # Se la voce e' entrata tramite spostamento da sandbox/bozze,
            # salva il timestamp dello spostamento. Viene usato in STEP 6
            # e da PuliziaCache per il controllo eta', evitando di scartare
            # voci vecchie ma spostate di recente in NS0.
            if move_ts_str:
                record['move_timestamp'] = move_ts_str
            pages_data.append(record)

            existing_titles.add(title)

        except Exception as e:
            skipped_error.append((title, str(e)))
            continue

    total_skipped = skipped_duplicate + skipped_cached + len(skipped_old) + len(skipped_notexist) + len(skipped_redirect) + len(skipped_error)
    if total_skipped > 0:
        print(f"\n  Skippate {total_skipped} voci:")
        if skipped_duplicate:
            print(f"    - Gia' in cache: {skipped_duplicate}")
        if skipped_cached:
            print(f"    - Da moves_cache: {skipped_cached}")
        if skipped_old:
            print(f"    - Troppo vecchie: {len(skipped_old)}")
            for t in skipped_old[:5]:
                print(f"      . {t}")
        if skipped_notexist:
            print(f"    - Non esistono: {len(skipped_notexist)}")
            for t in skipped_notexist[:5]:
                print(f"      . {t}")
        if skipped_redirect:
            print(f"    - Redirect: {len(skipped_redirect)}")
            for t in skipped_redirect[:5]:
                print(f"      . {t}")
        if skipped_error:
            print(f"    - Errori: {len(skipped_error)}")
            for t, err in skipped_error[:5]:
                print(f"      . {t}: {err}")

    return pages_data


# ========================================
# FORMATTAZIONE E SALVATAGGIO LUA
# ========================================

def escape_for_lua_longstring(s):
    """Calcola i delimitatori long string Lua appropriati per la stringa s"""
    if not s:
        return "", ""
    level = 0
    while f"]{'=' * level}]" in s:
        level += 1
    open_delim = f"[{'=' * level}["
    close_delim = f"]{'=' * level}]"
    return open_delim, close_delim


def format_lua_row(page):
    """Formatta una singola voce in Lua (una riga del array d={}).
    Struttura: {titolo, timestamp, {categorie}, {templates}, preview, move_timestamp}
    Il 6° campo move_timestamp e' una stringa vuota se non presente.
    Il modulo Lua ignora il 6° campo (retrocompatibile).
    """
    cats = page.get('categorie', [])
    cats_lua = "{" + ",".join(lua_str(c) for c in cats) + "}"

    tmpl_list = []
    for t in page.get('templates', []):
        nome = lua_str(t.get('nome', ''))
        params_lua = "{" + ",".join(lua_str(p) for p in t.get('params', [])) + "}"
        tmpl_list.append(f"{{{nome},{params_lua}}}")
    tmpls_lua = "{" + ",".join(tmpl_list) + "}"

    preview = lua_str(page.get('preview', ''))
    move_ts = lua_str(page.get('move_timestamp', ''))
    return (
        f"    {{{lua_str(page['titolo'])},{lua_str(page['timestamp'])},"
        f"{cats_lua},{tmpls_lua},{preview},{move_ts}}}"
    )


# Overhead fisso dell'intestazione di ogni file (header + chiusura)
_LUA_FILE_OVERHEAD = 300


def split_pages_into_files(pages_data):
    """
    Divide le voci in piu' file misurando la dimensione Lua reale di ogni voce
    (non una stima), garantendo che ogni file non superi MAX_CHARS_PER_FILE.
    """
    print(f"\nSuddivisione in file (max {MAX_CHARS_PER_FILE:,} byte per file)...")

    # Limite effettivo: lascia margine per header e struttura del file
    effective_limit = MAX_CHARS_PER_FILE - _LUA_FILE_OVERHEAD

    files = []
    current_file = []
    current_bytes = 0

    for page in pages_data:
        try:
            row = format_lua_row(page)
        except Exception as e:
            print(f"  WARNING: Skip voce {page.get('titolo', 'N/A')}: {e}")
            continue

        row_bytes = len(row.encode('utf-8'))

        if current_bytes + row_bytes > effective_limit and current_file:
            files.append(current_file)
            print(f"  File {len(files)}: {len(current_file)} voci, ~{current_bytes:,} byte")
            current_file = []
            current_bytes = 0

        current_file.append(page)
        current_bytes += row_bytes

    if current_file:
        files.append(current_file)
        print(f"  File {len(files)}: {len(current_file)} voci, ~{current_bytes:,} byte")

    print(f"\nTotale: {len(files)} file necessari")
    return files


def lua_str(s):
    """
    Serializza una stringa in formato Lua long string.
    Sceglie il livello minimo tale che NE il delimitatore di apertura
    NE quello di chiusura compaiano nel contenuto:
      livello 0: [[ ]]  - non deve contenere [[ ne ]]
      livello 1: [=[ ]=]  - non deve contenere [=[ ne ]=]
      ecc.
    """
    if not s:
        return "[[]]"
    s = str(s)
    level = 0
    while True:
        d = "=" * level
        if ("[" + d + "[") not in s and ("]" + d + "]") not in s:
            break
        level += 1
    d = "=" * level
    return f"[{d}[{s}]{d}]"


def validate_lua_longstrings(lua_code, pages_data):
    """
    Verifica che tutti i long string nel codice Lua siano bilanciati.
    Individua la voce problematica se presente.
    Restituisce None se ok, stringa descrittiva se c'e' un problema.
    Ottimizzato: usa re.finditer per trovare tutte le aperture in un colpo,
    evitando il loop carattere per carattere su file da ~1.4MB.
    """
    import re as _re

    def find_unclosed(text):
        # Trova tutte le aperture [=*[ in ordine, salta le chiusure gia' consumate
        pos = 0
        for m in _re.finditer(r'\[(?P<eq>=*)\[', text):
            if m.start() < pos:
                continue  # gia' consumato da una long string precedente
            eq = m.group('eq')
            close = ']' + eq + ']'
            start = m.end()
            end = text.find(close, start)
            if end == -1:
                return m.start(), 'Long string [' + eq + '[...] non chiuso'
            pos = end + len(close)
        return None, None

    pos, err = find_unclosed(lua_code)
    if not err:
        return None

    line_num = lua_code[:pos].count('\n') + 1

    # Cerca la voce problematica testando una per volta
    for j, page in enumerate(pages_data):
        try:
            cats_parts = ','.join(lua_str(c) for c in page.get('categorie', []))
            cats_lua = '{' + cats_parts + '}'
            tmpl_list = []
            for t in page.get('templates', []):
                nome = lua_str(t.get('nome', ''))
                params_lua = '{' + ','.join(lua_str(p) for p in t.get('params', [])) + '}'
                tmpl_list.append('{' + nome + ',' + params_lua + '}')
            tmpls_lua = '{' + ','.join(tmpl_list) + '}'
            preview = lua_str(page.get('preview', ''))
            titolo = lua_str(page['titolo'])
            ts = lua_str(page['timestamp'])
            row = '{' + titolo + ',' + ts + ',' + cats_lua + ',' + tmpls_lua + ',' + preview + '}'
            row_pos, row_err = find_unclosed(row)
            if row_err:
                msg = 'Voce #' + str(j+1) + ' ' + repr(page['titolo']) + ': ' + row_err
                msg += '\n  Preview: ' + repr(page.get('preview', ''))[:80]
                msg += '\n  Templates: ' + str(page.get('templates', []))[:200]
                return msg
        except Exception as ex:
            return 'Voce #' + str(j+1) + ' errore: ' + str(ex)

    return 'Errore a riga ' + str(line_num) + ': ' + err + ' (voce non identificata)'


def format_lua_data(pages_data, part_number, total_parts):
    """
    Formatta dati in Lua con formato compatto senza keyword ripetute per voce.
    Schema array posizionale:
      {titolo, timestamp, {categorie}, {{tmpl_nome,{params}}, ...}, preview}
    """
    lines = []
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines.append("-- Dati automatici per Modulo:VociRecenti")
    lines.append(f"-- PARTE {part_number} di {total_parts}")
    lines.append(f"-- Aggiornato: {now_str} UTC")
    lines.append(f"-- VERSIONE {VERSION}\n")
    lines.append("return {")
    lines.append(f"  u={lua_str(datetime.now().strftime('%d/%m/%Y %H:%M'))},")
    lines.append(f"  v={lua_str(VERSION)},")
    lines.append(f"  p={part_number},")
    lines.append(f"  tp={total_parts},")
    lines.append(f"  n={len(pages_data)},")
    lines.append("  d={")

    for i, page in enumerate(pages_data):
        try:
            sep = "," if i < len(pages_data) - 1 else ""
            lines.append(format_lua_row(page) + sep)
        except Exception as e:
            print(f"  WARNING: Skip voce {page.get('titolo', 'N/A')}: {e}")
            continue

    lines.append("  }")
    lines.append("}")
    return '\n'.join(lines)


def blank_old_data_files(num_files_needed):
    """Svuota eventuali file Dati vecchi oltre quelli necessari"""
    print(f"\nVerifica file obsoleti...")

    empty_structure = (
        "-- File cache obsoleto - Svuotato automaticamente\n"
        f"return {{u='(vuoto)',v='{VERSION}',p=0,tp=0,n=0,d={{}}}}"
    )

    blanked = 0
    i = num_files_needed + 1

    while i <= num_files_needed + 2:  # +2 e' sufficiente: il numero di file varia raramente di piu'
        page_name = f"{DATA_PAGE_PREFIX}{i}"
        page = pywikibot.Page(SITE, page_name)

        if page.exists():
            print(f"  Svuotamento {page_name} (obsoleto)...")
            try:
                page.text = empty_structure
                page.save(
                    summary=f'Bot: Voci recenti (cache) - File obsoleto svuotato (v{VERSION})',
                    minor=True,
                    bot=True
                )
                blanked += 1
                print(f"    OK Svuotato")
            except Exception as e:
                print(f"    ERRORE: {e}")
        else:
            break

        i += 1

    if blanked > 0:
        print(f"OK {blanked} file obsoleti svuotati")
    else:
        print("  Nessun file obsoleto")

    return blanked


def update_data_page(page_name, lua_code, part_num, total_parts):
    """Aggiorna singola pagina dati"""
    page = pywikibot.Page(SITE, page_name)
    try:
        page.text = lua_code
        page.save(
            summary=f'Bot: Voci recenti (cache) - Aggiornamento (v{VERSION}) - Parte {part_num}/{total_parts}',
            minor=True,
            bot=True
        )
        return True
    except Exception as e:
        print(f"    ERRORE: {e}")
        return False


# ========================================
# MAIN
# ========================================

def _fmt_elapsed(seconds):
    """Formatta una durata in secondi come stringa leggibile."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s:02d}s"


def check_deleted_pages(cached_pages):
    """
    Controlla via API batch quali voci della cache sono state cancellate,
    diventate redirect, o spostate fuori da NS0.
    Restituisce lista di titoli da rimuovere con motivo.
    Usa batch da BATCH_SIZE_CHECK titoli per minimizzare le chiamate API.
    """
    if not cached_pages:
        return []

    titles = [p['titolo'] for p in cached_pages]
    to_remove = []
    n = len(titles)
    checked = 0

    print(f"  Controllo {n} voci in cache via API batch ({BATCH_SIZE_CHECK} titoli/chiamata)...")

    for start in range(0, n, BATCH_SIZE_CHECK):
        batch = titles[start:start + BATCH_SIZE_CHECK]
        try:
            pages_info = {}
            query = SITE.simple_request(
                action='query',
                prop='info',
                titles='|'.join(batch),
                inprop=''
            )
            result = query.submit()
            query_data = result.get('query', {})
            pages = query_data.get('pages', {})

            # Mappa normalizzazioni (es. maiuscole/minuscole)
            normalized = {n['from']: n['to'] for n in query_data.get('normalized', [])}
            # Mappa redirect
            redirects = {r['from']: r['to'] for r in query_data.get('redirects', [])}

            for page_id, page_info in pages.items():
                title_in_result = page_info.get('title', '')

                # Risali al titolo originale (prima della normalizzazione)
                orig_title = title_in_result
                for norm_from, norm_to in normalized.items():
                    if norm_to == title_in_result:
                        orig_title = norm_from
                        break

                if page_id == '-1' or 'missing' in page_info:
                    to_remove.append((orig_title, 'non esiste'))
                elif 'redirect' in page_info:
                    to_remove.append((orig_title, 'redirect'))
                elif page_info.get('ns', 0) != 0:
                    to_remove.append((orig_title, f"NS{page_info.get('ns', '?')}"))

        except Exception as e:
            print(f"  WARNING batch {start//BATCH_SIZE_CHECK + 1}: {e}")

        checked += len(batch)
        if checked % 500 == 0 or checked == n:
            print(f"  [{checked}/{n}] Controllo...")

    return to_remove


def main():
    tee = setup_log()
    print("=" * 60)
    print(f"Bot VociRecenti v{VERSION} - RICERCA COMPLETA DA CUTOFF")
    print("=" * 60)

    if BOT_PASSWORD == 'inserisci_password_qui':
        print("ERRORE: Inserisci credenziali")
        tee.close()
        return

    run_start = datetime.now()
    print(f"  Avvio: {run_start.strftime('%H:%M:%S')}")

    print(f"\nConfigurazione:")
    print(f"  Limite voci:        {MAX_PAGES}")
    print(f"  Max car. per file:  {MAX_CHARS_PER_FILE:,}")
    print(f"  Prefisso file:      {DATA_PAGE_PREFIX}")
    print(f"  Max eta' voci:      {MAX_AGE_DAYS} giorni")
    print(f"  AutoClean:          {AutoClean}")
    if AutoClean == 'Once':
        print(f"  Fascia pulizia:     {AutoCleanTimeBegin} - {AutoCleanTimeEnd}")
    print(f"  CacheMoved:         {CACHE_MOVED_PAGE} (scansione NS: {NS_SCAN})")
    print(f"  Cache parsed flag:  {CACHE_PARSED_PAGE}")

    print(f"\nControllo PuliziaCache.py...")
    pulizia_ok = check_pulizia_version()

    print(f"\nLogin come {BOT_USERNAME}...")
    try:
        if not SITE.logged_in():
            SITE.login()
        if not SITE.logged_in():
            print("ERRORE: Login fallito!")
            tee.close()
            return
        print(f"OK - Login: {SITE.username()}\n")
    except Exception as e:
        print(f"ERRORE login: {e}")
        tee.close()
        return

    # ----------------------------------------
    # STEP 1: Pulizia cache (AutoClean)
    # ----------------------------------------
    print("=" * 60)
    print("STEP 1: PULIZIA CACHE AUTOMATICA")
    print("=" * 60)
    _t1 = datetime.now()
    print(f"  Ora corrente: {_t1.strftime('%H:%M')}")

    if should_run_cleanup():
        if pulizia_ok:
            run_cleanup()
        else:
            print("  SKIP pulizia: PuliziaCache.py non valida")
    print(f"  [STEP 1] Tempo: {_fmt_elapsed((datetime.now()-_t1).total_seconds())}")
    print()

    # ----------------------------------------
    # STEP 2: Carica cache esistente
    # ----------------------------------------
    print("=" * 60)
    print("STEP 2: CARICAMENTO CACHE ESISTENTE")
    print("=" * 60)
    _t2 = datetime.now()
    cached_pages, existing_titles = load_existing_cache_from_all_files()
    print(f"  [STEP 2] Tempo: {_fmt_elapsed((datetime.now()-_t2).total_seconds())}")

    # ----------------------------------------
    # STEP 3: Calcola data limite
    # ----------------------------------------
    print("=" * 60)
    print("STEP 3: CALCOLO DATA LIMITE")
    print("=" * 60)
    _t3 = datetime.now()
    cutoff_date = compute_cutoff_date(cached_pages)
    print(f"  [STEP 3] Tempo: {_fmt_elapsed((datetime.now()-_t3).total_seconds())}")

    # ----------------------------------------
    # STEP 3b: Controllo voci cancellate/redirect
    # ----------------------------------------
    print()
    print("=" * 60)
    print("STEP 3b: CONTROLLO VOCI CANCELLATE/REDIRECT")
    print("=" * 60)
    _t3b = datetime.now()
    deleted_titles = set()
    if CheckDeleted:
        removed_info = check_deleted_pages(cached_pages)
        counts = {}
        for title, reason in removed_info:
            deleted_titles.add(title.lower())
            counts[reason] = counts.get(reason, 0) + 1
            print(f"  RIMOSSA ({reason}): {title}")
        if removed_info:
            summary = ', '.join(f"{v} {k}" for k, v in counts.items())
            print(f"  Totale rimosse: {len(removed_info)} ({summary})")
            # Rimuovi subito da cached_pages per non portarle avanti
            cached_pages = [p for p in cached_pages if p['titolo'].lower() not in deleted_titles]
            existing_titles -= deleted_titles
        else:
            print("  Nessuna voce cancellata o redirect trovata")
    else:
        print("  CheckDeleted=False -> skip")
    print(f"  [STEP 3b] Tempo: {_fmt_elapsed((datetime.now()-_t3b).total_seconds())}")

    # ----------------------------------------
    # STEP 4a: CacheMoved manuale (sotto CacheParsed)
    # ----------------------------------------
    print("=" * 60)
    print("STEP 4a: CACHE MANUALE (CacheMoved)")
    print("=" * 60)
    _t4a = datetime.now()

    should_load = check_should_load_manual_cache()
    titles_to_remove = []
    pages_to_update = []

    if should_load:
        print("CacheParsed assente o != 'True' -> elaborazione CacheMoved...")
        # Lookup {titolo: record} per gestire 'Aggiorna:' in O(1)
        cached_by_title = {p['titolo']: p for p in cached_pages}
        cm_pages, titles_to_remove, pages_to_update = read_cache_moved(
            existing_titles, cutoff_date, cached_by_title)

        if cm_pages:
            cached_pages.extend(cm_pages)
            print(f"\n  Aggiunte {len(cm_pages)} voci da CacheMoved")
        else:
            print("  Nessuna voce nuova da CacheMoved")

        if pages_to_update:
            # I vecchi record sono gia' in titles_to_remove e saranno
            # eliminati in STEP 6. Aggiungiamo i record aggiornati.
            cached_pages.extend(pages_to_update)
            print(f"  Aggiornate {len(pages_to_update)} voci (Aggiorna:)")

        mark_manual_cache_as_parsed()
    else:
        print("CacheParsed = 'True' -> CacheMoved gia' processata, skip")
    print(f"  [STEP 4a] Tempo: {_fmt_elapsed((datetime.now()-_t4a).total_seconds())}")

    # ----------------------------------------
    # STEP 4b: Scarica nuove voci da RecentChanges NS0 (fonte principale)
    # ----------------------------------------
    print()
    print("=" * 60)
    print("STEP 4b: RICERCA NUOVE VOCI NS0 (RecentChanges)")
    print("=" * 60)
    _t4b = datetime.now()

    print("Caricamento moves_cache...")
    moves_cache = load_moves_cache()

    new_pages = get_new_pages_only(existing_titles, cutoff_date, moves_cache)

    print("\nSalvataggio moves_cache...")
    save_moves_cache(moves_cache)
    print(f"  [STEP 4b] Tempo: {_fmt_elapsed((datetime.now()-_t4b).total_seconds())}")

    # ----------------------------------------
    # STEP 5: Scansione altri namespace (NS2/NS118)
    # ----------------------------------------
    print("\n" + "=" * 60)
    print("STEP 5: SCANSIONE ALTRI NAMESPACE (NS2/NS118)")
    print("=" * 60)
    _t5 = datetime.now()

    ns_pages = scan_and_load_ns_pages(existing_titles, cutoff_date, moves_cache)
    if ns_pages:
        cached_pages.extend(ns_pages)
        print(f"  Aggiunte {len(ns_pages)} voci da altri namespace")
    print(f"  [STEP 5] Tempo: {_fmt_elapsed((datetime.now()-_t5).total_seconds())}")


    # ----------------------------------------
    # STEP 6: Unisci, rimuovi, ordina, tronca
    # ----------------------------------------
    print("=" * 60)
    print("STEP 6: UNIONE E ORDINAMENTO")
    print("=" * 60)
    _t6 = datetime.now()

    # Filtra cached_pages: rimuove voci troppo vecchie già in cache.
    # Usa move_timestamp se presente (voci da sandbox spostate di recente),
    # altrimenti timestamp di creazione. Cutoff fisso a MAX_AGE_DAYS giorni fa,
    # indipendente dalla voce più vecchia in cache (a differenza di cutoff_date).
    cutoff_30 = datetime.now() - timedelta(days=MAX_AGE_DAYS)
    cutoff_30_str = cutoff_30.strftime('%Y%m%d%H%M%S')
    before_filter = len(cached_pages)
    cached_pages = [
        p for p in cached_pages
        if (p.get('move_timestamp') or p.get('timestamp', '')) >= cutoff_30_str
    ]
    filtered_old = before_filter - len(cached_pages)
    if filtered_old > 0:
        print(f"  Voci vecchie rimosse dalla cache: {filtered_old}")

    all_pages = new_pages + cached_pages

    # Applica rimozioni da CacheMoved (righe Rimuovi:)
    if titles_to_remove:
        before = len(all_pages)
        # I titoli in pages_to_update sono in titles_to_remove solo per eliminare
        # il vecchio record prima di inserire quello aggiornato. Il nuovo record
        # e' gia' in all_pages (aggiunto via cached_pages), quindi va preservato.
        update_titles_set = {p['titolo'].lower() for p in pages_to_update}
        remove_set = {t.lower() for t in titles_to_remove if t.lower() not in update_titles_set}
        all_pages = [p for p in all_pages if p.get('titolo', '').lower() not in remove_set]
        removed_count = before - len(all_pages)
        print(f"  Voci rimosse da CacheMoved: {removed_count} "
              f"(richieste {len(titles_to_remove)})")

    # Dedup esplicito: se un titolo compare piu' volte (es. vecchio record in cache
    # + record aggiornato da Aggiorna:), mantieni il record aggiornato se presente
    # in pages_to_update, altrimenti il primo trovato (ordine di all_pages).
    if pages_to_update:
        update_titles_map = {p['titolo']: p for p in pages_to_update}
        seen_titles = {}
        deduped = []
        for p in all_pages:
            t = p['titolo']
            if t not in seen_titles:
                seen_titles[t] = len(deduped)
                deduped.append(p)
            elif t in update_titles_map:
                # Sostituisci il record gia' inserito con quello aggiornato
                deduped[seen_titles[t]] = update_titles_map[t]
        if len(deduped) < len(all_pages):
            print(f"  Dedup: {len(all_pages) - len(deduped)} duplicati rimossi (record aggiornati mantenuti)")
        all_pages = deduped

    all_pages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    all_pages = all_pages[:MAX_PAGES]

    rimosse = len(new_pages) + len(cached_pages) - len(all_pages)
    print(f"\nVoci finali: {len(all_pages)}")
    print(f"  Nuove da RecentChanges (NS0): {len(new_pages)}")
    print(f"  Nuove da altri NS (NS2/118):  {len(ns_pages)}")
    print(f"  Dalla cache:                  {len(cached_pages)}")
    if titles_to_remove:
        print(f"  Rimosse da CacheMoved:  {removed_count}")
    if rimosse > 0:
        print(f"  Rimosse per limite:     {rimosse}")
    print(f"  [STEP 6] Tempo: {_fmt_elapsed((datetime.now()-_t6).total_seconds())}")

    # ----------------------------------------
    # STEP 7: Suddividi in file e salva
    # ----------------------------------------
    _t_split = datetime.now()
    file_groups = split_pages_into_files(all_pages)
    print(f"  [split] Tempo: {_fmt_elapsed((datetime.now()-_t_split).total_seconds())}")

    print("\n" + "=" * 60)
    print("STEP 7: GENERAZIONE E SALVATAGGIO")
    print("=" * 60)
    _t7 = datetime.now()

    total_files = len(file_groups)
    successes = 0

    for i, pages_group in enumerate(file_groups, 1):
        page_name = f"{DATA_PAGE_PREFIX}{i}"
        print(f"\n[{i}/{total_files}] {page_name}")
        print(f"  Voci: {len(pages_group)}")

        _t_fmt = datetime.now()
        lua_code = format_lua_data(pages_group, i, total_files)
        size_mb = len(lua_code) / (1024 * 1024)
        print(f"  Dimensione: {size_mb:.2f} MB  [generazione: {_fmt_elapsed((datetime.now()-_t_fmt).total_seconds())}]")

        if size_mb > 2.0:
            print(f"  ATTENZIONE: Supera 2MB! Riduci MAX_CHARS_PER_FILE")

        # Validazione: verifica long string bilanciati e individua voce problematica
        _t_val = datetime.now()
        validation_error = validate_lua_longstrings(lua_code, pages_group)
        _val_elapsed = _fmt_elapsed((datetime.now() - _t_val).total_seconds())
        if validation_error:
            print(f"  ERRORE VALIDAZIONE ({_val_elapsed}): {validation_error}")
            print(f"  Salvataggio saltato per evitare corruzione cache")
            continue
        print(f"  Validazione OK ({_val_elapsed})")

        print(f"  Salvataggio...")
        _t_save = datetime.now()
        if update_data_page(page_name, lua_code, i, total_files):
            elapsed_save = _fmt_elapsed((datetime.now() - _t_save).total_seconds())
            print(f"  OK Salvato! ({elapsed_save})")
            successes += 1
        else:
            print(f"  ERRORE salvataggio")

    _t_blank = datetime.now()
    blank_old_data_files(total_files)
    print(f"  [blank_old] Tempo: {_fmt_elapsed((datetime.now()-_t_blank).total_seconds())}")
    print(f"  [STEP 7] Tempo: {_fmt_elapsed((datetime.now()-_t7).total_seconds())}")

    # ----------------------------------------
    # STEP 8: Riepilogo finale
    # ----------------------------------------
    total_elapsed = _fmt_elapsed((datetime.now() - run_start).total_seconds())
    print("\n" + "=" * 60)
    if successes == total_files:
        print("OK COMPLETATO!")
        print("=" * 60)
        print(f"  Voci totali:  {len(all_pages)}")
        print(f"  File creati:  {total_files}")
        print(f"  Nuove voci:   {len(new_pages)}")
        print(f"  Tempo totale: {total_elapsed}")
        print(f"\nURL file:")
        for i in range(1, total_files + 1):
            print(f"  https://it.wikipedia.org/wiki/{DATA_PAGE_PREFIX}{i}")
    else:
        print(f"ATTENZIONE: {successes}/{total_files} file salvati correttamente")
        print(f"  Tempo totale: {total_elapsed}")

    tee.close()


if __name__ == '__main__':
    main()
