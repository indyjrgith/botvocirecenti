#!/usr/bin/env python3
"""
ResetCache.py - Svuota rapidamente tutti i file cache di VociRecenti

Scrive una struttura Lua vuota e valida in ogni file Dati esistente
(Dati1, Dati2, ...) finché ne trova. Si ferma al primo file non esistente.

Uso: python3 ResetCache.py
"""

import pywikibot
import pywikibot.config as config

# ========================================
# CONFIGURAZIONE (identica al bot)
# ========================================

DATA_PAGE_PREFIX = 'Modulo:VociRecenti/Dati'
TIMEOUT = 300
# ========================================


SITE = pywikibot.Site('it', 'wikipedia')

EMPTY_LUA = """\
-- File cache svuotato da ResetCache.py
return {
  u = [[(vuoto)]],
  v = [[reset]],
  p = 1,
  tp = 1,
  n = 0,
  d = {}
}
"""


def main():
    print("=" * 60)
    print("ResetCache.py - Svuotamento cache VociRecenti")
    print("=" * 60)

    print(f"\nLogin come {BOT_USERNAME}...")
    try:
        if not SITE.logged_in():
            SITE.login()
        print(f"OK - Login: {SITE.username()}\n")
    except Exception as e:
        print(f"ERRORE login: {e}")
        return

    svuotati = 0
    i = 1

    while True:
        page_name = f"{DATA_PAGE_PREFIX}{i}"
        page = pywikibot.Page(SITE, page_name)

        if not page.exists():
            print(f"  {page_name}: non esiste, stop.")
            break

        print(f"  [{i}] Svuotamento {page_name}...", end=' ', flush=True)
        try:
            page.text = EMPTY_LUA
            page.save(
                summary='Bot: Reset cache VociRecenti',
                minor=False,
                bot=True
            )
            svuotati += 1
            print("OK")
        except Exception as e:
            print(f"ERRORE: {e}")

        i += 1

    print(f"\n{'=' * 60}")
    print(f"Completato: {svuotati} file svuotati.")
    print(f"Esegui ora il bot principale per ricostruire la cache.")
    print("=" * 60)


if __name__ == '__main__':
    main()
