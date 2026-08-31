#!/usr/bin/env python3
"""
Bot ArchiviaVociRecenti v1.3.1

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
- v1.2.0: Refactoring dell'accoppiamento sezione sorgente <-> sezione
        archiviata: rimossa la logica basata sulle intestazioni di livello
        2 (source_instance_blocks/section_key/split_archive_sections/
        merge_instance_section/merge_structured_archive, introdotte in
        v1.1.3), causa di fallimenti dell'archiviazione al minimo cambio
        di intestazione o in assenza di intestazioni. Sostituita con
        marcatori HTML a hash (<!-- ArchiviaVociRecenti:sezione:HASH -->)
        piazzati prima del testo grezzo che precede ciascuna istanza
        VociRecenti: l'hash e' calcolato su quel testo grezzo, quindi
        qualunque modifica dell'etichetta (anche minima) fa si' che la
        sezione archiviata resti intatta dov'e' (mai cancellata) e ne
        venga creata una nuova con il testo aggiornato. Se l'archivio non
        contiene alcun marcatore riconoscibile e non e' vuoto, il bot non
        modifica la pagina e segnala una volta in talk; testo estraneo
        prima del primo marcatore viene invece preservato cosi' com'e' e
        non blocca l'elaborazione delle sezioni riconosciute.
- v1.2.2: Fix di find_balanced_template_end: contava ogni singola '{' e
        '}' invece delle sole coppie doppie '{{'/'}}' che delimitano
        davvero un template per MediaWiki. Un valore di parametro con una
        graffa singola isolata (es. una regexp con '%{...}') veniva quindi
        interpretato erroneamente come apertura di un livello di
        annidamento mai richiuso, facendo scartare l'intera istanza come
        "non bilanciata" pur essendo perfettamente valida per il wiki; il
        suo testo grezzo restava cosi' visibile, non espanso, nell'
        etichetta della sezione archiviata successiva. Riscritta la
        funzione per contare solo le coppie '{{'/'}}' (avanzando di 2
        caratteri quando trovate, di 1 sulle graffe singole isolate); il
        rilevamento di squilibri genuini (es. un template annidato aperto
        e mai chiuso) resta invariato.
- v1.2.3: Fix di append_new_entries: quando la sezione a cui si accodano
        nuove voci e' l'ultima del blocco bot (adiacente a
        BOT_END_MARKER), il suo 'body' include il '\n\n' che precede il
        marcatore di fine, inserito da build_final_text. Cio' faceva si'
        che il body terminasse gia' con newline multipli, non
        normalizzati a uno solo prima di accodare le nuove voci, con
        conseguente riga vuota spuria fra l'ultima voce preesistente e la
        prima voce nuova (che rompeva la numerazione automatica delle
        liste wikitext). La funzione ora normalizza sempre il body a
        terminare con un singolo '\n' prima di accodare, indipendentemente
        da quanti newline finali fossero presenti.
- v1.3.0: Nuovo parametro 'pulizia' (off/on/si/lasciaredirect, default off).
        Quando l'archiviazione viene eseguita (should_archive == True),
        se pulizia != off il bot interroga in batch (query_titles_status,
        chunk da CLEANUP_API_CHUNK_SIZE titoli per chiamata) lo stato
        delle pagine di TUTTE le voci presenti nel blocco bot dell'
        archivio (non solo quelle appena aggiunte in questo passaggio) e
        rimuove le righe relative a pagine cancellate (sempre, in
        modalita' 'on'/'si' e 'lasciaredirect') o diventate redirect
        (solo in modalita' 'on'/'si'; in 'lasciaredirect' i redirect
        restano per verifiche manuali). La pulizia e' applicata da
        apply_pulizia() sul blocco gia' fuso da merge_marker_sections,
        dopo il merge e prima della ricostruzione del testo finale;
        righe-voce senza un wikilink riconoscibile non vengono toccate.
        Poiche' la pulizia puo' rimuovere voci anche quando non ce ne
        sono di nuove da aggiungere, build_final_text ora restituisce
        anche n_removed e il salvataggio viene eseguito se n_new > 0
        OPPURE n_removed > 0 (prima veniva saltato se n_new == 0). In
        caso di errore della query API su un batch di titoli, quei
        titoli non vengono toccati (nessuna rimozione), per sicurezza.
- v1.3.1: Fix: se la pagina sorgente non contiene piu' alcuna istanza di
        VociRecenti (spans_v vuoto, es. template rimosso dopo che le voci
        sono gia' state archiviate) e la pulizia e' attiva (pulizia !=
        off), il bot non esce piu' immediatamente: prosegue fino a
        should_archive/build_final_text, cosi' la pulizia dell'archivio
        viene comunque valutata al passaggio previsto in base all'opzione
        'giorni', anche in assenza di voci nuove da archiviare. In questo
        caso non viene piu' postato l'avviso 'manca-vocirecenti' in talk,
        trattandosi di uno stato normale di funzionamento (non un errore)
        quando la pulizia e' attiva. Comportamento invariato quando
        pulizia == off: il bot esce subito con l'avviso, come prima.
"""

import pywikibot
import pywikibot.data.api
import pywikibot.config as config
from datetime import datetime, timedelta
import re
import os
import sys
import hashlib
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

# Marcatore per sezione (accoppiamento a hash fra istanza sorgente e
# sezione archiviata). Vedi build_source_instances/merge_marker_sections.
SECTION_MARKER_PREFIX = '<!-- ArchiviaVociRecenti:sezione:'
SECTION_MARKER_SUFFIX = ' -->'

ARCHIVE_MAX_CHARS = 1_500_000

SAVE_CONFLICT_RETRIES = 2

# Numero di titoli per chiamata API nella verifica batch dello stato delle
# pagine (parametro pulizia=). Il bot e' flaggato (apihighlimits, 500 per
# chiamata) ma per prudenza si usa lo stesso valore gia' adottato per
# l'altro bot del progetto.
CLEANUP_API_CHUNK_SIZE = 50

VERSION = '1.3.1'

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

    Conta esclusivamente le COPPIE doppie '{{' / '}}' (i veri delimitatori
    di template per MediaWiki), non le singole graffe isolate: un valore
    di parametro che contiene una '{' o '}' solitaria (es. una regexp con
    '%{...}' o simili) e' testo letterale per il parser del wiki e non
    deve alterare il livello di annidamento, altrimenti template
    perfettamente validi verrebbero scartati come "non bilanciati".
    """
    level = 0
    i = start
    n = len(text)
    while i < n - 1:
        if text[i] == '{' and text[i + 1] == '{':
            level += 1
            i += 2
            continue
        if text[i] == '}' and text[i + 1] == '}':
            level -= 1
            i += 2
            if level == 0:
                return i
            continue
        i += 1
    return None


_TEMPLATE_OPEN_RE_CACHE = {}


def _template_open_re(template_name):
    rx = _TEMPLATE_OPEN_RE_CACHE.get(template_name)
    if rx is None:
        rx = re.compile(r'\{\{\s*' + re.escape(template_name) + r'\s*(?=[|}])', re.IGNORECASE)
        _TEMPLATE_OPEN_RE_CACHE[template_name] = rx
    return rx


def find_all_template_spans_ex(text, template_name):
    """
    Come find_all_template_spans, ma restituisce anche il numero di
    occorrenze scartate perche' con graffe non bilanciate (tipicamente un
    bug nella sorgente: un valore di parametro che contiene una '{' senza
    la '}' corrispondente). Un'occorrenza del genere viene saltata SENZA
    interrompere la scansione, cosi' da non perdere le istanze successive
    valide: prima del fix, un'unica istanza malformata faceva sparire
    silenziosamente tutte quelle dopo di essa nella pagina.
    """
    spans = []
    n_skipped = 0
    pos = 0
    open_re = _template_open_re(template_name)
    while True:
        m = open_re.search(text, pos)
        if not m:
            break
        open_pos = m.start()
        end = find_balanced_template_end(text, open_pos)
        if end is None:
            n_skipped += 1
            pos = m.end()
            continue
        spans.append((open_pos, end))
        pos = end
    return spans, n_skipped


def find_all_template_spans(text, template_name):
    """Trova tutte le istanze di {{template_name...}} nel testo, in
    ordine di apparizione. Le istanze con graffe non bilanciate vengono
    saltate silenziosamente; usare find_all_template_spans_ex per essere
    avvisati di eventuali scarti."""
    spans, _ = find_all_template_spans_ex(text, template_name)
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

    pulizia_raw = (params.get('pulizia') or '').strip().lower()
    if pulizia_raw in ('', 'off', 'no'):
        pulizia = 'off'
    elif pulizia_raw in ('on', 'si'):
        pulizia = 'on'
    elif pulizia_raw == 'lasciaredirect':
        pulizia = 'lasciaredirect'
    else:
        pulizia = None  # non valido, gestito sotto dopo il check su 'pagina'

    result = {
        'ok': False, 'pagina': None, 'giorni': DEFAULT_GIORNI,
        'intestazione': None, 'forza': forza, 'pulizia': 'off', 'errore': None,
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
            result['pagina'] = pagina  # titolo comunque valido/risolvibile
            result['errore'] = (
                f'Errore: il numero dei giorni deve essere compreso fra '
                f'{MIN_GIORNI} e {MAX_GIORNI}'
            )
            return result

    if pulizia is None:
        result['pagina'] = pagina  # titolo comunque valido/risolvibile
        result['giorni'] = giorni
        result['errore'] = (
            'Errore: il parametro pulizia deve essere "off", "on" (o "si") '
            f'oppure "lasciaredirect" (valore fornito: "{pulizia_raw}")'
        )
        return result

    result['ok'] = True
    result['pagina'] = pagina
    result['giorni'] = giorni
    result['intestazione'] = intestazione
    result['pulizia'] = pulizia
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


# ========================================
# PULIZIA ARCHIVIO (parametro pulizia=on/si/lasciaredirect)
# ========================================

def extract_voce_title(line):
    """Estrae il titolo della voce (primo wikilink della riga),
    normalizzato come voce_key. None se la riga non ha un wikilink
    riconoscibile."""
    m = WIKILINK_RE.search(line)
    if not m:
        return None
    return m.group(1).replace('_', ' ').strip()


def query_titles_status(titles):
    """
    Interroga in batch (chunk da CLEANUP_API_CHUNK_SIZE titoli per
    chiamata, action=query&prop=info) lo stato delle pagine indicate.
    Restituisce un dict {titolo: {'missing': bool, 'redirect': bool,
    'error': bool}}. In caso di errore su un batch, i titoli di quel
    batch vengono marcati 'error': True (nessuna rimozione verra'
    applicata a quei titoli, per sicurezza).
    """
    status = {}
    unique_titles = list(dict.fromkeys(titles))  # dedup preservando l'ordine

    for i in range(0, len(unique_titles), CLEANUP_API_CHUNK_SIZE):
        chunk = unique_titles[i:i + CLEANUP_API_CHUNK_SIZE]
        try:
            req = pywikibot.data.api.Request(
                site=SITE,
                parameters={
                    'action': 'query',
                    'prop': 'info',
                    'titles': '|'.join(chunk),
                }
            )
            data = req.submit()
        except Exception as e:
            print(f"WARNING: query stato pagine (pulizia) fallita per un batch di {len(chunk)} titoli: {e}")
            for t in chunk:
                status[t] = {'missing': False, 'redirect': False, 'error': True}
            continue

        query = data.get('query', {})
        pages = query.get('pages', {})
        for pinfo in pages.values():
            title = pinfo.get('title')
            if title is None:
                continue
            status[title] = {
                'missing': 'missing' in pinfo,
                'redirect': 'redirect' in pinfo,
                'error': False,
            }

        # I titoli normalizzati da MediaWiki (es. differenze di
        # maiuscola/minuscola nella prima lettera) vanno rimappati sul
        # titolo originale richiesto, se non gia' presente.
        for norm in query.get('normalized', []):
            orig, to = norm.get('from'), norm.get('to')
            if orig and to in status and orig not in status:
                status[orig] = status[to]

    return status


def apply_pulizia(merged_block, modalita):
    """
    Applica la pulizia al blocco bot GIA' FUSO (tutte le sezioni
    dell'archivio, non solo quelle toccate in questo passaggio):
    rimuove le righe-voce relative a pagine cancellate (sempre, se
    modalita' != 'off') e, solo in modalita' 'on', anche quelle
    relative a pagine diventate redirect. Righe senza un wikilink
    riconoscibile non vengono toccate. In caso di errore della query
    API su un titolo, quel titolo non viene toccato.
    Restituisce (nuovo_blocco, n_rimosse).
    """
    if modalita == 'off':
        return merged_block, 0

    line_matches = list(VOCE_LINE_RE.finditer(merged_block))
    if not line_matches:
        return merged_block, 0

    titles_by_match = []
    titles_to_query = []
    for m in line_matches:
        title = extract_voce_title(m.group(0))
        titles_by_match.append(title)
        if title is not None:
            titles_to_query.append(title)

    if not titles_to_query:
        return merged_block, 0

    status = query_titles_status(titles_to_query)

    spans_to_remove = []
    for m, title in zip(line_matches, titles_by_match):
        if title is None:
            continue
        st = status.get(title)
        if st is None or st['error']:
            continue
        remove = st['missing'] or (st['redirect'] and modalita == 'on')
        if not remove:
            continue
        start, end = m.span()
        if end < len(merged_block) and merged_block[end] == '\n':
            end += 1
        spans_to_remove.append((start, end))

    if not spans_to_remove:
        return merged_block, 0

    new_block = merged_block
    for start, end in sorted(spans_to_remove, reverse=True):
        new_block = new_block[:start] + new_block[end:]

    return new_block, len(spans_to_remove)


# ========================================
# MARCATORI A HASH PER SEZIONE
#
# Ogni istanza {{VociRecenti}} della sorgente e' preceduta da testo grezzo
# (etichetta: es. un titolo di sezione, un grassetto...). Quel testo grezzo
# viene hashato per ottenere un id stabile che accoppia l'istanza sorgente
# alla sezione corrispondente gia' archiviata, indipendentemente da
# eventuali riordini altrove nella pagina. Se il testo grezzo cambia anche
# di poco, l'hash cambia: la vecchia sezione archiviata resta intatta
# (Caso B, mai cancellata) e ne viene creata una nuova (Caso A).
# ========================================

SECTION_MARKER_RE = re.compile(
    re.escape(SECTION_MARKER_PREFIX) + r'([0-9a-f]{10}(?:-\d+)?)' + re.escape(SECTION_MARKER_SUFFIX)
)


def section_marker(marker_id):
    return f'{SECTION_MARKER_PREFIX}{marker_id}{SECTION_MARKER_SUFFIX}'


def compute_instance_labels(text, spans_a, spans_v):
    """
    Restituisce, nell'ordine della sorgente, il testo grezzo che precede
    ciascuna istanza VociRecenti: dalla fine dell'istanza precedente (o
    dalla fine della prima istanza di ArchiviaVociRecenti, per la prima
    VociRecenti) fino all'inizio dell'istanza corrente.
    """
    labels = []
    prev_end = spans_a[0][1] if spans_a else 0
    for (s, e) in spans_v:
        labels.append(text[prev_end:s])
        prev_end = e
    return labels


def compute_section_marker_ids(labels):
    """
    Calcola l'id marcatore (10 caratteri esadecimali di uno sha256) per
    ciascuna etichetta, nell'ordine della sorgente. Se piu' istanze
    condividono la stessa identica etichetta (caso raro), l'id viene
    disambiguato aggiungendo l'indice di occorrenza di quell'etichetta
    ripetuta (non l'indice assoluto dell'istanza), cosi' che un
    inserimento/rimozione altrove nella pagina non comprometta
    l'accoppiamento di queste istanze.
    """
    total_by_label = {}
    for label in labels:
        total_by_label[label] = total_by_label.get(label, 0) + 1

    occurrence_counts = {}
    ids = []
    for label in labels:
        h = hashlib.sha256(label.encode('utf-8')).hexdigest()[:10]
        if total_by_label[label] > 1:
            occ = occurrence_counts.get(label, 0)
            occurrence_counts[label] = occ + 1
            ids.append(f'{h}-{occ}')
        else:
            ids.append(h)
    return ids


def build_source_instances(text, spans_a, spans_v, expanded_by_index):
    """
    Costruisce, per ogni istanza VociRecenti della sorgente, l'etichetta
    (testo grezzo che la precede), il marcatore a hash corrispondente e le
    voci (deduplicate esclusivamente all'interno della singola istanza).
    """
    labels = compute_instance_labels(text, spans_a, spans_v)
    marker_ids = compute_section_marker_ids(labels)

    instances = []
    for idx in range(len(spans_v)):
        instances.append({
            'marker_id': marker_ids[idx],
            'label': labels[idx],
            'lines': dedup_instance_lines(expanded_by_index[idx]),
        })
    return instances


def parse_marker_sections(block_text):
    """
    Analizza il blocco bot esistente dell'archivio individuando i
    marcatori di sezione. Restituisce (ok, preamble, sections):
      - ok=False: nessun marcatore presente e il blocco non e' vuoto ->
        struttura non riconoscibile (Caso C), nessuna corrispondenza
        possibile con la sorgente.
      - preamble: testo eventualmente presente prima del primo marcatore.
        Viene preservato COSI' COM'E' in cima al blocco ricostruito (mai
        validato ne' cancellato): se in una pagina di archivio esiste
        anche solo una porzione con marcatori riconoscibili, quella
        porzione viene comunque elaborata normalmente.
      - sections: lista ordinata di dict {marker_id, body}, dove body e'
        tutto il testo (etichetta + voci) fino al marcatore successivo o
        alla fine del blocco.
    """
    matches = list(SECTION_MARKER_RE.finditer(block_text))

    if not matches:
        if block_text.strip():
            return False, '', []
        return True, '', []

    preamble = block_text[:matches[0].start()]
    sections = []
    for i, m in enumerate(matches):
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(block_text)
        sections.append({
            'marker_id': m.group(1),
            'body': block_text[m.end():body_end],
        })
    return True, preamble, sections


def append_new_entries(existing_body, new_lines):
    """
    Aggiunge in fondo al corpo di una sezione esistente (dopo l'ultima
    voce, prima del marcatore successivo) solo le voci nuove non ancora
    presenti; non tocca il contenuto preesistente (etichetta + voci gia'
    archiviate, anche se modificato manualmente).
    """
    existing_lines = extract_voci(existing_body)
    existing_keys = {voce_key(line) for line in existing_lines}

    to_append = []
    for line in new_lines:  # gia' deduplicate internamente all'istanza
        key = voce_key(line)
        if key in existing_keys:
            continue
        to_append.append(line)
        existing_keys.add(key)

    if not to_append:
        return existing_body, 0

    body = existing_body
    if body:
        body = body.rstrip('\n') + '\n'
    body += '\n'.join(to_append) + '\n'
    return body, len(to_append)


def merge_marker_sections(existing_block_text, source_instances):
    """
    Fonde le nuove voci nell'archivio esistente accoppiando le sezioni
    tramite i marcatori a hash.

    - Marcatore esistente combacia con un'istanza sorgente: la sezione
      esistente e' preservata cosi' com'e' e solo le voci nuove vengono
      aggiunte in fondo (aggiornamento).
    - Nessun marcatore combacia: nuova sezione creata da zero, tutte le
      voci trattate come nuove (Caso A).
    - Marcatore esistente senza corrispondenza nella sorgente attuale:
      sezione conservata intatta in fondo, nell'ordine originale
      dell'archivio (Caso B, mai cancellata).

    Restituisce (merged_block, n_new, ok). ok=False indica struttura non
    riconoscibile (Caso C): il chiamante non deve modificare l'archivio.
    """
    ok, preamble, existing_sections = parse_marker_sections(existing_block_text)
    if not ok:
        return None, 0, False

    existing_by_id = {sec['marker_id']: sec for sec in existing_sections}
    used_ids = set()

    output_parts = [preamble] if preamble else []
    total_new = 0

    # NB: 'body' include SEMPRE la propria interruzione di riga iniziale
    # (che separa il marcatore dal contenuto). Il marcatore viene quindi
    # concatenato al body senza aggiungere un proprio '\n': se lo si
    # aggiungesse qui, verrebbe "catturato" dentro il body al successivo
    # parse_marker_sections e ri-aggiunto ad ogni ciclo, accumulando righe
    # vuote a ogni archiviazione successiva.
    for inst in source_instances:
        marker_id = inst['marker_id']
        existing_sec = existing_by_id.get(marker_id)

        if existing_sec is not None:
            used_ids.add(marker_id)
            body, n_new = append_new_entries(existing_sec['body'], inst['lines'])
        else:
            label = inst['label']
            body = label if label.startswith('\n') else '\n' + label
            if not body.endswith('\n'):
                body += '\n'
            if inst['lines']:
                body += '\n'.join(inst['lines']) + '\n'
            n_new = len(inst['lines'])

        total_new += n_new
        output_parts.append(section_marker(marker_id) + body)

    # Sezioni dell'archivio non piu' presenti nella sorgente attuale:
    # conservate intatte in fondo, nell'ordine originale dell'archivio.
    for sec in existing_sections:
        if sec['marker_id'] not in used_ids:
            output_parts.append(section_marker(sec['marker_id']) + sec['body'])

    return ''.join(output_parts), total_new, True


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
    #    (le istanze con graffe sbilanciate vengono scartate da find_
    #    all_template_spans_ex; qui l'avviso puo' andare solo sulla talk
    #    della pagina sorgente, dato che l'archivio non e' ancora noto)
    spans_a, n_skipped_a = find_all_template_spans_ex(text, 'ArchiviaVociRecenti')
    if not spans_a:
        print("  Nessuna istanza del template trovata (inatteso), skip.")
        return

    if n_skipped_a:
        post_talk_notice_once(
            page, 'istanza-archiviavocirecenti-non-bilanciata',
            "Errore: una o piu' istanze del template di archiviazione "
            "hanno graffe non bilanciate (probabile errore in un valore "
            "di parametro) e sono state ignorate dal bot."
        )

    raw_a = text[spans_a[0][0]:spans_a[0][1]]
    params = parse_params(raw_a)
    v = validate_archivia_params(params)

    # Da qui in avanti, se il titolo della pagina di archivio e'
    # risolvibile, tutti gli avvisi del bot vanno sulla SUA talk (non su
    # quella della pagina sorgente): e' li' che chi la gestisce guarda.
    notice_page = pywikibot.Page(SITE, v['pagina']) if v['pagina'] else page

    if not v['ok']:
        post_talk_notice_once(notice_page, 'parametri-non-validi', v['errore'])
        print(f"  Parametri non validi: {v['errore']}")
        return

    if len(spans_a) > 1:
        post_talk_notice_once(
            notice_page, 'istanza-multipla',
            "Errore: piu' istanze del template di archiviazione nella "
            "pagina. Verra' considerata solo la prima."
        )

    # 3. Trova tutte le istanze di VociRecenti.
    spans_v, n_skipped_v = find_all_template_spans_ex(text, 'VociRecenti')

    if n_skipped_v:
        post_talk_notice_once(
            notice_page, 'istanza-vocirecenti-non-bilanciata',
            "Errore: una o piu' istanze di VociRecenti hanno graffe non "
            "bilanciate (probabile errore in un valore di parametro, es. "
            "una '{' senza '}' corrispondente) e sono state ignorate dal "
            "bot; le istanze successive nella pagina sono state comunque "
            "elaborate normalmente."
        )

    if not spans_v and v['pulizia'] == 'off':
        post_talk_notice_once(
            notice_page, 'manca-vocirecenti',
            "Errore: Template VociRecenti non presente nella pagina."
        )
        print("  Nessuna istanza di VociRecenti trovata, skip archiviazione.")
        return

    if not spans_v:
        # Nessuna istanza di VociRecenti nella sorgente, ma la pulizia e'
        # attiva: e' uno stato normale di funzionamento (es. template
        # rimosso dopo che le voci sono gia' state archiviate), non un
        # errore da segnalare in talk. Si prosegue comunque fino a
        # should_archive/build_final_text, cosi' la pulizia dell'archivio
        # viene comunque valutata al passaggio previsto in base a 'giorni'.
        print("  Nessuna istanza di VociRecenti trovata; pulizia attiva, valuto solo l'eventuale pulizia.")

    archive_page = notice_page

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
            archive_page, 'istanza-in-errore',
            "Attenzione: una o piu' istanze di VociRecenti hanno prodotto "
            "un errore durante l'espansione; le voci corrispondenti non "
            "sono state archiviate. Le altre istanze, se valide, sono "
            "comunque state archiviate."
        )

    if not any(expanded_by_index.values()) and v['pulizia'] == 'off':
        print("  Nessuna voce estratta (tutte le istanze in errore o vuote), skip salvataggio.")
        return

    data_it = now_it().strftime('%d/%m/%Y')
    heading = build_heading(v['intestazione'], data_it)

    # Ricostruisce la struttura della sorgente: ogni VociRecenti e'
    # accoppiata alla sezione archiviata corrispondente tramite un
    # marcatore a hash calcolato sul testo grezzo che la precede.
    source_instances = build_source_instances(text, spans_a, spans_v, expanded_by_index)

    def build_final_text():
        try:
            archive_text = archive_page.get(force=True) if archive_page.exists() else ''
        except Exception:
            archive_text = ''

        before, block, after = ensure_markers(
            archive_text, archive_page.title()
        )

        merged_block, n_new, ok = merge_marker_sections(block, source_instances)
        if not ok:
            return None, 0, 0, False

        # Pulizia sull'intero blocco bot gia' fuso (tutte le sezioni
        # dell'archivio, non solo quelle appena toccate in questo
        # passaggio), eseguita solo nei passaggi in cui si archivia
        # effettivamente (siamo gia' oltre il check should_archive).
        n_removed = 0
        if v['pulizia'] != 'off':
            merged_block, n_removed = apply_pulizia(merged_block, v['pulizia'])

        final_text = heading
        if heading:
            final_text += '\n'
        # The BOT marker is always followed by exactly one blank line before
        # the first section, preserving readable wikitext structure.
        final_text += BOT_START_MARKER + '\n\n'
        final_text += merged_block.strip('\n')
        final_text += '\n\n' + BOT_END_MARKER + after
        return final_text, n_new, n_removed, True

    final_text, n_new, n_removed, ok = build_final_text()

    if not ok:
        post_talk_notice_once(
            archive_page, 'archivio-struttura-non-riconosciuta',
            f"Errore: nella pagina di archivio {v['pagina']} non e' stato "
            "trovato alcun marcatore di sezione riconoscibile dal bot e la "
            "pagina non e' vuota; per sicurezza non e' stata modificata "
            "automaticamente. Se l'archivio e' stato creato manualmente o "
            "con una versione precedente del bot, e' necessario un "
            "intervento manuale."
        )
        print("  Struttura archivio non riconoscibile, salvataggio annullato.")
        return

    if len(final_text) > ARCHIVE_MAX_CHARS:
        post_talk_notice_once(
            archive_page, 'dimensione-eccessiva',
            f"Errore: la pagina di archivio {v['pagina']} supererebbe la "
            f"dimensione massima consentita ({ARCHIVE_MAX_CHARS:,} caratteri) "
            f"e non e' stata aggiornata."
        )
        print("  Dimensione massima superata, salvataggio annullato.")
        return

    if n_new == 0 and n_removed == 0:
        print("  Nessuna voce nuova da archiviare e nessuna voce da rimuovere, skip salvataggio.")
        return

    summary_parts = []
    if n_new:
        summary_parts.append(f'{n_new} nuove voci archiviate')
    if n_removed:
        summary_parts.append(f'{n_removed} voci rimosse (pulizia)')
    summary = f"Bot: {'; '.join(summary_parts)} (v.{VERSION})"

    if DRY_RUN:
        print(f"[DRY-RUN] Salverei: {n_new} nuove voci, {n_removed} voci rimosse su {v['pagina']} ({len(final_text)} caratteri).")
        return

    attempts = 0
    while True:
        try:
            archive_page.text = final_text
            archive_page.save(summary=summary, minor=True, bot=True)
            print(f"  OK - {n_new} nuove voci archiviate, {n_removed} voci rimosse su {v['pagina']}.")
            return
        except pywikibot.exceptions.EditConflictError:
            attempts += 1
            if attempts > SAVE_CONFLICT_RETRIES:
                print(f"  ERRORE: edit conflict persistente su {v['pagina']} dopo {SAVE_CONFLICT_RETRIES} tentativi, skip.")
                return
            print(f"  Edit conflict su {v['pagina']}, ricarico e riapplico il merge (tentativo {attempts}/{SAVE_CONFLICT_RETRIES})...")
            final_text, n_new, n_removed, ok = build_final_text()
            if not ok:
                post_talk_notice_once(
                    archive_page, 'archivio-struttura-non-riconosciuta',
                    f"Errore: nella pagina di archivio {v['pagina']} non e' "
                    "stato trovato alcun marcatore di sezione riconoscibile "
                    "dal bot e la pagina non e' vuota; per sicurezza non e' "
                    "stata modificata automaticamente. Se l'archivio e' "
                    "stato creato manualmente o con una versione precedente "
                    "del bot, e' necessario un intervento manuale."
                )
                print("  Struttura archivio non riconoscibile dopo ricarico, salvataggio annullato.")
                return
            if n_new == 0 and n_removed == 0:
                print("  Dopo il ricalcolo non ci sono piu' voci nuove ne' da rimuovere, skip.")
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



if __name__ == "__main__":
    main()