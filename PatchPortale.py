#!/usr/bin/env python3
"""
PatchPortale.py - Aggiorna direttamente nei file Dati Lua i record con
{{Portale}} senza parametri, leggendo il wikitesto reale da Wikipedia.

Invece di usare il meccanismo Aggiorna: del bot (1 API call ogni ~9s per voce),
questo script:
  1. Scansiona i file Dati cercando {[[Portale]],{}} (Portale senza params)
  2. Scarica il wikitesto di ogni voce interessata
  3. Estrae i parametri reali di {{Portale}} dal wikitesto
  4. Riscrive solo il blocco template Portale nel testo Lua grezzo
  5. Salva il file Dati aggiornato (una scrittura per file, non per voce)
  6. Rimuove le righe Aggiorna: corrispondenti da CacheMoved

Versione: PP-1.2
Changelog:
  PP-1.2: parser Lua riscritto seguendo VVCache (robusto per titoli con ]],
          long string di livello 1+, brace bilanciate che skippano longstring).
          find_voce_block_bounds non usa più regex sul titolo ma scansione
          sequenziale dei blocchi voce. Aggiunto logging su file patchportale.log.
  PP-1.1: validazione Lua prima del salvataggio, filtro '['/']' nei nomi
          parametri named.
"""

import re
import sys
import time
import datetime
import pywikibot
import pywikibot.config as config

# ========================================
# CONFIGURAZIONE
# ========================================
DATA_PAGE_PREFIX = 'Modulo:VociRecenti/Dati'
CACHE_MOVED_PAGE = 'Utente:BotVociRecenti/CacheMoved'
TIMEOUT          = 300
VERSION          = 'PP-1.2'
REQUEST_DELAY    = 0.5
CHUNK_SIZE       = 50
LOG_FILE         = 'patchportale.log'
# ========================================


SITE = pywikibot.Site('it', 'wikipedia')

# -----------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------

_log_fh = None

def log_open():
    global _log_fh
    _log_fh = open(LOG_FILE, 'a', encoding='utf-8')
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log(f'\n{"="*60}')
    log(f'PatchPortale {VERSION} — avvio {ts}')
    log(f'{"="*60}')

def log(msg):
    print(msg)
    if _log_fh:
        _log_fh.write(msg + '\n')
        _log_fh.flush()

def log_close():
    if _log_fh:
        _log_fh.close()

# -----------------------------------------------------------------------
# Primitivi parser Lua (da VVCache — robusti per long string di qualsiasi livello)
# -----------------------------------------------------------------------

def skip_lua_longstring(text, pos):
    """Salta un long string Lua che inizia a pos. Restituisce pos dopo la chiusura,
    o None se a pos non c'è un long string."""
    m = re.match(r'\[=*\[', text[pos:])
    if not m:
        return None
    open_delim  = m.group(0)
    eq_count    = open_delim.count('=')
    close_delim = ']' + '=' * eq_count + ']'
    close_pos   = text.find(close_delim, pos + len(open_delim))
    if close_pos == -1:
        return None
    return close_pos + len(close_delim)


def find_balanced_braces(text, start):
    """Trova la } che chiude la { a text[start]. Restituisce l'indice della },
    o None se non trovata. Skippa i long string per non contare { } dentro di essi."""
    level = 0
    i = start
    while i < len(text):
        next_pos = skip_lua_longstring(text, i)
        if next_pos is not None:
            i = next_pos
            continue
        if text[i] == '{':
            level += 1
        elif text[i] == '}':
            level -= 1
            if level == 0:
                return i
        i += 1
    return None


def extract_lua_longstring(text, pos):
    """Estrae il contenuto di un long string Lua a partire da pos.
    Restituisce (contenuto, pos_dopo) oppure (None, pos_originale)."""
    m = re.match(r'\[(?P<eq>=*)\[', text[pos:])
    if not m:
        return None, pos
    eq    = m.group('eq')
    close = f']{eq}]'
    start = pos + len(m.group(0))
    end   = text.find(close, start)
    if end == -1:
        return None, pos
    return text[start:end], end + len(close)


def skip_lua_value(text, pos):
    """Salta un valore Lua (long string o blocco {…}) a partire da pos,
    skippando prima gli spazi. Restituisce la posizione dopo il valore,
    o None se fallisce."""
    while pos < len(text) and text[pos] in ' \t\n\r':
        pos += 1
    if pos >= len(text):
        return None
    if text[pos] == '[':
        result = skip_lua_longstring(text, pos)
        return result  # None se malformato
    if text[pos] == '{':
        end = find_balanced_braces(text, pos)
        return end + 1 if end is not None else None
    return None


def skip_comma(text, pos):
    """Salta spazi/newline e un'eventuale virgola."""
    while pos < len(text) and text[pos] in ' \t\n\r':
        pos += 1
    if pos < len(text) and text[pos] == ',':
        pos += 1
    return pos

# -----------------------------------------------------------------------
# lua_str e serialize_templates (identiche al bot)
# -----------------------------------------------------------------------

def lua_str(s):
    if not s:
        return '[[]]'
    s = str(s)
    level = 0
    while True:
        d = '=' * level
        if ('[' + d + '[') not in s and (']' + d + ']') not in s:
            break
        level += 1
    d = '=' * level
    return f'[{d}[{s}]{d}]'


def serialize_templates(templates):
    tmpl_list = []
    for t in templates:
        nome       = lua_str(t.get('nome', ''))
        params_lua = '{' + ','.join(lua_str(p) for p in t.get('params', [])) + '}'
        tmpl_list.append(f'{{{nome},{params_lua}}}')
    return '{' + ','.join(tmpl_list) + '}'

# -----------------------------------------------------------------------
# Validazione Lua
# -----------------------------------------------------------------------

def validate_lua(text):
    """Verifica long string bilanciati e assenza di nesting invalido.
    Restituisce (None, None) se OK, (pos, msg) se errore."""
    pos = 0
    for m in re.finditer(r'\[(?P<eq>=*)\[', text):
        if m.start() < pos:
            continue
        eq    = m.group('eq')
        close = ']' + eq + ']'
        start = m.end()
        end   = text.find(close, start)
        if end == -1:
            return m.start(), f'Long string [{eq}[...] non chiuso'
        content    = text[start:end]
        inner_open = '[' + eq + '['
        if inner_open in content:
            return m.start(), f'Nesting [{eq}[...{inner_open}...] non permesso'
        pos = end + len(close)
    return None, None

# -----------------------------------------------------------------------
# Parser wikitesto (identico al bot)
# -----------------------------------------------------------------------

def parse_templates_from_wikitext(text):
    templates = []
    i = 0
    n = len(text)
    while i < n - 1:
        if text[i] == '{' and text[i+1] == '{':
            depth = 1
            j = i + 2
            while j < n - 1 and depth > 0:
                if text[j] == '{' and text[j+1] == '{':
                    depth += 1; j += 2
                elif text[j] == '}' and text[j+1] == '}':
                    depth -= 1
                    if depth == 0:
                        break
                    j += 2
                else:
                    j += 1
            if depth == 0:
                inner    = text[i+2:j]
                parts    = inner.split('|')
                raw_name = parts[0].strip()
                if raw_name and not raw_name.startswith('#') and not raw_name.startswith(':'):
                    name   = raw_name.replace('_', ' ').strip()
                    params = []
                    for part in parts[1:]:
                        if '=' in part:
                            pname, _, pval = part.partition('=')
                            pname = pname.strip().replace('{','').replace('}','').strip()
                            pval  = pval.strip()
                            # Filtra '[' e ']' nel nome parametro (evita nesting Lua invalido)
                            if pname and pval and '[' not in pname and ']' not in pname:
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

# -----------------------------------------------------------------------
# Scansione file Lua: trova titoli con Portale vuoto
# -----------------------------------------------------------------------

# Pattern per trovare {[[Portale]],{}} o {[=[Portale]=],{}}
PORTALE_EMPTY_RE = re.compile(
    r'\{\[=*\[Portale\]=*\]\s*,\s*\{\s*\}',
    re.IGNORECASE
)

# Pattern per trovare l'apertura di un blocco voce: newline+spazi+{[=*[
# (NON usa .+? per il titolo, perché con ]=] il non-greedy matcherebbe male)
VOCE_OPEN_RE = re.compile(r'\n[ \t]*\{(\[=*\[)')


def find_titles_with_empty_portale(lua_text):
    """
    Restituisce lista di (titolo, pos_inizio_blocco) per le voci
    con {[[Portale]],{}} nel testo Lua.
    Usa VOCE_OPEN_RE per trovare l'apertura del blocco, poi estrae
    il titolo con extract_lua_longstring (robusto per qualsiasi livello).
    """
    results = []
    seen    = set()

    for m in PORTALE_EMPTY_RE.finditer(lua_text):
        portale_pos = m.start()
        preceding   = lua_text[:portale_pos]

        # Trova l'ultima apertura di blocco voce prima del Portale
        voce_matches = list(VOCE_OPEN_RE.finditer(preceding))
        if not voce_matches:
            continue

        last = voce_matches[-1]
        # brace_pos: posizione della { di apertura del blocco voce
        # group(0) = '\n    {[=*['  -> la { è un char prima del long string
        # group(1) = '[=*['
        brace_pos  = last.start() + len(last.group(0)) - len(last.group(1)) - 1
        # ls_pos: posizione del long string del titolo
        ls_pos = last.end() - len(last.group(1))

        titolo, _ = extract_lua_longstring(lua_text, ls_pos)
        if not titolo or len(titolo) <= 2 or titolo.isdigit():
            continue
        if titolo in seen:
            continue
        seen.add(titolo)
        results.append((titolo, brace_pos))

    return results


# -----------------------------------------------------------------------
# Trova bounds blocco voce tramite scansione sequenziale (no regex sul titolo)
# -----------------------------------------------------------------------

def find_voce_block_bounds(lua_text, brace_pos):
    """
    Dato brace_pos (posizione della { di apertura del blocco voce nel lua_text),
    restituisce (brace_pos, end) dove lua_text[brace_pos:end] è l'intero blocco
    inclusa eventuale virgola finale.
    Restituisce (None, None) se la struttura non è riconoscibile.
    """
    end = find_balanced_braces(lua_text, brace_pos)
    if end is None:
        return None, None
    block_end = end + 1  # dopo la }
    # Includi eventuale virgola finale
    if block_end < len(lua_text) and lua_text[block_end] == ',':
        block_end += 1
    return brace_pos, block_end


# -----------------------------------------------------------------------
# Patch del blocco voce: sostituisce il 4° campo (template array)
# -----------------------------------------------------------------------

def patch_portale_in_block(voce_block, new_templates_lua):
    """
    Sostituisce il campo template (4° campo) nel blocco voce Lua.
    Struttura: {titolo, timestamp, {cat,...}, {tmpl,...}, preview, move_ts}
    Salta i primi 3 campi poi sostituisce il blocco {tmpl}.
    Restituisce il blocco aggiornato, o None se la struttura non è riconoscibile.
    """
    pos = 1  # dopo la { iniziale

    # Salta titolo, timestamp, categorie
    for campo in ('titolo', 'timestamp', 'categorie'):
        pos = skip_lua_value(voce_block, pos)
        if pos is None:
            return None
        pos = skip_comma(voce_block, pos)

    # Ora siamo sul 4° campo: il blocco template {…}
    while pos < len(voce_block) and voce_block[pos] in ' \t\n\r':
        pos += 1
    if pos >= len(voce_block) or voce_block[pos] != '{':
        return None

    end = find_balanced_braces(voce_block, pos)
    if end is None:
        return None

    return voce_block[:pos] + new_templates_lua + voce_block[end+1:]


# -----------------------------------------------------------------------
# Scaricamento wikitesto in batch
# -----------------------------------------------------------------------

def download_wikitext_batch(titles):
    result = {}
    for start in range(0, len(titles), CHUNK_SIZE):
        chunk = titles[start:start + CHUNK_SIZE]
        pages = list(SITE.preloadpages(
            (pywikibot.Page(SITE, t) for t in chunk),
            groupsize=CHUNK_SIZE
        ))
        for page in pages:
            try:
                if not page.exists() or page.isRedirectPage():
                    continue
                result[page.title()] = page.text
            except Exception as e:
                log(f'    WARNING scaricamento {page.title()}: {e}')
        time.sleep(REQUEST_DELAY)
    return result


# -----------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------

def main():
    log_open()
    log(f'PatchPortale {VERSION} — Fix {{{{Portale}}}} senza params nei Dati Lua')

    log('\nConnessione a Wikipedia...')
    SITE.login()
    log(f'  OK - Login: {SITE.user()}')

    # Fase 1: scansiona tutti i file Dati
    log('\n--- Fase 1: scansione file Dati ---')
    # file_data: {page_name: (page_obj, lua_text, [(titolo, brace_pos), ...])}
    file_data         = {}
    all_titles_to_fix = []

    i = 1
    while True:
        page_name = f'{DATA_PAGE_PREFIX}{i}'
        page = pywikibot.Page(SITE, page_name)
        if not page.exists():
            break
        lua_text = page.text
        entries  = find_titles_with_empty_portale(lua_text)
        log(f'  {page_name}: {len(entries)} voci da fixare')
        if entries:
            file_data[page_name] = (page, lua_text, entries)
            all_titles_to_fix.extend(t for t, _ in entries)
        i += 1

    total = len(all_titles_to_fix)
    log(f'\nTotale voci da fixare: {total}')
    if total == 0:
        log('Niente da fare.')
        log_close()
        return

    # Fase 2: scarica wikitesto in batch
    log(f'\n--- Fase 2: scaricamento wikitesto ({total} voci, chunk={CHUNK_SIZE}) ---')
    wikitext_map = download_wikitext_batch(all_titles_to_fix)
    log(f'  Scaricate: {len(wikitext_map)} / {total}')

    # Fase 3: patch dei file Dati
    log('\n--- Fase 3: patch file Dati ---')
    total_fixed  = 0
    total_skip   = 0
    fixed_titles = set()

    for page_name, (page, lua_text, entries) in file_data.items():
        log(f'\n  {page_name}: {len(entries)} voci...')
        patched_text  = lua_text
        fixed_in_file = 0
        # Offset cumulativo: ogni patch cambia la lunghezza del testo,
        # i brace_pos originali vanno aggiustati
        offset = 0

        for titolo, orig_brace_pos in entries:
            brace_pos = orig_brace_pos + offset

            wikitext = wikitext_map.get(titolo)
            if wikitext is None:
                log(f'    SKIP(no_wikitext): {titolo}')
                total_skip += 1
                continue

            all_templates     = parse_templates_from_wikitext(wikitext)
            portale_templates = [t for t in all_templates if 'portale' in t['nome'].lower()]

            if not portale_templates:
                log(f'    SKIP(no_portale_in_wikitext): {titolo}')
                total_skip += 1
                continue

            has_params = any(t['params'] for t in portale_templates)
            if not has_params:
                log(f'    SKIP(portale_empty_in_wikitext): {titolo}')
                total_skip += 1
                continue

            # Verifica che brace_pos punti ancora al blocco corretto
            # (dopo offset il char deve essere '{')
            if brace_pos >= len(patched_text) or patched_text[brace_pos] != '{':
                log(f'    SKIP(brace_pos_invalido dopo offset): {titolo} pos={brace_pos}')
                total_skip += 1
                continue

            block_start, block_end = find_voce_block_bounds(patched_text, brace_pos)
            if block_start is None:
                log(f'    SKIP(bounds_non_trovati): {titolo}')
                total_skip += 1
                continue

            voce_block = patched_text[block_start:block_end]
            has_trailing_comma = voce_block.endswith(',')
            block_content      = voce_block.rstrip(',')

            new_templates_lua = serialize_templates(all_templates)
            patched_block     = patch_portale_in_block(block_content, new_templates_lua)
            if patched_block is None:
                log(f'    SKIP(patch_fallita): {titolo}')
                log(f'      blocco: {repr(block_content[:120])}')
                total_skip += 1
                continue

            if has_trailing_comma:
                patched_block += ','

            old_len      = block_end - block_start
            new_len      = len(patched_block)
            offset      += new_len - old_len

            patched_text = patched_text[:block_start] + patched_block + patched_text[block_end:]

            portale_params = [p for t in portale_templates for p in t['params']]
            log(f'    OK: {titolo} → {portale_params}')
            fixed_in_file += 1
            fixed_titles.add(titolo)

        if fixed_in_file == 0:
            log(f'  Nessuna modifica effettiva — skip salvataggio')
            continue

        # Validazione Lua prima di salvare
        err_pos, err_msg = validate_lua(patched_text)
        if err_pos is not None:
            line_num = patched_text[:err_pos].count('\n') + 1
            log(f'  ERRORE VALIDAZIONE LUA (riga {line_num}): {err_msg}')
            log(f'  Il file NON verrà salvato.')
            log(f'  Contesto: {repr(patched_text[max(0,err_pos-60):err_pos+100])}')
            total_skip += fixed_in_file
            for titolo, _ in entries:
                fixed_titles.discard(titolo)
            continue

        log(f'  Validazione Lua OK')
        log(f'  Salvataggio {page_name} ({fixed_in_file} voci fixate)...')
        page.text = patched_text
        page.save(
            summary=f'PatchPortale {VERSION}: fix Portale params per {fixed_in_file} voci',
            minor=True
        )
        total_fixed += fixed_in_file
        log(f'  OK — salvato')

    # Fase 4: pulizia CacheMoved
    log(f'\n--- Fase 4: pulizia CacheMoved ---')
    cm_page = pywikibot.Page(SITE, CACHE_MOVED_PAGE)
    if cm_page.exists() and cm_page.text.strip():
        lines     = cm_page.text.strip().split('\n')
        new_lines = []
        removed   = 0
        for line in lines:
            stripped = line.strip()
            if stripped.lower().startswith('aggiorna:'):
                titolo_cm = stripped[len('aggiorna:'):].strip()
                if titolo_cm in fixed_titles:
                    removed += 1
                    continue
            new_lines.append(line)
        cm_page.text = '\n'.join(new_lines)
        cm_page.save(
            summary=f'PatchPortale {VERSION}: rimossi {removed} Aggiorna: già processati',
            minor=True
        )
        log(f'  Rimossi {removed} Aggiorna: da CacheMoved')
    else:
        log('  CacheMoved vuota — skip')

    log(f'\n{"="*60}')
    log(f'Riepilogo:')
    log(f'  Voci fixate:  {total_fixed}')
    log(f'  Voci saltate: {total_skip}')
    log(f'{"="*60}')
    log_close()


if __name__ == '__main__':
    main()
