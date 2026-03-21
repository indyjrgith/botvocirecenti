#!/usr/bin/env python3
"""
PuliziaCache.py - Script di pulizia cache VociRecenti
Versione PC-2.0

Changelog:
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
3. Rimuove voci cancellate/non esistenti
4. Rimuove voci con eta' effettiva > MAX_AGE_DAYS giorni fa
   (usa move_timestamp se presente, altrimenti timestamp di creazione)
"""

import pywikibot
import pywikibot.config as config
import re
import os
from datetime import datetime, timedelta

# ========================================
# CONFIGURAZIONE
# ========================================
VERSION = 'PC-2.0'
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
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pulizia_cache.log')
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



def main():
    global _log_file
    _log_file = open(LOG_FILE, 'a', encoding='utf-8')
    start_time = datetime.now()
    log(f"\n{'=' * 60}")
    log(f"PULIZIA CACHE VOCI RECENTI - {VERSION}")
    log(f"Avvio: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    log('=' * 60)

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
    print("FASE 3: RIMOZIONE VOCI CANCELLATE")
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
    print("SALVATAGGIO CACHE PULITA")
    print("=" * 60)
    save_cache(cached_pages, cache_files)

    print("\n" + "=" * 60)
    print("COMPLETATO!")
    print("=" * 60)

    end_time = datetime.now()
    log_only(f"\nFine: {end_time.strftime('%Y-%m-%d %H:%M:%S')} "
             f"(durata: {(end_time - start_time).seconds}s)")
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


def check_pages_batch(pages):
    """
    Verifica via API batch (50 titoli/chiamata, senza seguire redirect)
    quali voci sono cancellate, redirect o fuori NS0.
    Restituisce un dict titolo -> motivo per le voci da rimuovere.
    """
    BATCH = 50
    titles = [p['titolo'] for p in pages]
    to_remove = {}
    n = len(titles)

    print(f"  Verifica batch {n} voci ({BATCH} titoli/chiamata)...")

    for start in range(0, n, BATCH):
        batch = titles[start:start + BATCH]
        try:
            query = SITE.simple_request(
                action='query',
                prop='info',
                titles='|'.join(batch),
                inprop=''
                # NB: redirects=True NON viene passato: cosi' MediaWiki restituisce
                # le info sulla pagina stessa, incluso il flag 'redirect' se e' un redirect.
            )
            result = query.submit()
            query_data = result.get('query', {})
            pages_info = query_data.get('pages', {})

            # Mappa normalizzazioni (maiuscole/minuscole ecc.)
            normalized = {n['from']: n['to'] for n in query_data.get('normalized', [])}
            # Mappa inversa: da titolo normalizzato a titolo originale
            inv_norm = {v: k for k, v in normalized.items()}

            for page_id, page_info in pages_info.items():
                title_result = page_info.get('title', '')
                orig_title = inv_norm.get(title_result, title_result)

                if page_id == '-1' or 'missing' in page_info:
                    to_remove[orig_title] = 'cancellata'
                elif 'redirect' in page_info:
                    to_remove[orig_title] = 'redirect'
                elif page_info.get('ns', 0) != 0:
                    to_remove[orig_title] = f"NS{page_info.get('ns', '?')}"

        except Exception as e:
            print(f"  WARNING batch [{start//BATCH + 1}]: {e}")

        done = min(start + BATCH, n)
        if done % 500 == 0 or done == n:
            print(f"  [{done}/{n}] Verifica batch...")

    return to_remove


def remove_deleted_pages(pages):
    """
    Rimuove voci cancellate, redirect o fuori NS0 tramite query API batch.
    Per le voci sopravvissute aggiorna i metadati (categorie, template, preview)
    solo se cambiati, con chiamate singole.
    """
    print("Verifica esistenza e aggiornamento metadati...")

    # FASE 1: verifica batch
    to_remove = check_pages_batch(pages)
    removed = len(to_remove)
    for title, reason in to_remove.items():
        log_only(f"  RIMOSSA ({reason}): {title}")

    # FASE 2: aggiornamento metadati per le voci sopravvissute
    surviving = [p for p in pages if p['titolo'] not in to_remove]
    updated = 0
    valid_pages = []
    total = len(surviving)

    print(f"  Aggiornamento metadati {total} voci sopravvissute...")

    for i, page in enumerate(surviving):
        if (i + 1) % 50 == 0:
            print(f"  Aggiornate: {i+1}/{total}, modificate: {updated}")

        title = page['titolo']

        try:
            page_obj = pywikibot.Page(SITE, title, ns=0)

            # Rileggi metadati
            try:
                new_cats = [cat.title(with_ns=False) for cat in page_obj.categories()]
            except Exception:
                new_cats = page.get('categorie', [])

            try:
                wikitext = page_obj.text
                new_templates = parse_templates_from_wikitext(wikitext)
                new_preview = wikitext[:100].replace('\n', ' ').strip() if wikitext else ''
            except Exception:
                new_templates = page.get('templates', [])
                new_preview = page.get('preview', '')

            # Confronta con i dati in cache
            old_cats = page.get('categorie', [])
            old_templates = page.get('templates', [])

            cats_changed = set(new_cats) != set(old_cats)
            old_tmpl_set = {(t.get('nome',''), tuple(t.get('params',[]))) for t in old_templates}
            new_tmpl_set = {(t.get('nome',''), tuple(t.get('params',[]))) for t in new_templates}
            tmpls_changed = old_tmpl_set != new_tmpl_set

            if cats_changed or tmpls_changed:
                page = dict(page)
                page['categorie'] = new_cats
                page['templates'] = new_templates
                page['preview'] = new_preview
                updated += 1
                changes = []
                if cats_changed:
                    changes.append('categorie')
                if tmpls_changed:
                    changes.append('template')
                msg = f"  AGGIORNATA ({', '.join(changes)}): {title}"
                log_only(msg)
                if tmpls_changed:
                    removed_t = old_tmpl_set - new_tmpl_set
                    added_t   = new_tmpl_set - old_tmpl_set
                    for nome, params in sorted(removed_t):
                        log_only(f"    TMPL RIMOSSO:   {nome}  params={list(params)}")
                    for nome, params in sorted(added_t):
                        log_only(f"    TMPL AGGIUNTO:  {nome}  params={list(params)}")

            valid_pages.append(page)

        except Exception as e:
            removed += 1
            log_only(f"  RIMOSSA (errore): {title} - {e}")
            continue

    print(f"\nRisultato: {removed} voci rimosse, {updated} voci aggiornate")
    return valid_pages, removed


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
        page.save(summary="Bot: Pulizia cache - Rimozione duplicati/errori/vecchie", minor=False)
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
                page.save(summary="Bot: Pulizia cache - File obsoleto", minor=True)
                print(f"  OK Svuotato")
            else:
                break
        except Exception as e:
            print(f"  ERRORE svuotamento {page_name}: {e}")
            break


if __name__ == '__main__':
    main()
