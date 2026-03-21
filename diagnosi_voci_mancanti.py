#!/usr/bin/env python3
"""
Diagnostica voci mancanti dalla cache
Verifica perché alcune voci non sono state incluse
"""

import pywikibot
import pywikibot.config as config
from datetime import datetime

BOT_USERNAME = 'IndyJrBot@Pywikibot'
BOT_PASSWORD = 't1ej4nl6vp6up1fvqlu44n7da1m5j90d'

config.authenticate['it.wikipedia.org'] = (BOT_USERNAME, BOT_PASSWORD)
config.usernames['wikipedia']['it'] = BOT_USERNAME.split('@')[0]

SITE = pywikibot.Site('it', 'wikipedia')

# Voci da verificare
test_titles = [
    "Grimpella thaumastocheir",
    "Megaleledone setebos"
]

print("=" * 60)
print("DIAGNOSTICA VOCI MANCANTI")
print("=" * 60)

# Login
print("\nLogin...")
if not SITE.logged_in():
    SITE.login()
print(f"OK - {SITE.username()}\n")

for title in test_titles:
    print("\n" + "=" * 60)
    print(f"VOCE: {title}")
    print("=" * 60)
    
    try:
        page = pywikibot.Page(SITE, title)
        
        # 1. Verifica esistenza
        if not page.exists():
            print("❌ La voce NON ESISTE (è stata cancellata?)")
            continue
        
        print("✓ La voce esiste")
        
        # 2. Verifica se è redirect
        if page.isRedirectPage():
            print("❌ La voce è un REDIRECT")
            target = page.getRedirectTarget()
            print(f"   Punta a: {target.title()}")
            continue
        
        print("✓ Non è un redirect")
        
        # 3. Verifica namespace
        ns = page.namespace()
        if ns != 0:
            print(f"❌ Namespace SBAGLIATO: {ns} (deve essere 0)")
            continue
        
        print("✓ Namespace corretto (0)")
        
        # 4. Verifica data creazione
        try:
            oldest = page.oldest_revision
            created_time = oldest.timestamp
            print(f"✓ Data creazione: {created_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Confronta con orario bot
            bot_time_str = "2026-02-28 21:58:00"
            bot_time = datetime.strptime(bot_time_str, '%Y-%m-%d %H:%M:%S')
            
            if created_time > bot_time:
                print(f"❌ Creata DOPO l'esecuzione del bot!")
                print(f"   Bot eseguito: {bot_time_str}")
                print(f"   Voce creata: {created_time.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print(f"✓ Creata PRIMA dell'esecuzione del bot")
        except Exception as e:
            print(f"❌ Errore nel recupero data: {e}")
        
        # 5. Verifica categorie
        try:
            cats = list(page.categories())
            print(f"✓ Categorie: {len(cats)}")
            if cats:
                for cat in cats[:5]:
                    print(f"   - {cat.title(with_ns=False)}")
                if len(cats) > 5:
                    print(f"   ... e altre {len(cats) - 5}")
        except Exception as e:
            print(f"⚠ Errore categorie: {e}")
        
        # 6. Verifica contenuto
        try:
            content = page.text
            print(f"✓ Contenuto: {len(content)} caratteri")
        except Exception as e:
            print(f"❌ Errore lettura contenuto: {e}")
        
        # 7. Verifica in RecentChanges
        print("\n🔍 Verifica in RecentChanges...")
        params = {
            'action': 'query',
            'list': 'recentchanges',
            'rctype': 'new',
            'rcnamespace': 0,
            'rctitle': title,
            'rclimit': 1,
            'rcprop': 'title|timestamp',
            'format': 'json'
        }
        
        try:
            request = SITE.simple_request(**params)
            data = request.submit()
            
            if 'query' in data and 'recentchanges' in data['query']:
                changes = data['query']['recentchanges']
                if changes:
                    print(f"✓ Trovata in RecentChanges")
                    print(f"   Timestamp: {changes[0]['timestamp']}")
                else:
                    print("❌ NON trovata in RecentChanges (troppo vecchia?)")
            else:
                print("⚠ RecentChanges non disponibile")
        except Exception as e:
            print(f"⚠ Errore RecentChanges: {e}")
        
    except Exception as e:
        print(f"❌ ERRORE GENERALE: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 60)
print("POSSIBILI CAUSE SE LE VOCI ESISTONO:")
print("=" * 60)
print("1. Create DOPO l'esecuzione del bot")
print("2. Erano redirect quando il bot ha girato")
print("3. Sono state cancellate e ricreate")
print("4. Il bot ha avuto un errore durante il download")
print("5. Limite API raggiunto (bot ha scaricato solo 2000 voci)")
print("\nSOLUZIONE: Riesegui il bot per aggiornare la cache")
