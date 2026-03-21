#!/usr/bin/env python3
"""
FixPortale.py - Identifica voci in cache con {{Portale}} senza parametri
e le aggiunge a CacheMoved come "Aggiorna:" per forzare il refresh dei metadati.

Strategia: ricerca regex diretta nel testo Lua grezzo cercando il pattern
{[[Portale]],{}} (template Portale con array params vuoto).
Per ogni match risale al titolo della voce tramite il long string precedente.

Versione: FP-1.1
"""

import pywikibot
import pywikibot.config as config
import re

# ========================================
# CONFIGURAZIONE
# ========================================
DATA_PAGE_PREFIX = 'Modulo:VociRecenti/Dati'
CACHE_MOVED_PAGE = 'Utente:BotVociRecenti/CacheMoved'
TIMEOUT = 300
# ========================================


SITE = pywikibot.Site('it', 'wikipedia')


# Pattern che matcha {[[Portale]],{}} con qualsiasi livello di escape Lua
PORTALE_EMPTY_PATTERN = re.compile(
    r'\{\[=*\[Portale\]=*\]\s*,\s*\{\s*\}',
    re.IGNORECASE
)

# Pattern per trovare l'apertura di un blocco voce: newline + spazi + { + long string
# Corrisponde al formato prodotto da format_lua_row: "    {[[titolo]],..."
VOCE_OPEN_PATTERN = re.compile(r'\n\s*\{(\[=*\[)(.+?)(\]=*\])')


def find_titles_with_empty_portale(lua_text):
    """
    Trova i titoli delle voci che hanno {[[Portale]],{}} nel testo Lua.
    Per ogni match di Portale vuoto, risale al titolo della voce cercando
    l'ultima apertura di blocco voce (newline + spazi + {[[titolo]]) prima del match.
    """
    titles = []
    seen = set()

    for m in PORTALE_EMPTY_PATTERN.finditer(lua_text):
        portale_pos = m.start()
        preceding = lua_text[:portale_pos]
        voce_matches = list(VOCE_OPEN_PATTERN.finditer(preceding))
        if not voce_matches:
            continue
        titolo = voce_matches[-1].group(2).strip()
        if titolo and titolo not in seen:
            if len(titolo) > 2 and not titolo.isdigit():
                seen.add(titolo)
                titles.append(titolo)

    return titles


def main():
    print("=" * 60)
    print("FixPortale FP-1.1 - Ricerca {{Portale}} vuoto nel Lua grezzo")
    print("=" * 60)

    print("\nConnessione a Wikipedia...")
    SITE.login()
    print(f"  OK - Login: {SITE.user()}")

    all_titles = []
    i = 1
    while True:
        page_name = f'{DATA_PAGE_PREFIX}{i}'
        page = pywikibot.Page(SITE, page_name)
        if not page.exists():
            break
        print(f"\nScansione {page_name}...")
        text = page.text
        titles = find_titles_with_empty_portale(text)
        print(f"  Voci con Portale senza params: {len(titles)}")
        for t in titles[:10]:
            print(f"    • {t}")
        if len(titles) > 10:
            print(f"    ... e altre {len(titles)-10}")
        all_titles.extend(titles)
        i += 1

    print(f"\n{'=' * 60}")
    print(f"Totale voci da aggiornare: {len(all_titles)}")

    if not all_titles:
        print("Nessuna voce da aggiornare.")
        return

    cm_page = pywikibot.Page(SITE, CACHE_MOVED_PAGE)
    existing_text = cm_page.text if cm_page.exists() else ''
    existing_lines = set(existing_text.strip().split('\n')) if existing_text.strip() else set()

    new_lines = []
    skipped = 0
    for title in all_titles:
        line = f'Aggiorna: {title}'
        if line not in existing_lines:
            new_lines.append(line)
        else:
            skipped += 1

    print(f"  Già presenti in CacheMoved: {skipped}")
    print(f"  Da aggiungere: {len(new_lines)}")

    if not new_lines:
        print("Nessuna riga nuova da aggiungere.")
        return

    separator = '\n' if existing_text.strip() else ''
    new_text = existing_text.rstrip() + separator + '\n' + '\n'.join(new_lines)

    print(f"\nAggiornamento {CACHE_MOVED_PAGE}...")
    cm_page.text = new_text
    cm_page.save(
        summary=f'FixPortale: {len(new_lines)} voci con Portale senza params da rielaborare',
        minor=False
    )
    print(f"  OK - {len(new_lines)} righe Aggiorna: aggiunte")
    print("\nAl prossimo run del bot i metadati verranno aggiornati automaticamente.")


if __name__ == '__main__':
    main()


# ----------------------------------------
# Parser Lua (stesso di PuliziaCache)
# ----------------------------------------

def extract_lua_longstring(text, pos):
    while pos < len(text) and text[pos] in ' \t\n\r,':
        pos += 1
    if pos >= len(text):
        return None, pos
    if text[pos] == '[':
        level = 0
        p = pos + 1
        while p < len(text) and text[p] == '=':
            level += 1
            p += 1
        if p < len(text) and text[p] == '[':
            open_delim = '[' + '=' * level + '['
            close_delim = ']' + '=' * level + ']'
            start = p + 1
            end = text.find(close_delim, start)
            if end == -1:
                return None, pos
            return text[start:end], end + len(close_delim)
    if text[pos] in ('"', "'"):
        q = text[pos]
        start = pos + 1
        end = text.find(q, start)
        if end == -1:
            return None, pos
        return text[start:end], end + 1
    return None, pos


def find_balanced_braces(text, pos):
    if pos >= len(text) or text[pos] != '{':
        return None
    depth = 1
    i = pos + 1
    while i < len(text) and depth > 0:
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
        i += 1
    return i - 1 if depth == 0 else None


def parse_templates_from_block(block):
    """Estrae i template da un blocco voce Lua (campo 4 = array template)."""
    templates = []
    pos = 0
    while pos < len(block) and block[pos] in ' \t\n\r,':
        pos += 1
    if pos >= len(block) or block[pos] != '{':
        return templates
    tmpl_arr_end = find_balanced_braces(block, pos)
    if tmpl_arr_end is None:
        return templates
    tmpl_block = block[pos+1:tmpl_arr_end]
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
    return templates


def has_portale_without_params(templates):
    """Restituisce True se c'è un template Portale con params vuoti."""
    for t in templates:
        nome = t.get('nome', '').lower().strip()
        if 'portale' in nome and len(t.get('params', [])) == 0:
            return True
    return False


def has_portale(templates):
    """Restituisce True se c'è qualsiasi template Portale."""
    for t in templates:
        nome = t.get('nome', '').lower().strip()
        if 'portale' in nome:
            return True
    return False


def scan_file_for_broken_portale(page_text):
    """
    Scansiona il testo Lua di un file Dati cercando voci con
    {{Portale}} presente ma senza parametri.
    Restituisce lista di titoli da aggiornare.
    """
    titles_to_update = []

    # Trova tutti i blocchi voce: ogni riga dell'array d={}
    # Il formato è: {titolo, timestamp, {cat}, {tmpl}, preview, [move_ts]}
    # Usiamo un approccio a brace bilanciate
    i = 0
    n = len(page_text)

    # Cerca l'array d={ ... }
    d_start = page_text.find('d={')
    if d_start == -1:
        d_start = page_text.find('d = {')
    if d_start == -1:
        return titles_to_update

    # Trova la { dell'array
    brace_pos = page_text.find('{', d_start + 1)
    if brace_pos == -1:
        return titles_to_update

    arr_end = find_balanced_braces(page_text, brace_pos)
    if arr_end is None:
        return titles_to_update

    arr_content = page_text[brace_pos+1:arr_end]

    # Scansiona i blocchi voce dentro l'array
    pos = 0
    while pos < len(arr_content):
        while pos < len(arr_content) and arr_content[pos] in ' \t\n\r,':
            pos += 1
        if pos >= len(arr_content):
            break
        if arr_content[pos] == '{':
            voce_end = find_balanced_braces(arr_content, pos)
            if voce_end is None:
                break
            voce_block = arr_content[pos+1:voce_end]

            # Campo 1: titolo
            def next_ls(p):
                while p < len(voce_block) and voce_block[p] in ' \t\n\r,':
                    p += 1
                return extract_lua_longstring(voce_block, p)

            titolo, p = next_ls(0)
            if titolo is None:
                pos = voce_end + 1
                continue

            # Campo 2: timestamp
            _, p = next_ls(p)

            # Campo 3: categorie (salta il blocco {})
            while p < len(voce_block) and voce_block[p] in ' \t\n\r,':
                p += 1
            if p < len(voce_block) and voce_block[p] == '{':
                cat_end = find_balanced_braces(voce_block, p)
                if cat_end is None:
                    pos = voce_end + 1
                    continue
                p = cat_end + 1

            # Campo 4: template — qui cerchiamo Portale
            while p < len(voce_block) and voce_block[p] in ' \t\n\r,':
                p += 1
            if p < len(voce_block) and voce_block[p] == '{':
                tmpl_block = voce_block[p:]
                templates = parse_templates_from_block(tmpl_block)
                if has_portale(templates) and has_portale_without_params(templates):
                    titles_to_update.append(titolo)

            pos = voce_end + 1
        else:
            pos += 1

    return titles_to_update


def main():
    print("=" * 60)
    print("FixPortale.py - Ricerca voci con {{Portale}} senza params")
    print("=" * 60)

    print("\nConnessione a Wikipedia...")
    SITE.login()
    print(f"  OK - Login: {SITE.user()}")

    # Scansiona tutti i file Dati
    all_titles = []
    i = 1
    while True:
        page_name = f'{DATA_PAGE_PREFIX}{i}'
        page = pywikibot.Page(SITE, page_name)
        if not page.exists():
            break
        print(f"\nScansione {page_name}...")
        text = page.text
        titles = scan_file_for_broken_portale(text)
        print(f"  Voci con Portale senza params: {len(titles)}")
        for t in titles[:5]:
            print(f"    • {t}")
        if len(titles) > 5:
            print(f"    ... e altre {len(titles)-5}")
        all_titles.extend(titles)
        i += 1

    print(f"\n{'=' * 60}")
    print(f"Totale voci da aggiornare: {len(all_titles)}")

    if not all_titles:
        print("Nessuna voce da aggiornare.")
        return

    # Leggi CacheMoved attuale
    cm_page = pywikibot.Page(SITE, CACHE_MOVED_PAGE)
    existing_text = cm_page.text if cm_page.exists() else ''

    # Costruisci le righe Aggiorna: da aggiungere
    # Evita duplicati con righe già presenti
    existing_lines = set(existing_text.strip().split('\n')) if existing_text.strip() else set()
    new_lines = []
    skipped = 0
    for title in all_titles:
        line = f'Aggiorna: {title}'
        if line not in existing_lines:
            new_lines.append(line)
        else:
            skipped += 1

    print(f"  Già presenti in CacheMoved: {skipped}")
    print(f"  Da aggiungere: {len(new_lines)}")

    if not new_lines:
        print("Nessuna riga nuova da aggiungere.")
        return

    # Aggiorna CacheMoved
    separator = '\n' if existing_text.strip() else ''
    new_text = existing_text.rstrip() + separator + '\n' + '\n'.join(new_lines)

    print(f"\nAggiornamento {CACHE_MOVED_PAGE}...")
    cm_page.text = new_text
    cm_page.save(
        summary=f'FixPortale: aggiunge {len(new_lines)} voci con Portale senza params da rielaborare',
        minor=False
    )
    print(f"  OK - {len(new_lines)} righe Aggiorna: aggiunte")
    print("\nAl prossimo run del bot i metadati verranno aggiornati automaticamente.")


if __name__ == '__main__':
    main()
