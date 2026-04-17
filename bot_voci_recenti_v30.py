#!/usr/bin/env python3
"""
Bot VociRecenti v9.1.2

Changelog:
- v9.1.2: FIX ordinamento STEP 6: le voci spostate da altro namespace non venivano
          piu' visualizzate una volta raggiunto il limite MAX_PAGES.
          Il problema era nell'ordinamento che usava solo 'timestamp' (data di prima
          creazione): voci create mesi fa ma spostate di recente finivano in fondo alla
          lista e venivano tagliate dal troncamento a MAX_PAGES.
          L'ordinamento ora usa la stessa logica gia' presente nel filtro per eta':
          move_timestamp se presente, altrimenti timestamp. Cosi' una voce creata a
          luglio 2025 ma spostata ieri scala in cima e non viene eliminata.
- v9.1.1: (precedente)
- v9.1: FIX doppia scrittura su Wikipedia: rimossa la chiamata a _cleanup_save_cache
        da run_cleanup_internal (che ora restituisce solo i dati puliti senza scrivere).
        Il salvataggio avviene una sola volta in STEP 7, come previsto dalla fusione v9.0.
        FIX CRITICO timestamp creazione: rvdir=newer con rvlimit su batch multi-titolo
        genera 'invalidparammix' nell'API MediaWiki (il parametro e' ammesso solo per
        una pagina alla volta). _cleanup_fetch_wikitext_for_titles ora esegue la
        CHIAMATA A (rvdir=newer&rvlimit=1) in un loop titolo per titolo; la CHIAMATA B
        (rvprop=content, nessun parametro di ordinamento) rimane in batch.
- v9.0: MAJOR RELEASE — Fusione completa di PuliziaCache.py nel bot.
        La pulizia cache non e' piu' uno script separato: viene eseguita
        internamente al bot nella stessa esecuzione, eliminando la doppia
        scrittura su Wikipedia che si verificava quando AutoClean='Every'.
        AGGIUNTA modalita' DRY-RUN (--dry-run da riga di comando oppure
        DRY_RUN=True nel codice): esegue tutte le fasi e tutte le chiamate
        API senza scrivere nulla su Wikipedia. Il report diagnostico al
        termine mostra statistiche aggregate e allarmi per individuare
        corruzioni prima che avvengano. Con DRY_RUN il bot in produzione
        su Toolforge puo' restare attivo mentre si esegue il test.
        BATCH API ovunque: download_page_data e validate_ns_or_manual_page
        riscritte per usare chiamate batch (prop=info|categories|revisions,
        50 titoli per chiamata) invece di chiamate singole per voce,
        allineandosi all'approccio gia' presente in PuliziaCache >=PC-2.3.
        Riduzione stimata delle chiamate API: da ~N singole a ~N/50 batch.
        Rimossi: subprocess.run(PuliziaCache.py), check_pulizia_version(),
        run_cleanup(), PULIZIA_SCRIPT, REQUIRED_PULIZIA_VERSION.
        Aggiunto: run_cleanup_internal() che esegue le 4 fasi di pulizia
        nella stessa sessione pywikibot del bot, con DRY_RUN support.
        L'oggetto delle modifiche diventa:
        'Bot: Voci recenti - Aggiornamento cache (v.9.0)'
        dove la versione e' una variabile che si aggiorna ad ogni release.
- v8.46: FIX timestamp voci spostate: il campo timestamp (data visibile nella lista)
         tornato a essere sempre la data di prima creazione (oldest_revision).
         FIX spostamenti NS0->NS0: get_moved_to_ns0_since_cutoff ora scarta i
         log dove il namespace sorgente e' gia' 0.
- v8.45: Per ricreazioni e spostamenti usa rc_ts_it/move_ts come timestamp in cache.
- v8.44: FIX confronto UTC vs IT in get_new_creations_since_cutoff e scan_other_namespaces.
- v8.43: FIX ricreazioni mw-recreated.
- v8.42: FIX timestamp IT senza dipendenze esterne (algoritmo DST europeo puro).
- v8.41: Timestamp in ora italiana (CET/CEST).
- v8.40: Versione PuliziaCache nell'oggetto modifiche.
- (precedenti: vedi changelog completo in archivio)
"""

import pywikibot
import pywikibot.config as config
from datetime import datetime, timedelta
import re
from urllib.parse import unquote
import json
import os
import sys
import logging
import calendar as _calendar

# ========================================
# FUSO ORARIO ITALIANO - implementazione robusta senza dipendenze esterne
# Non usa ZoneInfo ne pytz: calcola offset CET/CEST con l'algoritmo DST europeo
# (ultima domenica di marzo ore 01:00 UTC -> +2, ultima domenica di ottobre
# ore 01:00 UTC -> +1). Funziona su qualsiasi sistema Linux/Windows/Toolforge.
# ========================================

def _last_sunday(year, month):
    """Restituisce il giorno (int) dell'ultima domenica del mese dato."""
    last_day = _calendar.monthrange(year, month)[1]
    last_weekday = datetime(year, month, last_day).weekday()  # 0=lun, 6=dom
    return last_day - (last_weekday - 6) % 7


def _it_offset_for_utc(dt_utc_naive):
    """
    Restituisce l'offset italiano in ore (+1 CET, +2 CEST) per un datetime
    UTC naive. Regola DST europea:
      inizio ora legale: ultima domenica di marzo alle 01:00 UTC
      fine ora legale:   ultima domenica di ottobre alle 01:00 UTC
    """
    y = dt_utc_naive.year
    dst_start = datetime(y, 3,  _last_sunday(y, 3),  1, 0, 0)
    dst_end   = datetime(y, 10, _last_sunday(y, 10), 1, 0, 0)
    return 2 if dst_start <= dt_utc_naive < dst_end else 1


def ts_utc_to_it(ts):
    """
    Converte un pywikibot.Timestamp (o qualsiasi datetime, aware o naive)
    in stringa YYYYMMDDHHMMSS in ora italiana (CET/CEST).
    Se ts e' aware l'offset UTC viene rimosso prima del calcolo DST.
    Se ts e' naive viene trattato come UTC (comportamento di pywikibot).
    Non dipende da ZoneInfo ne pytz.
    """
    dt = ts.replace(tzinfo=None)  # normalizza a naive-UTC
    return (dt + timedelta(hours=_it_offset_for_utc(dt))).strftime('%Y%m%d%H%M%S')


def ts_utc_str_to_it(ts_str):
    """
    Converte una stringa timestamp UTC in formato ISO 8601
    (es. '2026-04-14T01:35:00Z') oppure YYYYMMDDHHMMSS
    nella corrispondente stringa YYYYMMDDHHMMSS in ora italiana.
    Usata nei risultati delle chiamate API batch.
    """
    ts_str = ts_str.strip()
    if 'T' in ts_str:
        ts_str_clean = ts_str.replace('Z','').replace('-','').replace('T','').replace(':','')
    else:
        ts_str_clean = ts_str
    try:
        dt = datetime.strptime(ts_str_clean, '%Y%m%d%H%M%S')
        return (dt + timedelta(hours=_it_offset_for_utc(dt))).strftime('%Y%m%d%H%M%S')
    except Exception:
        return ts_str_clean


def migrate_ts_utc_to_it(ts_str):
    """
    Converte una stringa YYYYMMDDHHMMSS interpretata come UTC
    nel corrispondente orario italiano (CET/CEST).
    Usata nella migrazione one-shot dei timestamp gia' in cache.
    """
    try:
        dt = datetime.strptime(ts_str, '%Y%m%d%H%M%S')
        return (dt + timedelta(hours=_it_offset_for_utc(dt))).strftime('%Y%m%d%H%M%S')
    except Exception:
        return ts_str


def now_it():
    """
    Restituisce il datetime corrente in ora italiana (CET/CEST) come oggetto
    naive pronto per strftime e confronti con timestamp delle voci.
    Non dipende da ZoneInfo ne pytz.
    """
    from datetime import timezone as _tz
    utc_now = datetime.now(_tz.utc).replace(tzinfo=None)
    return utc_now + timedelta(hours=_it_offset_for_utc(utc_now))

# ========================================
# CONFIGURAZIONE
# ========================================
MAX_PAGES = 3500                            # Totale voci da mantenere
MAX_CHARS_PER_FILE = 1500000               # ~1.5MB per file
DATA_PAGE_PREFIX = 'Modulo:VociRecenti/Dati'
NAMESPACE = 0
MAX_ITERATIONS = 100
TIMEOUT = 300
VERSION = '9.1.2'
MAX_AGE_DAYS = 30
config.put_throttle = 1
config.minthrottle = 0
config.maxthrottle = 2

# --- Modalita' DRY-RUN ---
# Se True: esegue tutte le fasi e tutte le chiamate API ma NON salva nulla
# su Wikipedia. Utile per testing senza interrompere il bot in produzione.
# Puo' essere attivata anche da riga di comando con --dry-run.
DRY_RUN = False

# --- Configurazione pulizia automatica ---
# 'Once'  = una volta per fascia oraria
# 'Every' = ad ogni esecuzione del bot
# 'None'  = mai
AutoClean = 'Every'

# Fascia oraria in cui eseguire la pulizia (formato 'HH:MM')
AutoCleanTimeBegin = '02:00'
AutoCleanTimeEnd   = '05:00'

# Percorso directory dati
DATA_DIR = os.environ.get('BOT_DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
CLEANUP_STATE_FILE = os.path.join(DATA_DIR, 'cleanup_state.json')
MOVES_CACHE_FILE   = os.path.join(DATA_DIR, 'moves_cache.json')
MOVES_CACHE_MAX_AGE_DAYS = 30

# File di log
LOG_FILE      = os.path.join(DATA_DIR, 'bot_voci_recenti.log')
LOG_MAX_BYTES = 2 * 1024 * 1024  # 2 MB

# Pulizia interna — parametri
CLEANUP_MAX_AGE_DAYS       = 30   # rimuovi voci create/spostate piu' di N giorni fa
CLEANUP_REMOVE_DELETED     = True
CLEANUP_REMOVE_REDIRECTS   = True
CLEANUP_REMOVE_WRONG_NS    = True
CLEANUP_REMOVE_TOO_OLD     = True
CLEANUP_BATCH_SIZE         = 50   # titoli per chiamata API (max MediaWiki)
CLEANUP_BATCH_SIZE_REV     = 10   # titoli per chiamata revisions (wikitext puo' essere grande)
CLEANUP_LOG_FILE           = os.path.join(DATA_DIR, 'pulizia_cache.log')

# Controllo voci cancellate/redirect ad ogni run del bot (STEP 3b)
CheckDeleted      = True
BATCH_SIZE_CHECK  = 50

# Namespace da scansionare per voci spostate in NS0
NS_SCAN = [2, 118]

# Cache voci da altri namespace
CACHE_MOVED_PAGE  = 'Utente:BotVociRecenti/CacheMoved'
CACHE_PARSED_PAGE = 'Utente:BotVociRecenti/CacheParsed'
# ========================================

SITE = pywikibot.Site('it', 'wikipedia')

_LUA_FILE_OVERHEAD = 300  # margine header + struttura file

# Handle globale al file di log della pulizia (usato da log/log_only interni)
_cleanup_log_file = None


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
        return begin_t <= now_t < end_t
    else:
        return now_t >= begin_t or now_t < end_t


def _load_cleanup_state():
    if not os.path.exists(CLEANUP_STATE_FILE):
        return {'cleaned_today': False}
    try:
        with open(CLEANUP_STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'cleaned_today': False}


def _save_cleanup_state(state):
    try:
        with open(CLEANUP_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"  WARNING: impossibile salvare cleanup_state.json: {e}")


def should_run_cleanup():
    """
    Determina se la pulizia cache deve essere eseguita in questo run.
    AutoClean='Every' -> sempre True
    AutoClean='None'  -> sempre False
    AutoClean='Once'  -> una volta per fascia oraria
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
        if state.get('cleaned_today', False):
            state['cleaned_today'] = False
            _save_cleanup_state(state)
            print(f"  AutoClean=Once, fuori fascia ({AutoCleanTimeBegin}-{AutoCleanTimeEnd}) -> flag resettato")
        else:
            print(f"  AutoClean=Once, fuori fascia ({AutoCleanTimeBegin}-{AutoCleanTimeEnd}) -> skip")
        return False

    if state.get('cleaned_today', False):
        print(f"  AutoClean=Once, in fascia ({AutoCleanTimeBegin}-{AutoCleanTimeEnd}) -> pulizia gia' eseguita, skip")
        return False

    print(f"  AutoClean=Once, in fascia ({AutoCleanTimeBegin}-{AutoCleanTimeEnd}) -> eseguo pulizia")
    state['cleaned_today'] = True
    _save_cleanup_state(state)
    return True


# ========================================
# MOVES CACHE
# ========================================

def load_moves_cache():
    cache = {}
    if os.path.exists(MOVES_CACHE_FILE):
        try:
            with open(MOVES_CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
        except Exception as e:
            print(f"  WARNING: impossibile leggere moves_cache.json: {e}")
            cache = {}

    cutoff = (now_it() - timedelta(days=MOVES_CACHE_MAX_AGE_DAYS)).strftime('%Y%m%d%H%M%S')
    before = len(cache)
    cache = {t: v for t, v in cache.items() if v.get('processed_at', '0') >= cutoff}
    removed = before - len(cache)
    if removed > 0:
        print(f"  moves_cache: {len(cache)} entry ({removed} scadute rimosse)")
    else:
        print(f"  moves_cache: {len(cache)} entry")
    return cache


def save_moves_cache(cache):
    try:
        with open(MOVES_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=None, separators=(',', ':'))
        print(f"  moves_cache: salvate {len(cache)} entry")
    except Exception as e:
        print(f"  WARNING: impossibile salvare moves_cache.json: {e}")


def checkpoint_moves_cache(cache, counter, interval=200):
    if counter % interval == 0:
        save_moves_cache(cache)
    return counter


# ========================================
# LOG SU FILE
# ========================================

class _Tee:
    """Sostituisce sys.stdout reindirizzando ogni write() sia al terminale
    che al file di log, senza buffering aggiuntivo."""
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
    """Attiva il logging su file affiancato all'output a video."""
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


# ========================================
# LOG PULIZIA (su file separato pulizia_cache.log)
# ========================================

def _clog(msg):
    """Scrive msg sia a schermo che nel file di log della pulizia."""
    print(msg)
    if _cleanup_log_file:
        _cleanup_log_file.write(msg + '\n')
        _cleanup_log_file.flush()


def _clog_only(msg):
    """Scrive msg solo nel file di log della pulizia (verbose)."""
    if _cleanup_log_file:
        _cleanup_log_file.write(msg + '\n')
        _cleanup_log_file.flush()


# ========================================
# CALCOLO DATA LIMITE
# ========================================

def compute_cutoff_date(cached_pages):
    """Calcola la data limite per accettare nuove voci."""
    cutoff_30 = now_it() - timedelta(days=MAX_AGE_DAYS)

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
    try:
        page = pywikibot.Page(SITE, CACHE_PARSED_PAGE)
        if not page.exists():
            return True
        return page.text.strip() != "True"
    except Exception:
        return True


def mark_manual_cache_as_parsed():
    if DRY_RUN:
        print(f"  [DRY-RUN] Skip marcatura CacheParsed")
        return
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


# ========================================
# PARSER LUA ROBUSTO (condiviso bot + pulizia)
# ========================================

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
    """Parsa vecchio formato con keyword: {titolo=[[...]], timestamp='...', ...}"""
    try:
        titolo_match = re.search(r'titolo\s*=\s*\[\[(.+?)\]\]', block)
        if not titolo_match:
            return None
        titolo = titolo_match.group(1)
        timestamp_match = re.search(r"timestamp\s*=\s*['\"](\\d{14})['\"]", block)
        if not timestamp_match:
            return None
        timestamp = timestamp_match.group(1)
        categorie = []
        cat_section_match = re.search(r'categorie\s*=\s*\{(.+?)\}(?:,|\s*contenuto)', block, re.DOTALL)
        if cat_section_match:
            cat_content = cat_section_match.group(1)
            categorie = re.findall(r'\[\[(.+?)\]\]', cat_content)
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
    """
    stripped = block.lstrip('{ \t\n\r')
    if not stripped.startswith('['):
        return parse_single_voce_legacy(block)

    try:
        pos = 0
        ob = block.find('{')
        if ob == -1:
            return None
        pos = ob + 1

        def next_longstring(p):
            while p < len(block) and block[p] in ' \t\n\r,':
                p += 1
            return extract_lua_longstring(block, p)

        titolo, pos = next_longstring(pos)
        if titolo is None:
            return None
        timestamp, pos = next_longstring(pos)
        if timestamp is None:
            return None

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
                t_nome, t_pos = extract_lua_longstring(t_inner, 0)
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

        preview, pos = next_longstring(pos)
        if preview is None:
            preview = ""

        move_timestamp, pos = next_longstring(pos)
        if not move_timestamp:
            move_timestamp = ""

        record = {
            'titolo': titolo,
            'timestamp': timestamp,
            'categorie': categorie,
            'templates': templates,
            'preview': preview
        }
        if move_timestamp:
            record['move_timestamp'] = move_timestamp
        return record
    except Exception:
        return None


def parse_lua_to_json(lua_content):
    """
    Converte contenuto Lua in struttura Python.
    Rileva il formato automaticamente:
    - Nuovo formato (d={...}): parsing veloce per righe
    - Vecchio formato (voci={...}): parsing bilanciato delle graffe
    """
    voci = []
    m_new = re.search(r'(?<![a-zA-Z_])d\s*=\s*\{', lua_content)
    m_old = re.search(r'voci\s*=\s*\{', lua_content)

    if m_new:
        brace_start = lua_content.find('{', m_new.start())
        if brace_start == -1:
            return voci
        section = lua_content[brace_start:]
        for line in section.splitlines():
            stripped = line.strip()
            if stripped.startswith('{['):
                if stripped.endswith(','):
                    stripped = stripped[:-1]
                voce = parse_single_voce(stripped)
                if voce:
                    voci.append(voce)
        return voci

    elif m_old:
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


def load_existing_cache_from_all_files():
    """Carica cache da TUTTI i file esistenti, ignorando duplicati.
    Migrazione one-shot: se un file non ha il flag '-- tz=IT-v8.42' in testa,
    i timestamp vengono convertiti da UTC a ora italiana prima di essere
    inseriti in memoria."""
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
            needs_migration = '-- tz=IT-v8.42' not in content[:500]
            if needs_migration:
                print(f"    Migrazione timestamp UTC->IT per {page_name}...")
            voci = parse_lua_to_json(content)
            migrated = 0
            added = 0
            duplicates = []
            for voce in voci:
                if needs_migration:
                    ts = voce.get('timestamp', '')
                    if ts and len(ts) == 14:
                        voce['timestamp'] = migrate_ts_utc_to_it(ts)
                        migrated += 1
                    mt = voce.get('move_timestamp', '')
                    if mt and len(mt) == 14:
                        voce['move_timestamp'] = migrate_ts_utc_to_it(mt)
                if voce['titolo'] not in existing_titles:
                    existing_pages.append(voce)
                    existing_titles.add(voce['titolo'])
                    added += 1
                else:
                    duplicates.append(voce['titolo'])
            msg = f"    OK {added} voci caricate"
            if needs_migration and migrated:
                msg += f" ({migrated} timestamp migrati UTC->IT)"
            if duplicates:
                msg += f" ({len(duplicates)} duplicate ignorate)"
            print(msg)
        except Exception as e:
            print(f"    ERRORE: {e}")

    print(f"\nOK Cache totale: {len(existing_pages)} voci da {len(data_pages)} file\n")
    return existing_pages, existing_titles


# ========================================
# TEMPLATE DAL WIKITEXT (condiviso bot + pulizia)
# ========================================

def parse_templates_from_wikitext(text):
    """
    Estrae template di primo livello dal wikitesto.
    Per ogni template restituisce nome e lista dei nomi di parametri valorizzati.
    Ignora: template annidati, parser functions (#if, #switch, ecc.).
    """
    if not text:
        return []
    # Rimuovi commenti HTML
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
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
                if raw_name and not raw_name.startswith('#') and not raw_name.startswith(':') and ':' not in raw_name.split('|')[0]:
                    name = raw_name.replace('_', ' ').strip()
                    name = name.replace('{', '').replace('}', '')
                    params = []
                    for part in parts[1:]:
                        if '=' in part:
                            pname, _, pval = part.partition('=')
                            pname = pname.strip().replace('{','').replace('}','').strip()
                            pval = pval.strip()
                            if pname and pval:
                                params.append(pname)
                        else:
                            pval = part.strip().replace('{','').replace('}','').strip()
                            if pval and '[' not in pval and ']' not in pval:
                                params.append(pval[:100])
                    templates.append({'nome': name, 'params': params})
                i = j + 2
                continue
        i += 1
    return templates


# ========================================
# FORMATTAZIONE LUA (condivisa bot + pulizia)
# ========================================

def lua_str(s):
    """
    Serializza una stringa in formato Lua long string.
    Sceglie il livello minimo di '=' tale che ne il delimitatore di apertura
    ne quello di chiusura compaiano nel contenuto.
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


def format_lua_row(page):
    """Formatta una singola voce in Lua (una riga del array d={}).
    Struttura: {titolo, timestamp, {categorie}, {templates}, preview, move_timestamp}
    Il 6° campo move_timestamp e' una stringa vuota se non presente.
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


def format_lua_data(pages_data, part_number, total_parts):
    """
    Formatta dati in Lua con formato compatto senza keyword ripetute per voce.
    Schema array posizionale:
      {titolo, timestamp, {categorie}, {{tmpl_nome,{params}}, ...}, preview, move_ts}
    """
    lines = []
    now_str = now_it().strftime('%Y-%m-%d %H:%M:%S')
    lines.append("-- Dati automatici per Modulo:VociRecenti")
    lines.append(f"-- PARTE {part_number} di {total_parts}")
    lines.append(f"-- Aggiornato: {now_str} ora italiana")
    lines.append(f"-- VERSIONE {VERSION}")
    lines.append("-- tz=IT-v8.42\n")
    lines.append("return {")
    lines.append(f"  u={lua_str(now_it().strftime('%d/%m/%Y %H:%M'))},")
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


def split_pages_into_files(pages_data):
    """
    Divide le voci in piu' file misurando la dimensione Lua reale di ogni voce,
    garantendo che ogni file non superi MAX_CHARS_PER_FILE.
    """
    print(f"\nSuddivisione in file (max {MAX_CHARS_PER_FILE:,} byte per file)...")
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


# ========================================
# PULIZIA CACHE INTERNA (ex PuliziaCache.py)
# ========================================

def _cleanup_fetch_categories_for_titles(titles):
    """
    Scarica le categorie complete per una lista di titoli tramite API batch.
    Itera su batch da CLEANUP_BATCH_SIZE titoli. Per ogni batch gestisce la
    paginazione con clcontinue. Restituisce dict {titolo: [lista categorie]}.
    NON usa clshow=!hidden: le categorie delle disambigue sono nascoste e
    verrebbero silenziosamente scartate.
    """
    cats_by_title = {t: [] for t in titles}

    for batch_start in range(0, len(titles), CLEANUP_BATCH_SIZE):
        batch = titles[batch_start:batch_start + CLEANUP_BATCH_SIZE]
        norm_to_orig = {}
        params = {
            'action': 'query',
            'prop': 'categories',
            'titles': '|'.join(batch),
            'cllimit': '500',
            'format': 'json',
        }
        while True:
            try:
                result = SITE.simple_request(**params).submit()
            except Exception as e:
                _clog_only(f"  WARNING _fetch_categories batch [{batch_start//CLEANUP_BATCH_SIZE + 1}]: {e}")
                break
            query_data = result.get('query', {})
            if not norm_to_orig:
                for n in query_data.get('normalized', []):
                    norm_to_orig[n['to']] = n['from']
            for page_id, page_info in query_data.get('pages', {}).items():
                if page_id == '-1' or 'missing' in page_info:
                    continue
                title_norm = page_info.get('title', '')
                orig = norm_to_orig.get(title_norm, title_norm)
                key = orig if orig in cats_by_title else title_norm
                if key not in cats_by_title:
                    continue
                for cat in page_info.get('categories', []):
                    cat_title = cat.get('title', '')
                    if ':' in cat_title:
                        cat_title = cat_title.split(':', 1)[1]
                    if cat_title and cat_title not in cats_by_title[key]:
                        cats_by_title[key].append(cat_title)
            cont = result.get('query-continue', {}).get('categories', {})
            if not cont:
                cont = result.get('continue', {})
                clcontinue = cont.get('clcontinue', '')
            else:
                clcontinue = cont.get('clcontinue', '')
            if clcontinue:
                params['clcontinue'] = clcontinue
            else:
                break

    return cats_by_title


def _cleanup_fetch_wikitext_for_titles(titles):
    """
    Scarica wikitext e timestamp di prima creazione per una lista di titoli.

    CHIAMATA A — timestamp prima creazione, un titolo alla volta:
      rvdir=newer e rvlimit non sono compatibili con batch multi-titolo
      nell'API MediaWiki (invalidparammix). Si itera quindi titolo per titolo.
      Per attenuare l'impatto sulle performance si usa CLEANUP_BATCH_SIZE_REV
      come taglia dei gruppi di chiamate consecutive prima di un breve yield.

    CHIAMATA B — wikitext corrente, batch da CLEANUP_BATCH_SIZE_REV titoli:
      rvprop=content senza parametri di ordinamento: compatibile con batch.

    Restituisce dict {titolo: {'wikitext': str, 'creation_ts': str (IT)}}
    """
    result_by_title = {}
    creation_ts_by_title = {}

    # --- CHIAMATA A: timestamp di prima creazione (uno per volta) ---
    for title in titles:
        try:
            result = SITE.simple_request(
                action='query',
                prop='revisions',
                titles=title,
                rvprop='timestamp',
                rvdir='newer',
                rvlimit='1',
                format='json',
            ).submit()
        except Exception as e:
            _clog_only(f"  WARNING _fetch_creation_ts '{title}': {e}")
            continue
        query_data = result.get('query', {})
        inv_norm = {n_entry['to']: n_entry['from']
                    for n_entry in query_data.get('normalized', [])}
        for page_id, page_info in query_data.get('pages', {}).items():
            if page_id == '-1' or 'missing' in page_info:
                continue
            title_result = page_info.get('title', '')
            orig_title = inv_norm.get(title_result, title_result)
            try:
                revisions = page_info.get('revisions', [])
                if revisions:
                    ts_utc = revisions[0].get('timestamp', '')
                    creation_ts_by_title[orig_title] = ts_utc_str_to_it(ts_utc) if ts_utc else ''
            except Exception:
                pass

    # --- CHIAMATA B: wikitext corrente (batch, nessun parametro incompatibile) ---
    for start in range(0, len(titles), CLEANUP_BATCH_SIZE_REV):
        batch = titles[start:start + CLEANUP_BATCH_SIZE_REV]
        try:
            result = SITE.simple_request(
                action='query',
                prop='revisions',
                titles='|'.join(batch),
                rvprop='content',
                rvslots='main',
                format='json',
            ).submit()
        except Exception as e:
            _clog_only(f"  WARNING _fetch_wikitext batch: {e}")
            continue
        query_data = result.get('query', {})
        inv_norm = {n_entry['to']: n_entry['from']
                    for n_entry in query_data.get('normalized', [])}
        for page_id, page_info in query_data.get('pages', {}).items():
            if page_id == '-1' or 'missing' in page_info:
                continue
            title_result = page_info.get('title', '')
            orig_title = inv_norm.get(title_result, title_result)
            wikitext = ''
            try:
                revisions = page_info.get('revisions', [])
                if revisions:
                    slots = revisions[0].get('slots', {})
                    wikitext = slots.get('main', {}).get('*', '') if slots else revisions[0].get('*', '')
            except Exception:
                pass
            result_by_title[orig_title] = {
                'wikitext': wikitext,
                'creation_ts': creation_ts_by_title.get(orig_title, ''),
            }

    for t in titles:
        if t not in result_by_title:
            result_by_title[t] = {'wikitext': '', 'creation_ts': creation_ts_by_title.get(t, '')}

    return result_by_title


def _cleanup_check_and_update_pages_batch(pages):
    """
    Verifica e aggiorna i metadati di tutte le voci in cache tramite API batch.
    Tre passate:
      1. prop=info (CLEANUP_BATCH_SIZE): rilevamento missing/redirect/NS errato
      2. prop=categories (CLEANUP_BATCH_SIZE, con paginazione)
      3. prop=revisions (CLEANUP_BATCH_SIZE_REV): wikitext + timestamp creazione

    Per ogni voce sopravvissuta: sovrascrive il timestamp con il valore reale
    dall'API (corregge corruzioni da doppia migrazione UTC->IT).
    Restituisce (valid_pages, removed_count).
    """
    n = len(pages)
    to_remove = {}
    updated_records = {}

    print(f"  Verifica e aggiornamento batch {n} voci "
          f"(info:{CLEANUP_BATCH_SIZE} titoli/chiamata, rev:{CLEANUP_BATCH_SIZE_REV} titoli/chiamata)...")

    all_normalized = {}
    all_inv_norm = {}
    survivor_titles = []

    for start in range(0, n, CLEANUP_BATCH_SIZE):
        batch = pages[start:start + CLEANUP_BATCH_SIZE]
        batch_titles = [p['titolo'] for p in batch]
        done = min(start + CLEANUP_BATCH_SIZE, n)
        if done % 500 == 0 or done == n:
            print(f"  [{done}/{n}] Info: {len(to_remove)} rimosse...")
        try:
            result = SITE.simple_request(
                action='query',
                prop='info',
                titles='|'.join(batch_titles),
                inprop='',
                format='json',
            ).submit()
        except Exception as e:
            _clog_only(f"  WARNING batch info [{start//CLEANUP_BATCH_SIZE + 1}]: {e}")
            survivor_titles.extend(batch_titles)
            continue
        query_data = result.get('query', {})
        for n_entry in query_data.get('normalized', []):
            all_normalized[n_entry['from']] = n_entry['to']
            all_inv_norm[n_entry['to']] = n_entry['from']
        for page_id, page_info in query_data.get('pages', {}).items():
            title_result = page_info.get('title', '')
            orig_title = all_inv_norm.get(title_result, title_result)
            if page_id == '-1' or 'missing' in page_info:
                to_remove[orig_title] = 'cancellata'
                _clog_only(f"  RIMOSSA (cancellata): {orig_title}")
            elif 'redirect' in page_info:
                to_remove[orig_title] = 'redirect'
                _clog_only(f"  RIMOSSA (redirect): {orig_title}")
            elif page_info.get('ns', 0) != 0:
                to_remove[orig_title] = f"NS{page_info.get('ns', '?')}"
                _clog_only(f"  RIMOSSA (NS{page_info.get('ns','?')}): {orig_title}")
            else:
                survivor_titles.append(orig_title)

    print(f"  Sopravvissute: {len(survivor_titles)}, rimosse: {len(to_remove)}")

    print(f"  Recupero categorie per {len(survivor_titles)} voci...")
    cats_by_title = _cleanup_fetch_categories_for_titles(survivor_titles)

    print(f"  Recupero wikitext e timestamp creazione per {len(survivor_titles)} voci ({CLEANUP_BATCH_SIZE_REV} titoli/chiamata)...")
    rev_by_title = _cleanup_fetch_wikitext_for_titles(survivor_titles)

    batch_by_title = {p['titolo']: p for p in pages}
    ts_fixed_count = 0

    for orig_title in survivor_titles:
        record = batch_by_title.get(orig_title)
        if record is None:
            norm_title = all_normalized.get(orig_title, orig_title)
            record = batch_by_title.get(norm_title)
        if record is None:
            continue

        rev_data = rev_by_title.get(orig_title, {})
        wikitext = rev_data.get('wikitext', '')
        creation_ts = rev_data.get('creation_ts', '')

        if orig_title in cats_by_title:
            new_cats = cats_by_title[orig_title]
        else:
            norm_title = all_normalized.get(orig_title, orig_title)
            new_cats = cats_by_title.get(norm_title, [])

        new_templates = parse_templates_from_wikitext(wikitext)
        new_preview = wikitext[:100].replace('\n', ' ').strip() if wikitext else ''

        old_cats = record.get('categorie', [])
        old_templates = record.get('templates', [])

        cats_changed = set(new_cats) != set(old_cats) or (not old_cats and bool(new_cats))
        old_tmpl_set = {(t.get('nome', ''), tuple(t.get('params', []))) for t in old_templates}
        new_tmpl_set = {(t.get('nome', ''), tuple(t.get('params', []))) for t in new_templates}
        tmpls_changed = old_tmpl_set != new_tmpl_set
        old_ts = record.get('timestamp', '')
        ts_changed = bool(creation_ts) and creation_ts != old_ts

        if cats_changed or tmpls_changed or ts_changed:
            updated = dict(record)
            updated['categorie'] = new_cats
            updated['templates'] = new_templates
            updated['preview'] = new_preview
            if ts_changed:
                updated['timestamp'] = creation_ts
                ts_fixed_count += 1
            updated_records[orig_title] = updated
            changes = []
            if ts_changed:
                changes.append(f'timestamp ({old_ts}->{creation_ts})')
            if cats_changed:
                changes.append('categorie')
            if tmpls_changed:
                changes.append('template')
            _clog_only(f"  AGGIORNATA ({', '.join(changes)}): {orig_title}")

    removed_count = len(to_remove)
    valid_pages = []
    for page in pages:
        title = page['titolo']
        if title in to_remove:
            continue
        valid_pages.append(updated_records.get(title, page))

    print(f"\nRisultato: {removed_count} voci rimosse, {len(updated_records)} voci aggiornate"
          f" (di cui {ts_fixed_count} timestamp corretti)")
    return valid_pages, removed_count


def _cleanup_remove_duplicates(pages):
    print("Ricerca duplicati...")
    by_title = {}
    for page in pages:
        by_title.setdefault(page['titolo'], []).append(page)
    unique_pages = []
    duplicates_removed = 0
    for title, versions in by_title.items():
        if len(versions) > 1:
            versions.sort(key=lambda x: x['timestamp'], reverse=True)
            duplicates_removed += len(versions) - 1
            print(f"  Duplicato: {title} ({len(versions)} copie -> 1 mantenuta)")
        unique_pages.append(versions[0])
    print(f"\nRisultato: {duplicates_removed} duplicati rimossi")
    return unique_pages, duplicates_removed


def _cleanup_remove_wrong_namespace(pages):
    print("Verifica namespace...")
    valid_pages = []
    removed = 0
    for i, page in enumerate(pages):
        title = page['titolo']
        if ':' in title:
            try:
                page_obj = pywikibot.Page(SITE, title)
                ns = page_obj.namespace()
                if ns != 0:
                    removed += 1
                    _clog_only(f"  RIMOSSA (NS{ns}): {title}")
                    continue
            except Exception as e:
                removed += 1
                _clog_only(f"  RIMOSSA (errore ns): {title} - {e}")
                continue
        valid_pages.append(page)
    print(f"\nRisultato: {removed} voci non-NS0 rimosse")
    return valid_pages, removed


def _cleanup_remove_old_pages(pages, cutoff_date):
    print(f"Verifica eta' voci (limite: {cutoff_date.strftime('%d/%m/%Y')})...")
    valid_pages = []
    removed = 0
    for page in pages:
        title = page['titolo']
        move_ts_str = page.get('move_timestamp', '')
        ref_str = move_ts_str if move_ts_str else page.get('timestamp', '')
        try:
            ref_date = datetime.strptime(ref_str, '%Y%m%d%H%M%S')
        except Exception:
            valid_pages.append(page)
            continue
        if ref_date < cutoff_date:
            removed += 1
            label = "spostata" if move_ts_str else "creata"
            _clog_only(f"  RIMOSSA ({label} {ref_date.strftime('%d/%m/%Y')}): {title}")
            continue
        valid_pages.append(page)
    print(f"\nRisultato: {removed} voci troppo vecchie rimosse")
    return valid_pages, removed


def _cleanup_dry_run_report(pages):
    """
    Stampa un report diagnostico completo senza salvare nulla.
    Rileva corruzioni (campi vuoti, dimensione anomala) prima che avvengano.
    """
    n = len(pages)
    if n == 0:
        print("  Nessuna voce da analizzare.")
        return

    total_cats = sum(len(p.get('categorie', [])) for p in pages)
    total_tmpls = sum(len(p.get('templates', [])) for p in pages)
    total_preview_len = sum(len(p.get('preview', '')) for p in pages)
    voci_no_cats = sum(1 for p in pages if not p.get('categorie'))
    voci_no_tmpls = sum(1 for p in pages if not p.get('templates'))
    voci_no_preview = sum(1 for p in pages if not p.get('preview', '').strip())

    avg_cats = total_cats / n
    avg_tmpls = total_tmpls / n
    avg_preview = total_preview_len / n

    file_groups = split_pages_into_files(pages)
    total_size_bytes = 0
    for group in file_groups:
        for p in group:
            try:
                total_size_bytes += len(format_lua_row(p).encode('utf-8'))
            except Exception:
                pass
    size_mb = total_size_bytes / (1024 * 1024)

    WARN_AVG_CATS    = 1.0
    WARN_AVG_TMPLS   = 0.5
    WARN_NO_CATS_PCT = 50.0
    WARN_NO_TMPLS_PCT = 70.0
    WARN_NO_PREV_PCT = 80.0
    WARN_SIZE_MB     = 0.5

    alerts = []
    if avg_cats < WARN_AVG_CATS:
        alerts.append(f"  *** ALLARME: media categorie/voce troppo bassa ({avg_cats:.2f} < {WARN_AVG_CATS})")
    if avg_tmpls < WARN_AVG_TMPLS:
        alerts.append(f"  *** ALLARME: media template/voce troppo bassa ({avg_tmpls:.2f} < {WARN_AVG_TMPLS})")
    if (voci_no_cats / n * 100) > WARN_NO_CATS_PCT:
        alerts.append(f"  *** ALLARME: {voci_no_cats}/{n} voci ({voci_no_cats/n*100:.1f}%) senza categorie")
    if (voci_no_tmpls / n * 100) > WARN_NO_TMPLS_PCT:
        alerts.append(f"  *** ALLARME: {voci_no_tmpls}/{n} voci ({voci_no_tmpls/n*100:.1f}%) senza template")
    if (voci_no_preview / n * 100) > WARN_NO_PREV_PCT:
        alerts.append(f"  *** ALLARME: {voci_no_preview}/{n} voci ({voci_no_preview/n*100:.1f}%) senza preview")
    if size_mb < WARN_SIZE_MB:
        alerts.append(f"  *** ALLARME: dimensione stimata troppo piccola ({size_mb:.2f} MB < {WARN_SIZE_MB} MB)")

    print(f"Statistiche aggregate ({n} voci):")
    print(f"  Dimensione stimata output:  {size_mb:.2f} MB ({len(file_groups)} file)")
    print(f"  Media categorie/voce:       {avg_cats:.2f}  "
          f"(voci senza categorie: {voci_no_cats}/{n} = {voci_no_cats/n*100:.1f}%)")
    print(f"  Media template/voce:        {avg_tmpls:.2f}  "
          f"(voci senza template:  {voci_no_tmpls}/{n} = {voci_no_tmpls/n*100:.1f}%)")
    print(f"  Media lunghezza preview:    {avg_preview:.0f} car  "
          f"(voci senza preview:   {voci_no_preview}/{n} = {voci_no_preview/n*100:.1f}%)")

    print(f"\nCampione prime 10 voci:")
    print(f"  {'Titolo':<45} {'Timestamp':<15} {'Cat':>4} {'Tmpl':>5} {'Prev':>5}")
    print(f"  {'-'*45} {'-'*15} {'-'*4} {'-'*5} {'-'*5}")
    for p in pages[:10]:
        titolo = p.get('titolo', '')[:44]
        ts = p.get('timestamp', '')
        nc = len(p.get('categorie', []))
        nt = len(p.get('templates', []))
        np_ = len(p.get('preview', ''))
        print(f"  {titolo:<45} {ts:<15} {nc:>4} {nt:>5} {np_:>5}")

    worst = sorted(pages, key=lambda p: (
        len(p.get('categorie', [])) + len(p.get('templates', [])) + len(p.get('preview', ''))
    ))[:10]
    print(f"\nCampione 10 voci con meno dati (potenziali corruzioni):")
    print(f"  {'Titolo':<45} {'Timestamp':<15} {'Cat':>4} {'Tmpl':>5} {'Prev':>5}")
    print(f"  {'-'*45} {'-'*15} {'-'*4} {'-'*5} {'-'*5}")
    for p in worst:
        titolo = p.get('titolo', '')[:44]
        ts = p.get('timestamp', '')
        nc = len(p.get('categorie', []))
        nt = len(p.get('templates', []))
        np_ = len(p.get('preview', ''))
        print(f"  {titolo:<45} {ts:<15} {nc:>4} {nt:>5} {np_:>5}")

    if alerts:
        print(f"\n{'!' * 60}")
        print("ATTENZIONE - RILEVATI PROBLEMI:")
        for a in alerts:
            print(a)
        print("NON eseguire in modalita' normale finche' i problemi non sono risolti.")
        print(f"{'!' * 60}")
    else:
        print(f"\nOK - Nessun allarme rilevato. I dati sembrano integri.")
        if DRY_RUN:
            print(f"Per salvare su Wikipedia: rimuovere --dry-run e rieseguire.")


def _cleanup_save_cache(pages, original_files_count):
    """
    Salva la cache pulita su Wikipedia.
    Gestisce piu' file e svuota i file diventati obsoleti.
    In modalita' DRY_RUN non scrive nulla.
    """
    file_groups = split_pages_into_files(pages)
    total_files = len(file_groups)
    print(f"File necessari: {total_files}")

    empty_lua = (
        "-- File cache obsoleto - Svuotato automaticamente\n"
        f"return {{u='(vuoto)',v='{VERSION}',p=0,tp=0,n=0,d={{}}}}"
    )

    for i, pages_group in enumerate(file_groups, 1):
        page_name = f"{DATA_PAGE_PREFIX}{i}"
        print(f"\n[{i}/{total_files}] {page_name}")
        print(f"  Voci: {len(pages_group)}")
        lua_content = format_lua_data(pages_group, i, total_files)
        size_mb = len(lua_content) / (1024 * 1024)
        print(f"  Dimensione: {size_mb:.2f} MB")
        if DRY_RUN:
            print(f"  [DRY-RUN] Skip salvataggio {page_name}")
            continue
        page = pywikibot.Page(SITE, page_name)
        page.text = lua_content
        page.save(
            summary=f"Bot: Voci recenti - Aggiornamento cache (v.{VERSION})",
            minor=False
        )
        print(f"  OK Salvato")

    for i in range(total_files + 1, original_files_count + 5):
        page_name = f"{DATA_PAGE_PREFIX}{i}"
        try:
            page = pywikibot.Page(SITE, page_name)
            if page.exists():
                print(f"\n  Svuotamento {page_name} (obsoleto)...")
                if DRY_RUN:
                    print(f"  [DRY-RUN] Skip svuotamento {page_name}")
                else:
                    page.text = empty_lua
                    page.save(
                        summary=f"Bot: Voci recenti - File obsoleto (v.{VERSION})",
                        minor=True
                    )
                    print(f"  OK Svuotato")
            else:
                break
        except Exception as e:
            print(f"  ERRORE svuotamento {page_name}: {e}")
            break


def run_cleanup_internal(cached_pages, cache_files_count):
    """
    Esegue le 4 fasi di pulizia cache internamente (ex PuliziaCache.py).
    Restituisce la lista di voci pulita dopo tutte le fasi.
    In DRY_RUN mode le fasi vengono eseguite ma nessuna scrittura avviene:
    al termine viene stampato il report diagnostico invece di salvare.
    """
    global _cleanup_log_file

    try:
        _cleanup_log_file = open(CLEANUP_LOG_FILE, 'a', encoding='utf-8')
    except Exception as e:
        print(f"  WARNING: impossibile aprire pulizia_cache.log: {e}")

    dry_tag = " [DRY-RUN]" if DRY_RUN else ""
    start_time = datetime.now()
    _clog(f"\n{'=' * 60}")
    _clog(f"PULIZIA CACHE VOCI RECENTI - v{VERSION}{dry_tag}")
    _clog(f"Avvio: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    _clog('=' * 60)

    if DRY_RUN:
        print("*** MODALITA' DRY-RUN: nessuna modifica verra' salvata su Wikipedia ***\n")

    original_count = len(cached_pages)
    cutoff_date = datetime.now() - timedelta(days=CLEANUP_MAX_AGE_DAYS)
    print(f"Limite data creazione: {cutoff_date.strftime('%d/%m/%Y')} ({CLEANUP_MAX_AGE_DAYS} giorni fa)\n")

    print("=" * 60)
    print("FASE 1: RIMOZIONE DUPLICATI")
    print("=" * 60)
    cached_pages, removed_duplicates = _cleanup_remove_duplicates(cached_pages)

    print("\n" + "=" * 60)
    print("FASE 2: RIMOZIONE VOCI NON-NS0")
    print("=" * 60)
    cached_pages, removed_wrong_ns = _cleanup_remove_wrong_namespace(cached_pages)

    print("\n" + "=" * 60)
    print("FASE 3: RIMOZIONE VOCI CANCELLATE / AGGIORNAMENTO METADATI")
    print("=" * 60)
    cached_pages, removed_deleted = _cleanup_check_and_update_pages_batch(cached_pages)

    print("\n" + "=" * 60)
    print("FASE 4: RIMOZIONE VOCI TROPPO VECCHIE")
    print("=" * 60)
    cached_pages, removed_old = _cleanup_remove_old_pages(cached_pages, cutoff_date)

    total_removed = removed_duplicates + removed_wrong_ns + removed_deleted + removed_old

    print("\n" + "=" * 60)
    print("RIEPILOGO PULIZIA")
    print("=" * 60)
    print(f"Voci originali: {original_count}")
    print(f"  Duplicati rimossi:   {removed_duplicates}")
    print(f"  Wrong NS rimossi:    {removed_wrong_ns}")
    print(f"  Cancellate rimosse:  {removed_deleted}")
    print(f"  Troppo vecchie:      {removed_old}")
    print(f"  Totale rimosse:      {total_removed}")
    print(f"Voci finali: {len(cached_pages)}")

    print("\n" + "=" * 60)
    if DRY_RUN:
        print("REPORT DIAGNOSTICO [DRY-RUN]")
        print("=" * 60)
        _cleanup_dry_run_report(cached_pages)
        print("\n*** DRY-RUN: nessun file modificato (il salvataggio avverra' in STEP 7) ***")
    else:
        print("PULIZIA COMPLETATA")
        print("=" * 60)
        print("  Salvataggio rinviato a STEP 7 (scrittura unica su Wikipedia).")

    end_time = datetime.now()
    _clog_only(f"\nFine pulizia: {end_time.strftime('%Y-%m-%d %H:%M:%S')} "
               f"(durata: {(end_time - start_time).seconds}s){dry_tag}")
    _clog_only(f"Riepilogo: originali={original_count}, rimosse={total_removed}, "
               f"finali={len(cached_pages)}")
    _clog_only('=' * 60)

    if _cleanup_log_file:
        try:
            _cleanup_log_file.close()
        except Exception:
            pass
    _cleanup_log_file = None

    return cached_pages


# ========================================
# BATCH API PER NUOVE VOCI
# ========================================

def _batch_fetch_page_info(titles):
    """
    Recupera in batch prop=info per una lista di titoli.
    Restituisce dict {orig_title: page_info_dict} e dict inv_norm.
    """
    info_by_title = {}
    inv_norm = {}
    for start in range(0, len(titles), BATCH_SIZE_CHECK):
        batch = titles[start:start + BATCH_SIZE_CHECK]
        try:
            result = SITE.simple_request(
                action='query',
                prop='info',
                titles='|'.join(batch),
                inprop='',
                format='json',
            ).submit()
        except Exception as e:
            print(f"  WARNING batch info [{start//BATCH_SIZE_CHECK + 1}]: {e}")
            continue
        query_data = result.get('query', {})
        for n_entry in query_data.get('normalized', []):
            inv_norm[n_entry['to']] = n_entry['from']
        for page_id, page_info in query_data.get('pages', {}).items():
            title_result = page_info.get('title', '')
            orig = inv_norm.get(title_result, title_result)
            info_by_title[orig] = page_info
    return info_by_title, inv_norm


def _batch_fetch_categories(titles):
    """
    Recupera categorie per una lista di titoli tramite API batch.
    Equivalente a _cleanup_fetch_categories_for_titles ma usata
    anche per le nuove voci in download_page_data_batch.
    """
    return _cleanup_fetch_categories_for_titles(titles)


def _batch_fetch_wikitext(titles):
    """
    Recupera wikitext corrente e timestamp di prima creazione per una lista
    di titoli. Restituisce dict {titolo: {'wikitext': str, 'creation_ts': str}}.
    """
    return _cleanup_fetch_wikitext_for_titles(titles)


def download_page_data_batch(titles, existing_titles, cutoff_date, moves_cache=None, move_timestamps=None):
    """
    Scarica i dati completi di una lista di titoli usando chiamate API batch.
    Sostituisce download_page_data (che usava chiamate singole per voce).

    Tre passate batch:
      1. prop=info (BATCH_SIZE_CHECK titoli): rilevamento non esistenti/redirect/NS errato
      2. prop=categories (CLEANUP_BATCH_SIZE titoli): categorie
      3. prop=revisions (CLEANUP_BATCH_SIZE_REV titoli): wikitext + timestamp creazione

    Salta: duplicati, non esistenti, redirect, voci create prima di cutoff_date.
    Se moves_cache e' fornito, registra i rifiuti per evitare riverifiche nei run futuri.
    move_timestamps: dict {titolo: move_ts_str} con timestamp di spostamento in NS0.
    """
    if not titles:
        return []

    # Dedup preventiva (la lista candidati puo' avere duplicati)
    unique_titles = []
    seen = set()
    for t in titles:
        if t not in existing_titles and t not in seen:
            unique_titles.append(t)
            seen.add(t)

    print(f"  Scaricamento batch {len(unique_titles)} titoli candidati...")
    now_str = now_it().strftime('%Y%m%d%H%M%S')
    skipped_cached = 0

    # Filtra subito da moves_cache i rifiuti certi (no new move)
    filtered = []
    for title in unique_titles:
        if moves_cache is not None:
            cached = moves_cache.get(title)
            has_new_move = move_timestamps and title in move_timestamps
            if cached and cached.get('result') == 'rejected' and not has_new_move:
                skipped_cached += 1
                continue
            elif cached and cached.get('result') == 'rejected' and has_new_move:
                print(f"    RIVALUTATA (era too_old in cache, nuovo spostamento in NS0): {title}")
        filtered.append(title)

    if skipped_cached:
        print(f"  Skip da moves_cache: {skipped_cached}")

    if not filtered:
        return []

    # --- PASSATA 1: prop=info ---
    print(f"  [1/3] prop=info per {len(filtered)} titoli...")
    info_by_title, inv_norm = _batch_fetch_page_info(filtered)

    survivors = []
    skipped_notexist = []
    skipped_redirect = []
    skipped_wrong_ns = []

    for title in filtered:
        page_info = info_by_title.get(title)
        if page_info is None:
            # Non trovato nella risposta API: includi comunque (errore batch)
            survivors.append(title)
            continue
        if 'missing' in page_info:
            skipped_notexist.append(title)
            if moves_cache is not None:
                moves_cache[title] = {'processed_at': now_str, 'result': 'rejected', 'reason': 'not_exist'}
            continue
        if 'redirect' in page_info:
            skipped_redirect.append(title)
            if moves_cache is not None:
                moves_cache[title] = {'processed_at': now_str, 'result': 'rejected', 'reason': 'redirect'}
            continue
        if page_info.get('ns', 0) != 0:
            skipped_wrong_ns.append(title)
            if moves_cache is not None:
                moves_cache[title] = {'processed_at': now_str, 'result': 'rejected', 'reason': f"ns{page_info.get('ns','')}"}
            continue
        survivors.append(title)

    print(f"  Sopravvissuti: {len(survivors)} / {len(filtered)} "
          f"(non esistono: {len(skipped_notexist)}, redirect: {len(skipped_redirect)}, NS errato: {len(skipped_wrong_ns)})")

    if not survivors:
        return []

    # --- PASSATA 2: prop=categories ---
    print(f"  [2/3] prop=categories per {len(survivors)} titoli...")
    cats_by_title = _batch_fetch_categories(survivors)

    # --- PASSATA 3: prop=revisions ---
    print(f"  [3/3] prop=revisions per {len(survivors)} titoli ({CLEANUP_BATCH_SIZE_REV} titoli/chiamata)...")
    rev_by_title = _batch_fetch_wikitext(survivors)

    # --- Costruzione record ---
    pages_data = []
    skipped_old = []
    skipped_error = []

    for title in survivors:
        rev_data = rev_by_title.get(title, {})
        wikitext = rev_data.get('wikitext', '')
        creation_ts = rev_data.get('creation_ts', '')

        if not creation_ts:
            skipped_error.append((title, "timestamp creazione non disponibile"))
            continue

        timestamp = creation_ts  # gia' in formato IT da _batch_fetch_wikitext

        # Controllo eta'
        move_ts_str = move_timestamps.get(title) if move_timestamps else None
        if move_ts_str:
            try:
                ref_date = datetime.strptime(move_ts_str, '%Y%m%d%H%M%S')
            except Exception:
                try:
                    ref_date = datetime.strptime(creation_ts, '%Y%m%d%H%M%S')
                except Exception:
                    skipped_error.append((title, "move_ts non parsabile"))
                    continue
        else:
            try:
                ref_date = datetime.strptime(creation_ts, '%Y%m%d%H%M%S')
            except Exception:
                skipped_error.append((title, "creation_ts non parsabile"))
                continue

        if ref_date < cutoff_date:
            skipped_old.append(title)
            label = f"spostata {ref_date.strftime('%d/%m/%Y')}" if move_ts_str else f"creata {ref_date.strftime('%d/%m/%Y')}"
            print(f"    SKIP (troppo vecchia, {label}): {title}")
            if moves_cache is not None:
                moves_cache[title] = {'processed_at': now_str, 'result': 'rejected', 'reason': 'too_old'}
            continue

        categories = cats_by_title.get(title, [])
        templates = parse_templates_from_wikitext(wikitext)
        preview = wikitext[:100].replace("\n", " ").strip() if wikitext else ""

        record = {
            'titolo': title,
            'timestamp': timestamp,
            'categorie': categories,
            'templates': templates,
            'preview': preview
        }
        if move_ts_str:
            record['move_timestamp'] = move_ts_str

        pages_data.append(record)
        existing_titles.add(title)

    total_skipped = len(skipped_old) + len(skipped_error)
    if total_skipped > 0:
        if skipped_old:
            print(f"    - Troppo vecchie: {len(skipped_old)}")
            for t in skipped_old[:5]:
                print(f"      . {t}")
        if skipped_error:
            print(f"    - Errori: {len(skipped_error)}")
            for t, err in skipped_error[:5]:
                print(f"      . {t}: {err}")

    return pages_data


# ========================================
# CACHE MANUALE E SCANSIONE ALTRI NS (CacheMoved)
# ========================================

def scan_other_namespaces(cutoff_date):
    """
    Interroga RecentChanges per i namespace in NS_SCAN (NS2 Utente, NS118 Bozze).
    Restituisce una lista di titoli.
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
                    if rc_ts:
                        try:
                            dt_utc = datetime.strptime(rc_ts, '%Y%m%d%H%M%S')
                            rc_ts_it = (dt_utc + timedelta(hours=_it_offset_for_utc(dt_utc))).strftime('%Y%m%d%H%M%S')
                        except Exception:
                            rc_ts_it = rc_ts
                    else:
                        rc_ts_it = rc_ts
                    if rc_ts_it and rc_ts_it < cutoff_str:
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


def validate_ns_or_manual_page_batch(titles, existing_titles, cutoff_date, moves_cache=None):
    """
    Versione batch di validate_ns_or_manual_page.
    Valida una lista di titoli (da NS non-0 o da CacheMoved manuale) usando
    chiamate API batch invece di chiamate singole.
    Restituisce (pages_valide, dict_skip_reason).
    """
    if not titles:
        return [], {}

    now_str = now_it().strftime('%Y%m%d%H%M%S')
    # Risolvi titoli NS0 da titoli non-NS0
    ns0_map = {}   # ns0_title -> original_title
    skip_reasons = {}

    for title in titles:
        try:
            temp_page = pywikibot.Page(SITE, title)
            original_ns = temp_page.namespace()
            if original_ns == 0:
                ns0_title = temp_page.title()
            else:
                base_name = temp_page.title(with_ns=False)
                if '/' in base_name:
                    base_name = base_name.split('/')[-1]
                ns0_title = pywikibot.Page(SITE, base_name, ns=0).title()
        except Exception as e:
            skip_reasons[title] = f'error: {e}'
            continue

        if ns0_title in existing_titles:
            skip_reasons[title] = 'duplicate'
            continue

        if moves_cache is not None:
            cached = moves_cache.get(ns0_title)
            if cached and cached.get('result') == 'rejected' and cached.get('reason') != 'too_old':
                skip_reasons[title] = 'cached_rejected'
                continue

        ns0_map[ns0_title] = title

    if not ns0_map:
        return [], skip_reasons

    ns0_titles = list(ns0_map.keys())
    print(f"  Validazione batch {len(ns0_titles)} titoli NS0...")

    # Batch info
    info_by_title, inv_norm = _batch_fetch_page_info(ns0_titles)

    survivors = []
    for ns0_title in ns0_titles:
        orig_title = ns0_map[ns0_title]
        page_info = info_by_title.get(ns0_title)
        if page_info is None:
            skip_reasons[orig_title] = 'api_error'
            continue
        if 'missing' in page_info:
            skip_reasons[orig_title] = 'no_ns0'
            if moves_cache is not None:
                moves_cache[ns0_title] = {'processed_at': now_str, 'result': 'rejected', 'reason': 'no_ns0'}
            continue
        if 'redirect' in page_info:
            skip_reasons[orig_title] = 'redirect'
            if moves_cache is not None:
                moves_cache[ns0_title] = {'processed_at': now_str, 'result': 'rejected', 'reason': 'redirect'}
            continue
        if page_info.get('ns', 0) != 0:
            skip_reasons[orig_title] = f"NS{page_info.get('ns','?')}"
            if moves_cache is not None:
                moves_cache[ns0_title] = {'processed_at': now_str, 'result': 'rejected', 'reason': f"ns{page_info.get('ns','')}"}
            continue
        survivors.append(ns0_title)

    if not survivors:
        return [], skip_reasons

    # Batch categories + revisions
    cats_by_title = _batch_fetch_categories(survivors)
    rev_by_title = _batch_fetch_wikitext(survivors)

    pages_valide = []
    for ns0_title in survivors:
        orig_title = ns0_map[ns0_title]
        rev_data = rev_by_title.get(ns0_title, {})
        creation_ts = rev_data.get('creation_ts', '')
        wikitext = rev_data.get('wikitext', '')

        if not creation_ts:
            skip_reasons[orig_title] = 'no_timestamp'
            continue

        try:
            ref_date = datetime.strptime(creation_ts, '%Y%m%d%H%M%S')
        except Exception:
            skip_reasons[orig_title] = 'ts_parse_error'
            continue

        if ref_date < cutoff_date:
            skip_reasons[orig_title] = f"old ({ref_date.strftime('%d/%m/%Y')})"
            if moves_cache is not None:
                moves_cache[ns0_title] = {'processed_at': now_str, 'result': 'rejected', 'reason': 'too_old'}
            continue

        categories = cats_by_title.get(ns0_title, [])
        templates = parse_templates_from_wikitext(wikitext)
        preview = wikitext[:100].replace("\n", " ").strip() if wikitext else ""

        if moves_cache is not None:
            moves_cache[ns0_title] = {'processed_at': now_str, 'result': 'accepted', 'reason': 'ns0'}

        record = {
            'titolo': ns0_title,
            'timestamp': creation_ts,
            'categorie': categories,
            'templates': templates,
            'preview': preview
        }
        pages_valide.append(record)
        existing_titles.add(ns0_title)
        print(f"    OK {ns0_title}")

    return pages_valide, skip_reasons


def extract_title_from_wiki_url(line):
    m = re.search(r'it\.wikipedia\.org/wiki/([^?#\s]+)', line)
    if not m:
        return None
    raw = m.group(1)
    title = unquote(raw).replace('_', ' ').strip()
    return title if title else None


def read_cache_moved(existing_titles, cutoff_date, cached_pages_by_title=None):
    """
    Legge CacheMoved (lista manuale).
    Usa validate_ns_or_manual_page_batch per la validazione batch.
    Restituisce (pages_to_add, titles_to_remove, pages_to_update).
    """
    pages_to_add = []
    titles_to_remove = []
    pages_to_update = []

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
            if line.lower().startswith('aggiorna:'):
                update_title = line[len('aggiorna:'):].strip()
                update_title = extract_title_from_wiki_url(update_title) or update_title.replace('_', ' ')
                if update_title:
                    update_titles.append(update_title)
                continue
            if line.lower().startswith('rimuovi:'):
                remove_title = line[len('rimuovi:'):].strip()
                remove_title = extract_title_from_wiki_url(remove_title) or remove_title.replace('_', ' ')
                if remove_title:
                    remove_titles.append(remove_title)
                continue
            wiki_title = extract_title_from_wiki_url(line)
            if wiki_title:
                add_titles.append(wiki_title)
                continue
            m = re.search(r'\d{2}:\d{2}, \d{1,2} \w+ \d{4} (.+?) \(cron \|', line)
            add_titles.append(m.group(1).strip() if m else line)

        print(f"  Da aggiungere: {len(add_titles)}, Da rimuovere: {len(remove_titles)}, Da aggiornare: {len(update_titles)}")

        for rt in remove_titles:
            titles_to_remove.append(rt)
            print(f"  Rimuovi: {rt}")

        # Gestione Aggiorna: (ancora singola per voce - logica specifica)
        for title in update_titles:
            print(f"  Aggiorna: {title}")
            try:
                page_obj = pywikibot.Page(SITE, title, ns=0)
                if not page_obj.exists() or page_obj.isRedirectPage():
                    titles_to_remove.append(title)
                    reason = "cancellata" if not page_obj.exists() else "redirect"
                    print(f"    RIMUOVI ({reason}): {title}")
                    continue
                try:
                    page_obj.purge()
                except Exception:
                    pass
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
                    record = dict(cached_pages_by_title[title])
                    record['categorie'] = new_cats
                    record['templates'] = new_templates
                    record['preview'] = new_preview
                    pages_to_update.append(record)
                    titles_to_remove.append(title)
                    print(f"    OK Metadati aggiornati: {title}")
                else:
                    try:
                        oldest = page_obj.oldest_revision
                        timestamp = ts_utc_to_it(oldest.timestamp)
                    except Exception:
                        timestamp = now_it().strftime('%Y%m%d%H%M%S')
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

        # Validazione batch per i titoli da aggiungere
        if add_titles:
            valide, skip_reasons = validate_ns_or_manual_page_batch(
                add_titles, existing_titles, cutoff_date, moves_cache=None)
            pages_to_add.extend(valide)
            skipped = {}
            for title, reason in skip_reasons.items():
                skipped[reason] = skipped.get(reason, 0) + 1
            if skipped:
                print(f"  Skippate da CacheMoved: {skipped}")

    except Exception as e:
        print(f"  ERRORE lettura CacheMoved: {e}")

    return pages_to_add, titles_to_remove, pages_to_update


def scan_and_load_ns_pages(existing_titles, cutoff_date, moves_cache):
    """
    Interroga RecentChanges per NS_SCAN, valida le voci in batch.
    """
    ns_titles = scan_other_namespaces(cutoff_date)

    if not ns_titles:
        print("  Nessun titolo trovato da altri NS")
        return []

    print(f"  Validazione batch {len(ns_titles)} titoli da NS{NS_SCAN}...")
    valide, skip_reasons = validate_ns_or_manual_page_batch(
        ns_titles, existing_titles, cutoff_date, moves_cache)

    skipped = {}
    for reason in skip_reasons.values():
        skipped[reason] = skipped.get(reason, 0) + 1
    if skipped:
        print(f"  Skippate da NS: {skipped}")

    # Salva moves_cache aggiornato
    save_moves_cache(moves_cache)

    print(f"  Aggiunte da altri NS: {len(valide)}")
    return valide


# ========================================
# SCARICAMENTO NUOVE VOCI
# ========================================

def get_new_pages_only(existing_titles, cutoff_date, moves_cache):
    """
    Raccoglie TUTTE le voci nuove in NS0 nell'arco del cutoff.
    Usa download_page_data_batch al posto delle chiamate singole.
    """
    print(f"Ricerca nuove voci in NS0 (dal cutoff {cutoff_date.strftime('%d/%m/%Y')})...")
    print(f"Cache esistente: {len(existing_titles)} voci")

    candidate_titles = set()
    cutoff_str = cutoff_date.strftime('%Y%m%d%H%M%S')

    print("\nFonte 1: Creazioni dirette NS0...")
    direct, recreation_timestamps = get_new_creations_since_cutoff(existing_titles, cutoff_str)
    candidate_titles.update(direct)
    print(f"  Trovate: {len(direct)} voci candidate ({len(recreation_timestamps)} ricreazioni)")

    print("\nFonte 2: Spostamenti in NS0 dal log...")
    moved = get_moved_to_ns0_since_cutoff(existing_titles, cutoff_date, moves_cache)
    candidate_titles.update(moved.keys())
    move_timestamps = {**recreation_timestamps, **moved}
    print(f"  Trovate: {len(moved)} voci spostate")

    print(f"\nTotale candidate NS0: {len(candidate_titles)}")
    print(f"Scaricamento dati completi (batch API)...")
    new_pages = download_page_data_batch(
        list(candidate_titles), existing_titles, cutoff_date, moves_cache, move_timestamps)

    print(f"\nOK Nuove voci da NS0: {len(new_pages)}\n")
    return new_pages


def get_new_creations_since_cutoff(existing_titles, cutoff_str):
    """
    Scorre RecentChanges NS0 (solo nuove creazioni) fino a cutoff_str.
    Restituisce (found_titles, recreation_timestamps).
    """
    site = SITE
    found_titles = set()
    recreation_timestamps = {}
    iteration = 0
    total_checked = 0

    params = {
        'action': 'query',
        'list': 'recentchanges',
        'rctype': 'new',
        'rcnamespace': NAMESPACE,
        'rcshow': '!redirect|!bot',
        'rclimit': 500,
        'rcprop': 'title|timestamp|tags',
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
                if rc_ts:
                    try:
                        dt_utc = datetime.strptime(rc_ts, '%Y%m%d%H%M%S')
                        rc_ts_it = (dt_utc + timedelta(hours=_it_offset_for_utc(dt_utc))).strftime('%Y%m%d%H%M%S')
                    except Exception:
                        rc_ts_it = rc_ts
                else:
                    rc_ts_it = rc_ts
                if rc_ts_it and rc_ts_it < cutoff_str:
                    stop = True
                    break
                if title not in existing_titles:
                    found_titles.add(title)
                    tags = change.get('tags', [])
                    if 'mw-recreated' in tags and rc_ts_it:
                        recreation_timestamps[title] = rc_ts_it
            if iteration % 5 == 0:
                print(f"    [{iteration}] Trovate: {len(found_titles)}, Controllate: {total_checked}, Ricreate: {len(recreation_timestamps)}")
            if stop:
                break
            if 'continue' in data and 'rccontinue' in data['continue']:
                continue_param = data['continue']['rccontinue']
            else:
                break
        except Exception as e:
            print(f"    Errore API: {e}")
            break

    print(f"    Totale controllate: {total_checked}, nuove trovate: {len(found_titles)}, ricreate: {len(recreation_timestamps)}")
    return found_titles, recreation_timestamps


def get_moved_to_ns0_since_cutoff(existing_titles, cutoff_date, moves_cache):
    """
    Scorre il log degli spostamenti. Raccoglie solo destinazioni NS0
    provenienti da namespace sorgente diverso da 0.
    Restituisce dict {titolo_ns0: move_timestamp_str}.
    """
    site = SITE
    found_titles = {}
    checked = 0
    skipped_cached = 0
    now_str = now_it().strftime('%Y%m%d%H%M%S')

    try:
        logs = site.logevents(logtype='move', total=MAX_ITERATIONS * 500)
        for log in logs:
            checked += 1
            if checked % 200 == 0:
                print(f"    Log spostamenti: {checked} controllati, "
                      f"{len(found_titles)} trovati, {skipped_cached} skip da cache")
            log_ts = log.timestamp()
            if log_ts.replace(tzinfo=None) < cutoff_date:
                break
            move_ts_str = ts_utc_to_it(log_ts)
            try:
                params = log.data.get('params', log.data)
                target_title = params.get('target_title', '')
                if not target_title:
                    continue
                if target_title in existing_titles:
                    continue
                cached = moves_cache.get(target_title)
                if cached and cached.get('result') == 'rejected':
                    skipped_cached += 1
                    continue
                source_page = log.page()
                source_ns = int(source_page.namespace())
                if source_ns == 0:
                    moves_cache[target_title] = {
                        'processed_at': now_str, 'result': 'rejected', 'reason': 'ns0_to_ns0'}
                    continue
                target_page = pywikibot.Page(site, target_title)
                if int(target_page.namespace()) != 0:
                    moves_cache[target_title] = {
                        'processed_at': now_str, 'result': 'rejected',
                        'reason': f"ns{target_page.namespace()}"}
                    continue
                moves_cache[target_title] = {
                    'processed_at': now_str, 'result': 'accepted', 'reason': 'ns0'}
                found_titles[target_title] = move_ts_str
                source_title = source_page.title()
                print(f"    Spostamento NS{source_ns}->NS0: '{source_title}' -> '{target_title}'")
            except Exception:
                continue
    except Exception as e:
        print(f"    Errore log spostamenti: {e}")

    print(f"    Log spostamenti: {checked} controllati, "
          f"{len(found_titles)} trovati, {skipped_cached} skip da cache")
    return found_titles


# ========================================
# CONTROLLO VOCI CANCELLATE (STEP 3b)
# ========================================

def check_deleted_pages(cached_pages):
    """
    Controlla via API batch quali voci della cache sono state cancellate,
    diventate redirect, o spostate fuori da NS0.
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
            result = SITE.simple_request(
                action='query',
                prop='info',
                titles='|'.join(batch),
                inprop=''
            ).submit()
            query_data = result.get('query', {})
            pages = query_data.get('pages', {})
            normalized = {n_e['from']: n_e['to'] for n_e in query_data.get('normalized', [])}

            for page_id, page_info in pages.items():
                title_in_result = page_info.get('title', '')
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


# ========================================
# FORMATTAZIONE E SALVATAGGIO LUA FINALE
# ========================================

def escape_for_lua_longstring(s):
    if not s:
        return "", ""
    level = 0
    while f"]{'=' * level}]" in s:
        level += 1
    open_delim = f"[{'=' * level}["
    close_delim = f"]{'=' * level}]"
    return open_delim, close_delim


def validate_lua_longstrings(lua_code, pages_data):
    """
    Verifica che tutti i long string nel codice Lua siano bilanciati.
    Restituisce None se ok, stringa descrittiva se c'e' un problema.
    """
    import re as _re

    def find_unclosed(text):
        pos = 0
        for m in _re.finditer(r'\[(?P<eq>=*)\[', text):
            if m.start() < pos:
                continue
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


def blank_old_data_files(num_files_needed):
    """Svuota eventuali file Dati vecchi oltre quelli necessari."""
    print(f"\nVerifica file obsoleti...")
    empty_structure = (
        "-- File cache obsoleto - Svuotato automaticamente\n"
        f"return {{u='(vuoto)',v='{VERSION}',p=0,tp=0,n=0,d={{}}}}"
    )
    blanked = 0
    i = num_files_needed + 1
    while i <= num_files_needed + 2:
        page_name = f"{DATA_PAGE_PREFIX}{i}"
        page = pywikibot.Page(SITE, page_name)
        if page.exists():
            print(f"  Svuotamento {page_name} (obsoleto)...")
            if DRY_RUN:
                print(f"  [DRY-RUN] Skip svuotamento {page_name}")
                blanked += 1
            else:
                try:
                    page.text = empty_structure
                    page.save(
                        summary=f'Bot: Voci recenti - Aggiornamento cache (v.{VERSION}) - File obsoleto svuotato',
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
        print(f"OK {blanked} file obsoleti {'(DRY-RUN)' if DRY_RUN else 'svuotati'}")
    else:
        print("  Nessun file obsoleto")
    return blanked


def update_data_page(page_name, lua_code, part_num, total_parts):
    """Aggiorna singola pagina dati. In DRY_RUN non scrive."""
    if DRY_RUN:
        print(f"    [DRY-RUN] Skip salvataggio {page_name}")
        return True
    page = pywikibot.Page(SITE, page_name)
    try:
        page.text = lua_code
        page.save(
            summary=f'Bot: Voci recenti - Aggiornamento cache (v.{VERSION}) - Parte {part_num}/{total_parts}',
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
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s:02d}s"


def main():
    global DRY_RUN

    # Supporto flag --dry-run da riga di comando
    if '--dry-run' in sys.argv:
        DRY_RUN = True

    tee = setup_log()

    dry_tag = " [DRY-RUN]" if DRY_RUN else ""
    print("=" * 60)
    print(f"Bot VociRecenti v{VERSION} - RICERCA COMPLETA DA CUTOFF{dry_tag}")
    print("=" * 60)

    if DRY_RUN:
        print("\n*** MODALITA' DRY-RUN ATTIVA: nessuna modifica verra' salvata su Wikipedia ***\n")

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
    print(f"  DRY_RUN:            {DRY_RUN}")
    print(f"  CacheMoved:         {CACHE_MOVED_PAGE} (scansione NS: {NS_SCAN})")
    print(f"  Cache parsed flag:  {CACHE_PARSED_PAGE}")

    print("\nLogin come BotVociRecenti...")
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
    # STEP 1: Carica cache esistente
    # ----------------------------------------
    print("=" * 60)
    print("STEP 1: CARICAMENTO CACHE ESISTENTE")
    print("=" * 60)
    _t1 = datetime.now()
    cached_pages, existing_titles = load_existing_cache_from_all_files()
    cache_files_count = len(get_all_data_pages())
    print(f"  [STEP 1] Tempo: {_fmt_elapsed((datetime.now()-_t1).total_seconds())}")

    # ----------------------------------------
    # STEP 2: Pulizia cache (fusione di PuliziaCache)
    # ----------------------------------------
    print("=" * 60)
    print("STEP 2: PULIZIA CACHE AUTOMATICA (interna)")
    print("=" * 60)
    _t2 = datetime.now()
    print(f"  Ora corrente: {_t2.strftime('%H:%M')}")

    if should_run_cleanup():
        cached_pages = run_cleanup_internal(cached_pages, cache_files_count)
        # Ricostruisci existing_titles dopo la pulizia
        existing_titles = {p['titolo'] for p in cached_pages}
        # Rileggi cache_files_count dopo eventuale modifica della struttura file
        cache_files_count = len(get_all_data_pages())
    else:
        print(f"  Skip pulizia")
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
            cached_pages = [p for p in cached_pages if p['titolo'].lower() not in deleted_titles]
            existing_titles -= deleted_titles
        else:
            print("  Nessuna voce cancellata o redirect trovata")
    else:
        print("  CheckDeleted=False -> skip")
    print(f"  [STEP 3b] Tempo: {_fmt_elapsed((datetime.now()-_t3b).total_seconds())}")

    # ----------------------------------------
    # STEP 4a: CacheMoved manuale
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
        cached_by_title = {p['titolo']: p for p in cached_pages}
        cm_pages, titles_to_remove, pages_to_update = read_cache_moved(
            existing_titles, cutoff_date, cached_by_title)

        if cm_pages:
            cached_pages.extend(cm_pages)
            print(f"\n  Aggiunte {len(cm_pages)} voci da CacheMoved")
        else:
            print("  Nessuna voce nuova da CacheMoved")

        if pages_to_update:
            cached_pages.extend(pages_to_update)
            print(f"  Aggiornate {len(pages_to_update)} voci (Aggiorna:)")

        mark_manual_cache_as_parsed()
    else:
        print("CacheParsed = 'True' -> CacheMoved gia' processata, skip")
    print(f"  [STEP 4a] Tempo: {_fmt_elapsed((datetime.now()-_t4a).total_seconds())}")

    # ----------------------------------------
    # STEP 4b: Nuove voci NS0 (batch API)
    # ----------------------------------------
    print()
    print("=" * 60)
    print("STEP 4b: RICERCA NUOVE VOCI NS0 (RecentChanges + batch API)")
    print("=" * 60)
    _t4b = datetime.now()

    print("Caricamento moves_cache...")
    moves_cache = load_moves_cache()

    new_pages = get_new_pages_only(existing_titles, cutoff_date, moves_cache)

    print("\nSalvataggio moves_cache...")
    save_moves_cache(moves_cache)
    print(f"  [STEP 4b] Tempo: {_fmt_elapsed((datetime.now()-_t4b).total_seconds())}")

    # ----------------------------------------
    # STEP 5: Scansione altri namespace (batch API)
    # ----------------------------------------
    print("\n" + "=" * 60)
    print("STEP 5: SCANSIONE ALTRI NAMESPACE (NS2/NS118, batch API)")
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

    cutoff_30 = now_it() - timedelta(days=MAX_AGE_DAYS)
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

    if titles_to_remove:
        before = len(all_pages)
        update_titles_set = {p['titolo'].lower() for p in pages_to_update}
        remove_set = {t.lower() for t in titles_to_remove if t.lower() not in update_titles_set}
        all_pages = [p for p in all_pages if p.get('titolo', '').lower() not in remove_set]
        removed_count = before - len(all_pages)
        print(f"  Voci rimosse da CacheMoved: {removed_count} "
              f"(richieste {len(titles_to_remove)})")

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
                deduped[seen_titles[t]] = update_titles_map[t]
        if len(deduped) < len(all_pages):
            print(f"  Dedup: {len(all_pages) - len(deduped)} duplicati rimossi (record aggiornati mantenuti)")
        all_pages = deduped

    all_pages.sort(
        key=lambda x: x.get('move_timestamp') or x.get('timestamp', ''),
        reverse=True
    )
    all_pages = all_pages[:MAX_PAGES]

    rimosse = len(new_pages) + len(cached_pages) - len(all_pages)
    print(f"\nVoci finali: {len(all_pages)}")
    print(f"  Nuove da RecentChanges (NS0): {len(new_pages)}")
    print(f"  Nuove da altri NS (NS2/118):  {len(ns_pages)}")
    print(f"  Dalla cache:                  {len(cached_pages)}")
    if titles_to_remove:
        print(f"  Rimosse da CacheMoved:        {removed_count}")
    if rimosse > 0:
        print(f"  Rimosse per limite:           {rimosse}")
    print(f"  [STEP 6] Tempo: {_fmt_elapsed((datetime.now()-_t6).total_seconds())}")

    # ----------------------------------------
    # STEP 7: Suddividi in file e salva
    # ----------------------------------------
    _t_split = datetime.now()
    file_groups = split_pages_into_files(all_pages)
    print(f"  [split] Tempo: {_fmt_elapsed((datetime.now()-_t_split).total_seconds())}")

    print("\n" + "=" * 60)
    print(f"STEP 7: GENERAZIONE E SALVATAGGIO{dry_tag}")
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
            print(f"  OK {'[DRY-RUN] Simulato' if DRY_RUN else 'Salvato!'} ({elapsed_save})")
            successes += 1
        else:
            print(f"  ERRORE salvataggio")

    _t_blank = datetime.now()
    blank_old_data_files(total_files)
    print(f"  [blank_old] Tempo: {_fmt_elapsed((datetime.now()-_t_blank).total_seconds())}")
    print(f"  [STEP 7] Tempo: {_fmt_elapsed((datetime.now()-_t7).total_seconds())}")

    # ----------------------------------------
    # STEP 8: Report diagnostico DRY-RUN o riepilogo finale
    # ----------------------------------------
    if DRY_RUN:
        print("\n" + "=" * 60)
        print("STEP 8: REPORT DIAGNOSTICO [DRY-RUN]")
        print("=" * 60)
        _cleanup_dry_run_report(all_pages)
        print("\n*** DRY-RUN completato: nessun file e' stato modificato su Wikipedia ***")

    total_elapsed = _fmt_elapsed((datetime.now() - run_start).total_seconds())
    print("\n" + "=" * 60)
    if successes == total_files:
        print(f"OK COMPLETATO!{dry_tag}")
        print("=" * 60)
        print(f"  Voci totali:  {len(all_pages)}")
        print(f"  File creati:  {total_files}")
        print(f"  Nuove voci:   {len(new_pages)}")
        print(f"  Tempo totale: {total_elapsed}")
        if not DRY_RUN:
            print(f"\nURL file:")
            for i in range(1, total_files + 1):
                print(f"  https://it.wikipedia.org/wiki/{DATA_PAGE_PREFIX}{i}")
    else:
        print(f"ATTENZIONE: {successes}/{total_files} file {'simulati' if DRY_RUN else 'salvati'} correttamente")
        print(f"  Tempo totale: {total_elapsed}")

    tee.close()


if __name__ == '__main__':
    main()
