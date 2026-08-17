-- Modulo:VociRecenti
-- Versione 8.51 - Rilascio esplicito dei moduli DatiN durante lo streaming:
--                dopo l'elaborazione di ogni DatiN, il modulo viene rimosso da
--                package.loaded. NON usa collectgarbage(), che non è disponibile
--                nell'ambiente Lua di Scribunto. L'eliminazione da package.loaded
--                rimuove il riferimento mantenuto da require(); gli eventuali
--                oggetti non più referenziati possono quindi essere recuperati
--                automaticamente dal garbage collector di Scribunto.
--                Mantiene il filtraggio streaming della 8.49, senza cambiare
--                la logica dei filtri o il formato dell'output.
-- Versione 8.49 - Filtraggio streaming per cache grandi:
--                con Order=Data, Timestamp=off e senza First esplicito, ogni
--                DatiN viene filtrato durante il caricamento e la lettura si
--                ferma al raggiungimento di Num risultati. Evita allVoci e
--                filtered completi nelle pagine con molte istanze filtrate.
-- Versione 8.46 - FIX sintassi /Nome/ (slash) non riconosciuta in Portali= e OrPortali=:
--                matchesPortali e matchesOrPortali confrontano i termini cercati
--                direttamente contro i parametri del template Portale/Portali tramite
--                contains(), che non conosce la sintassi slash. Il termine /storia/
--                veniva cercato letteralmente (con gli slash) nei parametri, che
--                contengono solo "storia", causando sempre un mancato match.
--                Fix: aggiunta funzione matchPortaleParam() che rileva la sintassi
--                /Nome/ (esatto), "Nome" (parola intera) e Nome (sottostringa),
--                usata al posto di contains() nei due punti di matchesPortali e
--                matchesOrPortali. Overhead nullo: il rilevamento slash/virgolette
--                avviene una volta per termine, fuori dal loop sui parametri.
-- Versione 8.45 - FIX falsi positivi nei filtri sui template (NoTemplate, AndTemplate,
--                OrTemplate, Portali, OrPortali): il match per sottostringa e il match
--                "parola intera" (tra virgolette, es. "Libro") matchavano anche template
--                il cui nome contiene la parola cercata come token separato, es.
--                NoTemplate=Libro o NoTemplate="Libro" escludevano erroneamente anche le
--                voci con {{cita libro}}, non solo quelle con {{Libro}}.
--                Aggiunta nuova sintassi /Nome/ (slash) per il match ESATTO sull'intero
--                nome del template: NoTemplate=/Libro/ esclude solo {{Libro}}, lasciando
--                {{cita libro}} non filtrato. Gli underscore nel nome tra slash vengono
--                normalizzati come spazi prima del confronto (es. /cita_libro/ combacia
--                con {{cita libro}}), coerentemente con la normalizzazione dei nomi
--                pagina/template di MediaWiki. La sintassi esistente tra virgolette
--                (match parola intera dentro il nome) non è stata modificata.
-- Versione 8.44 - Nuovo parametro |First=N: limita le voci caricate alle prime N
--                della cache (le più recenti, nell'ordine in cui il bot le ha scritte),
--                riducendo RAM e CPU proporzionalmente. Il caricamento si interrompe
--                appena raggiunte N voci, senza allocare il resto della cache.
--                Con First= valorizzato la memoizzazione è disabilitata per quell'istanza
--                (istanze diverse possono avere N diversi). Senza First= il comportamento
--                è identico alle versioni precedenti, memoizzazione inclusa: più template
--                senza First= sulla stessa pagina continuano a condividere la cache.
-- Versione 8.43 - Ottimizzazioni performance (nessuna modifica alla logica):
--                1) splitParens fast-path: se la stringa non contiene '(' usa split()
--                   diretto (caso più comune: nessun not(...) nel parametro),
--                   evitando l'intero loop di analisi parentesi.
--                2) getArgs: sostituito mw.ustring.lower con string.lower per le chiavi
--                   parametro template (sempre ASCII).
--                3) contains() refactoring: introdotti parseNeedle() e containsParsed()
--                   per separare il parsing del needle (una volta) dal match (per ogni
--                   haystack). matchesAndCat, matchesOrCat, matchesNoCat pre-lowercasano
--                   l'array categorie una sola volta fuori dal loop termini, eliminando
--                   N×M chiamate a mw.ustring.lower (il hot path più costoso).
--                4) matchesExclIfNotCat: pre-lowercase categorie + string.find per '>'
--                   (ASCII), eliminando mw.ustring.find/sub per il separatore.
--                5) matchesSingleTemplate: string.lower per nomi template (ASCII),
--                   rimosso doppio mw.ustring.lower ridondante nel ramo portale/portali.
--                6) buildSearchable guard nel ramo And=on: costruisce la stringa solo se
--                   regexPattern ~= ''. Early exit nel ramo And=off per i veto finali
--                   (noCat, hNoCat, noTemplate, exclIfNotCat): saltati se matches=false.
-- Versione 8.41 - FIX ordinamento Order=Data e Order=Dataold: entrambi usavano sempre
--                voce[2] (timestamp di creazione) per il confronto, ignorando voce[6]
--                (move_timestamp) per le voci spostate da altro namespace. Questo causava
--                un ordine disallineato rispetto alle date visualizzate (che già usavano
--                voce[6] tramite formatTimestampDisplay). Fix: entrambi i sort usano ora
--                lo stesso timestamp visualizzato: voce[6] se presente e non vuoto,
--                altrimenti voce[2]. Aggiunto inoltre sort esplicito per Order=Data
--                (in precedenza si affidava all'ordine implicito della cache, che poteva
--                non essere garantito dopo merge parziali dei file Dati).
-- Versione 8.40 - Categorie nascoste: il 7° campo del formato cache (voce[7])
--                contiene le categorie nascoste, distinte da quelle visibili (voce[3]).
--                Nuovi parametri HAndCat, HOrCat, HNoCat: operano su voce[7]
--                con la stessa logica di AndCat, OrCat, NoCat (incluso not()).
--                NoCat=* e tutti gli altri parametri esistenti operano solo sulle
--                categorie visibili (voce[3]), correggendo il caso in cui una voce
--                senza categorie visibili ma con categorie nascoste non veniva
--                segnalata da NoCat=*.
--                Retrocompatibilita': cache prodotte dal bot v9.1.x (senza voce[7])
--                restituiscono {} per voce[7] tramite il fallback nel loadAllData.
-- Versione 8.39 - FIX calcDaysRange: il conteggio dei giorni ora usa lo stesso timestamp
--                visualizzato dalla voce (move_timestamp se presente, altrimenti timestamp
--                di creazione), coerentemente con formatTimestampDisplay. In precedenza
--                veniva usato sempre e solo voce[2] (timestamp di creazione), ignorando
--                voce[6] (move_timestamp) per le voci spostate da altro namespace,
--                causando un calcolo dei giorni disallineato rispetto alle date mostrate.
-- Versione 8.38 - Visualizzazione corsivo per voci spostate da altro namespace.
-- Versione 8.37 - FIX loadAllData: nel ramo di normalizzazione formato "vecchio" (voce.titolo),
--                voce[4] (template) era sempre impostato a {} (tabella vuota), ignorando
--                completamente voce.template. Questo causava il mancato funzionamento di
--                NoTemplate=Categorizzare (e qualunque filtro su template: AndTemplate,
--                OrTemplate, NoTemplate, Portali, OrPortali) quando la cache è nel formato
--                con campi nominati (titolo/timestamp/categorie/template/contenuto).
--                Con voce[4]={} ogni voce risultava priva di template, quindi
--                matchesNoTemplate restituiva sempre true e le voci con {{Categorizzare}}
--                non venivano escluse. Corretto: voce[4] = voce.template or {}.
-- Versione 8.36 - FIX formatTimestamp: rimossa sigla "UTC" dall'orario delle voci
--                (introdotta in v8.19 quando i timestamp erano effettivamente UTC).
--                La correzione del fuso orario è avvenuta nel bot di aggiornamento
--                cache: i timestamp scritti in cache sono ora in ora locale, quindi
--                la sigla "UTC" era diventata scorretta. La rimozione era già stata
--                pianificata ma non era mai confluita in una versione pubblicata.
-- Versione 8.35 - FIX timestamp fuori dalle colonne: in v8.34 column-span:all era
--                applicato al tag <small> che è inline — i browser ignorano
--                column-span su elementi inline. Avvolto il <small> in un <div>
--                block-level, su cui column-span:all ha effetto. La modifica è
--                centralizzata in buildTimestampLine e copre automaticamente tutti
--                i casi (nessuna voce trovata, scrollbox, display h, display normale).
-- Versione 8.34 - FIX layout multicolonna: aggiunto column-span:all ai div di avviso
--                (cache non inizializzata, cache vuota, nessuna voce trovata) e alla
--                riga "Ultimo aggiornamento". Senza questo stile, quando il template
--                è avvolto in un <div style="column-count:N"> il contenuto veniva
--                distribuito nelle colonne spezzando i box di avviso.
--                column-span:all forza questi elementi a occupare l'intera larghezza
--                del contenitore, ignorando la suddivisione in colonne.
-- Versione 8.33 - FIX not() con sotto-termini multipli in AndCat, OrCat, NoCat:
--                il valore inner estratto da parseNot (es. '"russa";"russi";"russia"')
--                veniva passato direttamente a contains() come stringa intera invece
--                di essere espanso in sotto-termini separati da ";" o ",".
--                Questo causava il mancato match: contains cercava letteralmente
--                la stringa '"russa";"russi";"russia"' nelle categorie, non la trovava,
--                e il not() risultava erroneamente soddisfatto.
--                Soluzione: nei rami isNot di matchesAndCat, matchesOrCat, matchesNoCat
--                l'inner viene ora espanso con split(inner, ';') e split(inner, ',')
--                (OR tra sotto-termini), replicando la logica già presente in
--                matchesPortali e matchesOrPortali dalla v8.30.
--                Esempi ora funzionanti:
--                  AndCat=ucrain,not("russa";"russi";"russia")
--                    -> ha cat con "ucrain" E nessuna cat con parola intera
--                       "russa", "russi" o "russia"
--                  OrCat=not(calcio;tennis)
--                    -> match se la voce non ha né "calcio" né "tennis"
-- Versione 8.32 - FIX not() con separatori interni (";", ",") in tutti i parametri
--                filtro: AndCat, OrCat, NoCat, AndTemplate, OrTemplate, NoTemplate,
--                Title, Text. La funzione split() usata per espandere i termini dentro
--                ogni gruppo spezzava ingenuamente sul separatore, senza rispettare i
--                caratteri che si trovano dentro parentesi tonde. Questo causava il
--                malfunzionamento di not(X;Y) e not(X,Y) in tutti i parametri tranne
--                Portali/OrPortali (che avevano già un percorso separato).
--                Esempio del bug: AndCat=ucrain,not("russa";"russi") veniva splittato
--                in tre token: not("russa"  /  "russi"  /  "russia") perdendo le
--                parentesi e rendendo il not() inoperante.
--                Soluzione: nuova funzione splitParens(str, sep) che ignora i
--                separatori dentro parentesi tonde. Sostituisce split() per tutti
--                gli split su "," e ";" nelle funzioni di matching.
--                Esempi ora funzionanti:
--                  AndCat=ucrain,not("russa";"russi","russia")
--                    -> ha cat con "ucrain" E nessuna cat con "russa","russi","russia"
--                  NoCat=not(Nati a Roma),Morti a Roma
--                    -> stesso comportamento di prima (non rotto, ora più robusto)
-- Versione 8.31 - (versione intermedia su Wikipedia, nessuna modifica documentata)
-- Versione 8.30 - FIX not() in Portali= e OrPortali=: supporto OR interno con ";"
--                dentro not(). Sintassi: not(radio;cinema) esclude le voci che hanno
--                il portale "radio" OPPURE il portale "cinema" (equivalente per De Morgan
--                a: non radio AND non cinema). In precedenza "radio;cinema" veniva trattato
--                come stringa letterale e non matchava nulla. Ora il separatore ";" viene
--                espanso in più condizioni NOT, coerentemente con il comportamento degli
--                altri parametri (AndCat, OrCat, ecc.).
--                Esempi:
--                  Portali=televisione,not(radio;cinema)
--                    -> portale televisione presente; né radio né cinema presenti
--                  OrPortali=sport,not(calcio;tennis)
--                    -> portale sport presente, oppure né calcio né tennis tra i portali
-- Versione 8.29 - FIX ExclIfNotCat: cambiato separatore trigger>eccezione da "~" a ">"
--                per maggiore accessibilità su tastiere italiane standard (Shift+.).
--                Sintassi aggiornata: ExclIfNotCat=Morti a Parigi>Nati a Parigi
-- Versione 8.28 - FIX ExclIfNotCat: cambiato separatore trigger~eccezione da "|" a "~"
--                per evitare che MediaWiki interpreti il pipe come separatore di parametro
--                template, troncando il valore e rendendo la regola non funzionante.
--                Sintassi aggiornata: ExclIfNotCat=Morti a Parigi~Nati a Parigi
-- Versione 8.27 - Aggiunto parametro |ExclIfNotCat=: esclude una voce se ha la categoria X
--                ma NON ha la categoria Y. Risolve il caso in cui una voce è collegata a un
--                argomento solo tramite una categoria "negativa" (es. morte in un luogo) senza
--                avere altri legami positivi con quell'argomento.
--                Sintassi: ExclIfNotCat=X>Y
--                  X = categoria trigger (sottostringa, case-insensitive)
--                  Y = categoria eccezione (sottostringa, case-insensitive)
--                  > = separatore obbligatorio tra trigger ed eccezione
--                  , = AND tra regole multiple
--                Significato: "escludi la voce se ha X, a meno che non abbia anche Y"
--                Esempi:
--                  ExclIfNotCat=Morti a Parigi>Nati a Parigi
--                    -> esclude chi è morto a Parigi ma non nato a Parigi
--                  ExclIfNotCat=Morti a Roma>Nati a Roma,Morti a Milano>Nati a Milano
--                    -> applica la regola in AND per due città distinte
--                Applicato sempre come veto finale (come NoCat), in entrambe le
--                modalità And=on e And=off.
-- Versione 8.26 - Supporto not() in tutti i parametri filtro: AndCat, OrCat, NoCat,
--                AndTemplate, OrTemplate, NoTemplate, Title, Text, Portali, OrPortali.
--                Sintassi: not(termine) nega il match del singolo termine nel contesto
--                del parametro in cui appare. Il termine interno supporta le virgolette
--                per match parola intera (es. not("morti")).
--                Esempi:
--                  AndCat=not(Nati a Parigi),morti a Parigi
--                    -> non nati a Parigi E morti a Parigi
--                  NoCat=not(Nati a Parigi),morti a Parigi
--                    -> escludi chi non ha "Nati a Parigi" (richiede positivamente
--                       quella cat) E escludi chi ha "morti a Parigi"
--                  AndCat=not("morti"),"nati"
--                    -> ha cat "nati" (parola intera) e non ha cat "morti"
-- Versione 8.25 - FIX matchesPortali/matchesOrPortali: sostituito mw.ustring.find
--                diretto con contains(), portando il supporto ai doppi apici per
--                match esatto anche su Portali= e OrPortali=. In precedenza termini
--                come "Cina" facevano match parziale su "medicina" causando falsi
--                positivi. Ora "Cina" (senza virgolette) fa ancora match parziale,
--                mentre '"Cina"' (con virgolette) cerca solo il portale esatto.
-- Versione 8.24 - FIX matchesPortali/matchesOrPortali: sostituita ricerca sottostringa
--                con confronto esatto tramite isPortaleTemplate() che riconosce sia
--                "portale" che "portali". Necessario perche string.find e mw.ustring.find
--                non trovano "portale" in "portali" su MediaWiki Lua (comportamento anomalo).
-- Versione 8.23 - FIX matchesPortali/matchesOrPortali: sostituito mw.ustring.find
--                con string.find per il controllo del nome template. mw.ustring.find
--                con plain=true su MediaWiki restituisce nil per sottostringhe in
--                posizione finale (es. cerca portale in portali -> nil). Risolve il
--                mancato match di {{portali}} nei filtri Portali= e OrPortali=.
-- Versione 8.22 - FIX debugVoce: legge i parametri da frame.args invece di
--                frame:getParent().args, corretto per chiamate #invoke dirette.
-- Versione 8.21 - Match parola intera: se il termine è racchiuso tra doppi apici
--                (es. OrCat="nati") cerca la parola esatta invece della sottostringa.
--                Funziona in tutti i parametri: OrCat, AndCat, NoCat, Title, Text,
--                AndTemplate, OrTemplate, NoTemplate. Case-insensitive come il match
--                normale. Es: OrCat="nati" trova "Nati in Italia" ma non "Campionati".
--                FIX: i doppi apici ora funzionano anche nel nome template (AndTemplate,
--                OrTemplate, NoTemplate) tramite matchesSingleTemplate aggiornato.
-- Versione 8.20 - FIX logica filtraggio con soli filtri negativi (NoCat/NoTemplate):
--                in modalità And=off, specificare solo NoCat= o NoTemplate= ora
--                funziona correttamente (mostra tutto tranne le voci escluse).
--                Aggiunto valore speciale "*" per NoCat e NoTemplate: esclude voci
--                che hanno almeno una categoria (NoCat=*) o almeno un template
--                (NoTemplate=*). Utile per trovare voci completamente spoglie.
-- Versione 8.19 - formatTimestamp: aggiunta sigla "UTC" accanto all'ora per chiarire
--                che i timestamp delle voci sono in UTC (non nel fuso orario locale).
-- Versione 8.18 - Aggiunto valore 'h' per Disp e DispScroll: visualizzazione orizzontale
--                delle voci separate da ' · ', senza data né numerazione.
--                DispScroll=h,NNN avvolge la lista in uno scrollbox orizzontale.
-- Versione 8.17 - Memoizzazione di loadAllData(): i file cache vengono caricati
--                una sola volta per pagina. Più template VociRecenti sulla stessa
--                pagina riusano i dati già in memoria, dimezzando il consumo RAM
--                in caso di template multipli e risolvendo l'errore OOM con cache grandi.
-- Versione 8.16 - Default di |And= cambiato da 'on' a 'off': in assenza del parametro
--                i filtri AndCat, OrCat, Title, Text, TextRegExp, AndTemplate, OrTemplate,
--                Portali, OrPortali vengono combinati in logica OR anziché AND.
-- Versione 8.15 - Aggiunto parametro |NoTemplate=: esclude voci che contengono almeno uno
--                dei template elencati. Stessa logica di NoCat: virgola = AND tra gruppi di
--                esclusione, punto e virgola = OR dentro ogni gruppo. Applicato sempre in AND
--                anche con And=off. Match parziale, case-insensitive.
-- Versione 8.14 - Parametro Title: supporto "+" come AND tra termini dentro ogni gruppo OR.
--                Sintassi: "riserva+darwin;oasi" -> (riserva AND darwin) OR oasi.
--                Il separatore ";" (OR tra gruppi) e "|" (via {{!}}) restano invariati.
-- Versione 8.13 - Supporto ";" come separatore OR nei parametri Title, Text,
--                AndCat, OrCat, NoCat, AndTemplate, OrTemplate.
--                Per AndCat/NoCat/AndTemplate la virgola separa gruppi AND,
--                il punto e virgola separa alternative OR dentro ogni gruppo.
--                Es: AndCat=parte1;parte2,parte3 -> (parte1 OR parte2) AND parte3
-- Versione 8.12 - (saltata per allineamento versioni)
-- Versione 8.11 - (saltata per allineamento versioni)
-- Versione 8.10 - Aggiunto parametro |DispScroll=: stessa logica di |Disp= ma il risultato
--               viene avvolto in uno scrollbox verticale. Sintassi: |DispScroll=v,300 (valore
--               disp + altezza in px, default 200px). DispScroll ha precedenza su Disp.
-- Versione 8.9 - Parametri del template ora case-insensitive: |Disp, |disp, |DISP sono equivalenti;
--               vale per tutti i parametri (And, AndCat, OrCat, NoCat, Title, Text, TextRegExp,
--               AndTemplate, OrTemplate, Portali, OrPortali, DataFine, Disp, Timestamp, Order,
--               CaseSensitive, num)
-- Versione 8.8 - Fix normalizzazione parametri: stringa vuota e 'off' trattati come assenza di valore
--               in tutti i filtri stringa (AndCat, OrCat, NoCat, Title, Text, TextRegExp, AndTemplate,
--               OrTemplate, Portali, OrPortali, DataFine); And='' ora usa correttamente il default (era 'on', ora 'off' dalla v8.16)
-- Versione 8.7 - Aggiunto parametro |OrPortali: logica OR sui portali (basta almeno uno presente);
--               il parametro |Portali esistente mantiene la logica AND (tutti devono essere presenti)
-- Versione 8.5 - Fix Order=Dateold/Alpha: usava campi keyword (a.timestamp, a.titolo) invece di array posizionale (a[2], a[1])
-- Legge automaticamente Dati1, Dati2, Dati3, ... (quanti ce ne sono)

local p = {}

-- Funzione per ottenere gli argomenti
local function getArgs(frame)
    local args = {}
    for k, v in pairs(frame:getParent().args) do
        if v ~= '' then
            -- I nomi parametro template sono sempre ASCII: string.lower è sufficiente e più veloce
            local key = type(k) == 'string' and string.lower(k) or k
            args[key] = v
        end
    end
    return args
end

-- Funzione per dividere stringhe
local function split(str, sep)
    local result = {}
    for match in (str..sep):gmatch("(.-)"..sep) do
        local trimmed = mw.text.trim(match)
        if trimmed ~= '' then
            table.insert(result, trimmed)
        end
    end
    return result
end

-- Funzione per dividere stringhe rispettando le parentesi tonde.
-- I separatori che si trovano dentro parentesi tonde (es. dentro not(...))
-- vengono ignorati e non producono uno split.
-- Usata al posto di split() in tutte le funzioni di matching, per gestire
-- correttamente not(X;Y) e not(X,Y) senza spezzare il not() in token distinti.
local function splitParens(str, sep)
    -- Fast-path: se non ci sono parentesi, usa split() diretto (caso più comune)
    if not string.find(str, '(', 1, true) then
        return split(str, sep)
    end
    local result = {}
    local depth = 0
    local tokenStart = 1
    local len = #str
    local i = 1
    -- Cerca solo i caratteri che contano: '(', ')', sep
    -- string.find è implementato in C: molto più veloce di str:sub(i,i) in loop Lua
    while i <= len do
        local c = str:sub(i, i)
        if c == '(' then
            depth = depth + 1
        elseif c == ')' then
            depth = depth - 1
            if depth < 0 then depth = 0 end
        elseif c == sep and depth == 0 then
            local token = mw.text.trim(str:sub(tokenStart, i - 1))
            if token ~= '' then
                table.insert(result, token)
            end
            tokenStart = i + 1
        end
        -- Salta al prossimo carattere significativo: '(', ')', sep, o fine stringa
        local next = string.find(str, '[()' .. sep .. ']', i + 1, false)
        i = next or (len + 1)
    end
    local token = mw.text.trim(str:sub(tokenStart))
    if token ~= '' then
        table.insert(result, token)
    end
    return result
end

-- Mappa caratteri accentati/diacritici -> base ASCII (per ordinamento alfabetico)
local diacriticMap = {
    ['à'] = 'a', ['á'] = 'a', ['â'] = 'a', ['ã'] = 'a', ['ä'] = 'a', ['å'] = 'a', ['ā'] = 'a', ['ă'] = 'a', ['ą'] = 'a',
    ['ç'] = 'c', ['ć'] = 'c', ['č'] = 'c',
    ['ď'] = 'd', ['đ'] = 'd',
    ['è'] = 'e', ['é'] = 'e', ['ê'] = 'e', ['ë'] = 'e', ['ē'] = 'e', ['ĕ'] = 'e', ['ę'] = 'e', ['ě'] = 'e',
    ['ğ'] = 'g',
    ['ì'] = 'i', ['í'] = 'i', ['î'] = 'i', ['ï'] = 'i', ['ī'] = 'i', ['ĭ'] = 'i', ['į'] = 'i',
    ['ł'] = 'l', ['ĺ'] = 'l', ['ļ'] = 'l', ['ľ'] = 'l',
    ['ñ'] = 'n', ['ń'] = 'n', ['ņ'] = 'n', ['ň'] = 'n',
    ['ò'] = 'o', ['ó'] = 'o', ['ô'] = 'o', ['õ'] = 'o', ['ö'] = 'o', ['ø'] = 'o', ['ō'] = 'o', ['ő'] = 'o',
    ['ř'] = 'r', ['ŕ'] = 'r',
    ['š'] = 's', ['ś'] = 's', ['ş'] = 's', ['ș'] = 's',
    ['ť'] = 't', ['ţ'] = 't', ['ț'] = 't',
    ['ù'] = 'u', ['ú'] = 'u', ['û'] = 'u', ['ü'] = 'u', ['ū'] = 'u', ['ŭ'] = 'u', ['ů'] = 'u', ['ű'] = 'u', ['ų'] = 'u',
    ['ý'] = 'y', ['ÿ'] = 'y',
    ['ž'] = 'z', ['ź'] = 'z', ['ż'] = 'z',
}

-- Normalizza una stringa per l'ordinamento: lowercase + rimozione diacritici
local function normalizeForSort(str)
    if not str then return '' end
    str = mw.ustring.lower(str)
    str = mw.ustring.gsub(str, '[^%z\1-\127]', function(c)
        return diacriticMap[c] or c
    end)
    return str
end

-- Funzione contains (case-insensitive, con supporto match parola intera tramite "...")
-- Se needle è racchiuso tra doppi apici (es. "nati"), cerca la parola intera:
-- il termine deve essere preceduto e seguito da un carattere non alfanumerico.
local function isWordChar(s, pos)
    -- Restituisce true se il carattere in posizione pos (1-based) è alfanumerico
    -- Gestisce sia ASCII che caratteri Unicode/accentati
    if pos < 1 or pos > mw.ustring.len(s) then return false end
    local c = mw.ustring.sub(s, pos, pos)
    -- Alfanumerico ASCII
    if mw.ustring.find(c, '^[%w]$') then return true end
    -- Lettere accentate e Unicode (code point > 127)
    local b = string.byte(c)
    if b and b > 127 then return true end
    return false
end

local function containsWholeWord(haystack, needle)
    -- Cerca needle come parola intera in haystack (già lowercased entrambi)
    local hlen = mw.ustring.len(haystack)
    local nlen = mw.ustring.len(needle)
    local start = 1
    while true do
        local s, e = mw.ustring.find(haystack, needle, start, true)
        if not s then return false end
        -- Verifica boundary: carattere prima e dopo non deve essere alfanumerico
        local before_ok = not isWordChar(haystack, s - 1)
        local after_ok  = not isWordChar(haystack, e + 1)
        if before_ok and after_ok then return true end
        start = s + 1
    end
end

-- Analizza il needle una sola volta: estrae il termine e il flag wholeWord.
-- Restituisce: needle normalizzato (lowercase, senza virgolette), wholeWord (bool).
-- Usato per pre-processare il needle fuori dai loop categorie.
local function parseNeedle(needle)
    if not needle then return nil, false end
    local trimmed = mw.text.trim(needle)
    local wholeWord = false
    if trimmed:sub(1,1) == '"' and trimmed:sub(-1) == '"' and #trimmed > 2 then
        trimmed = trimmed:sub(2, -2)
        wholeWord = true
    end
    trimmed = mw.ustring.lower(trimmed)
    if trimmed == '' then return nil, false end
    return trimmed, wholeWord
end

-- Match needle (già parseato con parseNeedle) contro haystack (già lowercased).
-- Versione interna: non ri-lowercasa né ri-parsa, usa dati già pronti.
local function containsParsed(haystackLow, needleLow, wholeWord)
    if not haystackLow or not needleLow then return false end
    if wholeWord then
        return containsWholeWord(haystackLow, needleLow)
    end
    return mw.ustring.find(haystackLow, needleLow, 1, true) ~= nil
end

local function contains(haystack, needle)
    if not haystack or not needle then return false end
    -- Rileva match parola intera: needle racchiuso tra doppi apici
    local wholeWord = false
    local trimmed = mw.text.trim(needle)
    if trimmed:sub(1,1) == '"' and trimmed:sub(-1) == '"' and #trimmed > 2 then
        needle = trimmed:sub(2, -2)
        wholeWord = true
    end
    haystack = mw.ustring.lower(haystack)
    needle = mw.ustring.lower(needle)
    if needle == '' then return false end
    if wholeWord then
        return containsWholeWord(haystack, needle)
    end
    return mw.ustring.find(haystack, needle, 1, true) ~= nil
end

-- Rileva la sintassi not(...) in un termine.
-- Restituisce isNot=true e il termine interno se il termine è "not(...)",
-- altrimenti restituisce isNot=false e il termine invariato.
-- Supporta spazi opzionali: "not( foo )" -> inner = "foo" (trimmed).
-- Le virgolette per match parola intera sono supportate nell'inner:
-- not("morti") -> isNot=true, inner='"morti"'
local function parseNot(term)
    term = mw.text.trim(term)
    local inner = term:match('^[Nn][Oo][Tt]%s*%((.-)%)%s*$')
    if inner ~= nil then
        return true, mw.text.trim(inner)
    end
    return false, term
end

-- Espande l'inner di un not() in sotto-termini separati da ";" o ",".
-- Restituisce una lista di termini che devono essere trattati in OR tra loro
-- (il not() è soddisfatto se NESSUNO dei sotto-termini matcha).
-- Es: inner='"russa";"russi";"russia"' -> {'"russa"', '"russi"', '"russia"'}
-- Es: inner='calcio,tennis'            -> {'calcio', 'tennis'}
-- Es: inner='sport'                    -> {'sport'}
local function expandNotInner(inner)
    inner = mw.text.trim(inner)
    -- Prima prova a splittare su ";", poi su ","
    local terms = split(inner, ';')
    if #terms <= 1 then
        terms = split(inner, ',')
    end
    if #terms == 0 then terms = {inner} end
    return terms
end

local function matchesAndCat(categories, andCat)
    if not andCat or andCat == '' then return true end
    -- Pre-lowercase categorie una volta sola (hot path: N categorie × M termini)
    local catsLow = {}
    for i, cat in ipairs(categories) do
        catsLow[i] = mw.ustring.lower(cat)
    end
    -- Virgola = AND tra gruppi; punto e virgola = OR dentro ogni gruppo
    local groups = splitParens(andCat, ',')
    for _, group in ipairs(groups) do
        local found = false
        local terms = splitParens(group, ';')
        if #terms == 0 then terms = {group} end
        for _, term in ipairs(terms) do
            term = mw.text.trim(term)
            if term ~= '' then
                local isNot, inner = parseNot(term)
                if isNot then
                    local subTerms = expandNotInner(inner)
                    local anyMatch = false
                    for _, subTerm in ipairs(subTerms) do
                        local needleLow, wholeWord = parseNeedle(subTerm)
                        if needleLow then
                            for _, catLow in ipairs(catsLow) do
                                if containsParsed(catLow, needleLow, wholeWord) then anyMatch = true; break end
                            end
                        end
                        if anyMatch then break end
                    end
                    if not anyMatch then found = true; break end
                else
                    local needleLow, wholeWord = parseNeedle(term)
                    if needleLow then
                        for _, catLow in ipairs(catsLow) do
                            if containsParsed(catLow, needleLow, wholeWord) then found = true; break end
                        end
                    end
                    if found then break end
                end
            end
        end
        if not found then return false end
    end
    return true
end

local function matchesOrCat(categories, orCat)
    if not orCat or orCat == '' then return true end
    -- Pre-lowercase categorie una volta sola
    local catsLow = {}
    for i, cat in ipairs(categories) do
        catsLow[i] = mw.ustring.lower(cat)
    end
    -- Virgola = OR tra gruppi; punto e virgola = OR dentro ogni gruppo
    local groups = splitParens(orCat, ',')
    for _, group in ipairs(groups) do
        local terms = splitParens(group, ';')
        if #terms == 0 then terms = {group} end
        for _, term in ipairs(terms) do
            term = mw.text.trim(term)
            if term ~= '' then
                local isNot, inner = parseNot(term)
                if isNot then
                    local subTerms = expandNotInner(inner)
                    local anyMatch = false
                    for _, subTerm in ipairs(subTerms) do
                        local needleLow, wholeWord = parseNeedle(subTerm)
                        if needleLow then
                            for _, catLow in ipairs(catsLow) do
                                if containsParsed(catLow, needleLow, wholeWord) then anyMatch = true; break end
                            end
                        end
                        if anyMatch then break end
                    end
                    if not anyMatch then return true end
                else
                    local needleLow, wholeWord = parseNeedle(term)
                    if needleLow then
                        for _, catLow in ipairs(catsLow) do
                            if containsParsed(catLow, needleLow, wholeWord) then return true end
                        end
                    end
                end
            end
        end
    end
    return false
end

local function matchesNoCat(categories, noCat)
    if not noCat or noCat == '' then return true end
    if mw.text.trim(noCat) == '*' then
        return #categories == 0
    end
    -- Pre-lowercase categorie una volta sola
    local catsLow = {}
    for i, cat in ipairs(categories) do
        catsLow[i] = mw.ustring.lower(cat)
    end
    -- Virgola = AND tra gruppi di esclusione; punto e virgola = OR dentro ogni gruppo
    local groups = splitParens(noCat, ',')
    for _, group in ipairs(groups) do
        local terms = splitParens(group, ';')
        if #terms == 0 then terms = {group} end
        for _, term in ipairs(terms) do
            term = mw.text.trim(term)
            if term ~= '' then
                local isNot, inner = parseNot(term)
                if isNot then
                    local subTerms = expandNotInner(inner)
                    local hasAny = false
                    for _, subTerm in ipairs(subTerms) do
                        local needleLow, wholeWord = parseNeedle(subTerm)
                        if needleLow then
                            for _, catLow in ipairs(catsLow) do
                                if containsParsed(catLow, needleLow, wholeWord) then hasAny = true; break end
                            end
                        end
                        if hasAny then break end
                    end
                    if not hasAny then return false end
                else
                    local needleLow, wholeWord = parseNeedle(term)
                    if needleLow then
                        for _, catLow in ipairs(catsLow) do
                            if containsParsed(catLow, needleLow, wholeWord) then return false end
                        end
                    end
                end
            end
        end
    end
    return true
end

-- ExclIfNotCat: esclude la voce se ha la categoria X ma NON ha la categoria Y.
-- Sintassi: ExclIfNotCat=X>Y  oppure  X>Y,A>B  (virgola = AND tra regole distinte)
-- Significato: "escludi la voce se ha X, a meno che non abbia anche Y"
-- Il separatore è ">" (maggiore) e non "|" per evitare conflitti con il parser MediaWiki.
-- Es: ExclIfNotCat=Morti a Parigi>Nati a Parigi
--   -> passa solo se: non ha "Morti a Parigi", oppure ha sia "Morti a Parigi" che "Nati a Parigi"
-- Applicato sempre come veto finale indipendentemente da And=on/off.
local function matchesExclIfNotCat(categories, param)
    if not param or param == '' then return true end
    -- Pre-lowercase categorie una volta sola
    local catsLow = {}
    for i, cat in ipairs(categories) do
        catsLow[i] = mw.ustring.lower(cat)
    end
    local rules = split(param, ',')
    for _, rule in ipairs(rules) do
        rule = mw.text.trim(rule)
        if rule ~= '' then
            -- '>' è ASCII: string.find è sufficiente
            local gt = string.find(rule, '>', 1, true)
            if gt then
                local triggerStr   = mw.text.trim(rule:sub(1, gt - 1))
                local exceptionStr = mw.text.trim(rule:sub(gt + 1))
                local trigNeedleLow, trigWholeWord = parseNeedle(triggerStr)
                local hasTrigger = false
                if trigNeedleLow then
                    for _, catLow in ipairs(catsLow) do
                        if containsParsed(catLow, trigNeedleLow, trigWholeWord) then hasTrigger = true; break end
                    end
                end
                if hasTrigger then
                    local excNeedleLow, excWholeWord = parseNeedle(exceptionStr)
                    local hasException = false
                    if excNeedleLow then
                        for _, catLow in ipairs(catsLow) do
                            if containsParsed(catLow, excNeedleLow, excWholeWord) then hasException = true; break end
                        end
                    end
                    if not hasException then return false end
                end
            end
        end
    end
    return true
end

local function matchesTitle(title, titleSearch)
    if not titleSearch or titleSearch == '' then return true end
    -- Normalizza | (via {{!}}) in ;
    local normalized = titleSearch:gsub('|', ';')
    -- ; = OR tra gruppi; + = AND tra termini dentro ogni gruppo
    -- Es: "riserva+darwin;oasi" -> (riserva AND darwin) OR oasi
    -- not(X) in un termine: il termine è soddisfatto se il titolo NON contiene X
    -- splitParens: rispetta i separatori dentro not(...), es. not(X;Y) o not(X,Y)
    local groups = splitParens(normalized, ';')
    if #groups == 0 then groups = {normalized} end
    for _, group in ipairs(groups) do
        group = mw.text.trim(group)
        if group ~= '' then
            -- Verifica AND tra tutti i termini del gruppo
            local andTerms = splitParens(group, '+')
            if #andTerms == 0 then andTerms = {group} end
            local allMatch = true
            for _, term in ipairs(andTerms) do
                term = mw.text.trim(term)
                if term ~= '' then
                    local isNot, inner = parseNot(term)
                    if isNot then
                        if contains(title, inner) then allMatch = false; break end
                    else
                        if not contains(title, term) then allMatch = false; break end
                    end
                end
            end
            if allMatch then return true end
        end
    end
    return false
end

local function matchesText(content, text)
    if not text or text == '' then return true end
    if not content then return false end
    -- Supporta ; o | (via {{!}}) per OR: "gotico;romanico;barocco"
    -- not(X) in un termine: il termine è soddisfatto se il contenuto NON contiene X
    -- splitParens: rispetta i separatori dentro not(...), es. not(X;Y)
    if mw.ustring.find(text, '|', 1, true) or mw.ustring.find(text, ';', 1, true) then
        local normalized = text:gsub('|', ';')
        local terms = splitParens(normalized, ';')
        for _, term in ipairs(terms) do
            local isNot, inner = parseNot(term)
            if isNot then
                if not contains(content, inner) then return true end
            else
                if contains(content, term) then return true end
            end
        end
        return false
    end
    local isNot, inner = parseNot(text)
    if isNot then
        return not contains(content, inner)
    end
    return contains(content, text)
end

-- Espande un pattern con gruppi (a;b;c) o (a|b|c) in una lista di pattern alternativi.
local function expandPatternAlternatives(pattern)
    local pre, group, post = pattern:match('^(.-)%(([^()]+)%)(.*)$')
    if not pre then
        return {pattern}
    end
    local groupNorm = group:gsub(';', '|')
    local results = {}
    for alt in (groupNorm .. '|'):gmatch('([^|]*)|') do
        local subPattern = pre .. alt .. post
        for _, expanded in ipairs(expandPatternAlternatives(subPattern)) do
            table.insert(results, expanded)
        end
    end
    return results
end

local function matchesRegex(content, pattern, caseSensitive)
    if not pattern or pattern == '' then return true end
    if not content then return false end
    local variants = expandPatternAlternatives(pattern)
    for _, variant in ipairs(variants) do
        local searchPattern = variant
        if not caseSensitive then
            searchPattern = mw.ustring.lower(variant)
        end
        for line in (content .. '\n'):gmatch('([^\n]*)\n') do
            local searchLine = caseSensitive and line or mw.ustring.lower(line)
            local success, result = pcall(function()
                return mw.ustring.find(searchLine, searchPattern) ~= nil
            end)
            if success and result then
                return true
            end
        end
    end
    return false
end

local function isAfterDate(timestamp, dateLimit)
    if not dateLimit or dateLimit == '' then return true end
    local day, month, year = dateLimit:match('(%d+)/(%d+)/(%d+)')
    if not day then return true end
    local limitStr = string.format('%04d%02d%02d', tonumber(year), tonumber(month), tonumber(day))
    local dateStr = timestamp:sub(1, 8)
    return dateStr >= limitStr
end

local function formatTimestamp(timestamp)
    if not timestamp or #timestamp < 14 then return '' end
    local year = timestamp:sub(1, 4)
    local month = timestamp:sub(5, 6)
    local day = timestamp:sub(7, 8)
    local hour = timestamp:sub(9, 10)
    local min = timestamp:sub(11, 12)
    return string.format('%s/%s/%s %s:%s', day, month, year, hour, min)
end

-- Restituisce la data formattata per la visualizzazione nella lista.
-- Se voce[6] (move_timestamp) e' presente e non vuoto, usa quella data
-- avvolta in corsivo wikitext (voce spostata da altro namespace).
-- Altrimenti usa voce[2] (timestamp di prima creazione) in testo normale.
local function formatTimestampDisplay(voce)
    local movets = voce[6]
    if movets and movets ~= '' then
        return "''" .. formatTimestamp(movets) .. "''"
    end
    return formatTimestamp(voce[2])
end

-- Confronta un nome di template (con eventuali parametri richiesti) contro l'elenco
-- dei template presenti nella voce. Tre modalità di match sul nome, mutuamente esclusive:
--   Nome      -> substring match (default): "libro" matcha sia {{Libro}} che {{cita libro}}
--   "Nome"    -> parola intera dentro il nome: "libro" matcha ancora {{cita libro}}
--                (perché "libro" è un token separato dentro "cita libro"), ma non
--                matcherebbe un ipotetico {{librone}}
--   /Nome/    -> match ESATTO sull'intero nome del template: /libro/ matcha solo {{Libro}},
--                non {{cita libro}}. Underscore normalizzati come spazi prima del confronto.
local function matchesSingleTemplate(templates, tmplName, requiredParams)
    tmplName = mw.text.trim(tmplName)
    -- Rileva match esatto sull'intero nome: nome template racchiuso tra slash (/Nome/)
    local exactTmpl = false
    if tmplName:sub(1,1) == '/' and tmplName:sub(-1) == '/' and #tmplName > 2 then
        tmplName = tmplName:sub(2, -2)
        exactTmpl = true
    end
    -- Rileva match parola intera: nome template racchiuso tra doppi apici
    local wholeWordTmpl = false
    if not exactTmpl and tmplName:sub(1,1) == '"' and tmplName:sub(-1) == '"' and #tmplName > 2 then
        tmplName = tmplName:sub(2, -2)
        wholeWordTmpl = true
    end
    -- Nomi template sono ASCII: string.lower è sufficiente e più veloce
    tmplName = string.lower(tmplName)
    if exactTmpl then
        -- Normalizza underscore come spazi, come fa MediaWiki nei nomi pagina/template
        tmplName = tmplName:gsub('_', ' ')
    end
    for _, tmpl in ipairs(templates) do
        local nome = string.lower(tmpl[1] or '')
        local nameMatch
        if exactTmpl then
            -- Match esatto sull'intero nome del template (non una sua parola/sottostringa)
            nameMatch = (nome:gsub('_', ' ') == tmplName)
        elseif wholeWordTmpl then
            -- wholeWord può coinvolgere caratteri Unicode: usa mw.ustring
            nameMatch = containsWholeWord(nome, tmplName)
        else
            nameMatch = string.find(nome, tmplName, 1, true) ~= nil
            -- Workaround bug MediaWiki Lua: mw.ustring.find non trova "portale" in "portali".
            -- Se la ricerca fallisce, verifica se tmplName e nome sono alias portale/portali.
            if not nameMatch then
                if (tmplName == 'portale' and nome == 'portali') or
                   (tmplName == 'portali' and nome == 'portale') then
                    nameMatch = true
                end
            end
        end
        if nameMatch then
            local allParamsFound = true
            for _, reqParam in ipairs(requiredParams) do
                -- Parametri portale possono contenere caratteri accentati: mw.ustring necessario
                local rp = mw.ustring.lower(mw.text.trim(reqParam))
                local found = false
                for _, p in ipairs(tmpl[2] or {}) do
                    if mw.ustring.find(mw.ustring.lower(p), rp, 1, true) then
                        found = true
                        break
                    end
                end
                if not found then
                    allParamsFound = false
                    break
                end
            end
            if allParamsFound then return true end
        end
    end
    return false
end

local function parseTemplateSpec(spec)
    spec = mw.text.trim(spec)
    local nome, paramStr = spec:match('^(.-)%s*%((.-)%)%s*$')
    if not nome then
        return spec, {}
    end
    local params = {}
    for p in (paramStr .. ';'):gmatch('([^;]*);') do
        p = mw.text.trim(p)
        if p ~= '' then table.insert(params, p) end
    end
    return nome, params
end

-- NoTemplate: esclude la voce se contiene almeno uno dei template elencati.
-- Virgola = AND tra gruppi di esclusione; punto e virgola = OR dentro ogni gruppo.
-- Es: NoTemplate=Stub;Abbozzo,Redirect -> esclude se ha (Stub OR Abbozzo) oppure (Redirect)
-- Usare /Nome/ per match esatto sull'intero nome template (es. NoTemplate=/Libro/ esclude
-- solo {{Libro}}, non {{cita libro}}); vedi commento su matchesSingleTemplate.
-- not(X) inverte: not(X) in un gruppo NOTemplate richiede positivamente X
-- (se la voce NON ha X, viene esclusa - utile per filtrare voci prive di un certo template)
local function matchesNoTemplate(templates, noTmpl)
    if not noTmpl or noTmpl == '' then return true end
    -- Valore speciale '*': esclude voci che hanno almeno un template
    if mw.text.trim(noTmpl) == '*' then
        return #templates == 0
    end
    -- splitParens: rispetta i separatori dentro not(...), es. not(X;Y) o not(X,Y)
    local groups = splitParens(noTmpl, ',')
    for _, group in ipairs(groups) do
        -- Raccoglie gli spec del gruppo, separati da ";"
        -- Per ogni spec: se è not(X) -> la voce viene esclusa se NON ha X
        --                se è normale -> la voce viene esclusa se ha X
        local anyMatchPositive = false  -- almeno uno spec positivo ha trovato match
        local anyNotFailed = false      -- almeno uno spec not(X) non è soddisfatto
        local hasPositive = false
        local hasNot = false
        local specs = splitParens(group, ';')
        for _, spec in ipairs(specs) do
            spec = mw.text.trim(spec)
            if spec ~= '' then
                local isNot, inner = parseNot(spec)
                if isNot then
                    hasNot = true
                    local nome, params = parseTemplateSpec(inner)
                    -- not(X) in NoCat/NoTemplate: richiede positivamente X
                    -- se la voce NON ha il template X -> escludila (return false)
                    if not matchesSingleTemplate(templates, nome, params) then
                        anyNotFailed = true
                    end
                else
                    hasPositive = true
                    local nome, params = parseTemplateSpec(spec)
                    if matchesSingleTemplate(templates, nome, params) then
                        anyMatchPositive = true
                    end
                end
            end
        end
        -- Logica combinata per il gruppo (OR tra spec dello stesso gruppo):
        -- - uno spec positivo che matcha -> esclude la voce
        -- - uno spec not(X) non soddisfatto (voce priva di X) -> esclude la voce
        if anyMatchPositive then return false end
        if anyNotFailed then return false end
    end
    return true
end

-- AndTemplate: tutti i template elencati devono essere presenti
-- Virgola = AND tra gruppi; punto e virgola = OR dentro ogni gruppo
-- Es: "Bio;Wrestler,Portale" -> (Bio OR Wrestler) AND Portale
-- not(X) in un gruppo: il gruppo è soddisfatto se la voce NON ha X
-- Usare /Nome/ per match esatto sull'intero nome template (vedi matchesSingleTemplate)
-- splitParens: rispetta i separatori dentro not(...), es. not(X;Y) o not(X,Y)
local function matchesAndTemplate(templates, andTmpl)
    if not andTmpl or andTmpl == '' then return true end
    local groups = splitParens(andTmpl, ',')
    for _, group in ipairs(groups) do
        group = mw.text.trim(group)
        if group ~= '' then
            local found = false
            local specs = splitParens(group, ';')
            for _, spec in ipairs(specs) do
                spec = mw.text.trim(spec)
                if spec ~= '' then
                    local isNot, inner = parseNot(spec)
                    if isNot then
                        local nome, params = parseTemplateSpec(inner)
                        if not matchesSingleTemplate(templates, nome, params) then
                            found = true
                            break
                        end
                    else
                        local nome, params = parseTemplateSpec(spec)
                        if matchesSingleTemplate(templates, nome, params) then
                            found = true
                            break
                        end
                    end
                end
            end
            if not found then return false end
        end
    end
    return true
end

-- OrTemplate: almeno un template elencato deve essere presente
-- Virgola e punto e virgola sono entrambi OR
-- not(X): contribuisce come match se la voce NON ha X
-- Usare /Nome/ per match esatto sull'intero nome template (vedi matchesSingleTemplate)
-- splitParens: rispetta i separatori dentro not(...), es. not(X;Y) o not(X,Y)
local function matchesOrTemplate(templates, orTmpl)
    if not orTmpl or orTmpl == '' then return true end
    local groups = splitParens(orTmpl, ',')
    for _, group in ipairs(groups) do
        group = mw.text.trim(group)
        if group ~= '' then
            local specs = splitParens(group, ';')
            for _, spec in ipairs(specs) do
                spec = mw.text.trim(spec)
                if spec ~= '' then
                    local isNot, inner = parseNot(spec)
                    if isNot then
                        local nome, params = parseTemplateSpec(inner)
                        if not matchesSingleTemplate(templates, nome, params) then
                            return true
                        end
                    else
                        local nome, params = parseTemplateSpec(spec)
                        if matchesSingleTemplate(templates, nome, params) then
                            return true
                        end
                    end
                end
            end
        end
    end
    return false
end

-- Confronta un singolo parametro portale contro un needle con supporto alle tre sintassi:
--   /Nome/ -> match esatto (underscore normalizzati come spazi, case-insensitive)
--   "Nome" -> match parola intera (case-insensitive)
--   Nome   -> match sottostringa (case-insensitive, comportamento originale)
-- Il rilevamento della sintassi avviene una volta per needle, fuori dal loop sui parametri.
local function matchPortaleParam(param, needle)
    needle = mw.text.trim(needle)
    -- Sintassi /Nome/: match esatto sull'intero valore del parametro
    if needle:sub(1,1) == '/' and needle:sub(-1) == '/' and #needle > 2 then
        local name = mw.ustring.lower(needle:sub(2, -2):gsub('_', ' '))
        return mw.ustring.lower(param:gsub('_', ' ')) == name
    end
    -- Sintassi "Nome" e sottostringa: delega a contains() che già le gestisce
    return contains(param, needle)
end

-- Portali=p1,p2: AND su tutti i portali (tutti devono essere presenti)
-- Verifica se un nome template è di tipo Portale (gestisce sia "Portale" che "Portali")
local function isPortaleTemplate(nome)
    nome = string.lower(mw.text.trim(nome))
    return nome == 'portale' or nome == 'portali'
end

local function matchesPortali(templates, portali)
    if not portali or portali == '' then return true end
    local allPortaleParams = {}
    for _, tmpl in ipairs(templates) do
        local nome = string.lower(tmpl[1] or '')
        if isPortaleTemplate(nome) then
            for _, p in ipairs(tmpl[2] or {}) do
                table.insert(allPortaleParams, p)
            end
        end
    end
    -- Virgola = AND tra portali richiesti
    -- not(X): richiede che X NON sia tra i portali presenti.
    -- not(X;Y): ";" dentro not() = OR tra i termini da negare.
    --   Equivale a: non X AND non Y (per De Morgan).
    --   Es: not(radio;cinema) -> né radio né cinema devono essere presenti.
    for spec in (portali .. ','):gmatch('([^,]*),') do
        local portale = mw.text.trim(spec)
        if portale ~= '' then
            local isNot, inner = parseNot(portale)
            if isNot then
                -- not(X) oppure not(X;Y;...): espandi i sotto-termini separati da ";"
                -- e applica AND di negazioni (tutti devono essere assenti).
                local subTerms = split(inner, ';')
                if #subTerms == 0 then subTerms = {inner} end
                for _, subTerm in ipairs(subTerms) do
                    subTerm = mw.text.trim(subTerm)
                    if subTerm ~= '' then
                        -- Se anche uno solo di questi portali è presente, la condizione fallisce
                        for _, p in ipairs(allPortaleParams) do
                            if contains(p, subTerm) then return false end
                        end
                    end
                end
            else
                local found = false
                for _, p in ipairs(allPortaleParams) do
                    if matchPortaleParam(p, portale) then
                        found = true
                        break
                    end
                end
                if not found then return false end
            end
        end
    end
    return true
end

-- OrPortali=p1,p2: OR sui portali (basta almeno uno presente)
-- not(X): contribuisce come match se la voce NON ha il portale X
local function matchesOrPortali(templates, portali)
    if not portali or portali == '' then return true end
    local allPortaleParams = {}
    for _, tmpl in ipairs(templates) do
        local nome = string.lower(tmpl[1] or '')
        if isPortaleTemplate(nome) then
            for _, p in ipairs(tmpl[2] or {}) do
                table.insert(allPortaleParams, p)
            end
        end
    end
    -- Virgola e ";" sono entrambi OR tra portali
    -- not(X): match se la voce NON ha il portale X.
    -- not(X;Y): ";" dentro not() = OR tra i termini da negare.
    --   Match se la voce non ha X E non ha Y (AND di negazioni, De Morgan).
    --   Es: not(calcio;tennis) -> match se né calcio né tennis sono tra i portali.
    for spec in (portali .. ','):gmatch('([^,]*),') do
        local portale = mw.text.trim(spec)
        if portale ~= '' then
            local isNot, inner = parseNot(portale)
            if isNot then
                -- not(X) oppure not(X;Y;...): tutti i sotto-termini devono essere assenti
                local subTerms = split(inner, ';')
                if #subTerms == 0 then subTerms = {inner} end
                local allAbsent = true
                for _, subTerm in ipairs(subTerms) do
                    subTerm = mw.text.trim(subTerm)
                    if subTerm ~= '' then
                        for _, p in ipairs(allPortaleParams) do
                            if contains(p, subTerm) then allAbsent = false; break end
                        end
                        if not allAbsent then break end
                    end
                end
                if allAbsent then return true end
            else
                for _, p in ipairs(allPortaleParams) do
                    if matchPortaleParam(p, portale) then
                        return true
                    end
                end
            end
        end
    end
    return false
end

-- Memoizzazione: usata solo quando non è specificato firstLimit.
-- Più template senza First= sulla stessa pagina condividono questo risultato,
-- evitando di ricaricare i file Dati da zero per ogni istanza.
local _cachedData = nil

-- Rimuove un modulo DatiN dalla cache di require().
-- Scribunto non espone collectgarbage() come funzione Lua disponibile; non
-- dobbiamo quindi forzare il GC. È sufficiente eliminare il riferimento dalla
-- tabella package.loaded e lasciare che il garbage collector di Scribunto
-- intervenga autonomamente quando necessario.
-- Il riferimento locale 'data' viene azzerato dal chiamante prima di questa funzione.
local function releaseDataModule(pageName)
    if package and package.loaded then
        package.loaded[pageName] = nil
    end
end

-- Estrae il timestamp "effettivo" di una voce (move_timestamp se presente,
-- altrimenti timestamp di creazione), gestendo sia il formato "nuovo"
-- (voce.titolo/voce.timestamp/voce.move_timestamp) sia quello posizionale
-- (voce[2]/voce[6]), coerentemente con formatTimestampDisplay e calcDaysRange.
local function effectiveTimestamp(voce)
    if not voce then return nil end
    local ts, movets
    if voce.titolo ~= nil then
        ts, movets = voce.timestamp, voce.move_timestamp
    else
        ts, movets = voce[2], voce[6]
    end
    if movets and movets ~= '' then return movets end
    if ts and ts ~= '' then return ts end
    return nil
end

-- Conta economicamente i file cache esistenti: solo mw.title.new(...).exists,
-- nessun require(). Si ferma al primo file mancante.
-- Assunzione (confermata): il bot non produce mai file DatiN intermedi vuoti,
-- quindi l'indice dell'ultimo file esistente coincide col conteggio totale.
local function countExistingCacheFiles()
    local count = 0
    local i = 1
    while i <= 100 do
        local pageName = 'Modulo:VociRecenti/Dati' .. i
        local dataPage = mw.title.new(pageName)
        if dataPage and dataPage.exists then
            count = count + 1
            i = i + 1
        else
            break
        end
    end
    return count, count
end

-- Legge SOLO l'ultima voce dell'ultimo file di cache esistente (un solo
-- require() mirato), per ottenere economicamente il timestamp più vecchio
-- senza costruire l'array completo. Ritorna nil se il file non è leggibile
-- o non contiene voci.
local function getLastCacheTimestamp(lastIndex)
    if not lastIndex or lastIndex < 1 then return nil end
    local pageName = 'Modulo:VociRecenti/Dati' .. lastIndex
    local success, data = pcall(function() return require(pageName) end)
    local result = nil
    if success and type(data) == 'table' then
        local vociList = data.d or data.voci
        if vociList and type(vociList) == 'table' and #vociList > 0 then
            result = effectiveTimestamp(vociList[#vociList])
        end
    end
    data = nil
    releaseDataModule(pageName)
    return result
end

-- Carica automaticamente TUTTI i file Dati (Dati1, Dati2, ...)
-- firstLimit: se > 0, interrompe il caricamento dopo aver accumulato firstLimit voci,
-- senza allocare il resto della cache. In questo caso non viene usata la memoizzazione,
-- perché istanze diverse possono avere firstLimit diversi.
-- Se firstLimit è nil, usa la memoizzazione globale (comportamento precedente).
local function loadAllData(firstLimit)
    firstLimit = (firstLimit and firstLimit > 0) and firstLimit or nil
    if not firstLimit and _cachedData then return _cachedData end
    local allVoci = {}
    local ultimoAggiornamento = nil
    local filesLoaded = 0
    local errors = {}
    local i = 1
    local done = false
    while i <= 100 and not done do
        local pageName = 'Modulo:VociRecenti/Dati' .. i
        local dataPage = mw.title.new(pageName)
        if dataPage and dataPage.exists then
            local success, data = pcall(function()
                return require(pageName)
            end)
            if success then
                if type(data) == 'table' then
                    local vociList = data.d or data.voci
                    if vociList and type(vociList) == 'table' and #vociList > 0 then
                        for _, voce in ipairs(vociList) do
                            if voce.titolo ~= nil then
                                voce = {
                                    voce.titolo,
                                    voce.timestamp or '',
                                    voce.categorie or {},
                                    voce.template or {},
                                    (voce.contenuto or ''):sub(1, 100),
                                    voce.move_timestamp or '',
                                    voce.categorie_nascoste or {}
                                }
                            end
                            table.insert(allVoci, voce)
                            if firstLimit and #allVoci >= firstLimit then
                                done = true
                                break
                            end
                        end
                        if i == 1 then
                            ultimoAggiornamento = data.u or data.ultimo_aggiornamento
                        end
                        filesLoaded = filesLoaded + 1
                    end
                else
                    table.insert(errors, pageName .. ': formato non valido')
                end
            else
                table.insert(errors, pageName .. ': errore caricamento')
            end
            -- Anche nel percorso generale liberiamo il modulo DatiN.
            -- Se firstLimit è nil, _cachedData conserva le voci necessarie, ma
            -- eliminare package.loaded evita di conservare l'intera struttura
            -- radice del modulo e le voci non più referenziate.
            data = nil
            releaseDataModule(pageName)
        else
            break
        end
        i = i + 1
    end
    local result = {
        voci = allVoci,
        ultimo_aggiornamento = ultimoAggiornamento,
        num_files = filesLoaded,
        errors = errors
    }
    if not firstLimit then _cachedData = result end
    return result
end

-- Carica e filtra progressivamente. Valido quando l'ordine fisico della cache
-- coincide con Order=data: al raggiungimento del limite, i file successivi
-- conterrebbero solo voci piu' vecchie e non possono cambiare l'output.
local function loadFilteredData(matchVoce, maxMatches)
    local filtered, errors = {}, {}
    local ultimoAggiornamento, filesLoaded = nil, 0
    local primoTimestampCache = nil
    local i, done = 1, false
    while i <= 100 and not done do
        local pageName = 'Modulo:VociRecenti/Dati' .. i
        local dataPage = mw.title.new(pageName)
        if not dataPage or not dataPage.exists then break end
        local success, data = pcall(function() return require(pageName) end)
        if success and type(data) == 'table' then
            local vociList = data.d or data.voci
            if vociList and type(vociList) == 'table' and #vociList > 0 then
                if i == 1 then
                    ultimoAggiornamento = data.u or data.ultimo_aggiornamento
                    -- Cattura gratuita: Dati1 è già letto per ultimo_aggiornamento;
                    -- il timestamp della sua prima voce (prima del filtro) è il più
                    -- recente della cache, dato l'ordine cronologico decrescente.
                    primoTimestampCache = effectiveTimestamp(vociList[1])
                end
                filesLoaded = filesLoaded + 1
                for _, voce in ipairs(vociList) do
                    if voce.titolo ~= nil then
                        voce = { voce.titolo, voce.timestamp or '', voce.categorie or {},
                            voce.template or {}, (voce.contenuto or ''):sub(1, 100),
                            voce.move_timestamp or '', voce.categorie_nascoste or {} }
                    end
                    if matchVoce(voce) then
                        filtered[#filtered + 1] = voce
                        if #filtered >= maxMatches then done = true break end
                    end
                end
            end
            -- Rilascio fondamentale per evitare l'accumulo dei moduli DatiN tra istanze.
            -- Le sole voci che hanno fatto match restano vive perché referenziate
            -- da 'filtered'; il modulo non è più mantenuto da package.loaded.
            data = nil
            releaseDataModule(pageName)
        elseif not success then
            errors[#errors + 1] = pageName .. ': errore caricamento'
            -- In caso di errore, elimina comunque un eventuale caricamento parziale.
            releaseDataModule(pageName)
        else
            errors[#errors + 1] = pageName .. ': formato non valido'
            data = nil
            releaseDataModule(pageName)
        end
        i = i + 1
    end
    return { voci = filtered, ultimo_aggiornamento = ultimoAggiornamento,
        num_files = filesLoaded, errors = errors, primo_timestamp_cache = primoTimestampCache }
end
local function calcDaysRange(voci)
    if not voci or #voci == 0 then return nil end
    local function toDays(ts)
        if not ts or #ts < 8 then return nil end
        local y = tonumber(ts:sub(1,4))
        local m = tonumber(ts:sub(5,6))
        local d = tonumber(ts:sub(7,8))
        if not y or not m or not d then return nil end
        local a = math.floor((14 - m) / 12)
        local yy = y + 4800 - a
        local mm = m + 12 * a - 3
        return d + math.floor((153 * mm + 2) / 5) + 365 * yy
            + math.floor(yy / 4) - math.floor(yy / 100) + math.floor(yy / 400) - 32045
    end
    local tsMin, tsMax = nil, nil
    for _, voce in ipairs(voci) do
        -- Usa lo stesso timestamp visualizzato: move_timestamp (voce[6]) se presente,
        -- altrimenti il timestamp di creazione (voce[2]), coerentemente con formatTimestampDisplay.
        local movets = voce[6]
        local ts = (movets and movets ~= '') and movets or (voce[2] or '')
        if ts ~= '' then
            if not tsMin or ts < tsMin then tsMin = ts end
            if not tsMax or ts > tsMax then tsMax = ts end
        end
    end
    local dMin = toDays(tsMin)
    local dMax = toDays(tsMax)
    if not dMin or not dMax then return nil end
    return (dMax - dMin) + 1
end

-- cacheDaysOverride (opzionale, ultimo parametro): usato dal percorso streaming
-- economico per Timestamp=cachedays. Se nil, comportamento invariato (calcolo
-- da cacheVoci come prima, percorso loadAllData). Se '--', mostra un dato
-- mancante esplicito (calcolo economico fallito: Dati1 vuoto o ultimo file
-- irraggiungibile). Se numero, lo usa direttamente al posto di ricalcolare.
local function buildTimestampLine(timestampParam, ultimoAggiornamento, numFiles, voci, cacheVoci, cacheDaysOverride)
    local line = 'Ultimo aggiornamento: ' .. ultimoAggiornamento
    if (timestampParam == 'on' or timestampParam == 'cachedays') and numFiles then
        line = line .. ' (' .. numFiles .. ' file cache)'
    end
    if (timestampParam == 'on' or timestampParam == 'days') and voci and #voci > 0 then
        local days = calcDaysRange(voci)
        if days then
            local daysLabel = days == 1 and '1 giorno nelle voci filtrate' or (days .. ' giorni nelle voci filtrate')
            line = line .. ', ' .. daysLabel
        end
    end
    if timestampParam == 'cachedays' then
        if cacheDaysOverride ~= nil then
            local daysLabel
            if cacheDaysOverride == '--' then
                daysLabel = '-- giorni nella cache'
            else
                daysLabel = cacheDaysOverride == 1 and '1 giorno nella cache' or (cacheDaysOverride .. ' giorni nella cache')
            end
            line = line .. ', ' .. daysLabel
        elseif cacheVoci and #cacheVoci > 0 then
            local days = calcDaysRange(cacheVoci)
            if days then
                local daysLabel = days == 1 and '1 giorno nella cache' or (days .. ' giorni nella cache')
                line = line .. ', ' .. daysLabel
            end
        end
    end
    return '<div style="column-span:all;"><small>' .. line .. '</small></div>'
end

local function buildSearchable(voce)
    local parts = {}
    for _, cat in ipairs(voce[3] or {}) do
        table.insert(parts, cat)
    end
    for _, tmpl in ipairs(voce[4] or {}) do
        table.insert(parts, tmpl[1] or '')
        for _, p in ipairs(tmpl[2] or {}) do
            table.insert(parts, p)
        end
    end
    if voce[5] and voce[5] ~= '' then
        table.insert(parts, voce[5])
    end
    return table.concat(parts, '\n')
end

-- Funzione principale
function p.main(frame)
    local args = getArgs(frame)

    local num = tonumber(args.num) or 10
    if num < 1 then num = 10 end

    local function normFilter(v)
        if not v then return '' end
        local t = mw.text.trim(v)
        if t == '' or mw.ustring.lower(t) == 'off' then return '' end
        return t
    end

    local andCat = normFilter(args.andcat)
    local orCat = normFilter(args.orcat)
    local noCat = normFilter(args.nocat)
    local hAndCat = normFilter(args.handcat)
    local hOrCat = normFilter(args.horcat)
    local hNoCat = normFilter(args.hnocat)
    local titleSearch = normFilter(args.title)
    local searchText = normFilter(args.text)
    local regexPattern = normFilter(args.textregexp)
    local andTemplate = normFilter(args.andtemplate)
    local orTemplate = normFilter(args.ortemplate)
    local portali = normFilter(args.portali)
    local orPortali = normFilter(args.orportali)
    local dataFine = normFilter(args.datafine)
    local noTemplate = normFilter(args.notemplate)
    local exclIfNotCat = normFilter(args.exclifnotcat)

    -- Parametro DispScroll (ha precedenza su Disp se valorizzato)
    -- Sintassi: |DispScroll=v,300 -> disp=v, scrollbox altezza 300px
    local dispScroll = args.dispscroll or ''
    dispScroll = mw.text.trim(mw.ustring.lower(dispScroll))
    local scrollHeight = nil
    local disp
    if dispScroll ~= '' then
        local comma = dispScroll:find(',')
        local dispScrollVal, heightVal
        if comma then
            dispScrollVal = mw.text.trim(dispScroll:sub(1, comma - 1))
            heightVal = mw.text.trim(dispScroll:sub(comma + 1))
        else
            dispScrollVal = dispScroll
            heightVal = '200'
        end
        if not heightVal:match('^%d+$') then heightVal = '200' end
        scrollHeight = heightVal .. 'px'
        disp = dispScrollVal
    else
        disp = args.disp or 's'
    end

    local caseSensitive = args.casesensitive or 'off'
    caseSensitive = mw.text.trim(mw.ustring.lower(caseSensitive))
    local useCaseSensitive = (caseSensitive == 'on' or caseSensitive == 'true' or caseSensitive == '1' or caseSensitive == 'yes')

    local andMode = args['and'] or ''
    andMode = mw.text.trim(mw.ustring.lower(andMode))
    if andMode == '' then andMode = 'off' end
    local useAndLogic = (andMode == 'on' or andMode == 'true' or andMode == '1' or andMode == 'yes')

    local order = args.order or 'data'
    order = mw.text.trim(mw.ustring.lower(order))
    if order ~= 'data' and order ~= 'dataold' and order ~= 'alpha' then
        order = 'data'
    end

    local timestampParam = args.timestamp or 'cachedays'
    timestampParam = mw.text.trim(mw.ustring.lower(timestampParam))
    if timestampParam ~= 'off' and timestampParam ~= 'on' and timestampParam ~= 'date'
            and timestampParam ~= 'days' and timestampParam ~= 'cachedays' then
        timestampParam = 'cachedays'
    end

    disp = mw.text.trim(mw.ustring.lower(disp))
    if disp ~= 's' and disp ~= 'v' and disp ~= 'o' and disp ~= 't' and disp ~= 'h' then
        disp = 's'
    end

    local firstParam = tonumber(args.first)
    if firstParam and firstParam <= 0 then firstParam = nil end

    local function voceMatches(voce)
        local matches = true

        if useAndLogic then
            -- Early exit: ogni check viene eseguito solo se i precedenti sono passati.
            -- In AND puro basta un singolo fallimento per scartare la voce.
            if andCat ~= '' and not matchesAndCat(voce[3] or {}, andCat) then
                matches = false
            end
            if matches and orCat ~= '' and not matchesOrCat(voce[3] or {}, orCat) then
                matches = false
            end
            if matches and hAndCat ~= '' and not matchesAndCat(voce[7] or {}, hAndCat) then
                matches = false
            end
            if matches and hOrCat ~= '' and not matchesOrCat(voce[7] or {}, hOrCat) then
                matches = false
            end
            if matches and titleSearch ~= '' and not matchesTitle(voce[1], titleSearch) then
                matches = false
            end
            if matches and searchText ~= '' and not matchesText(voce[5], searchText) then
                matches = false
            end
            if matches and dataFine ~= '' and not isAfterDate(voce[2], dataFine) then
                matches = false
            end
            if matches and regexPattern ~= '' then
                if not matchesRegex(buildSearchable(voce), regexPattern, useCaseSensitive) then
                    matches = false
                end
            end
            if matches and andTemplate ~= '' and not matchesAndTemplate(voce[4] or {}, andTemplate) then
                matches = false
            end
            if matches and orTemplate ~= '' and not matchesOrTemplate(voce[4] or {}, orTemplate) then
                matches = false
            end
            if matches and portali ~= '' and not matchesPortali(voce[4] or {}, portali) then
                matches = false
            end
            if matches and orPortali ~= '' and not matchesOrPortali(voce[4] or {}, orPortali) then
                matches = false
            end
            if matches and noCat ~= '' and not matchesNoCat(voce[3] or {}, noCat) then
                matches = false
            end
            if matches and hNoCat ~= '' and not matchesNoCat(voce[7] or {}, hNoCat) then
                matches = false
            end
            if matches and noTemplate ~= '' and not matchesNoTemplate(voce[4] or {}, noTemplate) then
                matches = false
            end
            if matches and exclIfNotCat ~= '' and not matchesExclIfNotCat(voce[3] or {}, exclIfNotCat) then
                matches = false
            end
        else
            matches = false
            local hasPositiveFilters = (andCat ~= '' or orCat ~= '' or hAndCat ~= '' or hOrCat ~= '' or titleSearch ~= '' or searchText ~= '' or regexPattern ~= '' or andTemplate ~= '' or orTemplate ~= '' or portali ~= '' or orPortali ~= '')
            local hasNegativeFilters = (noCat ~= '' or hNoCat ~= '' or noTemplate ~= '')
            local hasFilters = hasPositiveFilters or hasNegativeFilters
            if not hasFilters then
                matches = true
            elseif not hasPositiveFilters then
                -- Solo filtri negativi: includi tutto solo se supera i filtri negativi
                local passNoCat  = (noCat  == '' or matchesNoCat(voce[3] or {}, noCat))
                local passHNoCat = (hNoCat == '' or matchesNoCat(voce[7] or {}, hNoCat))
                local passNoTmpl = (noTemplate == '' or matchesNoTemplate(voce[4] or {}, noTemplate))
                matches = passNoCat and passHNoCat and passNoTmpl
            else
                if andCat ~= '' and matchesAndCat(voce[3] or {}, andCat) then matches = true end
                if orCat ~= '' and matchesOrCat(voce[3] or {}, orCat) then matches = true end
                if hAndCat ~= '' and matchesAndCat(voce[7] or {}, hAndCat) then matches = true end
                if hOrCat ~= '' and matchesOrCat(voce[7] or {}, hOrCat) then matches = true end
                if titleSearch ~= '' and matchesTitle(voce[1], titleSearch) then matches = true end
                if searchText ~= '' and matchesText(voce[5], searchText) then matches = true end
                if regexPattern ~= '' and matchesRegex(buildSearchable(voce), regexPattern, useCaseSensitive) then matches = true end
                if andTemplate ~= '' and matchesAndTemplate(voce[4] or {}, andTemplate) then matches = true end
                if orTemplate ~= '' and matchesOrTemplate(voce[4] or {}, orTemplate) then matches = true end
                if portali ~= '' and matchesPortali(voce[4] or {}, portali) then matches = true end
                if orPortali ~= '' and matchesOrPortali(voce[4] or {}, orPortali) then matches = true end
            end
            if dataFine ~= '' and not isAfterDate(voce[2], dataFine) then matches = false end
            if matches and noCat ~= '' and not matchesNoCat(voce[3] or {}, noCat) then matches = false end
            if matches and hNoCat ~= '' and not matchesNoCat(voce[7] or {}, hNoCat) then matches = false end
            if matches and noTemplate ~= '' and not matchesNoTemplate(voce[4] or {}, noTemplate) then matches = false end
            if matches and exclIfNotCat ~= '' and not matchesExclIfNotCat(voce[3] or {}, exclIfNotCat) then matches = false end
        end

        return matches
    end

    local useStreaming = not firstParam and order == 'data'
    local data = useStreaming and loadFilteredData(voceMatches, num) or loadAllData(firstParam)
    local vociSlice = data.voci

    if not data or data.num_files == 0 then
        local msg = '<div class="noprint" style="padding:1em; border:2px solid #fc3; background:#ffc; column-span:all;">'
        if not data or data.num_files == 0 then
            msg = msg .. "'''⚠️ Cache non inizializzata'''<br/>Esegui il bot per creare la cache iniziale."
        else
            msg = msg .. "'''⚠️ Cache vuota'''<br/>Il bot sta rigenerando la cache. Riprova tra qualche minuto."
            if data.errors and #data.errors > 0 then
                msg = msg .. "<br/><small>Errori: " .. table.concat(data.errors, ", ") .. "</small>"
            end
        end
        msg = msg .. '</div>'
        return msg
    end

    -- In streaming, data.num_files riflette solo i file scansionati prima di
    -- fermarsi (non il totale reale), e per Timestamp=cachedays lo streaming
    -- non ha mai caricato l'intera cache. Calcolo qui, una sola volta, i
    -- valori economici da usare al posto di data.num_files / vociSlice nelle
    -- chiamate a buildTimestampLine/formatOutput più sotto.
    local effectiveNumFiles = data.num_files
    local cacheDaysOverride = nil
    if useStreaming and (timestampParam == 'on' or timestampParam == 'cachedays') then
        local totalFiles, lastIndex = countExistingCacheFiles()
        if totalFiles > 0 then effectiveNumFiles = totalFiles end
        if timestampParam == 'cachedays' then
            local tsRecente = data.primo_timestamp_cache
            local tsVecchio = getLastCacheTimestamp(lastIndex)
            if tsRecente and tsVecchio then
                cacheDaysOverride = calcDaysRange({ { [2] = tsRecente }, { [2] = tsVecchio } }) or '--'
            else
                -- Dati1 vuoto o ultimo file irraggiungibile (es. cache in fase
                -- di rigenerazione): mostro un dato mancante esplicito invece
                -- di ricadere su loadAllData (per non rischiare 503).
                cacheDaysOverride = '--'
            end
        end
    end

    local filtered
    if useStreaming then
        filtered = vociSlice
    else
        filtered = {}
        for _, voce in ipairs(vociSlice) do
            if voceMatches(voce) then filtered[#filtered + 1] = voce end
        end
    end

    if order == 'dataold' then
        table.sort(filtered, function(a, b)
            local ta = ((a[6] and a[6] ~= '') and a[6] or (a[2] or ''))
            local tb = ((b[6] and b[6] ~= '') and b[6] or (b[2] or ''))
            return ta < tb
        end)
    elseif order == 'data' then
        table.sort(filtered, function(a, b)
            local ta = ((a[6] and a[6] ~= '') and a[6] or (a[2] or ''))
            local tb = ((b[6] and b[6] ~= '') and b[6] or (b[2] or ''))
            return ta > tb
        end)
    elseif order == 'alpha' then
        table.sort(filtered, function(a, b)
            return normalizeForSort(a[1] or '') < normalizeForSort(b[1] or '')
        end)
    end

    -- Nessuna copia della tabella: il limite viene passato direttamente a formatOutput.
    local displayNum = math.min(#filtered, num)

    if displayNum == 0 then
        local msg = [=[<div class="noprint" style="padding:1em; border:1px solid #a2a9b1; background:#f8f9fa; column-span:all;">''Nessuna voce trovata con i criteri specificati.''</div>]=]
        if timestampParam ~= 'off' and data.ultimo_aggiornamento then
            msg = msg .. '\n' .. buildTimestampLine(timestampParam, data.ultimo_aggiornamento, effectiveNumFiles, nil, vociSlice, cacheDaysOverride)
        end
        return msg
    end

    local result
    if scrollHeight then
        local listWiki = p.formatOutput(filtered, disp, nil, nil, 'off', nil, displayNum)
        local listHtml
        if disp == 'h' then
            -- Orizzontale: non serve preprocess (è HTML puro, non wikitext lista)
            listHtml = listWiki
            result = '<div style="overflow-x:auto; height:' .. scrollHeight
                     .. '; border:1px solid #ccc; padding:0.3em;">'
                     .. listHtml .. '</div>'
        else
            listHtml = frame:preprocess('\n' .. listWiki)
            result = '<div style="overflow-y:auto; height:' .. scrollHeight
                     .. '; border:1px solid #ccc; padding:0.3em;">'
                     .. listHtml .. '</div>'
        end
        if timestampParam ~= 'off' and data.ultimo_aggiornamento then
            result = result .. '\n' .. buildTimestampLine(timestampParam,
                     data.ultimo_aggiornamento, effectiveNumFiles, filtered, vociSlice, cacheDaysOverride)
        end
    else
        result = p.formatOutput(filtered, disp, data.ultimo_aggiornamento, effectiveNumFiles, timestampParam, vociSlice, displayNum, cacheDaysOverride)
    end
    return result
end

-- Formattazione output wikitext
-- maxItems: numero massimo di voci da renderizzare (opzionale, default = #voci).
-- Evita di creare una tabella troncata: itera semplicemente fino a math.min(#voci, maxItems).
function p.formatOutput(voci, disp, ultimoAggiornamento, numFiles, timestampParam, cacheVoci, maxItems, cacheDaysOverride)
    local output = {}
    if timestampParam == nil then timestampParam = 'cachedays' end
    local limit = maxItems and math.min(#voci, maxItems) or #voci

    if disp == 'h' then
        local items = {}
        for i = 1, limit do
            table.insert(items, '[[' .. voci[i][1] .. ']]')
        end
        local listHtml = table.concat(items, ' · ')
        if timestampParam ~= 'off' and ultimoAggiornamento then
            return listHtml .. '<br/>' .. buildTimestampLine(timestampParam, ultimoAggiornamento, numFiles, voci, cacheVoci, cacheDaysOverride)
        end
        return listHtml
    elseif disp == 't' then
        for i = 1, limit do
            table.insert(output, '* [[' .. voci[i][1] .. ']]')
        end
    elseif disp == 'o' then
        for i = 1, limit do
            local dateStr = formatTimestampDisplay(voci[i])
            table.insert(output, '* [[' .. voci[i][1] .. ']] <small>(' .. dateStr .. ')</small>')
        end
    elseif disp == 'v' then
        for i = 1, limit do
            local dateStr = formatTimestampDisplay(voci[i])
            table.insert(output, '# [[' .. voci[i][1] .. ']] <small>(' .. dateStr .. ')</small>')
        end
    else
        for i = 1, limit do
            table.insert(output, '# [[' .. voci[i][1] .. ']]')
        end
    end

    if timestampParam ~= 'off' and ultimoAggiornamento then
        table.insert(output, '')
        table.insert(output, buildTimestampLine(timestampParam, ultimoAggiornamento, numFiles, voci, cacheVoci, cacheDaysOverride))
    end

    return table.concat(output, '\n')
end

-- Istruzioni setup
function p.showSetupInstructions(args, numFiles)
    local output = {}
    table.insert(output, '<div style="border:2px solid #fc3; background:#ffc; padding:1.5em; margin:1em 0;">')
    table.insert(output, "=== ⚠️ Configurazione necessaria ===\n")
    if numFiles == 0 then
        table.insert(output, "Nessun file cache trovato. Esegui il bot v3.0 per creare '''Modulo:VociRecenti/Dati1''', '''Dati2''', ecc.")
    else
        table.insert(output, "Cache caricata da " .. numFiles .. " file ma nessuna voce corrisponde ai filtri.")
    end
    table.insert(output, '</div>')
    return table.concat(output, '')
end

-- Funzione di debug per testare una voce specifica
function p.debugVoce(frame)
    -- debugVoce viene chiamata con #invoke diretto: i parametri sono in frame.args
    -- non in frame:getParent().args come per il template normale
    local args = {}
    for k, v in pairs(frame.args) do
        if v ~= '' then
            local key = type(k) == 'string' and string.lower(k) or k
            args[key] = v
        end
    end
    local titoloTest = args.titolo or args[1] or ''
    local orCatTest = args.orcat or ''

    if titoloTest == '' then
        return "Specifica un titolo: {{#invoke:VociRecenti|debugVoce|titolo=Rudolf Frank|OrCat=aviatori}}"
    end

    local data = loadAllData()
    if not data.voci or #data.voci == 0 then return "ERRORE: Cache vuota" end

    local voceTest = nil
    for _, voce in ipairs(data.voci) do
        if voce[1] == titoloTest then voceTest = voce break end
    end

    if not voceTest then
        return "ERRORE: Voce '" .. titoloTest .. "' non trovata nella cache"
    end

    local output = {}
    table.insert(output, "=== DEBUG VOCE ===\n")
    table.insert(output, "'''Titolo:''' " .. (voceTest[1] or '') .. "\n")
    table.insert(output, "'''Timestamp:''' " .. (voceTest[2] or '') .. "\n")
    table.insert(output, "'''Numero categorie:''' " .. #(voceTest[3] or {}) .. "\n\n")
    table.insert(output, "'''Categorie:'''\n")
    for i, cat in ipairs(voceTest[3] or {}) do
        table.insert(output, "* " .. cat .. "\n")
    end

    if orCatTest ~= '' then
        table.insert(output, "\n'''Test OrCat = '" .. orCatTest .. "':'''\n")
        local match = matchesOrCat(voceTest[3] or {}, orCatTest)
        table.insert(output, "* Risultato: " .. (match and "MATCH" or "NO MATCH") .. "\n")
        table.insert(output, "\n'''Dettaglio match:'''\n")
        local requiredCats = split(orCatTest, ',')
        for _, reqCat in ipairs(requiredCats) do
            table.insert(output, "* Cerca '" .. reqCat .. "':\n")
            for _, cat in ipairs(voceTest[3] or {}) do
                local found = mw.ustring.find(mw.ustring.lower(cat), mw.ustring.lower(reqCat), 1, true) ~= nil
                if found then
                    table.insert(output, "  ** TROVATO in: " .. cat .. "\n")
                end
            end
        end
    end

    -- Template
    local templates = voceTest[4] or {}
    table.insert(output, "\n'''Numero template:''' " .. #templates .. "\n")
    table.insert(output, "\n'''Template:'''\n")
    for i, tmpl in ipairs(templates) do
        local nome = tmpl[1] or "?"
        local params = tmpl[2] or {}
        local pstr = ""
        for j, p in ipairs(params) do
            pstr = pstr .. (j > 1 and ", " or "") .. p
        end
        table.insert(output, "* {{" .. nome .. "}} -> [" .. pstr .. "]\n")
    end

    -- Debug struttura template raw
    table.insert(output, "\n'''Debug struttura template raw:'''\n")
    -- Test diretto find
    local teststr = "portale"
    local testfind = mw.ustring.find(teststr, "portale", 1, true)
    table.insert(output, "* mw.ustring.find portale in portale: " .. tostring(testfind) .. "\n")
    local teststr2 = "portali"
    local testfind2 = mw.ustring.find(teststr2, "portale", 1, true)
    table.insert(output, "* mw.ustring.find portale in portali: " .. tostring(testfind2) .. "\n")
    local testfind3 = string.find(teststr2, "portale", 1, true)
    table.insert(output, "* string.find portale in portali: " .. tostring(testfind3) .. "\n")
    -- Verifica versione modulo
    table.insert(output, "* Versione modulo: 8.50\n")
    for i, tmpl in ipairs(templates) do
        local t1 = tmpl[1]
        local t2 = tmpl[2]
        local t1type = type(t1)
        local t1val = tostring(t1)
        local t1len = t1type == "string" and tostring(#t1) or "N/A"
        local has_portale = t1type == "string" and (mw.ustring.find(mw.ustring.lower(t1), "portale", 1, true) ~= nil)
        table.insert(output, "* tmpl[" .. i .. "]: type=" .. t1type .. " val=" .. t1val .. " len=" .. t1len .. " has_portale=" .. tostring(has_portale) .. "\n")
    end

    -- Test struttura voce raw
    table.insert(output, "\n'''Debug struttura voce:'''\n")
    table.insert(output, "* voceTest[4] type: " .. type(voceTest[4]) .. "\n")
    if type(voceTest[4]) == "table" then
        table.insert(output, "* voceTest[4] length: " .. #voceTest[4] .. "\n")
    end
    local tpl_field = voceTest[4] or {}
    table.insert(output, "* tpl_field length (or {}): " .. #tpl_field .. "\n")

    -- Test NoTemplate=*
    local noTmplTest = args.notemplate or ""
    if noTmplTest ~= "" then
        table.insert(output, "\n'''Test NoTemplate = '" .. noTmplTest .. "':'''\n")
        local trimmed = mw.text.trim(noTmplTest)
        table.insert(output, "* trimmed='" .. trimmed .. "' eq*=" .. tostring(trimmed == "*") .. "\n")
        table.insert(output, "* #templates=" .. #templates .. "\n")
        local result = (trimmed == "*") and (#templates == 0) or true
        table.insert(output, "* matchesNoTemplate result: " .. tostring(trimmed == "*" and #templates == 0) .. "\n")
    end

    -- Test Portali
    local portaliTest = args.portali or ""
    if portaliTest ~= "" then
        table.insert(output, "\n'''Test Portali = '" .. portaliTest .. "':'''\n")
        local match = matchesPortali(templates, portaliTest)
        table.insert(output, "* Risultato: " .. (match and "MATCH" or "NO MATCH") .. "\n")
        table.insert(output, "\n'''Params portale trovati:'''\n")
        for _, tmpl in ipairs(templates) do
            local nome = mw.ustring.lower(tmpl[1] or "")
            if isPortaleTemplate(nome) then
                for _, p in ipairs(tmpl[2] or {}) do
                    table.insert(output, "* [" .. nome .. "] param: " .. p .. "\n")
                end
            end
        end
    end

    return table.concat(output, "")
end

return p