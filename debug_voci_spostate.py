#!/usr/bin/env python3
"""
Debug: Analizza esattamente le due voci problematiche
"""

import pywikibot
import pywikibot.config as config

BOT_USERNAME = 'BOT_USERNAME_RIMOSSO'
BOT_PASSWORD = 'CREDENZIALE_RIMOSSA'

config.authenticate['it.wikipedia.org'] = (BOT_USERNAME, BOT_PASSWORD)
config.usernames['wikipedia']['it'] = BOT_USERNAME.split('@')[0]

SITE = pywikibot.Site('it', 'wikipedia')

test_titles = [
    'Grimpella thaumastocheir',
    'Megaleledone setebos'
]

print("=" * 60)
print("DEBUG DETTAGLIATO VOCI")
print("=" * 60)

if not SITE.logged_in():
    SITE.login()

for title in test_titles:
    print(f"\n{'=' * 60}")
    print(f"VOCE: {title}")
    print("=" * 60)
    
    try:
        page = pywikibot.Page(SITE, title, ns=0)
        
        print(f"\nEsiste: {page.exists()}")
        print(f"È redirect: {page.isRedirectPage()}")
        
        # Primo revision (creazione in NS0)
        oldest = page.oldest_revision
        print(f"\nPRIMO REVISION IN NS0:")
        print(f"  Timestamp: {oldest.timestamp}")
        print(f"  Utente: {oldest.user}")
        print(f"  Commento: '{oldest.comment}'")
        print(f"  Commento (lower): '{oldest.comment.lower()}'")
        
        # Cerca pattern
        comment_lower = oldest.comment.lower()
        print(f"\n  Contiene 'spostato': {'spostato' in comment_lower}")
        print(f"  Contiene 'moved': {'moved' in comment_lower}")
        print(f"  Contiene 'utente': {'utente' in comment_lower}")
        print(f"  Contiene 'bozza': {'bozza' in comment_lower}")
        print(f"  Contiene 'sandbox': {'sandbox' in comment_lower}")
        
        # Cerca log spostamenti per questa pagina
        print(f"\nLOG SPOSTAMENTI PER QUESTA PAGINA:")
        logs = list(SITE.logevents(page=title, logtype='move', total=5))
        
        if logs:
            for i, log in enumerate(logs, 1):
                print(f"\n  Spostamento #{i}:")
                print(f"    Timestamp: {log.timestamp()}")
                print(f"    Utente: {log.user()}")
                print(f"    Commento: {log.comment()}")
                
                # Dati spostamento
                try:
                    log_data = log.data
                    print(f"    Dati: {log_data}")
                    
                    # Titolo origine
                    if 'move' in log_data:
                        move_data = log_data['move']
                        print(f"    Da (new_title): {move_data.get('new_title', 'N/A')}")
                        print(f"    A (old_title?): {move_data.get('old_title', 'N/A')}")
                except:
                    pass
        else:
            print("  Nessun log spostamento trovato!")
        
        # API logevents diretta
        print(f"\nAPI LOGEVENTS DIRETTA:")
        params = {
            'action': 'query',
            'list': 'logevents',
            'letype': 'move',
            'letitle': title,
            'lelimit': 5,
            'leprop': 'title|timestamp|details|user|comment',
            'format': 'json'
        }
        
        request = SITE.simple_request(**params)
        data = request.submit()
        
        if 'query' in data and 'logevents' in data['query']:
            events = data['query']['logevents']
            print(f"  Trovati {len(events)} eventi")
            
            for i, event in enumerate(events, 1):
                print(f"\n  Evento #{i}:")
                print(f"    Title: {event.get('title')}")
                print(f"    Timestamp: {event.get('timestamp')}")
                print(f"    User: {event.get('user')}")
                print(f"    Comment: {event.get('comment')}")
                print(f"    Params: {event.get('params')}")
        else:
            print("  Nessun evento API trovato!")
        
    except Exception as e:
        print(f"ERRORE: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 60)
print("ANALISI COMPLETATA")
print("=" * 60)
