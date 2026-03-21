#!/usr/bin/env python3
"""
Analisi dettagliata cronologia voci
"""

import pywikibot
import pywikibot.config as config

BOT_USERNAME = 'BOT_USERNAME_RIMOSSO'
BOT_PASSWORD = 'CREDENZIALE_RIMOSSA'

config.authenticate['it.wikipedia.org'] = (BOT_USERNAME, BOT_PASSWORD)
config.usernames['wikipedia']['it'] = BOT_USERNAME.split('@')[0]

SITE = pywikibot.Site('it', 'wikipedia')

test_titles = [
    "Grimpella thaumastocheir",
    "Megaleledone setebos"
]

print("=" * 60)
print("ANALISI CRONOLOGIA VOCI")
print("=" * 60)

if not SITE.logged_in():
    SITE.login()

for title in test_titles:
    print(f"\n{'=' * 60}")
    print(f"VOCE: {title}")
    print("=" * 60)
    
    try:
        page = pywikibot.Page(SITE, title)
        
        print(f"\nEsiste: {page.exists()}")
        print(f"È redirect: {page.isRedirectPage()}")
        print(f"Namespace: {page.namespace()}")
        
        # Analizza cronologia
        print(f"\nCRONOLOGIA COMPLETA:")
        revisions = list(page.revisions(total=50, reverse=True))
        
        for i, rev in enumerate(revisions):
            print(f"\n[{i+1}] {rev.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"    Utente: {rev.user}")
            print(f"    Commento: {rev.comment[:100] if rev.comment else '(nessuno)'}")
            
            # Verifica se era redirect
            try:
                text = rev.text
                if text:
                    is_redirect = text.strip().upper().startswith('#RINVIA') or text.strip().upper().startswith('#REDIRECT')
                    if is_redirect:
                        print(f"    ⚠️  ERA UN REDIRECT!")
            except:
                pass
        
        # Controlla log degli spostamenti
        print(f"\nLOG SPOSTAMENTI:")
        try:
            logs = SITE.logevents(page=title, logtype='move', total=10)
            has_moves = False
            for log in logs:
                has_moves = True
                print(f"  {log.timestamp()} - Da: {log.data.get('target_title', 'N/A')}")
            if not has_moves:
                print("  Nessuno spostamento")
        except:
            print("  Errore nel recupero log")
        
        # Controlla log import
        print(f"\nLOG IMPORT:")
        try:
            logs = SITE.logevents(page=title, logtype='import', total=10)
            has_imports = False
            for log in logs:
                has_imports = True
                print(f"  {log.timestamp()} - Import")
            if not has_imports:
                print("  Nessun import")
        except:
            print("  Errore nel recupero log")
            
    except Exception as e:
        print(f"ERRORE: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 60)
print("CONCLUSIONE")
print("=" * 60)
print("Se le voci erano redirect alla creazione, NON appaiono")
print("in RecentChanges con rctype='new' perché tecnicamente")
print("non erano 'nuove pagine' ma redirect.")
print("\nSOLUZIONE: Usare anche rctype='edit' oppure rctype='new|edit'")
