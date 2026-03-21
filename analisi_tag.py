#!/usr/bin/env python3
"""
Verifica tag disponibili e tag delle voci specifiche
"""

import pywikibot
import pywikibot.config as config

BOT_USERNAME = 'IndyJrBot@Pywikibot'
BOT_PASSWORD = 't1ej4nl6vp6up1fvqlu44n7da1m5j90d'

config.authenticate['it.wikipedia.org'] = (BOT_USERNAME, BOT_PASSWORD)
config.usernames['wikipedia']['it'] = BOT_USERNAME.split('@')[0]

SITE = pywikibot.Site('it', 'wikipedia')

if not SITE.logged_in():
    SITE.login()

print("=" * 60)
print("ANALISI TAG")
print("=" * 60)

# 1. Lista tutti i tag disponibili
print("\n1. Tag disponibili su it.wiki:")
params = {
    'action': 'query',
    'list': 'tags',
    'tglimit': 100,
    'format': 'json'
}

request = SITE.simple_request(**params)
data = request.submit()

if 'query' in data and 'tags' in data['query']:
    tags = data['query']['tags']
    print(f"   Totale: {len(tags)} tag\n")
    for tag in tags[:20]:  # Primi 20
        print(f"   - {tag['name']}")

# 2. Tag delle nostre due voci
print("\n" + "=" * 60)
print("2. Tag delle voci specifiche:")
print("=" * 60)

for title in ['Grimpella thaumastocheir', 'Megaleledone setebos']:
    print(f"\n{title}:")
    
    # Cerca le ultime modifiche a questa voce
    params = {
        'action': 'query',
        'list': 'recentchanges',
        'rctitle': title,
        'rclimit': 10,
        'rcprop': 'title|timestamp|tags|comment',
        'format': 'json'
    }
    
    request = SITE.simple_request(**params)
    data = request.submit()
    
    if 'query' in data and 'recentchanges' in data['query']:
        changes = data['query']['recentchanges']
        print(f"  Trovate {len(changes)} modifiche recenti:")
        
        for i, ch in enumerate(changes[:5], 1):
            print(f"\n  Modifica {i}:")
            print(f"    Timestamp: {ch.get('timestamp')}")
            print(f"    Comment: {ch.get('comment', '')[:100]}")
            print(f"    Tags: {ch.get('tags', [])}")

# 3. Cerca modifiche recenti in NS0 per vedere quali tag appaiono
print("\n" + "=" * 60)
print("3. Sample tag in modifiche NS0 recenti:")
print("=" * 60)

params = {
    'action': 'query',
    'list': 'recentchanges',
    'rcnamespace': 0,
    'rclimit': 50,
    'rcprop': 'title|tags|comment',
    'format': 'json'
}

request = SITE.simple_request(**params)
data = request.submit()

tag_count = {}
if 'query' in data and 'recentchanges' in data['query']:
    for ch in data['query']['recentchanges']:
        for tag in ch.get('tags', []):
            tag_count[tag] = tag_count.get(tag, 0) + 1
        
        # Mostra quelle con "origin" o "ricre" nel commento
        comment = ch.get('comment', '').lower()
        if 'origin' in comment or 'ricre' in comment or 'sandbox' in comment:
            print(f"\n  {ch['title']}:")
            print(f"    Comment: {comment[:80]}")
            print(f"    Tags: {ch.get('tags', [])}")

print(f"\n\nTag più comuni nelle ultime 50 modifiche:")
for tag, count in sorted(tag_count.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f"  {tag}: {count}")
