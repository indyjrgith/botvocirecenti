# Guida Rapida - Parametro Disp del Template VociRecenti

## Modalità di Visualizzazione

Il parametro `Disp` controlla come vengono mostrate le voci nell'output del template.

### Riepilogo Modalità

| Codice | Nome | Descrizione | Numerazione | Data |
|--------|------|-------------|-------------|------|
| `s` | Standard | Solo voce con numero d'ordine | Sì (1, 2, 3...) | No |
| `v` | Verbose | Voce, numero e data | Sì (1, 2, 3...) | Sì (piccola) |
| `o` | Only date | Voce e data senza numero | No (bullet point) | Sì (piccola) |
| `t` | Title only | Solo titolo voce | No (bullet point) | No |

---

## Esempi Pratici

### Modalità s (Standard) - DEFAULT
```wikitext
{{VociRecenti|num=5|Disp=s}}
```

**Output:**
```
1. [[Prima voce]]
2. [[Seconda voce]]
3. [[Terza voce]]
4. [[Quarta voce]]
5. [[Quinta voce]]
```

**Quando usarla:**
- Liste semplici e pulite
- Quando la data non è importante
- Presentazioni formali

---

### Modalità v (Verbose)
```wikitext
{{VociRecenti|num=5|Disp=v}}
```

**Output:**
```
1. [[Prima voce]] (15/02/2025 18:30)
2. [[Seconda voce]] (15/02/2025 17:45)
3. [[Terza voce]] (15/02/2025 16:20)
4. [[Quarta voce]] (15/02/2025 15:10)
5. [[Quinta voce]] (15/02/2025 14:55)
```

**Quando usarla:**
- Monitoraggio temporale
- Verificare l'ordine cronologico
- Liste complete con tutte le info

---

### Modalità o (Only date)
```wikitext
{{VociRecenti|num=5|Disp=o}}
```

**Output:**
```
• [[Prima voce]] (15/02/2025 18:30)
• [[Seconda voce]] (15/02/2025 17:45)
• [[Terza voce]] (15/02/2025 16:20)
• [[Quarta voce]] (15/02/2025 15:10)
• [[Quinta voce]] (15/02/2025 14:55)
```

**Quando usarla:**
- In sidebar o box informativi
- Quando la numerazione non serve
- Liste più compatte visivamente

---

### Modalità t (Title only)
```wikitext
{{VociRecenti|num=5|Disp=t}}
```

**Output:**
```
• [[Prima voce]]
• [[Seconda voce]]
• [[Terza voce]]
• [[Quarta voce]]
• [[Quinta voce]]
```

**Quando usarla:**
- Massima pulizia visiva
- Box di navigazione
- Template molto compatti
- Quando serve solo l'elenco

---

## Casi d'Uso Reali

### 1. Pagina Portale - Sezione "Novità"
```wikitext
=== Ultime voci create ===
{{VociRecenti|num=10|OrCat=Fisica,Matematica,Chimica|Disp=t}}
```
Usa **t** per un box pulito senza date

### 2. Progetto Tematico - Monitoraggio
```wikitext
== Nuove biografie da controllare ==
{{VociRecenti|num=20|AndCat=Biografie|Disp=v}}
```
Usa **v** per vedere quando sono state create

### 3. Pagina Utente - Lista personale
```wikitext
=== Voci da rivedere ===
{{VociRecenti|num=15|Text=stub|Disp=o}}
```
Usa **o** per avere date senza numerazione

### 4. Template in Sidebar
```wikitext
{{Box
|titolo=Novità
|contenuto={{VociRecenti|num=5|AndCat=Categoria|Disp=t}}
}}
```
Usa **t** per massima compattezza

### 5. Pagina di Discussione Progetto
```wikitext
=== Da patrollare ===
{{VociRecenti|num=25|OrCat=Da controllare,Senza fonti|Disp=v}}
```
Usa **v** per info complete

---

## Combinazioni con Altri Parametri

### Esempio 1: Biografie recenti degli ultimi 30 giorni
```wikitext
{{VociRecenti
|num=15
|AndCat=Biografie
|DataFine=15/01/2025
|Disp=v
}}
```

### Esempio 2: Voci su calcio senza date
```wikitext
{{VociRecenti
|num=10
|OrCat=Calciatori,Società calcistiche,Stadi
|Disp=s
}}
```

### Esempio 3: Lista compatta per navigazione
```wikitext
{{VociRecenti
|num=8
|Text=premio Nobel
|Disp=t
}}
```

### Esempio 4: Monitoraggio con regex
```wikitext
{{VociRecenti
|num=20
|TextRegExp=\d{4}\s*-\s*\d{4}
|Disp=o
}}
```

---

## Consigli di Scelta

### Usa **s** (standard) quando:
✓ Vuoi una lista formale numerata
✓ La data di creazione non è rilevante
✓ Serve un elenco pulito e professionale

### Usa **v** (verbose) quando:
✓ Stai monitorando l'attività
✓ Serve sapere quando le voci sono state create
✓ Vuoi tutte le informazioni disponibili

### Usa **o** (only date) quando:
✓ La numerazione non aggiunge valore
✓ Vuoi date ma in modo più compatto
✓ Stai creando sidebar o box informativi

### Usa **t** (title only) quando:
✓ Serve massima pulizia visiva
✓ Stai creando menu di navigazione
✓ Lo spazio è limitato
✓ Le voci parlano da sole

---

## Differenze Visive

```
┌─────────────────────────────────────────┐
│ Disp=s (Standard)                       │
├─────────────────────────────────────────┤
│ 1. [[Voce A]]                           │
│ 2. [[Voce B]]                           │
│ 3. [[Voce C]]                           │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ Disp=v (Verbose)                        │
├─────────────────────────────────────────┤
│ 1. [[Voce A]] (15/02/2025 18:30)       │
│ 2. [[Voce B]] (15/02/2025 17:45)       │
│ 3. [[Voce C]] (15/02/2025 16:20)       │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ Disp=o (Only date)                      │
├─────────────────────────────────────────┤
│ • [[Voce A]] (15/02/2025 18:30)        │
│ • [[Voce B]] (15/02/2025 17:45)        │
│ • [[Voce C]] (15/02/2025 16:20)        │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ Disp=t (Title only)                     │
├─────────────────────────────────────────┤
│ • [[Voce A]]                            │
│ • [[Voce B]]                            │
│ • [[Voce C]]                            │
└─────────────────────────────────────────┘
```

---

## Tabella Riepilogativa Completa

| Aspetto | s | v | o | t |
|---------|---|---|---|---|
| Numero d'ordine | ✓ | ✓ | ✗ | ✗ |
| Data creazione | ✗ | ✓ | ✓ | ✗ |
| Bullet point | ✗ | ✗ | ✓ | ✓ |
| Numerazione | # | # | * | * |
| Compattezza | ★★★ | ★ | ★★ | ★★★★ |
| Informazioni | ★ | ★★★★ | ★★★ | ★ |

---

## Default

Se il parametro `Disp` viene omesso o ha un valore non valido, il template usa automaticamente `Disp=s` (standard).

**Valori non validi:** Qualsiasi valore diverso da s, v, o, t viene ignorato e si usa la modalità standard.

---

## Note sulla Data

Quando la data viene visualizzata (modalità `v` e `o`):
- Formato: GG/MM/AAAA HH:MM
- Font: small (più piccolo del testo normale)
- Colore: grigio scuro (inherit, dipende dal tema)
- Posizione: Tra parentesi dopo il titolo della voce

---

## FAQ

**Q: Posso cambiare il formato della data?**
A: No, il formato è fisso (GG/MM/AAAA HH:MM) nel modulo.

**Q: Posso usare Disp=v ma senza i numeri?**
A: No, usa Disp=o che ha date ma senza numeri.

**Q: Posso avere numeri senza bullet point in modalità t?**
A: No, usa Disp=s che ha numeri ma niente date.

**Q: Cosa succede se scrivo Disp=V (maiuscolo)?**
A: Il modulo normalizza in minuscolo, quindi funziona.

**Q: Posso personalizzare il formato?**
A: Sì, modificando il modulo Lua, ma non tramite parametri.
