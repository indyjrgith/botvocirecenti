#!/usr/bin/env python3
"""
Bot ArchiviaVociRecenti v1.1.6

Scansiona tutte le transclusioni di Template:ArchiviaVociRecenti, e per
ogni pagina sorgente che lo include: se e' ora di archiviare, "subst-a"
(via action=expandtemplates) le istanze di {{VociRecenti}} presenti nella
pagina, ne estrae le voci, le unisce (deduplicando) a quelle gia' presenti
nella pagina di archivio indicata, e salva.

Changelog:
- v1.0.0: Prima versione. Vedi PROGETTO_ArchiviaVociRecenti_HANDOFF.md per
        la spec completa e le decisioni di design.
        Comportamenti aggiuntivi rispetto all'handoff:
        - Edit conflict sul salvataggio della pagina di archivio: retry
          fino a 2 volte, ricaricando la pagina (force=True) e riapplicando
          il merge da capo su testo fresco prima di arrendersi.
        - Pagina sorgente trovata dal generator ma non piu' raggiungibile
          (race condition embeddedin/fetch): skip + avviso in talk (stesso
          meccanismo di dedup a marcatore delle altre notifiche).
- v1.1.1: Refactoring dedup: passaggio a extract_voci/merge dedicati,
        gestione ARCHIVE_MAX_CHARS, retry su edit conflict.
        BUG INTRODOTTO (non rilevato fino a v1.1.6): l'intero blocco
        get_pages_with_template/post_talk_notice_once/should_archive/
        expand_instance/process_page/main viene duplicato nel file,
        con due blocchi "if __name__ == '__main__'". Il primo main()
        (versione vecchia) falliva con NameError su source_instance_blocks
        se non ancora definita nel punto del file in cui veniva
        referenziata nelle versioni successive; il bot eseguiva inoltre
        il flusso due volte per lancio.
- v1.1.2: Rimossa chiusura </div> spuria da extract_voci. Prima modifica
        a build_final_text: BOT_START_MARKER + '\n' + merged_block.lstrip('\n').
- v1.1.3: Dedup per istanza invece che globale: introdotti
        source_instance_blocks/section_key/split_archive_sections/
        merge_instance_section/merge_structured_archive. La stessa voce
        puo' comparire in istanze VociRecenti diverse; la deduplica resta
        interna alla singola istanza.
- v1.1.4: Seconda modifica a build_final_text (definitiva):
        merged_block.strip('\n') con '\n\n' espliciti prima/dopo il blocco,
        per garantire sempre una riga vuota dopo BOT_START_MARKER e prima
        di BOT_END_MARKER.
- v1.1.5: Nessuna modifica funzionale rispetto a v1.1.4 (solo bump versione).
- v1.1.6: Fix del bug di duplicazione introdotto in v1.1.1: rimosso il
        blocco di funzioni duplicato (get_pages_with_template,
        post_talk_notice_once, should_archive, expand_instance,
        process_page, main) e il secondo 'if __name__'. Risolve il
        NameError su source_instance_blocks e la doppia esecuzione del
        bot ad ogni lancio.
"""

import pywikibot
import pywikibot.config as config
from datetime import datetime, timedelta
import re
import os
import sys
import calendar as _calendar

# ========================================
# FUSO ORARIO ITALIANO - implementazione robusta senza dipendenze esterne
# Ripresa identica da bot_voci_recenti_v30.py.
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
    dst_start = datetime(y, 3, _last_sunday(y, 3), 1, 0, 0)
    dst_end = datetime(y, 10, _last_sunday(y, 10), 1, 0, 0)
    return 2 if dst_start <= dt_utc_naive < dst_end else 1


def ts_utc_to_it(ts):
    """
    Converte un pywikibot.Timestamp (o qualsiasi datetime, aware o naive)
    in stringa YYYYMMDDHHMMSS in ora italiana (CET/CEST).
    """
    dt = ts.replace(tzinfo=None)  # normalizza a naive-UTC
    return (dt + timedelta(hours=_it_offset_for_utc(dt))).strftime('%Y%m%d%H%M%S')


def now_it():
    """
    Restituisce il datetime corrente in ora italiana (CET/CEST) come
    oggetto naive pronto per strftime e confronti.
    """
    from datetime import timezone as _tz
    utc_now = datetime.now(_tz.utc).replace(tzinfo=None)
    return utc_now + timedelta(hours=_it_offset_for_utc(utc_now))


# ========================================
# CONFIGURAZIONE
# ========================================
TEMPLATE_NAME = 'Template:ArchiviaVociRecenti'

ALLOWED_NS_PREFIXES = [
    'Wikipedia', 'Discussioni Wikipedia',
    'Utente', 'Discussioni utente',
    'Progetto', 'Discussioni progetto',
    'Portale', 'Discussioni portale',
]

DEFAULT_GIORNI = 10
MIN_GIORNI = 1
MAX_GIORNI = 10

DEFAULT_HEADING = '== Archiviazione eseguita il %d =='

BOT_START_MARKER = '<!-- INIZIO ELENCO BOT -->'
BOT_END_MARKER = '<!-- FINE ELENCO BOT -->'

ARCHIVE_MAX_CHARS = 1_500_000

SAVE_CONFLICT_RETRIES = 2

VERSION = '1.1.6'

config.put_throttle = 1
config.minthrottle = 0
config.maxthrottle = 2

# --- Modalita' DRY-RUN ---
# Se True: esegue tutte le fasi e tutte le chiamate API ma NON salva nulla
# su Wikipedia. Attivabile da riga di comando con --dry-run.
DRY_RUN = False

# --- Modalita' DEBUG ---
# Se True: stampa messaggi di diagnostica verbose.
# Attivabile da riga di comando con --debug.
DEBUG_MODE = False

DATA_DIR = os.environ.get('BOT_DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(DATA_DIR, 'archivia_voci_recenti.log')
LOG_MAX_BYTES = 2 * 1024 * 1024  # 2 MB

SITE = pywikibot.Site('it', 'wikipedia')

# Mappa prefisso -> namespace_id, caricata all'avvio in load_ns_prefix_map().
NS_PREFIX_MAP: dict = {}


def load_ns_prefix_map():
    """
    Carica la mappa prefisso -> namespace_id dal sito MediaWiki.
    Ripresa identica da bot_voci_recenti_v30.py.
    """
    global NS_PREFIX_MAP
    try:
        ns_map = {}
        for ns_id, ns_info in SITE.namespaces.items():
            if ns_id < 0:
                continue
            canonical = getattr(ns_info, 'canonical', None)
            if canonical:
                ns_map[canonical] = ns_id
            custom_name = getattr(ns_info, 'custom_name', None)
            if custom_name:
                ns_map[custom_name] = ns_id
            for alias in getattr(ns_info, 'aliases', []) or []:
                ns_map[alias] = ns_id
            try:
                ns_map[str(ns_info)] = ns_id
            except Exception:
                pass
        NS_PREFIX_MAP = ns_map
    except Exception as e:
        print(f"WARNING: impossibile caricare la mappa namespace: {e}")


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
# SCANNER A BILANCIAMENTO DI GRAFFE
# (adattato da find_balanced_braces di bot_voci_recenti_v30.py; qui non
# serve la gestione dei long string Lua)
# ========================================

def find_balanced_template_end(text, start):
    """
    Partendo da start (posizione della prima '{' di '{{'), trova la
    posizione subito dopo la '}' di chiusura bilanciata.
    """
    level = 0
    i = start
    n = len(text)
    while i < n:
        c = text[i]
        if c == '{':
            level += 1
        elif c == '}':
            level -= 1
            if level == 0:
                return i + 1
        i += 1
    return None


_TEMPLATE_OPEN_RE_CACHE = {}


def _template_open_re(template_name):
    rx = _TEMPLATE_OPEN_RE_CACHE.get(template_name)
    if rx is None:
        rx = re.compile(r'\{\{\s*' + re.escape(template_name) + r'\s*(?=[|}])', re.IGNORECASE)
        _TEMPLATE_OPEN_RE_CACHE[template_name] = rx
    return rx


def find_template_span(text, template_name, start=0):
    """Trova la prima istanza di {{template_name...}} da start in poi.
    Restituisce (start, end) oppure None."""
    m = _template_open_re(template_name).search(text, start)
    if not m:
        return None
    open_pos = m.start()
    end = find_balanced_template_end(text, open_pos)
    if end is None:
        return None
    return (open_pos, end)


def find_all_template_spans(text, template_name):
    """Trova tutte le istanze di {{template_name...}} nel testo, in
    ordine di apparizione."""
    spans = []
    pos = 0
    while True:
        span = find_template_span(text, template_name, pos)
        if span is None:
            break
        spans.append(span)
        pos = span[1]
    return spans


def split_top_level(s, sep):
    """Divide s in base a sep, ignorando i separatori annidati dentro
    {{...}} o [[...]]."""
    parts = []
    depth = 0
    current = []
    for c in s:
        if c in '{[':
            depth += 1
            current.append(c)
        elif c in '}]':
            depth -= 1
            current.append(c)
        elif c == sep and depth == 0:
            parts.append(''.join(current))
            current = []
        else:
            current.append(c)
    parts.append(''.join(current))
    return parts


def parse_params(raw_template_text):
    """Estrae i parametri di un'istanza di template gia' delimitata
    (testo completo '{{Nome|k=v|...}}'). Chiavi normalizzate lower-case."""
    inner = raw_template_text.strip()
    if inner.startswith('{{') and inner.endswith('}}'):
        inner = inner[2:-2]
    parts = split_top_level(inner, '|')
    params = {}
    for part in parts[1:]:  # parts[0] e' il nome del template
        if '=' not in part:
            continue
        key, val = part.split('=', 1)
        params[key.strip().lower()] = val.strip()
    return params


# ========================================
# VALIDAZIONE PARAMETRI ArchiviaVociRecenti
# ========================================

def validate_archivia_params(params):
    """
    Ri-valida per conto proprio i parametri dell'istanza del template
    (non si fida del solo rendering).
    Restituisce un dict: ok, pagina, giorni, intestazione, forza, errore.
    """
    pagina = (params.get('pagina') or '').strip()
    giorni_raw = (params.get('giorni') or '').strip()
    intestazione_raw = (params.get('intestazione') or '').strip()
    intestazione = intestazione_raw or None
    forza_raw = (params.get('forza') or '').strip().lower()
    forza = forza_raw == 'si'

    result = {
        'ok': False, 'pagina': None, 'giorni': DEFAULT_GIORNI,
        'intestazione': None, 'forza': forza, 'errore': None,
    }

    if not pagina:
        result['errore'] = (
            'Errore: pagina di archivio obbligatoria, da indicare nel '
            'parametro "pagina", preceduta dal namespace'
        )
        return result

    ns_ok = any(pagina.startswith(prefix + ':') for prefix in ALLOWED_NS_PREFIXES)
    if not ns_ok:
        result['errore'] = (
            'Errore: namespace errato. Sono ammessi i namespace Wikipedia:, '
            'Utente:, Progetto:, Portale: e le rispettive talk'
        )
        return result

    giorni = DEFAULT_GIORNI
    if giorni_raw:
        try:
            giorni = int(giorni_raw)
            if str(giorni) != giorni_raw or not (MIN_GIORNI <= giorni <= MAX_GIORNI):
                raise ValueError
        except ValueError:
            result['errore'] = (
                f'Errore: il numero dei giorni deve essere compreso fra '
                f'{MIN_GIORNI} e {MAX_GIORNI}'
            )
            return result

    result['ok'] = True
    result['pagina'] = pagina
    result['giorni'] = giorni
    result['intestazione'] = intestazione
    result['errore'] = None
    return result


# ========================================
# ESTRAZIONE VOCI E DEDUP
# ========================================

VOCE_LINE_RE = re.compile(r'^[ \t]*[*#][ \t]*\[\[.+?\]\].*$', re.MULTILINE)
WIKILINK_RE = re.compile(r'\[\[\s*([^|\]#]+)')

def extract_voci(expanded_text):
    """Estrae le righe voce da una singola istanza di VociRecenti,
    rimuovendo eventuali chiusure </div> spurie prodotte dall'espansione."""
    result = []
    for m in VOCE_LINE_RE.finditer(expanded_text):
        line = m.group(0)
        line = re.sub(r'</div>\s*$', '', line, flags=re.IGNORECASE)
        result.append(line)
    return result


def voce_key(line):
    """Chiave di dedup della singola istanza VociRecenti."""
    m = WIKILINK_RE.search(line)
    if not m:
        return line.strip()
    return m.group(1).replace('_', ' ').strip()


def dedup_instance_lines(lines):
    """Deduplica SOLO le righe prodotte dalla stessa istanza."""
    seen = set()
    result = []
    for line in lines:
        key = voce_key(line)
        if key in seen:
            continue
        seen.add(key)
        result.append(line)
    return result


def build_heading(intestazione_param, data_it):
    """
    Costruisce l'intestazione con la data odierna (formato GG/MM/AAAA)
    al posto di %d. Se intestazione_param e' None/vuoto, usa il default.
    Se intestazione_param e' letteralmente '""' (valore esplicitamente
    vuoto), restituisce stringa vuota (nessuna intestazione).
    """
    if intestazione_param == '""':
        return ''
    template = intestazione_param if intestazione_param else DEFAULT_HEADING
    return template.replace('%d', data_it)


_HEADING_LINE_RE = re.compile(r'^==.*==[ \t]*$')


def ensure_markers(archive_text, page_title=None):
    """
    Individua nel testo della pagina di archivio i marcatori bot e
    restituisce (before, block, after):
      - before: testo prima del marcatore di inizio (tipicamente
        l'intestazione esistente, verra' scartata e ricostruita da
        build_heading ad ogni archiviazione effettiva)
      - block: testo grezzo fra i due marcatori (contenuto di proprieta'
        del bot)
      - after: testo dopo il marcatore di fine (contenuto preesistente,
        mai toccato)
    Se i marcatori non sono presenti (pagina nuova o creata a mano),
    li posiziona subito dopo la prima riga di intestazione se presente,
    altrimenti in cima al testo.
    """
    start_idx = archive_text.find(BOT_START_MARKER)
    end_idx = archive_text.find(BOT_END_MARKER)

    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        before = archive_text[:start_idx]
        block = archive_text[start_idx + len(BOT_START_MARKER):end_idx]
        after = archive_text[end_idx + len(BOT_END_MARKER):]
        return before, block, after

    if (start_idx != -1) != (end_idx != -1):
        print(
            f"WARNING: marcatori bot malformati (uno presente, l'altro "
            f"assente) sulla pagina di archivio"
            f"{' ' + page_title if page_title else ''}; "
            f"verranno reinseriti da capo senza toccare il contenuto esistente."
        )

    if not archive_text:
        return '', '', ''

    lines = archive_text.split('\n', 1)
    first_line = lines[0]
    rest = lines[1] if len(lines) > 1 else ''
    if _HEADING_LINE_RE.match(first_line.strip()):
        return first_line + '\n', '', rest
    return '', '', archive_text


# ========================================
# RETE / ORCHESTRAZIONE
# ========================================

def get_pages_with_template():
    """Generator sulle pagine che transcludono TEMPLATE_NAME, filtrate ai
    soli namespace ammessi (embeddedin via API, nessun elenco statico)."""
    tmpl_page = pywikibot.Page(SITE, TEMPLATE_NAME)
    allowed_ns_ids = sorted({
        NS_PREFIX_MAP[prefix] for prefix in ALLOWED_NS_PREFIXES
        if prefix in NS_PREFIX_MAP
    })
    if not allowed_ns_ids:
        print("ERRORE: mappa namespace vuota, impossibile filtrare embeddedin.")
        return
    for page in tmpl_page.embeddedin(namespaces=allowed_ns_ids):
        yield page


def post_talk_notice_once(page, marker_id, message):
    """
    Posta un avviso in talk, identificato da un marcatore HTML stabile,
    solo se quel marcatore non e' gia' presente (evita spam ad ogni
    passaggio). Restituisce True se l'avviso e' stato postato (o lo
    sarebbe stato, in dry-run) o era gia' presente non necessitando
    ripubblicazione; False in caso di errore di salvataggio.
    """
    marker = f'<!-- BotArchiviaVociRecenti:{marker_id} -->'
    talk_page = page.toggleTalkPage()

    try:
        existing = talk_page.text if talk_page.exists() else ''
    except Exception as e:
        print(f"WARNING: impossibile leggere la talk di {page.title()}: {e}")
        existing = ''

    if marker in existing:
        return True

    new_section = (
        f"\n\n== Avviso automatico: ArchiviaVociRecenti ==\n"
        f"{marker}\n{message} --~~~~\n"
    )

    if DRY_RUN:
        print(f"[DRY-RUN] Avviso non pubblicato su {talk_page.title()}: {message}")
        return True

    try:
        talk_page.text = existing + new_section
        talk_page.save(
            summary=f'Bot: avviso ArchiviaVociRecenti (v.{VERSION})',
            minor=False, bot=True,
        )
        return True
    except Exception as e:
        print(f"ERRORE: impossibile salvare avviso in talk {talk_page.title()}: {e}")
        return False


def should_archive(archive_page, giorni, forza):
    """Decide se e' ora di archiviare."""
    if forza:
        return True
    if not archive_page.exists():
        return True
    try:
        last_rev_ts = archive_page.latest_revision.timestamp
    except Exception:
        return True
    last_it = ts_utc_to_it(last_rev_ts)
    last_date = datetime.strptime(last_it[:8], '%Y%m%d').date()
    today_date = now_it().date()
    return (today_date - last_date).days >= giorni


def expand_instance(page_title, raw_text):
    """
    Espande un'istanza {{VociRecenti|...}} via action=expandtemplates
    (mai action=parse). Restituisce (output, has_error). has_error e'
    True sia per errori Scribunto (class="error" nel testo espanso,
    indipendente dalla lingua dell'interfaccia) sia per eccezioni nella
    chiamata stessa.
    """
    try:
        expanded = SITE.expand_text(text=raw_text, title=page_title)
    except Exception as e:
        print(f"ERRORE: expand_text fallito per {page_title}: {e}")
        return None, True
    has_error = 'class="error"' in expanded
    return expanded, has_error


def process_page(page):
    """Orchestratore per una singola pagina sorgente."""
    title = page.title()
    print(f"\n--- Pagina: {title} ---")

    try:
        if not page.exists():
            print("  Pagina non piu' esistente (race condition), skip.")
            post_talk_notice_once(
                page, 'pagina-non-trovata',
                "Il bot ha rilevato una transclusione del template di "
                "archiviazione ma la pagina non risultava piu' raggiungibile "
                "al momento dell'elaborazione."
            )
            return
        text = page.get(force=True)
    except Exception as e:
        print(f"  Pagina non raggiungibile ({e}), skip con avviso.")
        try:
            post_talk_notice_once(
                page, 'pagina-non-trovata',
                "Il bot ha rilevato una transclusione del template di "
                "archiviazione ma la pagina non risultava piu' raggiungibile "
                "al momento dell'elaborazione."
            )
        except Exception:
            pass
        return

    # 1. Trova tutte le istanze di ArchiviaVociRecenti; usa solo la prima.
    spans_a = find_all_template_spans(text, 'ArchiviaVociRecenti')
    if not spans_a:
        print("  Nessuna istanza del template trovata (inatteso), skip.")
        return

    if len(spans_a) > 1:
        post_talk_notice_once(
            page, 'istanza-multipla',
            "Errore: piu' istanze del template di archiviazione nella "
            "pagina. Verra' considerata solo la prima."
        )

    raw_a = text[spans_a[0][0]:spans_a[0][1]]
    params = parse_params(raw_a)
    v = validate_archivia_params(params)

    if not v['ok']:
        post_talk_notice_once(page, 'parametri-non-validi', v['errore'])
        print(f"  Parametri non validi: {v['errore']}")
        return

    # 3. Trova tutte le istanze di VociRecenti.
    spans_v = find_all_template_spans(text, 'VociRecenti')
    if not spans_v:
        post_talk_notice_once(
            page, 'manca-vocirecenti',
            "Errore: Template VociRecenti non presente nella pagina."
        )
        print("  Nessuna istanza di VociRecenti trovata, skip archiviazione.")
        return

    archive_page = pywikibot.Page(SITE, v['pagina'])

    # 4. Decide se e' ora di archiviare.
    if not should_archive(archive_page, v['giorni'], v['forza']):
        print("  Non ancora ora di archiviare, skip.")
        return

    # 5-6. Espande ogni istanza VociRecenti separatamente.
    # La stessa voce puo' appartenere a istanze diverse: la deduplica
    # viene applicata esclusivamente all'interno della singola istanza.
    expanded_by_index = {}
    any_instance_error = False

    for idx, (s, e) in enumerate(spans_v):
        raw_v = text[s:e]
        expanded, has_error = expand_instance(title, raw_v)
        if has_error or expanded is None:
            any_instance_error = True
            expanded_by_index[idx] = []
            continue
        expanded_by_index[idx] = extract_voci(expanded)

    if any_instance_error:
        post_talk_notice_once(
            page, 'istanza-in-errore',
            "Attenzione: una o piu' istanze di VociRecenti hanno prodotto "
            "un errore durante l'espansione; le voci corrispondenti non "
            "sono state archiviate. Le altre istanze, se valide, sono "
            "comunque state archiviate."
        )

    if not any(expanded_by_index.values()):
        print("  Nessuna voce estratta (tutte le istanze in errore o vuote), skip salvataggio.")
        return

    data_it = now_it().strftime('%d/%m/%Y')
    heading = build_heading(v['intestazione'], data_it)

    # Ricostruisce la struttura della sorgente: ogni VociRecenti mantiene
    # la propria sezione e il proprio insieme di voci.
    source_blocks = source_instance_blocks(text, spans_v, expanded_by_index)

    def build_final_text():
        try:
            archive_text = archive_page.get(force=True) if archive_page.exists() else ''
        except Exception:
            archive_text = ''

        before, block, after = ensure_markers(
            archive_text, archive_page.title()
        )

        merged_block, n_new = merge_structured_archive(
            block, source_blocks
        )

        final_text = heading
        if heading:
            final_text += '\n'
        # The BOT marker is always followed by exactly one blank line before
        # the first section, preserving readable wikitext structure.
        final_text += BOT_START_MARKER + '\n\n'
        final_text += merged_block.strip('\n')
        final_text += '\n\n' + BOT_END_MARKER + after
        return final_text, n_new

    final_text, n_new = build_final_text()

    if len(final_text) > ARCHIVE_MAX_CHARS:
        post_talk_notice_once(
            page, 'dimensione-eccessiva',
            f"Errore: la pagina di archivio {v['pagina']} supererebbe la "
            f"dimensione massima consentita ({ARCHIVE_MAX_CHARS:,} caratteri) "
            f"e non e' stata aggiornata."
        )
        print("  Dimensione massima superata, salvataggio annullato.")
        return

    if n_new == 0:
        print("  Nessuna voce nuova da archiviare (tutte gia' presenti), skip salvataggio.")
        return

    summary = f'Bot: Archiviazione voci recenti (v.{VERSION})'

    if DRY_RUN:
        print(f"[DRY-RUN] Salverei {n_new} nuove voci su {v['pagina']} ({len(final_text)} caratteri).")
        return

    attempts = 0
    while True:
        try:
            archive_page.text = final_text
            archive_page.save(summary=summary, minor=True, bot=True)
            print(f"  OK - {n_new} nuove voci archiviate su {v['pagina']}.")
            return
        except pywikibot.exceptions.EditConflictError:
            attempts += 1
            if attempts > SAVE_CONFLICT_RETRIES:
                print(f"  ERRORE: edit conflict persistente su {v['pagina']} dopo {SAVE_CONFLICT_RETRIES} tentativi, skip.")
                return
            print(f"  Edit conflict su {v['pagina']}, ricarico e riapplico il merge (tentativo {attempts}/{SAVE_CONFLICT_RETRIES})...")
            final_text, n_new = build_final_text()
            if n_new == 0:
                print("  Dopo il ricalcolo non ci sono piu' voci nuove (gia' archiviate da un altro run), skip.")
                return
        except Exception as e:
            print(f"  ERRORE salvataggio su {v['pagina']}: {e}")
            return


def main():
    global DRY_RUN, DEBUG_MODE

    if '--dry-run' in sys.argv:
        DRY_RUN = True
    if '--debug' in sys.argv:
        DEBUG_MODE = True

    tee = setup_log()

    dry_tag = " [DRY-RUN]" if DRY_RUN else ""
    print("=" * 60)
    print(f"Bot ArchiviaVociRecenti v{VERSION}{dry_tag}")
    print("=" * 60)

    if DRY_RUN:
        print("\n*** MODALITA' DRY-RUN ATTIVA: nessuna modifica verra' salvata su Wikipedia ***\n")

    run_start = datetime.now()
    print(f"  Avvio: {run_start.strftime('%H:%M:%S')}")

    print("\nLogin...")
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

    print("Caricamento mappa namespace...")
    load_ns_prefix_map()
    print()

    n_pages = 0
    n_archived = 0
    n_errors = 0

    for page in get_pages_with_template():
        n_pages += 1
        try:
            before_log_len = 0
            process_page(page)
        except Exception as e:
            n_errors += 1
            print(f"ERRORE imprevisto su {page.title()}: {e}")
            continue

    elapsed = (datetime.now() - run_start).total_seconds()
    print("\n" + "=" * 60)
    print("REPORT FINALE")
    print("=" * 60)
    print(f"  Pagine esaminate: {n_pages}")
    print(f"  Errori imprevisti: {n_errors}")
    print(f"  Tempo totale: {elapsed:.1f}s")

    tee.close()



def source_instance_blocks(text, spans_v, expanded_by_index):
    """
    Crea un blocco distinto per ogni istanza VociRecenti.

    La stessa voce puo' quindi comparire in istanze diverse: la deduplica
    viene applicata esclusivamente all'interno della singola istanza.
    """
    blocks = []
    for idx, (s, e) in enumerate(spans_v):
        heading_match = None
        for m in re.finditer(r'(?m)^==[^=\n].*?==[ \t]*$', text[:s]):
            heading_match = m

        heading = heading_match.group(0).strip() if heading_match else ''
        blocks.append({
            'index': idx,
            'heading': heading,
            'lines': dedup_instance_lines(expanded_by_index[idx]),
        })
    return blocks


def section_key(heading):
    """Chiave stabile per associare una sezione dell'archivio alla sorgente."""
    return re.sub(r'\s+', ' ', heading.strip()).casefold()


def split_archive_sections(block_text):
    """
    Divide il blocco bot dell'archivio in sezioni di livello 2.
    Se il vecchio archivio e' piatto e non contiene sezioni, il contenuto
    viene conservato come preambolo per non perderlo.
    """
    matches = list(re.finditer(r'(?m)^==[^=\n].*?==[ \t]*$', block_text))
    if not matches:
        return block_text, []

    preamble = block_text[:matches[0].start()]
    sections = []
    for i, m in enumerate(matches):
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(block_text)
        sections.append({
            'heading': m.group(0).strip(),
            'body': block_text[m.end():body_end],
        })
    return preamble, sections


def merge_instance_section(existing_body, new_lines):
    """
    Fonde una singola istanza/sezione.

    La deduplica non attraversa mai sezioni diverse.
    """
    existing_lines = extract_voci(existing_body)
    existing_keys = {voce_key(line) for line in existing_lines}

    merged = list(existing_lines)
    n_new = 0
    for line in dedup_instance_lines(new_lines):
        key = voce_key(line)
        if key in existing_keys:
            continue
        merged.append(line)
        existing_keys.add(key)
        n_new += 1
    return merged, n_new


def merge_structured_archive(existing_block_text, source_blocks):
    """
    Fonde le nuove voci nelle sezioni corrispondenti.

    Ogni istanza VociRecenti della sorgente ha il proprio blocco e la
    propria deduplica. Due istanze diverse possono contenere la stessa voce.
    """
    preamble, existing_sections = split_archive_sections(existing_block_text)

    existing_by_key = {}
    for i, sec in enumerate(existing_sections):
        existing_by_key.setdefault(section_key(sec['heading']), []).append(i)

    output_sections = []
    used_existing = set()
    total_new = 0

    # La sorgente stabilisce ordine e struttura delle sezioni.
    for src_block in source_blocks:
        heading = src_block['heading']
        key = section_key(heading)

        existing_body = ''
        if heading:
            candidates = existing_by_key.get(key, [])
            candidate = next((i for i in candidates if i not in used_existing), None)
            if candidate is not None:
                used_existing.add(candidate)
                existing_body = existing_sections[candidate]['body']

        merged_lines, n_new = merge_instance_section(
            existing_body, src_block['lines']
        )
        total_new += n_new

        if heading:
            body = '\n' + '\n'.join(merged_lines) + '\n' if merged_lines else '\n'
            output_sections.append(f"{heading}\n{body}")
        elif merged_lines:
            output_sections.append('\n'.join(merged_lines) + '\n')

    # Non perdere sezioni eventualmente presenti nell'archivio ma assenti
    # dalla pagina sorgente corrente.
    for i, sec in enumerate(existing_sections):
        if i not in used_existing:
            output_sections.append(f"{sec['heading']}{sec['body']}")

    prefix = preamble if preamble.strip() else ''
    return prefix + ''.join(output_sections), total_new


# ========================================
# RETE / ORCHESTRAZIONE
# ========================================

if __name__ == "__main__":
    main()
