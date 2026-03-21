#!/usr/bin/env python3
"""
cachevocispostate.py - Cache locale voci spostate da sandbox a NS0

Mantiene un file JSON locale con l'elenco delle voci create in:
- Namespace Bozza (118)
- Namespace Utente (2)  
- Namespace Portale (100)

e poi spostate a NS0.

Il file cache contiene solo voci create negli ultimi 30 giorni o dalla data
della voce più vecchia in cache.
"""

import pywikibot
import pywikibot.config as config
import json
from datetime import datetime, timedelta
import os

# ========================================
# CONFIGURAZIONE
# ========================================
BOT_USERNAME = 'IndyJrBot@Pywikibot'
BOT_PASSWORD = 't1ej4nl6vp6up1fvqlu44n7da1m5j90d'

CACHE_FILE = 'voci_spostate_cache.json'
MAX_DAYS = 30  # Mantieni voci degli ultimi 30 giorni

# Namespace da monitorare (da cui vengono spostate voci)
NAMESPACES_TO_CHECK = {
    2: 'Utente',
    100: 'Portale', 
    118: 'Bozza'
}

# ========================================

config.authenticate['it.wikipedia.org'] = (BOT_USERNAME, BOT_PASSWORD)
config.usernames['wikipedia']['it'] = BOT_USERNAME.split('@')[0]

SITE = pywikibot.Site('it', 'wikipedia')


def main():
    print("=" * 60)
    print("CACHE VOCI SPOSTATE DA SANDBOX A NS0")
    print("=" * 60)
    
    # Login
    print(f"\nLogin come {BOT_USERNAME}...")
    if not SITE.logged_in():
        SITE.login()
    print(f"OK - Login: {SITE.username()}\n")
    
    # 1. Carica cache esistente
    cache_data = load_cache()
    
    # 2. Determina data limite
    cutoff_date = get_cutoff_date(cache_data)
    cutoff_iso = cutoff_date.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    print(f"Data limite: {cutoff_iso}")
    print(f"Cerco voci create dopo questa data e spostate a NS0\n")
    
    # 3. Cerca voci spostate
    existing_titles = {v['titolo'] for v in cache_data['voci']}
    new_moved = find_moved_pages(cutoff_iso, existing_titles)
    
    print(f"\nTrovate {len(new_moved)} nuove voci spostate")
    
    # 4. Aggiungi alla cache
    cache_data['voci'].extend(new_moved)
    
    # 5. Rimuovi voci troppo vecchie
    cache_data = cleanup_old_entries(cache_data, cutoff_date)
    
    # 6. Ordina per data creazione
    cache_data['voci'].sort(key=lambda x: x['data_creazione'])
    
    # 7. Aggiorna timestamp
    cache_data['ultimo_aggiornamento'] = datetime.now().isoformat()
    
    # 8. Salva cache
    save_cache(cache_data)
    
    # 9. DEBUG: Verifica voci specifiche
    check_specific_pages(cache_data)
    
    print("\n" + "=" * 60)
    print("COMPLETATO!")
    print("=" * 60)
    print(f"Voci in cache: {len(cache_data['voci'])}")
    print(f"File: {CACHE_FILE}")


def load_cache():
    """Carica cache esistente o crea nuova"""
    if os.path.exists(CACHE_FILE):
        print(f"Caricamento cache esistente: {CACHE_FILE}")
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"  OK - {len(data['voci'])} voci in cache\n")
            return data
        except Exception as e:
            print(f"  ERRORE lettura cache: {e}")
            print("  Creo nuova cache\n")
    else:
        print(f"Cache non esistente, creo nuova cache\n")
    
    return {
        'ultimo_aggiornamento': None,
        'voci': []
    }


def get_cutoff_date(cache_data):
    """Determina data limite per la ricerca"""
    if not cache_data['voci']:
        # Cache vuota: ultimi 30 giorni
        cutoff = datetime.now() - timedelta(days=MAX_DAYS)
        print(f"Cache vuota - cerco ultimi {MAX_DAYS} giorni")
    else:
        # Trova voce più vecchia in cache
        oldest = min(cache_data['voci'], key=lambda x: x['data_creazione'])
        cutoff = datetime.fromisoformat(oldest['data_creazione'])
        # Rimuovi timezone se presente
        if cutoff.tzinfo is not None:
            cutoff = cutoff.replace(tzinfo=None)
        print(f"Voce più vecchia in cache: {oldest['titolo']}")
        print(f"  Data creazione: {oldest['data_creazione']}")
    
    # Non andare oltre 30 giorni comunque
    min_date = datetime.now() - timedelta(days=MAX_DAYS)
    if cutoff < min_date:
        cutoff = min_date
        print(f"Limite portato a {MAX_DAYS} giorni fa")
    
    return cutoff


def find_moved_pages(since_iso, existing_titles):
    """
    Cerca voci in NS0 con rctype='edit' e verifica il primo commento
    per trovare quelle spostate da sandbox
    """
    moved_pages = []
    
    print("Ricerca voci spostate da sandbox a NS0...")
    print("Metodo: RecentChanges edit + verifica primo commento\n")
    
    params = {
        'action': 'query',
        'list': 'recentchanges',
        'rctype': 'edit',  # Modifiche (le voci spostate sono "edit")
        'rcnamespace': 0,
        'rcshow': '!bot',
        'rclimit': 500,
        'rcprop': 'title|timestamp',
        'rcdir': 'older',
        'rcstart': 'now',
        'rcend': since_iso,
        'format': 'json'
    }
    
    continue_param = None
    iteration = 0
    checked = 0
    found = 0
    max_iterations = 10  # Max 5000 edit da controllare
    
    print(f"Cerco dal {since_iso} ad oggi...")
    print(f"Controllerò max {max_iterations * 500} modifiche\n")
    
    try:
        while iteration < max_iterations:
            iteration += 1
            
            if continue_param:
                params['rccontinue'] = continue_param
            
            request = SITE.simple_request(**params)
            data = request.submit()
            
            if 'query' not in data or 'recentchanges' not in data['query']:
                break
            
            changes = data['query']['recentchanges']
            
            for change in changes:
                checked += 1
                title = change['title']
                
                if title in existing_titles:
                    continue
                
                try:
                    page = pywikibot.Page(SITE, title, ns=0)
                    
                    if not page.exists() or page.isRedirectPage():
                        continue
                    
                    # CHIAVE: Verifica il PRIMO commento della cronologia
                    oldest = page.oldest_revision
                    first_comment = oldest.comment.lower()
                    created_iso = oldest.timestamp.isoformat()
                    
                    # Cerca pattern di spostamento nel primo commento
                    is_moved = False
                    source_ns = None
                    
                    if 'spostato' in first_comment or 'moved' in first_comment:
                        if 'utente:' in first_comment or 'sandbox' in first_comment:
                            is_moved = True
                            source_ns = 'Utente'
                        elif 'bozza:' in first_comment:
                            is_moved = True
                            source_ns = 'Bozza'
                        elif 'portale:' in first_comment:
                            is_moved = True
                            source_ns = 'Portale'
                    
                    if is_moved and source_ns:
                        moved_pages.append({
                            'titolo': title,
                            'data_creazione': created_iso,
                            'data_creazione_sandbox': change['timestamp'],
                            'namespace_origine': source_ns,
                            'titolo_sandbox': f'{source_ns}:Sandbox',
                            'primo_commento': oldest.comment[:100]
                        })
                        
                        existing_titles.add(title)
                        found += 1
                        
                        print(f"  ✓ {title}")
                        print(f"     Da: {source_ns}")
                        print(f"     Commento: {oldest.comment[:80]}")
                
                except Exception as e:
                    continue
            
            if checked % 500 == 0:
                print(f"    Controllate: {checked}, Trovate: {found}")
            
            if 'continue' in data and 'rccontinue' in data['continue']:
                continue_param = data['continue']['rccontinue']
            else:
                print(f"    Fine risultati")
                break
            
            import time
            time.sleep(1)
    
    except Exception as e:
        print(f"  ERRORE: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\nTotale controllate: {checked}, Totale trovate: {found}\n")
    return moved_pages


def cleanup_old_entries(cache_data, cutoff_date):
    """Rimuovi voci più vecchie del cutoff"""
    original_count = len(cache_data['voci'])
    
    # Assicura che cutoff_date sia naive (senza timezone)
    if cutoff_date.tzinfo is not None:
        cutoff_date = cutoff_date.replace(tzinfo=None)
    
    cleaned_voci = []
    for v in cache_data['voci']:
        try:
            created = datetime.fromisoformat(v['data_creazione'])
            # Rimuovi timezone se presente
            if created.tzinfo is not None:
                created = created.replace(tzinfo=None)
            
            if created >= cutoff_date:
                cleaned_voci.append(v)
        except:
            # Se c'è errore nel parsing, mantieni la voce
            cleaned_voci.append(v)
    
    cache_data['voci'] = cleaned_voci
    
    removed = original_count - len(cache_data['voci'])
    if removed > 0:
        print(f"\nRimosse {removed} voci troppo vecchie")
    
    return cache_data


def save_cache(cache_data):
    """Salva cache su file"""
    print(f"\nSalvataggio cache...")
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
        print(f"  OK - Salvato {CACHE_FILE}")
    except Exception as e:
        print(f"  ERRORE: {e}")


def check_specific_pages(cache_data):
    """DEBUG: Verifica presenza voci specifiche"""
    test_pages = [
        'Grimpella thaumastocheir',
        'Megaleledone setebos'
    ]
    
    print("\n" + "=" * 60)
    print("DEBUG: Verifica voci specifiche")
    print("=" * 60)
    
    cache_titles = {v['titolo'] for v in cache_data['voci']}
    
    all_found = True
    for title in test_pages:
        if title in cache_titles:
            # Trova i dettagli
            voce = next(v for v in cache_data['voci'] if v['titolo'] == title)
            print(f"✓ {title}")
            print(f"  Creata: {voce['data_creazione']}")
            print(f"  Da: {voce['namespace_origine']}")
        else:
            print(f"✗ {title} - NON TROVATA")
            all_found = False
    
    if not all_found:
        print("\n" + "!" * 60)
        print("ERRORE: Le voci [[Grimpella thaumastocheir]] e")
        print("        [[Megaleledone setebos]] non esistono!")
        print("!" * 60)


if __name__ == '__main__':
    main()
