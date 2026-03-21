#!/usr/bin/env python3
"""
VVCache.py - Script di debug per la cache VociRecenti

Chiede all'utente il nome di una voce e mostra:
- In quale file Dati si trova (Dati1, Dati2, ...)
- Posizione nella cache (rank cronologico)
- Timestamp e data di creazione leggibile
- Eta' in giorni
- Numero e lista delle categorie
- Lunghezza del contenuto e prime righe
- Stato attuale della voce su Wikipedia (esiste? redirect? namespace?)
- Presenza in CacheMoved
"""

import pywikibot
import pywikibot.config as config
import re
import sys
from datetime import datetime

# ========================================
# CONFIGURAZIONE (identica al bot)
# ========================================
DATA_PAGE_PREFIX = 'Modulo:VociRecenti/Dati'
CACHE_MOVED_PAGE = 'Utente:BotVociRecenti/CacheMoved'
CACHE_PARSED_PAGE = 'Utente:BotVociRecenti/CacheParsed'
TIMEOUT = 300
# ========================================


SITE = pywikibot.Site('it', 'wikipedia')


# ========================================
# ========================================
# PARSER LUA (supporta vecchio e nuovo formato)
# ========================================

def skip_lua_longstring(text, pos):
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
    """Estrae il contenuto di un long string Lua che inizia a pos."""
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


def parse_lua_to_json(lua_content):
    """
    Parsa il file Lua e restituisce lista di voci (vecchio o nuovo formato).
    Nuovo formato (d={...}): parsing veloce per righe.
    Vecchio formato (voci={...}): parsing bilanciato delle graffe.
    """
    voci = []

    m_new = re.search(r'(?<![a-zA-Z_])d\s*=\s*\{', lua_content)
    m_old = re.search(r'voci\s*=\s*\{', lua_content)

    if m_new:
        brace_start = lua_content.find('{', m_new.start())
        if brace_start == -1:
            return voci
        for line in lua_content[brace_start:].splitlines():
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
            next_pos = skip_lua_longstring(voci_content, i)
            if next_pos is not None:
                i = next_pos
                continue
            if voci_content[i] == '{':
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


def skip_lua_longstring(text, pos):
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


def load_all_cache_files():
    """
    Carica tutti i file Dati e restituisce:
    - lista di tuple (voce, file_number, rank_globale)
    - metadata per file (nome, num_voci, ultimo_aggiornamento)
    """
    print("Caricamento cache...")
    all_voci = []       # (voce_dict, file_num, rank_in_file)
    file_meta = []      # {name, num_voci, ultimo_aggiornamento}
    rank_globale = 0

    i = 1
    while True:
        page_name = f"{DATA_PAGE_PREFIX}{i}"
        page = pywikibot.Page(SITE, page_name)
        if not page.exists():
            break
        try:
            lua_content = page.text
            # Estrae ultimo_aggiornamento (vecchio formato) o u= (nuovo formato)
            ua_match = re.search(r"u\s*=\s*\[=*\[([^\]]+)\]=*\]|ultimo_aggiornamento\s*=\s*'([^']+)'", lua_content)
            if ua_match:
                ultimo_agg = ua_match.group(1) or ua_match.group(2) or '?'
            else:
                ultimo_agg = '?'

            voci = parse_lua_to_json(lua_content)
            file_meta.append({
                'name': page_name,
                'num_voci': len(voci),
                'ultimo_aggiornamento': ultimo_agg
            })
            for rank_in_file, voce in enumerate(voci, 1):
                rank_globale += 1
                all_voci.append((voce, i, rank_in_file, rank_globale))
            print(f"  {page_name}: {len(voci)} voci")
        except Exception as e:
            print(f"  ERRORE {page_name}: {e}")
        i += 1

    print(f"  Totale: {rank_globale} voci in {len(file_meta)} file\n")
    return all_voci, file_meta


def load_cache_moved():
    """Legge CacheMoved e restituisce lista di titoli e flag CacheParsed."""
    try:
        page = pywikibot.Page(SITE, CACHE_MOVED_PAGE)
        if not page.exists():
            return [], '(pagina non esistente)'
        content = page.text.strip()
        lines = [l.strip() for l in content.split('\n') if l.strip() and not l.strip().startswith('#')]
        # Estrae titoli (supporta sia titoli semplici che formato dump)
        titles = []
        for line in lines:
            m = re.search(r'\d{2}:\d{2}, \d{1,2} \w+ \d{4} (.+?) \(cron \|', line)
            titles.append(m.group(1).strip() if m else line)
        return titles, content[:200] + ('...' if len(content) > 200 else '')
    except Exception as e:
        return [], f'ERRORE: {e}'


def get_cache_parsed_status():
    try:
        page = pywikibot.Page(SITE, CACHE_PARSED_PAGE)
        if not page.exists():
            return '(pagina non esistente)'
        return page.text.strip()
    except Exception as e:
        return f'ERRORE: {e}'


# ========================================
# VERIFICA STATO SU WIKIPEDIA
# ========================================

def check_wiki_status(title):
    """Controlla lo stato attuale della voce su Wikipedia."""
    info = {}
    try:
        page = pywikibot.Page(SITE, title)
        info['exists'] = page.exists()
        if not info['exists']:
            info['status'] = 'NON ESISTE'
            return info
        info['namespace'] = int(page.namespace())
        info['is_redirect'] = page.isRedirectPage()
        if info['is_redirect']:
            info['status'] = 'REDIRECT'
            try:
                info['redirect_target'] = page.getRedirectTarget().title()
            except Exception:
                info['redirect_target'] = '?'
        else:
            info['status'] = 'OK'
        try:
            oldest = page.oldest_revision
            info['created'] = oldest.timestamp.strftime('%d/%m/%Y %H:%M')
            info['created_by'] = oldest.user
        except Exception:
            info['created'] = '?'
            info['created_by'] = '?'
        try:
            latest = page.latest_revision
            info['last_edit'] = latest.timestamp.strftime('%d/%m/%Y %H:%M')
            info['last_edit_by'] = latest.user
            info['rev_count'] = page.revision_count()
        except Exception:
            info['last_edit'] = '?'
            info['last_edit_by'] = '?'
            info['rev_count'] = '?'
        try:
            info['size'] = len(page.text.encode('utf-8'))
        except Exception:
            info['size'] = '?'
        # Recupera storia spostamenti: cerca nel log se la voce e' arrivata da un altro NS
        try:
            move_log = []
            for entry in SITE.logevents(logtype='move', page=page, total=5):
                src = entry.data.get('params', {}).get('target_title') or ''
                move_log.append(
                    f"{entry.timestamp().strftime('%d/%m/%Y %H:%M')} "
                    f"{entry.user()} ha spostato da '{entry.page().title()}' a '{src}'"
                )
            info['move_log'] = move_log if move_log else []
        except Exception:
            info['move_log'] = []
    except Exception as e:
        info['status'] = f'ERRORE: {e}'
    return info


# ========================================
# FORMATTAZIONE OUTPUT
# ========================================

def format_timestamp(ts):
    """Converte YYYYMMDDHHMMSS in stringa leggibile e calcola eta' in giorni."""
    try:
        dt = datetime.strptime(ts, '%Y%m%d%H%M%S')
        age_days = (datetime.now() - dt).days
        return dt.strftime('%d/%m/%Y %H:%M:%S'), age_days
    except Exception:
        return ts, '?'


def sep(char='─', n=60):
    print(char * n)


def print_voce_info(voce, file_num, rank_in_file, rank_globale, total_voci):
    ts_str, age_days = format_timestamp(voce['timestamp'])
    templates = voce.get('templates', [])
    preview = voce.get('preview', '')

    sep('═')
    print(f"  VOCE TROVATA IN CACHE")
    sep('═')
    print(f"  Titolo:            {voce['titolo']}")
    print(f"  File:              {DATA_PAGE_PREFIX}{file_num}")
    print(f"  Posizione nel file: #{rank_in_file}")
    print(f"  Rank globale:      #{rank_globale} di {total_voci}")
    print(f"  Timestamp cache:   {voce['timestamp']}")
    print(f"  Data creazione:    {ts_str}")
    print(f"  Eta':              {age_days} giorni fa")
    sep()
    print(f"  Categorie ({len(voce['categorie'])}):")
    if voce['categorie']:
        for cat in voce['categorie']:
            print(f"    • {cat}")
    else:
        print("    (nessuna categoria)")
    sep()
    print(f"  Template ({len(templates)}):")
    if templates:
        for t in templates:
            nome = t.get('nome', '?')
            params = t.get('params', [])
            if params:
                print(f"    • {{{{{nome}}}}} → params: {', '.join(params)}")
            else:
                print(f"    • {{{{{nome}}}}}")
    else:
        print("    (nessun template in cache — voce in formato vecchio)")
    sep()
    print(f"  Preview (100 car.):")
    if preview:
        print(f"    | {preview[:100]}")
    else:
        print("    (assente)")


def print_wiki_status(title, info):
    sep()
    print(f"  STATO SU WIKIPEDIA")
    sep()
    status_icon = {'OK': '✓', 'REDIRECT': '→', 'NON ESISTE': '✗'}.get(info.get('status', ''), '?')
    print(f"  Stato:             {status_icon} {info.get('status', '?')}")
    if info.get('namespace') is not None:
        ns = info['namespace']
        ns_label = {0: 'NS0 (principale)', 2: 'NS2 (Utente)', 4: 'NS4 (Wikipedia)',
                    10: 'NS10 (Template)', 14: 'NS14 (Categoria)', 100: 'NS100 (Portale)',
                    118: 'NS118 (Bozze)'}.get(ns, f'NS{ns}')
        print(f"  Namespace:         {ns_label}")
    if info.get('status') == 'REDIRECT':
        print(f"  Punta a:           {info.get('redirect_target', '?')}")
    if info.get('created'):
        print(f"  Creata:            {info['created']} (da {info.get('created_by', '?')})")
    if info.get('last_edit'):
        print(f"  Ultima modifica:   {info['last_edit']} (da {info.get('last_edit_by', '?')})")
    if info.get('rev_count') is not None:
        print(f"  N. revisioni:      {info['rev_count']}")
    if info.get('size') is not None:
        print(f"  Dimensione:        {info['size']:,} byte" if isinstance(info['size'], int) else f"  Dimensione:        {info['size']}")
    move_log = info.get('move_log', [])
    if move_log:
        print(f"  Spostamenti ({len(move_log)}):")
        for entry in move_log:
            print(f"    ↳ {entry}")
    else:
        print(f"  Spostamenti:       nessuno registrato")


def print_cache_moved_status(title, cm_titles, cm_preview):
    sep()
    print(f"  CACHE MANUALE (CacheMoved)")
    sep()
    in_cm = title in cm_titles
    # Cerca anche corrispondenza parziale case-insensitive
    title_lower = title.lower()
    partial = [t for t in cm_titles if title_lower in t.lower() or t.lower() in title_lower]
    if in_cm:
        print(f"  Presente:          ✓ SÌ (corrispondenza esatta)")
    elif partial:
        print(f"  Presente:          ~ Corrispondenza parziale:")
        for t in partial:
            print(f"    → {t}")
    else:
        print(f"  Presente:          ✗ NO")
    print(f"  Totale titoli CM:  {len(cm_titles)}")


def print_cache_state(cache_parsed_status, file_meta):
    sep()
    print(f"  STATO CACHE")
    sep()
    print(f"  CacheParsed:       '{cache_parsed_status}'")
    print(f"  File cache:        {len(file_meta)}")
    for fm in file_meta:
        print(f"    • {fm['name']}: {fm['num_voci']} voci (agg. {fm['ultimo_aggiornamento']})")


# ========================================
# MAIN
# ========================================

def main():
    print()
    sep('═')
    print("  VVCache.py - Debug cache VociRecenti")
    sep('═')
    print()

    # Input titolo
    if len(sys.argv) > 1:
        search_title = ' '.join(sys.argv[1:])
    else:
        search_title = input("  Titolo da cercare: ").strip()

    if not search_title:
        print("  ERRORE: titolo non specificato.")
        return

    print(f"\n  Ricerca: '{search_title}'\n")

    # Login
    print("  Connessione a Wikipedia...")
    try:
        if not SITE.logged_in():
            SITE.login()
        print(f"  OK - Login: {SITE.username()}\n")
    except Exception as e:
        print(f"  ERRORE login: {e}")
        return

    # Carica cache
    all_voci, file_meta = load_all_cache_files()
    total_voci = len(all_voci)

    # Cerca la voce (prima esatta, poi case-insensitive)
    found_exact = None
    found_icase = []

    search_lower = search_title.lower()
    for (voce, file_num, rank_in_file, rank_globale) in all_voci:
        if voce['titolo'] == search_title:
            found_exact = (voce, file_num, rank_in_file, rank_globale)
            break
        if search_lower in voce['titolo'].lower():
            found_icase.append((voce, file_num, rank_in_file, rank_globale))

    # Carica CacheMoved e CacheParsed
    cm_titles, cm_preview = load_cache_moved()
    cache_parsed_status = get_cache_parsed_status()

    if found_exact:
        voce, file_num, rank_in_file, rank_globale = found_exact
        print_voce_info(voce, file_num, rank_in_file, rank_globale, total_voci)

        # Verifica stato su Wikipedia
        print(f"\n  Verifica stato su Wikipedia per '{voce['titolo']}'...")
        wiki_info = check_wiki_status(voce['titolo'])
        print_wiki_status(voce['titolo'], wiki_info)

        print_cache_moved_status(voce['titolo'], cm_titles, cm_preview)
        print_cache_state(cache_parsed_status, file_meta)
        sep('═')

    elif found_icase:
        print(f"  Corrispondenza esatta non trovata.")
        print(f"  Trovate {len(found_icase)} voci con match parziale:\n")
        for idx, (voce, file_num, rank_in_file, rank_globale) in enumerate(found_icase[:10], 1):
            ts_str, age_days = format_timestamp(voce['timestamp'])
            print(f"  {idx}. {voce['titolo']}")
            print(f"     File: {DATA_PAGE_PREFIX}{file_num} | Rank: #{rank_globale} | "
                  f"Data: {ts_str} ({age_days}gg)")
        if len(found_icase) > 10:
            print(f"  ... e altri {len(found_icase) - 10} risultati.")

        print()
        choice = input("  Numero da esaminare (invio per saltare): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(found_icase):
            voce, file_num, rank_in_file, rank_globale = found_icase[int(choice) - 1]
            print()
            print_voce_info(voce, file_num, rank_in_file, rank_globale, total_voci)
            print(f"\n  Verifica stato su Wikipedia per '{voce['titolo']}'...")
            wiki_info = check_wiki_status(voce['titolo'])
            print_wiki_status(voce['titolo'], wiki_info)
            print_cache_moved_status(voce['titolo'], cm_titles, cm_preview)
            print_cache_state(cache_parsed_status, file_meta)
            sep('═')
        else:
            print_cache_state(cache_parsed_status, file_meta)
            sep('═')

    else:
        sep('═')
        print(f"  VOCE NON TROVATA IN CACHE")
        sep('═')
        print(f"  '{search_title}' non è presente in nessun file Dati.")
        print()

        # Verifica comunque su Wikipedia
        print(f"  Verifica stato su Wikipedia...")
        wiki_info = check_wiki_status(search_title)
        print_wiki_status(search_title, wiki_info)

        print_cache_moved_status(search_title, cm_titles, cm_preview)
        print_cache_state(cache_parsed_status, file_meta)
        sep('═')

    print()


if __name__ == '__main__':
    main()
