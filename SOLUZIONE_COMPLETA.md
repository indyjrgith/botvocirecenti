# Soluzione VociRecenti per Wikipedia italiana (senza DPL)

## Il Problema

Su Wikipedia italiana (e sulla maggior parte delle wiki), l'estensione **DynamicPageList (DPL)** non è disponibile per problemi di prestazioni. Inoltre, i moduli Lua (Scribunto) **non possono accedere direttamente alle API MediaWiki** per motivi di sicurezza.

## La Soluzione: Bot + Cache

La soluzione funzionante consiste in un **sistema a due componenti**:

1. **Bot Python** che aggiorna periodicamente una pagina dati
2. **Modulo Lua** che legge quella pagina e filtra i risultati

```
┌─────────────┐         ┌──────────────────┐         ┌──────────────┐
│   Bot       │ API     │ Modulo:VociRecen-│ legge   │  Template:   │
│   Python    ├────────>│ ti/Dati          │<────────┤  VociRecenti │
│ (ogni ora)  │aggiorna │ (cache)          │         │              │
└─────────────┘         └──────────────────┘         └──────────────┘
```

## Componenti del Sistema

### 1. Bot Python (`bot_voci_recenti.py`)

**Funzione:**
- Si esegue periodicamente (es. ogni ora via cron)
- Recupera le ultime 500 pagine create tramite API MediaWiki
- Estrae: titolo, timestamp, categorie, estratto contenuto
- Salva i dati in formato Lua su `Modulo:VociRecenti/Dati`

**Vantaggi:**
- Usa le API MediaWiki liberamente (non è limitato come Lua)
- Può elaborare molte pagine
- Riduce il carico sul server (cache)

### 2. Modulo Lua (`Modulo:VociRecenti`)

**Funzione:**
- Legge i dati da `Modulo:VociRecenti/Dati` (velocissimo)
- Applica i filtri richiesti dall'utente
- Genera la tabella HTML

**Vantaggi:**
- Nessuna chiamata API a runtime
- Performance eccellenti
- Funziona con Scribunto standard

### 3. Pagina Dati (`Modulo:VociRecenti/Dati`)

**Funzione:**
- Cache in formato Lua (mw.loadData)
- Contiene lista pagine recenti pre-elaborata
- Aggiornata dal bot

**Formato:**
```lua
return {
  ultimo_aggiornamento = '15/02/2025 18:30',
  voci = {
    {
      titolo = 'Nome voce',
      timestamp = '20250215183000',
      categorie = {'Cat1', 'Cat2'},
      contenuto = 'estratto...'
    },
    -- altre voci...
  }
}
```

## Installazione Passo-Passo

### STEP 1: Installa il Modulo Lua

1. Vai su https://it.wikipedia.org/wiki/Modulo:VociRecenti
2. Crea la pagina con il contenuto di `Modulo_VociRecenti_ConBot.lua`
3. Salva

### STEP 2: Installa il Template

1. Vai su https://it.wikipedia.org/wiki/Template:VociRecenti
2. Crea con questo contenuto:

```wikitext
<includeonly>{{#invoke:VociRecenti|main}}</includeonly><noinclude>
Vedi [[Template:VociRecenti/Documentazione]]
</noinclude>
```

3. Salva

### STEP 3: Crea la Pagina Dati (temporanea)

1. Vai su https://it.wikipedia.org/wiki/Modulo:VociRecenti/Dati
2. Crea con il contenuto di `Modulo_VociRecenti_Dati_esempio.lua`
3. Questo è solo per testare - sarà sovrascritto dal bot

### STEP 4: Testa il Template

Crea una pagina di test:
```wikitext
{{VociRecenti|num=5}}
```

Dovresti vedere i dati di esempio.

### STEP 5: Configura il Bot

#### Requisiti:
```bash
pip install pywikibot
```

#### Configurazione:
```bash
# Genera file di configurazione
python pwb.py generate_user_files

# Segui le istruzioni:
# - Family: wikipedia
# - Language: it
# - Username: NomeDelTuoBot
# - Password: (inserisci)
```

#### Esecuzione manuale:
```bash
python bot_voci_recenti.py
```

#### Esecuzione automatica (cron):
```bash
# Apri crontab
crontab -e

# Aggiungi questa riga per eseguire ogni ora
0 * * * * cd /percorso/bot && python3 bot_voci_recenti.py >> bot.log 2>&1
```

### STEP 6: Test Finale

Dopo che il bot ha eseguito almeno una volta:
```wikitext
{{VociRecenti|num=10|AndCat=Biografie}}
```

Dovresti vedere voci reali e recenti!

## Utilizzo del Template

### Sintassi completa:
```wikitext
{{VociRecenti
|num=10
|AndCat=Categoria1,Categoria2
|OrCat=CategoriaA,CategoriaB
|Text=testo da cercare
|TextRegExp=pattern regex
|DataFine=01/01/2025
}}
```

### Esempi pratici:

#### Ultime 20 biografie:
```wikitext
{{VociRecenti|num=20|AndCat=Biografie}}
```

#### Voci su fisica O chimica:
```wikitext
{{VociRecenti|num=15|OrCat=Fisica,Chimica}}
```

#### Calciatori italiani con "Serie A":
```wikitext
{{VociRecenti|num=10|AndCat=Calciatori italiani|Text=Serie A}}
```

#### Con data limite:
```wikitext
{{VociRecenti|num=25|DataFine=01/02/2025}}
```

#### Con regex (trova anni nel formato AAAA-AAAA):
```wikitext
{{VociRecenti|num=10|TextRegExp=\d{4}\s*[-–]\s*\d{4}}}
```

## Personalizzazione

### Modificare il numero di voci nel cache

Nel bot, cambia:
```python
MAX_PAGES = 500  # Aumenta per più voci (max ~1000)
```

### Modificare la frequenza di aggiornamento

Nel cron:
```bash
# Ogni 30 minuti:
*/30 * * * * cd /percorso/bot && python3 bot_voci_recenti.py

# Ogni 2 ore:
0 */2 * * * cd /percorso/bot && python3 bot_voci_recenti.py
```

### Filtrare namespace diversi

Nel bot, cambia:
```python
NAMESPACE = 0  # 0=principale, 2=utente, 4=Wikipedia, ecc.
```

### Escludere redirect

Il bot già li esclude di default. Per includerli:
```python
if page.isRedirectPage():
    continue  # <-- Rimuovi questa riga
```

## Vantaggi di questa Soluzione

✅ **Funziona su qualsiasi Wikipedia** (non serve DPL)
✅ **Performance eccellenti** (usa cache)
✅ **Supporta tutti i filtri richiesti** (AND, OR, regex, date)
✅ **Scalabile** (può gestire molte pagine)
✅ **Manutenibile** (facile aggiornare il bot)

## Svantaggi e Limitazioni

⚠️ **Richiede un bot** con credenziali e server
⚠️ **Latenza** (aggiornamento ogni ora, non real-time)
⚠️ **Contenuto limitato** (solo primi 500 caratteri per regex)

## Alternative se Non Puoi Usare un Bot

### Opzione A: Aggiornamento Manuale
Aggiorna manualmente `Modulo:VociRecenti/Dati` copiando da [[Speciale:PaginePiùRecenti]]

### Opzione B: JavaScript Lato Client
Implementa il recupero nel browser dell'utente:
```javascript
// Carica via API quando la pagina viene visualizzata
new mw.Api().get({
    action: 'query',
    list: 'recentchanges',
    rctype: 'new',
    rclimit: 50
}).done(function(data) {
    // Mostra risultati
});
```

### Opzione C: Gadget con API
Crea un Gadget che ogni utente può attivare per vedere dati live

### Opzione D: Usare Template Statici
Crea template come `{{VociRecenti/Febbraio2025}}` aggiornati manualmente

## Monitoring e Manutenzione

### Verificare l'ultimo aggiornamento:
Vai su https://it.wikipedia.org/wiki/Modulo:VociRecenti/Dati
Controlla la riga `ultimo_aggiornamento`

### Log del bot:
```bash
tail -f bot.log
```

### Se il bot si blocca:
1. Controlla le credenziali
2. Verifica la connessione
3. Controlla i permessi del bot su Wikipedia
4. Leggi i log di errore

### Alert automatici:
Aggiungi al bot:
```python
import smtplib

def send_alert(message):
    # Invia email se il bot fallisce
    pass
```

## Permessi Necessari per il Bot

Il bot ha bisogno di:
- ✅ **Bot flag** (richiedi agli admin)
- ✅ **Permesso di edit** su namespace Module
- ✅ **Permesso API** (di default)

Per richiedere bot flag:
https://it.wikipedia.org/wiki/Wikipedia:Bot/Richieste

## FAQ

**Q: Il template mostra "Configurazione necessaria"**
A: Il bot non ha ancora aggiornato la pagina dati o la pagina non esiste.

**Q: Posso usare questo su altre wiki?**
A: Sì! Cambia semplicemente `SITE = pywikibot.Site('it', 'wikipedia')` nel bot.

**Q: Quanto costa far girare il bot?**
A: Gratis! Può girare su qualsiasi server/VPS o anche su Heroku/AWS free tier.

**Q: E se Wikipedia blocca il bot?**
A: Rispetta i rate limits (il bot ne usa pochissimi) e avrai il bot flag.

**Q: Posso contribuire al codice?**
A: Sì! Il codice è open source. Crea una pagina `/Bot/Codice` su Wikipedia.

## Supporto

Per problemi:
1. [[Discussioni template:VociRecenti]]
2. [[Wikipedia:Bar tecnico]]
3. [[Wikipedia:Bot/Richieste]]

## Crediti

Soluzione sviluppata per ovviare alla mancanza di DPL su Wikipedia italiana.
Basato su pattern comuni usati su altre wiki e sistemi di caching.
