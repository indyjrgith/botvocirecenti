#!/usr/bin/env python3
"""
PuliziaCache.py - Script di pulizia cache VociRecenti
Versione PC-2.9

Changelog:
- PC-2.9: TRE FIX in _fetch_categories_for_titles / check_and_update_pages_batch:
          FIX-A: rimosso clshow=!hidden da _fetch_categories_for_titles: le categorie
          delle pagine di disambiguazione (e altre categorie di servizio) sono nascoste
          e venivano silenziosamente scartate -> disambigue sempre con categorie=[] in
          cache indipendentemente dal numero di run eseguiti.
          FIX-B: lookup titolo in cats_by_title reso robusto con fallback normalizzato:
          se orig_title non e' in cats_by_title si prova con il titolo normalizzato da
          all_normalized (passata info). Evita che voci con normalizzazione Wikipedia
          (maiuscole, underscore) restino con categorie vuote nonostante l'API le abbia
          restituite correttamente.
          FIX-C: aggiornamento forzato se old_cats==[] e new_cats!=[]: le voci inserite
          in cache prima di avere categorie non venivano mai aggiornate: il confronto
          set([])==set([]) era True anche se l'API non aveva trovato il titolo (FIX-B
          non ancora applicato), mascherando il mancato aggiornamento. Ora cats_changed
          e' True anche quando old_cats era vuota ma new_cats e' non vuota.
- PC-2.8: Correzione one-shot timestamp corrotti in cache.
          _fetch_wikitext_for_titles ora esegue due chiamate batch per titolo:
          (A) rvdir=newer&rvlimit=1 per il timestamp reale di prima creazione,
          (B) rvdir=older (default) per il wikitext corrente.
          Restituisce dict {titolo: {'wikitext': ..., 'creation_ts': ...}}.
          Aggiunta ts_utc_to_it() per convertire i timestamp ISO 8601 dall'API.
          check_and_update_pages_batch: sovrascrive sempre il campo timestamp
          con il valore reale dall'API, loggando ogni correzione con i valori
          vecchio e nuovo. Il contatore 'timestamp corretti' e' incluso nel
          riepilogo di FASE 3. Questa correzione avviene ad ogni run di PC
          (nessun overhead extra: le chiamate API erano gia' presenti per il
          wikitext), ed e' idempotente: una volta che i timestamp sono corretti
          non produce piu' aggiornamenti.
- PC-2.7: FIX flag tz in format_lua_data: scritto '-- tz=IT' invece di
          '-- tz=IT-v8.42', causando la migrazione one-shot UTC->IT ad ogni
          run successivo del bot (doppia/tripla conversione timestamp).
          Effetti: timestamp delle voci in cache progressivamente in avanti
          nel tempo, voci nuove scalzate dal sort/MAX_PAGES.
          Fix: flag corretto a '-- tz=IT-v8.42'.
          Aggiunta funzione now_it() (con _last_sunday e _it_offset_for_utc)
          per scrivere il campo u= e l'header Aggiornato: in ora italiana
          invece di UTC (import calendar aggiunto).
- PC-2.6: FIX _fetch_wikitext_for_titles: corretto accesso al wikitext dalla
          risposta API rvslots=main: il campo e' "slots.main.*" non "slots.main.content".
          Senza questo fix il wikitext era sempre vuoto -> templates=[] e preview=""
          per tutte le voci.
- PC-2.5: FIX _fetch_categories_for_titles: aggiunto loop su batch da BATCH_SIZE
          titoli (MediaWiki accetta max 50 titoli/chiamata). Senza questo fix
          su 2895 voci venivano recuperate le categorie solo dei primi 50 titoli,
          lasciando cats=[] per tutte le altre -> nessun aggiornamento reale.
- PC-2.4: Aggiunto DRY_RUN mode (DRY_RUN = True): esegue tutte le fasi e
          tutte le chiamate API ma non salva nulla su Wikipedia. Al termine
          stampa un report diagnostico con dimensione stimata, campione delle
          prime voci, e statistiche aggregate (media cat/tmpl/voce, % preview
          vuote) per rilevare corruzioni prima che avvengano.
- PC-2.3: remove_deleted_pages ottimizzata: FASE 1 e FASE 2 collassate in un
          unico ciclo batch tramite la nuova check_and_update_pages_batch.
          Ogni batch da 50 titoli usa prop=info|categories|revisions per ottenere
          in una sola chiamata API: flag missing/redirect/NS, categorie complete
          (cllimit=500, con gestione paginazione clcontinue), wikitext per
          template e preview. Riduzione chiamate da ~3000 singole a ~60 batch.
          Rimossa la vecchia check_pages_batch (sostituita).
- PC-2.2: format_lua_data: aggiunto flag '-- tz=IT' nell'intestazione dei file
          Lua generati e aggiornata dicitura da 'UTC' a 'ora italiana', in linea
          con il bot v8.38 che scrive i timestamp in ora italiana (CET/CEST).
          Senza questo fix la PuliziaCache avrebbe riscritto i file senza il flag,
          riattivando inutilmente la migrazione one-shot al run successivo del bot.
- PC-2.1: Versione aggiunta nell'oggetto delle modifiche su Wikipedia:
          "Bot: Pulizia cache - Rimozione duplicati/errori/vecchie (PC-2.1)"
          "Bot: Pulizia cache - File obsoleto (PC-2.1)"
- PC-2.0: remove_deleted_pages ottimizzata con query API batch (50 titoli/chiamata,
          senza redirects=True). Fase 1: verifica batch cancellate/redirect/NS errato.
          Fase 2: aggiornamento metadati solo per le voci sopravvissute. Drastica
          riduzione chiamate API: da ~3000 singole a ~60 batch + singole per modificate.
- PC-1.9: AGGIORNATA e RIMOSSA vanno solo nel log (non a schermo).
          Contatore progresso mostra anche rimosse: 'Verificate X/TOT, rimosse Y, aggiornate Z'.
- PC-1.8: FIX parse_templates_from_wikitext: aggiunta gestione parametri
          posizionali (es. {{Portale|musica}}), allineata alla versione del bot.
          Senza questo fix i params posizionali erano sempre persi -> Portale params=[]
- PC-1.7: Aggiunto logging su file pulizia_cache.log (append). Logga inizio/fine
          esecuzione, ogni RIMOSSA, ogni AGGIORNATA con template prima e dopo
          (nome+params) per diagnosticare perdita parametri Portale.
- PC-1.6: FIX parse_lua_to_json: ripristina parsing veloce per righe per il
          nuovo formato (d={}), sostituendo startswith('{[[') con startswith('{[')
          per coprire anche titoli con long string di livello 1 ([=[ ]=]).
          Mantiene parsing a brace bilanciate solo per il vecchio formato (voci={}).
- PC-1.5: FIX parse_lua_to_json: sostituisce il parsing per righe con parsing
          a brace bilanciate (soluzione eccessiva, corretta in PC-1.6).
- PC-1.4: parse_single_voce: legge il 6° campo opzionale move_timestamp.
          remove_old_pages (FASE 4): usa move_timestamp se presente per il
          controllo eta', preservando voci vecchie ma spostate di recente in NS0.
- PC-1.3: FASE 5: riparazione Portale vuoti nei template.
- PC-1.2: Fix corruzione parametri template Portale in FASE 5.
- PC-1.1: Prima versione stabile.

Funzioni:
1. Rimuove duplicati
2. Rimuove voci non in NS0
3. Rimuove voci cancellate/non esistenti; aggiorna metadati modificati
4. Rimuove voci con eta' effettiva > MAX_AGE_DAYS giorni fa
   (usa move_timestamp se presente, altrimenti timestamp di creazione)
"""

import pywikibot
import pywikibot.config as config
import re
import os
import calendar as _calendar
from datetime import datetime, timedelta


# ========================================
# FUSO ORARIO ITALIANO - stesso algoritmo del bot (senza dipendenze esterne)
# ========================================

def _last_sunday(year, month):
    """Restituisce il giorno (int) dell'ultima domenica del mese dato."""
    last_day = _calendar.monthrange(year, month)[1]
    last_weekday = datetime(year, month, last_day).weekday()  # 0=lun, 6=dom
    return last_day - (last_weekday - 6) % 7


def _it_offset_for_utc(dt_utc_naive):
    """Restituisce l'offset italiano in ore (+1 CET, +2 CEST) per un datetime UTC naive."""
    y = dt_utc_naive.year
    dst_start = datetime(y, 3,  _last_sunday(y, 3),  1, 0, 0)
    dst_end   = datetime(y, 10, _last_sunday(y, 10), 1, 0, 0)
    return 2 if dst_start <= dt_utc_naive < dst_end else 1


def now_it():
    """Restituisce il datetime corrente in ora italiana (CET/CEST) come oggetto naive."""
    from datetime import timezone as _tz
    utc_now = datetime.now(_tz.utc).replace(tzinfo=None)
    return utc_now + timedelta(hours=_it_offset_for_utc(utc_now))


def ts_utc_to_it(ts_str):
    """
    Converte una stringa timestamp UTC in formato ISO 8601 (es. '2026-04-14T01:35:00Z')
    oppure YYYYMMDDHHMMSS nella corrispondente stringa YYYYMMDDHHMMSS in ora italiana.
    """
    ts_str = ts_str.strip()
    # Formato ISO 8601: 2026-04-14T01:35:00Z
    if 'T' in ts_str:
        ts_str_clean = ts_str.replace('Z', '').replace('-', '').replace('T', '').replace(':', '')
    else:
        ts_str_clean = ts_str
    try:
        dt = datetime.strptime(ts_str_clean, '%Y%m%d%H%M%S')
        return (dt + timedelta(hours=_it_offset_for_utc(dt))).strftime('%Y%m%d%H%M%S')
    except Exception:
        return ts_str_clean


# ========================================
# CONFIGURAZIONE
# ========================================
VERSION = 'PC-2.9'
MAX_PAGES = 3000
MAX_CHARS_PER_FILE = 1500000
DATA_PAGE_PREFIX = 'Modulo:VociRecenti/Dati'
NAMESPACE = 0
TIMEOUT = 300
MAX_AGE_DAYS = 30                          # Rimuovi voci create piu' di N giorni fa
REMOVE_DELETED = True
REMOVE_REDIRECTS = True
REMOVE_WRONG_NAMESPACE = True
REMOVE_TOO_OLD = True                      # Rimuovi voci troppo vecchie
BATCH_SIZE = 50                            # Titoli per chiamata API batch
DATA_DIR = '/data/project/botvocirecenti/botvocirecenti'
LOG_FILE = os.path.join(DATA_DIR, 'pulizia_cache.log')
DRY_RUN = False   # Se True: esegue tutto ma NON salva su Wikipedia.
                 # Impostare False solo dopo aver verificato il report diagnostico.
# ========================================


SITE = pywikibot.Site('it', 'wikipedia')
_LUA_FILE_OVERHEAD = 500   # margine header + struttura file

_log_file = None  # handle globale al file di log


def log(msg):
    """Scrive msg sia a schermo che nel file di log."""
    print(msg)
    if _log_file:
        _log_file.write(msg + '\n')
        _log_file.flush()


def log_only(msg):
    """Scrive msg solo nel file di log (dettagli verbose non a schermo)."""
    if _log_file:
        _log_file.write(msg + '\n')
        _log_file.flush()



def dry_run_report(pages):
    """
    Stampa un report diagnostico completo senza salvare nulla.
    Rileva corruzioni (campi vuoti, dimensione anomala) prima che avvengano.
    """
    n = len(pages)
    if n == 0:
        print("  Nessuna voce da analizzare.")
        return

    # ---- Statistiche aggregate ----
    total_cats = sum(len(p.get('categorie', [])) for p in pages)
    total_tmpls = sum(len(p.get('templates', [])) for p in pages)
    total_preview_len = sum(len(p.get('preview', '')) for p in pages)
    voci_no_cats = sum(1 for p in pages if not p.get('categorie'))
    voci_no_tmpls = sum(1 for p in pages if not p.get('templates'))
    voci_no_preview = sum(1 for p in pages if not p.get('preview', '').strip())

    avg_cats = total_cats / n
    avg_tmpls = total_tmpls / n
    avg_preview = total_preview_len / n

    # ---- Dimensione stimata ----
    file_groups = split_pages_into_files(pages)
    total_size_bytes = 0
    for group in file_groups:
        for p in group:
            try:
                total_size_bytes += len(format_lua_row(p).encode('utf-8'))
            except Exception:
                pass
    size_mb = total_size_bytes / (1024 * 1024)

    # ---- Soglie di allarme ----
    # Una cache sana su it.wiki ha mediamente almeno 2-3 categorie e 1 template per voce
    WARN_AVG_CATS   = 1.0
    WARN_AVG_TMPLS  = 0.5
    WARN_NO_CATS_PCT = 50.0   # % massima voci senza categorie
    WARN_NO_TMPLS_PCT = 70.0  # % massima voci senza template (molte voci stub ne hanno pochi)
    WARN_NO_PREV_PCT = 80.0   # % massima voci senza preview
    WARN_SIZE_MB    = 0.5     # soglia minima dimensione stimata (MB)

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

    # ---- Campione prime 10 voci ----
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

    # ---- Campione 10 voci peggiori (meno dati) ----
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

    # ---- Allarmi ----
    if alerts:
        print(f"\n{'!' * 60}")
        print("ATTENZIONE - RILEVATI PROBLEMI:")
        for a in alerts:
            print(a)
        print("NON eseguire con DRY_RUN=False finche' i problemi non sono risolti.")
        print(f"{'!' * 60}")
    else:
        print(f"\nOK - Nessun allarme rilevato. I dati sembrano integri.")
        print(f"Per salvare su Wikipedia: impostare DRY_RUN = False e rieseguire.")


def main():
    global _log_file
    _log_file = open(LOG_FILE, 'a', encoding='utf-8')
    start_time = datetime.now()
    dry_tag = " [DRY-RUN]" if DRY_RUN else ""
    log(f"\n{'=' * 60}")
    log(f"PULIZIA CACHE VOCI RECENTI - {VERSION}{dry_tag}")
    log(f"Avvio: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    log('=' * 60)

    if DRY_RUN:
        print("*** MODALITA' DRY-RUN: nessuna modifica verra' salvata su Wikipedia ***\n")

    print("\nLogin come BotVociRecenti...")
    if not SITE.logged_in():
        SITE.login()
    print(f"OK - Login: {SITE.username()}\n")

    print("=" * 60)
    print("CARICAMENTO CACHE")
    print("=" * 60)
    cached_pages, cache_files = load_all_cache_files()
    print(f"\nTotale voci caricate: {len(cached_pages)}\n")

    original_count = len(cached_pages)

    cutoff_date = datetime.now() - timedelta(days=MAX_AGE_DAYS)
    print(f"Limite data creazione: {cutoff_date.strftime('%d/%m/%Y')} ({MAX_AGE_DAYS} giorni fa)\n")

    print("=" * 60)
    print("FASE 1: RIMOZIONE DUPLICATI")
    print("=" * 60)
    cached_pages, removed_duplicates = remove_duplicates(cached_pages)

    print("\n" + "=" * 60)
    print("FASE 2: RIMOZIONE VOCI NON-NS0")
    print("=" * 60)
    cached_pages, removed_wrong_ns = remove_wrong_namespace(cached_pages)

    print("\n" + "=" * 60)
    print("FASE 3: RIMOZIONE VOCI CANCELLATE / AGGIORNAMENTO METADATI")
    print("=" * 60)
    cached_pages, removed_deleted = remove_deleted_pages(cached_pages)

    print("\n" + "=" * 60)
    print("FASE 4: RIMOZIONE VOCI TROPPO VECCHIE")
    print("=" * 60)
    cached_pages, removed_old = remove_old_pages(cached_pages, cutoff_date)

    total_removed = removed_duplicates + removed_wrong_ns + removed_deleted + removed_old

    print("\n" + "=" * 60)
    print("RIEPILOGO")
    print("=" * 60)
    print(f"Voci originali: {original_count}")
    print(f"  Duplicati rimossi:   {removed_duplicates}")
    print(f"  Wrong NS rimossi:    {removed_wrong_ns}")
    print(f"  Cancellate rimosse:  {removed_deleted}")
    print(f"  Troppo vecchie:      {removed_old}")
    print(f"  Totale rimosse:      {total_removed}")
    print(f"Voci finali: {len(cached_pages)}")

    if total_removed == 0:
        print("\nNessuna rimozione necessaria.")
        print("(eventuali aggiornamenti metadati sono stati salvati sopra)")

    print("\n" + "=" * 60)
    if DRY_RUN:
        print("REPORT DIAGNOSTICO [DRY-RUN]")
        print("=" * 60)
        dry_run_report(cached_pages)
        print("\n*** DRY-RUN completato: nessun file e' stato modificato su Wikipedia ***")
    else:
        print("SALVATAGGIO CACHE PULITA")
        print("=" * 60)
        save_cache(cached_pages, cache_files)

    print("\n" + "=" * 60)
    print("COMPLETATO!")
    print("=" * 60)

    end_time = datetime.now()
    log_only(f"\nFine: {end_time.strftime('%Y-%m-%d %H:%M:%S')} "
             f"(durata: {(end_time - start_time).seconds}s){dry_tag}")
    log_only(f"Riepilogo: originali={original_count}, rimosse={total_removed}, "
             f"finali={len(cached_pages)}")
    log_only('=' * 60)
    _log_file.close()
    _log_file = None


# ========================================
# PARSER LUA ROBUSTO
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
    - Nuovo formato (d={...}): parsing veloce per righe (startswith '{[')
    - Vecchio formato (voci={...}): parsing bilanciato delle graffe (lento ma raro)
    """
    voci = []

    m_new = re.search(r'(?<![a-zA-Z_])d\s*=\s*\{', lua_content)
    m_old = re.search(r'voci\s*=\s*\{', lua_content)

    if m_new:
        # NUOVO FORMATO: ogni voce e' su una riga che inizia con "{[["
        # (livello 0) o "{[=[" (livello 1, titoli con "]]" nel nome).
        # Parsing veloce: riga per riga invece di iterare carattere per carattere.
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

        # Campo 6: move_timestamp (opzionale, presente solo per voci da sandbox/bozze)
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



def parse_templates_from_wikitext(text):
    """
    Estrae template di primo livello dal wikitesto.
    Per ogni template restituisce nome e lista dei nomi di parametri valorizzati.
    Ignora: template annidati, parser functions (#if, #switch, ecc.),
    commenti HTML <!-- -->.
    """
    if not text:
        return []

    # Rimuovi commenti HTML
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)

    templates = []
    i = 0
    while i < len(text) - 1:
        if text[i] == '{' and text[i+1] == '{':
            # Trova la chiusura bilanciata
            level = 0
            j = i
            while j < len(text) - 1:
                if text[j] == '{' and text[j+1] == '{':
                    level += 1
                    j += 2
                elif text[j] == '}' and text[j+1] == '}':
                    level -= 1
                    j += 2
                    if level == 0:
                        break
                else:
                    j += 1

            inner = text[i+2:j-2].strip()

            # Ignora parser functions
            if not inner or inner.startswith('#') or inner.startswith('PAGENAME') or ':' in inner.split('|')[0]:
                i = j
                continue

            parts = inner.split('|')
            name = parts[0].strip()
            if not name:
                i = j
                continue

            # Ripulisci graffe residue da nome
            name = name.replace('{', '').replace('}', '')

            params = []
            for part in parts[1:]:
                part = part.strip()
                if '=' in part:
                    pname, _, pval = part.partition('=')
                    pname = pname.strip().replace('{','').replace('}','').strip()
                    pval = pval.strip()
                    if pname and pval:
                        # Parametro named valorizzato: salva il nome
                        params.append(pname)
                else:
                    pval = part.replace('{','').replace('}','').strip()
                    # Parametro posizionale: salva il valore
                    # (no parentesi quadre che rompono lua_str)
                    if pval and '[' not in pval and ']' not in pval:
                        params.append(pval[:100])

            templates.append({'nome': name, 'params': params})
            i = j
        else:
            i += 1

    return templates

def load_all_cache_files():
    """Carica tutti i file cache"""
    cache_files = []
    all_pages = []

    for i in range(1, 50):
        page_name = f"{DATA_PAGE_PREFIX}{i}"
        try:
            page = pywikibot.Page(SITE, page_name)
            if page.exists():
                cache_files.append(page_name)
                print(f"  Lettura {page_name}...")
                lua_content = page.text
                pages = parse_lua_to_json(lua_content)
                all_pages.extend(pages)
                print(f"    {len(pages)} voci")
            else:
                break
        except Exception as e:
            print(f"    ERRORE lettura {page_name}: {e}")
            break

    print(f"\nCaricati {len(cache_files)} file")
    return all_pages, cache_files


# ========================================
# FASI DI PULIZIA
# ========================================

def remove_duplicates(pages):
    """Rimuove voci duplicate mantenendo la piu' recente"""
    print("Ricerca duplicati...")

    by_title = {}
    for page in pages:
        title = page['titolo']
        if title not in by_title:
            by_title[title] = []
        by_title[title].append(page)

    unique_pages = []
    duplicates_removed = 0

    for title, versions in by_title.items():
        if len(versions) > 1:
            versions.sort(key=lambda x: x['timestamp'], reverse=True)
            unique_pages.append(versions[0])
            duplicates_removed += len(versions) - 1
            print(f"  Duplicato: {title} ({len(versions)} copie -> 1 mantenuta)")
        else:
            unique_pages.append(versions[0])

    print(f"\nRisultato: {duplicates_removed} duplicati rimossi")
    return unique_pages, duplicates_removed


def remove_wrong_namespace(pages):
    """Rimuove voci non in NS0"""
    print("Verifica namespace...")

    valid_pages = []
    removed = 0

    for i, page in enumerate(pages):
        if (i + 1) % 100 == 0:
            print(f"  Verificate: {i+1}/{len(pages)}")

        title = page['titolo']

        if ':' in title:
            try:
                page_obj = pywikibot.Page(SITE, title)
                ns = page_obj.namespace()
                if ns != 0:
                    removed += 1
                    print(f"  RIMOSSA (NS{ns}): {title}")
                    continue
            except Exception as e:
                removed += 1
                print(f"  RIMOSSA (errore ns): {title} - {e}")
                continue

        valid_pages.append(page)

    print(f"\nRisultato: {removed} voci non-NS0 rimosse")
    return valid_pages, removed


def _fetch_categories_for_titles(titles):
    """
    Scarica le categorie complete per una lista di titoli tramite API batch.
    Itera su batch da BATCH_SIZE titoli (MediaWiki accetta max 50 titoli per
    chiamata). Per ogni batch gestisce la paginazione con clcontinue per pagine
    con >500 categorie (raro su it.wiki ma gestito correttamente).
    Restituisce un dict {titolo_originale: [lista categorie]}.
    """
    cats_by_title = {t: [] for t in titles}

    for batch_start in range(0, len(titles), BATCH_SIZE):
        batch = titles[batch_start:batch_start + BATCH_SIZE]
        norm_to_orig = {}

        params = {
            'action': 'query',
            'prop': 'categories',
            'titles': '|'.join(batch),
            'cllimit': '500',
            # NON usare clshow='!hidden': le categorie delle disambigue e di altri
            # template di servizio sono nascoste e verrebbero scartate -> voci
            # di disambiguazione risulterebbero sempre senza categorie in cache.
            'format': 'json',
        }

        while True:
            try:
                result = SITE.simple_request(**params).submit()
            except Exception as e:
                log_only(f"  WARNING _fetch_categories batch [{batch_start//BATCH_SIZE + 1}]: {e}")
                break

            query_data = result.get('query', {})

            # Costruisci mappa normalizzazioni al primo giro del batch
            if not norm_to_orig:
                for n in query_data.get('normalized', []):
                    norm_to_orig[n['to']] = n['from']

            pages_info = query_data.get('pages', {})
            for page_id, page_info in pages_info.items():
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

            # Paginazione clcontinue per questo batch
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


def _fetch_wikitext_for_titles(titles):
    """
    Scarica il wikitext e il timestamp di prima creazione per una lista di titoli
    tramite API batch. Usa due chiamate separate per batch:
      - rvdir=newer&rvlimit=1: prima revisione (timestamp creazione reale)
      - rvdir=older&rvlimit=1: ultima revisione (wikitext corrente)
    Usa batch piccoli (BATCH_SIZE_REV titoli) per evitare che MediaWiki
    tronchi silenziosamente le revisions su pagine grandi.
    Restituisce un dict {titolo_originale: {'wikitext': str, 'creation_ts': str}}
    dove creation_ts e' in formato YYYYMMDDHHMMSS ora italiana, oppure '' se non
    disponibile.
    """
    BATCH_SIZE_REV = 10  # batch piccolo: wikitext puo' essere molto grande
    result_by_title = {}

    # --- CHIAMATA A: timestamp di prima creazione (rvdir=newer, rvlimit=1) ---
    creation_ts_by_title = {}
    for start in range(0, len(titles), BATCH_SIZE_REV):
        batch = titles[start:start + BATCH_SIZE_REV]
        try:
            result = SITE.simple_request(
                action='query',
                prop='revisions',
                titles='|'.join(batch),
                rvprop='timestamp',
                rvdir='newer',
                rvlimit='1',
                format='json',
            ).submit()
        except Exception as e:
            log_only(f"  WARNING _fetch_creation_ts batch: {e}")
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
                    creation_ts_by_title[orig_title] = ts_utc_to_it(ts_utc) if ts_utc else ''
            except Exception:
                pass

    # --- CHIAMATA B: wikitext corrente (rvdir=older, rvlimit=1 = default) ---
    for start in range(0, len(titles), BATCH_SIZE_REV):
        batch = titles[start:start + BATCH_SIZE_REV]
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
            log_only(f"  WARNING _fetch_wikitext batch: {e}")
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
                    if slots:
                        wikitext = slots.get('main', {}).get('*', '')
                    else:
                        wikitext = revisions[0].get('*', '')
            except Exception:
                pass

            result_by_title[orig_title] = {
                'wikitext': wikitext,
                'creation_ts': creation_ts_by_title.get(orig_title, ''),
            }

    # Assicura che tutti i titoli abbiano una entry (anche se entrambe le chiamate falliscono)
    for t in titles:
        if t not in result_by_title:
            result_by_title[t] = {'wikitext': '', 'creation_ts': ''}

    return result_by_title


def check_and_update_pages_batch(pages):
    """
    Verifica e aggiorna i metadati di tutte le voci in cache tramite API batch.
    Tre passate separate per batch:
      1. prop=info (BATCH_SIZE=50): rilevamento missing/redirect/NS
      2. prop=categories (BATCH_SIZE=50, con paginazione): categorie visibili
      3. prop=revisions (BATCH_SIZE_REV=10): wikitext corrente + timestamp prima
         revisione (creazione reale). Batch piccolo necessario: MediaWiki tronca
         silenziosamente le revisions quando la risposta supera i limiti di dimensione.

    Per ogni voce sopravvissuta: sovrascrive sempre il timestamp con il valore
    reale dall'API (corregge timestamp corrotti da doppia migrazione UTC->IT).
    Confronta categorie e template; se cambiati aggiorna il record e logga.

    Restituisce (valid_pages, removed_count).
    """
    n = len(pages)
    to_remove = {}       # titolo -> motivo
    updated_records = {} # titolo -> record aggiornato

    print(f"  Verifica e aggiornamento batch {n} voci "
          f"(info:{BATCH_SIZE} titoli/chiamata, rev:10 titoli/chiamata)...")

    # ========================================================
    # PASSATA 1: prop=info — rilevamento rimozioni
    # ========================================================
    # Mappa normalizzazioni costruita durante la passata info
    all_normalized = {}   # titolo_originale -> titolo_normalizzato
    all_inv_norm = {}     # titolo_normalizzato -> titolo_originale
    survivor_titles = []  # titoli sopravvissuti in ordine

    for start in range(0, n, BATCH_SIZE):
        batch = pages[start:start + BATCH_SIZE]
        batch_titles = [p['titolo'] for p in batch]
        done = min(start + BATCH_SIZE, n)

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
            log_only(f"  WARNING batch info [{start//BATCH_SIZE + 1}]: {e}")
            # In caso di errore conserva tutte le voci del batch
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
                log_only(f"  RIMOSSA (cancellata): {orig_title}")
            elif 'redirect' in page_info:
                to_remove[orig_title] = 'redirect'
                log_only(f"  RIMOSSA (redirect): {orig_title}")
            elif page_info.get('ns', 0) != 0:
                to_remove[orig_title] = f"NS{page_info.get('ns', '?')}"
                log_only(f"  RIMOSSA (NS{page_info.get('ns','?')}): {orig_title}")
            else:
                survivor_titles.append(orig_title)

    print(f"  Sopravvissute: {len(survivor_titles)}, rimosse: {len(to_remove)}")

    # ========================================================
    # PASSATA 2: prop=categories — categorie per sopravvissuti
    # ========================================================
    print(f"  Recupero categorie per {len(survivor_titles)} voci...")
    cats_by_title = _fetch_categories_for_titles(survivor_titles)

    # ========================================================
    # PASSATA 3: prop=revisions — wikitext + timestamp creazione per sopravvissuti
    # ========================================================
    print(f"  Recupero wikitext e timestamp creazione per {len(survivor_titles)} voci (10 titoli/chiamata)...")
    rev_by_title = _fetch_wikitext_for_titles(survivor_titles)

    # ========================================================
    # CONFRONTO e aggiornamento record
    # ========================================================
    batch_by_title = {p['titolo']: p for p in pages}
    ts_fixed_count = 0

    for orig_title in survivor_titles:
        record = batch_by_title.get(orig_title)
        if record is None:
            # Prova con titolo normalizzato (raro)
            norm_title = all_normalized.get(orig_title, orig_title)
            record = batch_by_title.get(norm_title)
        if record is None:
            continue

        rev_data = rev_by_title.get(orig_title, {})
        wikitext = rev_data.get('wikitext', '')
        creation_ts = rev_data.get('creation_ts', '')
        # FIX-B: se orig_title non e' in cats_by_title (es. normalizzazione Wikipedia),
        # prova con il titolo normalizzato ricavato dalla passata info.
        if orig_title in cats_by_title:
            new_cats = cats_by_title[orig_title]
        else:
            norm_title = all_normalized.get(orig_title, orig_title)
            new_cats = cats_by_title.get(norm_title, [])
        new_templates = parse_templates_from_wikitext(wikitext)
        new_preview = wikitext[:100].replace('\n', ' ').strip() if wikitext else ''

        old_cats = record.get('categorie', [])
        old_templates = record.get('templates', [])

        # FIX-C: forza aggiornamento se old_cats era vuota e ora ci sono categorie.
        # Senza questo fix, una voce inserita in cache prima di avere categorie
        # non veniva mai aggiornata: set([])==set([]) anche quando l'API
        # non trovava il titolo (FIX-B non ancora applicato).
        cats_changed = set(new_cats) != set(old_cats) or (not old_cats and bool(new_cats))
        old_tmpl_set = {(t.get('nome', ''), tuple(t.get('params', [])))
                        for t in old_templates}
        new_tmpl_set = {(t.get('nome', ''), tuple(t.get('params', [])))
                        for t in new_templates}
        tmpls_changed = old_tmpl_set != new_tmpl_set

        # Controlla se il timestamp in cache differisce da quello reale (corregge
        # timestamp corrotti da doppia/tripla migrazione UTC->IT)
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
            log_only(f"  AGGIORNATA ({', '.join(changes)}): {orig_title}")
            if tmpls_changed:
                removed_t = old_tmpl_set - new_tmpl_set
                added_t   = new_tmpl_set - old_tmpl_set
                for nome, params in sorted(removed_t):
                    log_only(f"    TMPL RIMOSSO:   {nome}  params={list(params)}")
                for nome, params in sorted(added_t):
                    log_only(f"    TMPL AGGIUNTO:  {nome}  params={list(params)}")

    # ---- Costruzione lista finale ----
    removed_count = len(to_remove)
    valid_pages = []
    for page in pages:
        title = page['titolo']
        if title in to_remove:
            continue
        if title in updated_records:
            valid_pages.append(updated_records[title])
        else:
            valid_pages.append(page)

    print(f"\nRisultato: {removed_count} voci rimosse, {len(updated_records)} voci aggiornate"
          f" (di cui {ts_fixed_count} timestamp corretti)")
    return valid_pages, removed_count


def remove_deleted_pages(pages):
    """
    Rimuove voci cancellate, redirect o fuori NS0; aggiorna metadati modificati.
    Delega interamente a check_and_update_pages_batch che gestisce tutto in batch.
    """
    print(f"Verifica esistenza e aggiornamento metadati ({len(pages)} voci)...")
    return check_and_update_pages_batch(pages)


def remove_old_pages(pages, cutoff_date):
    """
    Rimuove voci con eta' effettiva precedente a cutoff_date.
    Usa move_timestamp se presente (voci da sandbox spostate di recente in NS0),
    altrimenti timestamp di creazione.
    Nessuna chiamata API: usa solo i dati gia' in cache.
    """
    print(f"Verifica eta' voci (limite: {cutoff_date.strftime('%d/%m/%Y')})...")

    valid_pages = []
    removed = 0

    for page in pages:
        title = page['titolo']
        # Usa move_timestamp se disponibile, altrimenti timestamp di creazione
        move_ts_str = page.get('move_timestamp', '')
        ref_str = move_ts_str if move_ts_str else page.get('timestamp', '')

        try:
            ref_date = datetime.strptime(ref_str, '%Y%m%d%H%M%S')
        except Exception:
            print(f"  WARNING (timestamp non valido, mantenuta): {title}")
            valid_pages.append(page)
            continue

        if ref_date < cutoff_date:
            removed += 1
            label = "spostata" if move_ts_str else "creata"
            print(f"  RIMOSSA ({label} {ref_date.strftime('%d/%m/%Y')}): {title}")
            continue

        valid_pages.append(page)

    print(f"\nRisultato: {removed} voci troppo vecchie rimosse")
    return valid_pages, removed


# ========================================
# SALVATAGGIO
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
    Usata da split_pages_into_files per misurare la dimensione reale in byte.
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
    return (
        f"    {{{lua_str(page['titolo'])},{lua_str(page['timestamp'])},"
        f"{cats_lua},{tmpls_lua},{preview}}}"
    )


def split_pages_into_files(pages):
    """Divide le voci in file misurando la dimensione Lua reale di ogni voce,
    garantendo che nessun file superi il limite Wikipedia di 2048 KB."""
    effective_limit = MAX_CHARS_PER_FILE - _LUA_FILE_OVERHEAD
    files = []
    current_file = []
    current_bytes = 0

    for page in pages:
        try:
            row = format_lua_row(page)
        except Exception as e:
            print(f"  WARNING: Skip voce {page.get('titolo', 'N/A')}: {e}")
            continue

        row_bytes = len(row.encode('utf-8'))

        if current_bytes + row_bytes > effective_limit and current_file:
            files.append(current_file)
            print(f"  File {len(files)}: {len(current_file)} voci, ~{current_bytes/1024/1024:.2f} MB")
            current_file = []
            current_bytes = 0

        current_file.append(page)
        current_bytes += row_bytes

    if current_file:
        files.append(current_file)
        print(f"  File {len(files)}: {len(current_file)} voci, ~{current_bytes/1024/1024:.2f} MB")

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


def format_lua_data(pages_data, part_number, total_parts):
    """
    Formatta dati in Lua con formato compatto senza keyword ripetute per voce.
    Schema array posizionale:
      {titolo, timestamp, {categorie}, {{tmpl_nome,{params}}, ...}, preview}
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
            # Categorie
            cats = page.get('categorie', [])
            cats_parts = ",".join(lua_str(c) for c in cats)
            cats_lua = "{" + cats_parts + "}"

            # Templates: {{nome,{p1,p2,...}}, ...}
            tmpl_list = []
            for t in page.get('templates', []):
                nome = lua_str(t.get('nome', ''))
                params = t.get('params', [])
                params_lua = "{" + ",".join(lua_str(p) for p in params) + "}"
                tmpl_list.append(f"{{{nome},{params_lua}}}")
            tmpls_lua = "{" + ",".join(tmpl_list) + "}"

            # Preview (già troncata a 100 car in download_page_data)
            preview = lua_str(page.get('preview', ''))

            sep = "," if i < len(pages_data) - 1 else ""
            lines.append(
                f"    {{{lua_str(page['titolo'])},{lua_str(page['timestamp'])},"
                f"{cats_lua},{tmpls_lua},{preview}}}{sep}"
            )
        except Exception as e:
            print(f"  WARNING: Skip voce {page.get('titolo', 'N/A')}: {e}")
            continue

    lines.append("  }")
    lines.append("}")
    return '\n'.join(lines)


def save_cache(pages, original_files):
    """Salva cache pulita negli stessi file"""
    file_groups = split_pages_into_files(pages)
    total_files = len(file_groups)

    print(f"File necessari: {total_files}")

    for i, pages_group in enumerate(file_groups, 1):
        page_name = f"{DATA_PAGE_PREFIX}{i}"
        print(f"\n[{i}/{total_files}] {page_name}")
        print(f"  Voci: {len(pages_group)}")

        lua_content = format_lua_data(pages_group, i, total_files)
        size_mb = len(lua_content) / (1024 * 1024)
        print(f"  Dimensione: {size_mb:.2f} MB")

        page = pywikibot.Page(SITE, page_name)
        page.text = lua_content
        page.save(summary=f"Bot: Pulizia cache - Rimozione duplicati/errori/vecchie ({VERSION})", minor=False)
        print(f"  OK Salvato")

    empty_lua = (
        "-- File cache obsoleto - Svuotato automaticamente\n"
        "return {u='(vuoto)',n=0,d={}}"
    )
    for i in range(total_files + 1, len(original_files) + 5):
        page_name = f"{DATA_PAGE_PREFIX}{i}"
        try:
            page = pywikibot.Page(SITE, page_name)
            if page.exists():
                print(f"\n  Svuotamento {page_name} (obsoleto)...")
                page.text = empty_lua
                page.save(summary=f"Bot: Pulizia cache - File obsoleto ({VERSION})", minor=True)
                print(f"  OK Svuotato")
            else:
                break
        except Exception as e:
            print(f"  ERRORE svuotamento {page_name}: {e}")
            break


if __name__ == '__main__':
    main()
