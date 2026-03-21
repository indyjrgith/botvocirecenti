-- Modulo:VociRecenti
-- Versione 8.10 - Aggiunto parametro |DispScroll=: stessa logica di |Disp= ma il risultato
--               viene avvolto in uno scrollbox verticale. Sintassi: |DispScroll=v,300 (valore
--               disp + altezza in px, default 200px). DispScroll ha precedenza su Disp.
-- Versione 8.9 - Parametri del template ora case-insensitive: |Disp, |disp, |DISP sono equivalenti;
--               vale per tutti i parametri (And, AndCat, OrCat, NoCat, Title, Text, TextRegExp,
--               AndTemplate, OrTemplate, Portali, OrPortali, DataFine, Disp, Timestamp, Order,
--               CaseSensitive, num)
-- Versione 8.8 - Fix normalizzazione parametri: stringa vuota e 'off' trattati come assenza di valore
--               in tutti i filtri stringa (AndCat, OrCat, NoCat, Title, Text, TextRegExp, AndTemplate,
--               OrTemplate, Portali, OrPortali, DataFine); And='' ora usa correttamente il default 'on'
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
            -- Normalizza il nome del parametro in lowercase per renderlo
            -- case-insensitive: |Disp, |disp, |DISP sono tutti equivalenti
            local key = type(k) == 'string' and mw.ustring.lower(k) or k
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

-- Mappa caratteri accentati/diacritici -> base ASCII (per ordinamento alfabetico)
local diacriticMap = {
    -- a
    ['à'] = 'a', ['á'] = 'a', ['â'] = 'a', ['ã'] = 'a', ['ä'] = 'a', ['å'] = 'a', ['ā'] = 'a', ['ă'] = 'a', ['ą'] = 'a',
    -- c
    ['ç'] = 'c', ['ć'] = 'c', ['č'] = 'c',
    -- d
    ['ď'] = 'd', ['đ'] = 'd',
    -- e
    ['è'] = 'e', ['é'] = 'e', ['ê'] = 'e', ['ë'] = 'e', ['ē'] = 'e', ['ĕ'] = 'e', ['ę'] = 'e', ['ě'] = 'e',
    -- g
    ['ğ'] = 'g',
    -- i
    ['ì'] = 'i', ['í'] = 'i', ['î'] = 'i', ['ï'] = 'i', ['ī'] = 'i', ['ĭ'] = 'i', ['į'] = 'i',
    -- l
    ['ł'] = 'l', ['ĺ'] = 'l', ['ļ'] = 'l', ['ľ'] = 'l',
    -- n
    ['ñ'] = 'n', ['ń'] = 'n', ['ņ'] = 'n', ['ň'] = 'n',
    -- o
    ['ò'] = 'o', ['ó'] = 'o', ['ô'] = 'o', ['õ'] = 'o', ['ö'] = 'o', ['ø'] = 'o', ['ō'] = 'o', ['ő'] = 'o',
    -- r
    ['ř'] = 'r', ['ŕ'] = 'r',
    -- s
    ['š'] = 's', ['ś'] = 's', ['ş'] = 's', ['ș'] = 's',
    -- t
    ['ť'] = 't', ['ţ'] = 't', ['ț'] = 't',
    -- u
    ['ù'] = 'u', ['ú'] = 'u', ['û'] = 'u', ['ü'] = 'u', ['ū'] = 'u', ['ŭ'] = 'u', ['ů'] = 'u', ['ű'] = 'u', ['ų'] = 'u',
    -- y
    ['ý'] = 'y', ['ÿ'] = 'y',
    -- z
    ['ž'] = 'z', ['ź'] = 'z', ['ż'] = 'z',
}

-- Normalizza una stringa per l'ordinamento: lowercase + rimozione diacritici
local function normalizeForSort(str)
    if not str then return '' end
    str = mw.ustring.lower(str)
    -- Sostituisce ogni carattere accentato con la sua versione base
    str = mw.ustring.gsub(str, '[^%z\1-\127]', function(c)
        return diacriticMap[c] or c
    end)
    return str
end

-- Funzione contains (case-insensitive)
local function contains(haystack, needle)
    if not haystack or not needle then return false end
    haystack = mw.ustring.lower(haystack)
    needle = mw.ustring.lower(needle)
    return mw.ustring.find(haystack, needle, 1, true) ~= nil
end

-- Funzioni di matching
local function matchesAndCat(categories, andCat)
    if not andCat or andCat == '' then return true end
    local requiredCats = split(andCat, ',')
    for _, reqCat in ipairs(requiredCats) do
        local found = false
        for _, cat in ipairs(categories) do
            if contains(cat, reqCat) then
                found = true
                break
            end
        end
        if not found then return false end
    end
    return true
end

local function matchesOrCat(categories, orCat)
    if not orCat or orCat == '' then return true end
    local requiredCats = split(orCat, ',')
    for _, reqCat in ipairs(requiredCats) do
        for _, cat in ipairs(categories) do
            if contains(cat, reqCat) then
                return true
            end
        end
    end
    return false
end

local function matchesNoCat(categories, noCat)
    if not noCat or noCat == '' then return true end
    local excludedCats = split(noCat, ',')
    for _, exCat in ipairs(excludedCats) do
        for _, cat in ipairs(categories) do
            if contains(cat, exCat) then
                return false  -- trovata una categoria esclusa: voce scartata
            end
        end
    end
    return true
end

local function matchesTitle(title, titleSearch)
    if not titleSearch or titleSearch == '' then return true end
    
    -- Supporta | per OR: "Chiesa|Cattedrale|Basilica"
    if mw.ustring.find(titleSearch, '|', 1, true) then
        local terms = split(titleSearch, '|')
        for _, term in ipairs(terms) do
            if contains(title, term) then
                return true
            end
        end
        return false
    end
    
    -- Singolo termine
    return contains(title, titleSearch)
end

local function matchesText(content, text)
    if not text or text == '' then return true end
    if not content then return false end
    
    -- Supporta | per OR: "gotico|romanico|barocco"
    if mw.ustring.find(text, '|', 1, true) then
        local terms = split(text, '|')
        for _, term in ipairs(terms) do
            if contains(content, term) then
                return true
            end
        end
        return false
    end
    
    -- Singolo termine
    return contains(content, text)
end

-- Espande un pattern con gruppi (a;b;c) o (a|b|c) in una lista di pattern alternativi.
-- Il separatore preferito nei template è ';' perché '|' viene interpretato da
-- MediaWiki come separatore di parametri prima che Lua lo riceva.
-- Es: "portale.*(astro;stelle)" -> {"portale.*astro", "portale.*stelle"}
-- Gestisce gruppi multipli e annidati.
local function expandPatternAlternatives(pattern)
    -- Cerca il primo gruppo (...)
    local pre, group, post = pattern:match('^(.-)%(([^()]+)%)(.*)$')
    if not pre then
        return {pattern}
    end
    -- Supporta sia ';' (preferito nei template) che '|' (se arriva via {{!}})
    -- Normalizza ';' in '|' per la divisione
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

    -- Espande il pattern in varianti (gestisce gruppi OR tipo (a;b;c))
    local variants = expandPatternAlternatives(pattern)

    -- Applica ogni variante riga per riga: il separatore \n in buildSearchable
    -- divide i token, e cercando riga per riga evitiamo che .* attraversi
    -- i confini tra token diversi (es. "Portale" e "Gastronomia" sono su
    -- righe separate, quindi "portale.*astronomia" non genera falsi match)
    for _, variant in ipairs(variants) do
        local searchPattern = variant
        if not caseSensitive then
            searchPattern = mw.ustring.lower(variant)
        end
        -- Itera sulle righe del contenuto
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
    if not timestamp or #timestamp < 14 then
        return ''
    end
    local year = timestamp:sub(1, 4)
    local month = timestamp:sub(5, 6)
    local day = timestamp:sub(7, 8)
    local hour = timestamp:sub(9, 10)
    local min = timestamp:sub(11, 12)
    return string.format('%s/%s/%s %s:%s', day, month, year, hour, min)
end

-- Cerca un singolo template nella lista templates della voce.
-- Restituisce true se trova un template il cui nome contiene tmplName (case-insensitive)
-- e tutti i parametri elencati in requiredParams sono presenti (match parziale, case-insensitive).
local function matchesSingleTemplate(templates, tmplName, requiredParams)
    tmplName = mw.ustring.lower(mw.text.trim(tmplName))
    for _, tmpl in ipairs(templates) do
        local nome = mw.ustring.lower(tmpl[1] or '')
        if mw.ustring.find(nome, tmplName, 1, true) then
            -- Verifica tutti i parametri richiesti (AND tra di loro)
            local allParamsFound = true
            for _, reqParam in ipairs(requiredParams) do
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

-- Parsa una specifica template del tipo "nome(par1;par2)" o "nome"
-- Restituisce {nome, {params}}
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

-- AndTemplate: tutti i template elencati devono essere presenti nella voce
local function matchesAndTemplate(templates, andTmpl)
    if not andTmpl or andTmpl == '' then return true end
    for spec in (andTmpl .. ','):gmatch('([^,]*),') do
        spec = mw.text.trim(spec)
        if spec ~= '' then
            local nome, params = parseTemplateSpec(spec)
            if not matchesSingleTemplate(templates, nome, params) then
                return false
            end
        end
    end
    return true
end

-- OrTemplate: almeno un template elencato deve essere presente nella voce
local function matchesOrTemplate(templates, orTmpl)
    if not orTmpl or orTmpl == '' then return true end
    for spec in (orTmpl .. ','):gmatch('([^,]*),') do
        spec = mw.text.trim(spec)
        if spec ~= '' then
            local nome, params = parseTemplateSpec(spec)
            if matchesSingleTemplate(templates, nome, params) then
                return true
            end
        end
    end
    return false
end


-- Portali=p1,p2: raccoglie tutti i params di tutti i template "Portale"
-- e verifica che l'insieme contenga TUTTI i valori cercati (AND).
local function matchesPortali(templates, portali)
    if not portali or portali == '' then return true end
    -- Raccoglie tutti i params di tutti i template il cui nome contiene "portale"
    local allPortaleParams = {}
    for _, tmpl in ipairs(templates) do
        local nome = mw.ustring.lower(tmpl[1] or '')
        if mw.ustring.find(nome, 'portale', 1, true) then
            for _, p in ipairs(tmpl[2] or {}) do
                table.insert(allPortaleParams, mw.ustring.lower(p))
            end
        end
    end
    -- Verifica AND: tutti i portali cercati devono essere presenti
    for spec in (portali .. ','):gmatch('([^,]*),') do
        local portale = mw.ustring.lower(mw.text.trim(spec))
        if portale ~= '' then
            local found = false
            for _, p in ipairs(allPortaleParams) do
                if mw.ustring.find(p, portale, 1, true) then
                    found = true
                    break
                end
            end
            if not found then return false end
        end
    end
    return true
end


-- OrPortali=p1,p2: come matchesPortali ma logica OR (basta almeno un portale presente)
local function matchesOrPortali(templates, portali)
    if not portali or portali == '' then return true end
    local allPortaleParams = {}
    for _, tmpl in ipairs(templates) do
        local nome = mw.ustring.lower(tmpl[1] or '')
        if mw.ustring.find(nome, 'portale', 1, true) then
            for _, p in ipairs(tmpl[2] or {}) do
                table.insert(allPortaleParams, mw.ustring.lower(p))
            end
        end
    end
    -- Verifica OR: basta che almeno uno dei portali cercati sia presente
    for spec in (portali .. ','):gmatch('([^,]*),') do
        local portale = mw.ustring.lower(mw.text.trim(spec))
        if portale ~= '' then
            for _, p in ipairs(allPortaleParams) do
                if mw.ustring.find(p, portale, 1, true) then
                    return true
                end
            end
        end
    end
    return false
end


-- NOVITÀ: Carica automaticamente TUTTI i file Dati (Dati1, Dati2, Dati3, ...)
local function loadAllData()
    local allVoci = {}
    local ultimoAggiornamento = nil
    local filesLoaded = 0
    local errors = {}
    
    -- Prova a caricare Dati1, Dati2, Dati3, ... finché ne trova
    local i = 1
    while i <= 100 do  -- Max 100 file (sicurezza)
        local pageName = 'Modulo:VociRecenti/Dati' .. i
        local dataPage = mw.title.new(pageName)
        
        if dataPage and dataPage.exists then
            -- USA require() invece di mw.loadData() per file grandi
            local success, data = pcall(function()
                return require(pageName)
            end)
            
            if success then
                -- Verifica che data sia una tabella valida
                if type(data) == 'table' then
                    -- Supporta sia formato nuovo (data.d) che vecchio (data.voci)
                    local vociList = data.d or data.voci
                    if vociList and type(vociList) == 'table' and #vociList > 0 then
                        for _, voce in ipairs(vociList) do
                            -- Normalizza vecchio formato (keyword) in array posizionale
                            if voce.titolo ~= nil then
                                voce = {
                                    voce.titolo,
                                    voce.timestamp or '',
                                    voce.categorie or {},
                                    {},
                                    (voce.contenuto or ''):sub(1, 100)
                                }
                            end
                            table.insert(allVoci, voce)
                        end
                        
                        if i == 1 then
                            ultimoAggiornamento = data.u or data.ultimo_aggiornamento
                        end
                        
                        filesLoaded = filesLoaded + 1
                    end
                    -- Se data è una tabella ma senza voci, è un file vuoto - ignora
                else
                    -- data non è una tabella - errore di formato
                    table.insert(errors, pageName .. ': formato non valido')
                end
            else
                -- pcall ha fallito - errore di sintassi Lua
                table.insert(errors, pageName .. ': errore caricamento')
            end
        else
            -- Se non trova Dati(i), smetti di cercare
            break
        end
        
        i = i + 1
    end
    
    return {
        voci = allVoci,
        ultimo_aggiornamento = ultimoAggiornamento,
        num_files = filesLoaded,
        errors = errors
    }
end

-- Calcola la differenza in giorni tra il timestamp più recente e il più vecchio
-- nelle voci filtrate. I timestamp sono nel formato 'YYYYMMDDHHmmss'.
local function calcDaysRange(voci)
    if not voci or #voci == 0 then return nil end

    -- Converte un timestamp YYYYMMDDHHMMSS in numero di giorni giuliani
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

    -- Cerca min e max dei timestamp indipendentemente dall'ordinamento della lista
    local tsMin, tsMax = nil, nil
    for _, voce in ipairs(voci) do
        local ts = voce[2] or ''
        if ts ~= '' then
            if not tsMin or ts < tsMin then tsMin = ts end
            if not tsMax or ts > tsMax then tsMax = ts end
        end
    end

    local dMin = toDays(tsMin)
    local dMax = toDays(tsMax)
    if not dMin or not dMax then return nil end
    -- +1 perché un solo giorno conta come 1, non come 0
    -- (es. 1 maggio - 3 maggio = 3 giorni, non 2)
    return (dMax - dMin) + 1
end

-- Costruisce la riga di timestamp in base al valore del parametro Timestamp.
-- timestampParam: 'on' | 'date' | 'days' | 'cachedays'
-- voci:      lista delle voci filtrate (per 'on' e 'days'); nil = nessuna voce trovata
-- cacheVoci: lista dell'intera cache (per 'cachedays')
local function buildTimestampLine(timestampParam, ultimoAggiornamento, numFiles, voci, cacheVoci)
    -- Parte fissa: data aggiornamento
    local line = 'Ultimo aggiornamento: ' .. ultimoAggiornamento

    -- File cache: con 'on' e 'cachedays'
    if (timestampParam == 'on' or timestampParam == 'cachedays') and numFiles then
        line = line .. ' (' .. numFiles .. ' file cache)'
    end

    -- Giorni nelle voci filtrate: con 'on' e 'days'
    if (timestampParam == 'on' or timestampParam == 'days') and voci and #voci > 0 then
        local days = calcDaysRange(voci)
        if days then
            local daysLabel = days == 1 and '1 giorno nelle voci filtrate' or (days .. ' giorni nelle voci filtrate')
            line = line .. ', ' .. daysLabel
        end
    end

    -- Giorni nella cache: solo con 'cachedays'
    if timestampParam == 'cachedays' and cacheVoci and #cacheVoci > 0 then
        local days = calcDaysRange(cacheVoci)
        if days then
            local daysLabel = days == 1 and '1 giorno nella cache' or (days .. ' giorni nella cache')
            line = line .. ', ' .. daysLabel
        end
    end

    return '<small>' .. line .. '</small>'
end

-- Costruisce una stringa su cui applicare TextRegExp:
-- concatena categorie, nomi template, parametri template e preview.
local function buildSearchable(voce)
    local parts = {}
    -- Categorie
    for _, cat in ipairs(voce[3] or {}) do
        table.insert(parts, cat)
    end
    -- Template: nome + params
    -- Ogni token è separato da newline per evitare che la concatenazione
    -- di parole adiacenti crei falsi match (es. "Portale"+" Gastronomia"
    -- -> "portale.*astronomia" matcherebbe "Gastr-astronomia")
    for _, tmpl in ipairs(voce[4] or {}) do
        table.insert(parts, tmpl[1] or '')
        for _, p in ipairs(tmpl[2] or {}) do
            table.insert(parts, p)
        end
    end
    -- Preview
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
    
    -- Normalizza un valore di parametro filtro: stringa vuota o 'off' -> ''
    local function normFilter(v)
        if not v then return '' end
        local t = mw.text.trim(v)
        if t == '' or mw.ustring.lower(t) == 'off' then return '' end
        return t
    end

    local andCat = normFilter(args.andcat)
    local orCat = normFilter(args.orcat)
    local noCat = normFilter(args.nocat)
    local titleSearch = normFilter(args.title)
    local searchText = normFilter(args.text)
    local regexPattern = normFilter(args.textregexp)
    local andTemplate = normFilter(args.andtemplate)
    local orTemplate = normFilter(args.ortemplate)
    local portali = normFilter(args.portali)
    local orPortali = normFilter(args.orportali)
    local dataFine = normFilter(args.datafine)
    -- Parametro DispScroll (ha precedenza su Disp se valorizzato)
    -- Sintassi: |DispScroll=v,300 -> disp=v, scrollbox altezza 300px
    local dispScroll = args.dispscroll or ''
    dispScroll = mw.text.trim(mw.ustring.lower(dispScroll))
    local scrollHeight = nil  -- nil = non usare scrollbox
    local disp
    if dispScroll ~= '' then
        -- Estrai valore disp e altezza dallo scrollbox
        local comma = dispScroll:find(',')
        local dispScrollVal, heightVal
        if comma then
            dispScrollVal = mw.text.trim(dispScroll:sub(1, comma - 1))
            heightVal = mw.text.trim(dispScroll:sub(comma + 1))
        else
            dispScrollVal = dispScroll
            heightVal = '200'
        end
        -- Normalizza valore altezza (solo cifre, default 200)
        if not heightVal:match('^%d+$') then heightVal = '200' end
        scrollHeight = heightVal .. 'px'
        disp = dispScrollVal
    else
        disp = args.disp or 's'
    end
    
    -- Parametro CaseSensitive (default 'off' per compatibilità)
    local caseSensitive = args.casesensitive or 'off'
    caseSensitive = mw.text.trim(mw.ustring.lower(caseSensitive))
    local useCaseSensitive = (caseSensitive == 'on' or caseSensitive == 'true' or caseSensitive == '1' or caseSensitive == 'yes')
    
    -- Parametro And (default 'on')
    -- Stringa vuota trattata come assenza di valore -> default 'on'
    local andMode = args['and'] or ''
    andMode = mw.text.trim(mw.ustring.lower(andMode))
    if andMode == '' then andMode = 'on' end
    local useAndLogic = (andMode == 'on' or andMode == 'true' or andMode == '1' or andMode == 'yes')

    -- Parametro Order (default 'data')
    -- 'data'    = data decrescente (più recente prima, comportamento storico)
    -- 'dataold' = data crescente (più vecchia prima)
    -- 'alpha'   = ordine alfabetico crescente sul titolo
    local order = args.order or 'data'
    order = mw.text.trim(mw.ustring.lower(order))
    if order ~= 'data' and order ~= 'dataold' and order ~= 'alpha' then
        order = 'data'
    end

    -- Parametro Timestamp (default 'cachedays')
    -- 'cachedays' = (default) aggiornamento + file cache + giorni nella cache
    -- 'on'        = aggiornamento + file cache + giorni nelle voci filtrate
    -- 'off'       = nessuna informazione
    -- 'date'      = solo aggiornamento (senza file cache e senza giorni)
    -- 'days'      = aggiornamento + giorni nelle voci filtrate (senza file cache)
    local timestampParam = args.timestamp or 'cachedays'
    timestampParam = mw.text.trim(mw.ustring.lower(timestampParam))
    if timestampParam ~= 'off' and timestampParam ~= 'on' and timestampParam ~= 'date'
            and timestampParam ~= 'days' and timestampParam ~= 'cachedays' then
        timestampParam = 'cachedays'
    end

    disp = mw.text.trim(mw.ustring.lower(disp))
    if disp ~= 's' and disp ~= 'v' and disp ~= 'o' and disp ~= 't' then
        disp = 's'
    end
    
    -- Carica dati da TUTTI i file automaticamente
    local data = loadAllData()
    
    -- Gestisci cache vuota o assente
    if not data or not data.voci or #data.voci == 0 then
        local msg = '<div class="noprint" style="padding:1em; border:2px solid #fc3; background:#ffc;">'
        
        if not data or data.num_files == 0 then
            msg = msg .. "'''⚠️ Cache non inizializzata'''<br/>Esegui il bot per creare la cache iniziale."
        else
            msg = msg .. "'''⚠️ Cache vuota'''<br/>Il bot sta rigenerando la cache. Riprova tra qualche minuto."
            
            -- Mostra errori se presenti
            if data.errors and #data.errors > 0 then
                msg = msg .. "<br/><small>Errori: " .. table.concat(data.errors, ", ") .. "</small>"
            end
        end
        
        msg = msg .. '</div>'
        return msg
    end
    
    -- Filtra le voci
    local filtered = {}
    
    for _, voce in ipairs(data.voci) do
        local matches = true
        
        if useAndLogic then
            -- MODALITÀ AND: TUTTI i filtri devono essere soddisfatti
            if andCat ~= '' and not matchesAndCat(voce[3] or {}, andCat) then
                matches = false
            end
            
            if orCat ~= '' and not matchesOrCat(voce[3] or {}, orCat) then
                matches = false
            end
            
            if titleSearch ~= '' and not matchesTitle(voce[1], titleSearch) then
                matches = false
            end
            
            if searchText ~= '' and not matchesText(voce[5], searchText) then
                matches = false
            end
            
            if dataFine ~= '' and not isAfterDate(voce[2], dataFine) then
                matches = false
            end
            
            if regexPattern ~= '' and not matchesRegex(buildSearchable(voce), regexPattern, useCaseSensitive) then
                matches = false
            end
            
            if andTemplate ~= '' and not matchesAndTemplate(voce[4] or {}, andTemplate) then
                matches = false
            end
            
            if orTemplate ~= '' and not matchesOrTemplate(voce[4] or {}, orTemplate) then
                matches = false
            end
            
            if portali ~= '' and not matchesPortali(voce[4] or {}, portali) then
                matches = false
            end
            
            if orPortali ~= '' and not matchesOrPortali(voce[4] or {}, orPortali) then
                matches = false
            end
            -- NoCat: sempre in AND (esclusione), anche in modalità AND
            if noCat ~= '' and not matchesNoCat(voce[3] or {}, noCat) then
                matches = false
            end
        else
            -- MODALITÀ OR: ALMENO UNO dei filtri deve essere soddisfatto
            matches = false
            
            -- Se nessun filtro è specificato, mostra comunque le voci
            local hasFilters = (andCat ~= '' or orCat ~= '' or titleSearch ~= '' or searchText ~= '' or regexPattern ~= '' or andTemplate ~= '' or orTemplate ~= '' or portali ~= '' or orPortali ~= '')
            
            if not hasFilters then
                matches = true
            else
                if andCat ~= '' and matchesAndCat(voce[3] or {}, andCat) then
                    matches = true
                end
                
                if orCat ~= '' and matchesOrCat(voce[3] or {}, orCat) then
                    matches = true
                end
                
                if titleSearch ~= '' and matchesTitle(voce[1], titleSearch) then
                    matches = true
                end
                
                if searchText ~= '' and matchesText(voce[5], searchText) then
                    matches = true
                end
                
                if regexPattern ~= '' and matchesRegex(buildSearchable(voce), regexPattern, useCaseSensitive) then
                    matches = true
                end
                
                if andTemplate ~= '' and matchesAndTemplate(voce[4] or {}, andTemplate) then
                    matches = true
                end
                
                if orTemplate ~= '' and matchesOrTemplate(voce[4] or {}, orTemplate) then
                    matches = true
                end
                
                if portali ~= '' and matchesPortali(voce[4] or {}, portali) then
                    matches = true
                end
                
                if orPortali ~= '' and matchesOrPortali(voce[4] or {}, orPortali) then
                    matches = true
                end
            end
            
            -- DataFine è sempre applicato in AND anche in modalità OR
            if dataFine ~= '' and not isAfterDate(voce[2], dataFine) then
                matches = false
            end
            -- NoCat è sempre applicato in AND anche in modalità OR (è un'esclusione)
            if noCat ~= '' and not matchesNoCat(voce[3] or {}, noCat) then
                matches = false
            end
        end
        
        if matches then
            table.insert(filtered, voce)
        end
    end

    -- Ordinamento
    -- Nota: formato array posizionale -> voce[1]=titolo, voce[2]=timestamp
    if order == 'dataold' then
        -- Data crescente: dal timestamp più piccolo (più vecchio) al più grande
        table.sort(filtered, function(a, b)
            return (a[2] or '') < (b[2] or '')
        end)
    elseif order == 'alpha' then
        -- Alfabetico crescente sul titolo, ignorando diacritici e maiuscole
        table.sort(filtered, function(a, b)
            return normalizeForSort(a[1] or '') < normalizeForSort(b[1] or '')
        end)
    end
    -- order == 'data': la cache è già ordinata per data decrescente, nessun sort necessario

    -- Tronca al numero richiesto dopo l'ordinamento
    if #filtered > num then
        local truncated = {}
        for i = 1, num do
            truncated[i] = filtered[i]
        end
        filtered = truncated
    end

    if #filtered == 0 then
        local msg = [=[<div class="noprint" style="padding:1em; border:1px solid #a2a9b1; background:#f8f9fa;">''Nessuna voce trovata con i criteri specificati.''</div>]=]
        if timestampParam ~= 'off' and data.ultimo_aggiornamento then
            msg = msg .. '\n' .. buildTimestampLine(timestampParam, data.ultimo_aggiornamento, data.num_files, nil, data.voci)
        end
        return msg
    end

    local result = p.formatOutput(filtered, disp, data.ultimo_aggiornamento, data.num_files, timestampParam, data.voci)
    if scrollHeight then
        result = '<div style="overflow-y:auto; height:' .. scrollHeight .. '; border:1px solid #ccc; padding:0.3em;">'
                 .. frame:preprocess(result)
                 .. '</div>'
    end
    return result
end


-- Formattazione output
function p.formatOutput(voci, disp, ultimoAggiornamento, numFiles, timestampParam, cacheVoci)
    local output = {}

    -- timestampParam: default 'on' se non passato (compatibilità chiamate dirette)
    if timestampParam == nil then timestampParam = 'cachedays' end

    if disp == 't' then
        for i, voce in ipairs(voci) do
            table.insert(output, '* [[' .. voce[1] .. ']]')
        end
    elseif disp == 'o' then
        for i, voce in ipairs(voci) do
            local dateStr = formatTimestamp(voce[2])
            table.insert(output, '* [[' .. voce[1] .. ']] <small>(' .. dateStr .. ')</small>')
        end
    elseif disp == 'v' then
        for i, voce in ipairs(voci) do
            local dateStr = formatTimestamp(voce[2])
            table.insert(output, '# [[' .. voce[1] .. ']] <small>(' .. dateStr .. ')</small>')
        end
    else
        for i, voce in ipairs(voci) do
            table.insert(output, '# [[' .. voce[1] .. ']]')
        end
    end

    if timestampParam ~= 'off' and ultimoAggiornamento then
        table.insert(output, '')
        table.insert(output, buildTimestampLine(timestampParam, ultimoAggiornamento, numFiles, voci, cacheVoci))
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
    local args = getArgs(frame)
    local titoloTest = args.titolo or args[1] or ''
    local orCatTest = args.orcat or ''
    
    if titoloTest == '' then
        return "Specifica un titolo: {{#invoke:VociRecenti|debugVoce|titolo=Rudolf Frank|OrCat=aviatori}}"
    end
    
    -- Carica dati
    local data = loadAllData()
    
    if not data.voci or #data.voci == 0 then
        return "ERRORE: Cache vuota"
    end
    
    -- Cerca la voce
    local voceTest = nil
    for _, voce in ipairs(data.voci) do
        if voce[1] == titoloTest then
            voceTest = voce
            break
        end
    end
    
    if not voceTest then
        return "ERRORE: Voce '" .. titoloTest .. "' non trovata nella cache"
    end
    
    -- Output debug
    local output = {}
    table.insert(output, "=== DEBUG VOCE ===\n")
    table.insert(output, "'''Titolo:''' " .. voceTest.titolo .. "\n")
    table.insert(output, "'''Timestamp:''' " .. voceTest.timestamp .. "\n")
    table.insert(output, "'''Numero categorie:''' " .. #(voceTest.categorie or {}) .. "\n\n")
    
    table.insert(output, "'''Categorie:'''\n")
    for i, cat in ipairs(voceTest.categorie or {}) do
        table.insert(output, "* " .. cat .. "\n")
    end
    
    if orCatTest ~= '' then
        table.insert(output, "\n'''Test OrCat = '" .. orCatTest .. "':'''\n")
        local match = matchesOrCat(voceTest.categorie or {}, orCatTest)
        table.insert(output, "* Risultato: " .. (match and "MATCH" or "NO MATCH") .. "\n")
        
        -- Test dettagliato
        table.insert(output, "\n'''Dettaglio match:'''\n")
        local requiredCats = split(orCatTest, ',')
        for _, reqCat in ipairs(requiredCats) do
            table.insert(output, "* Cerca '" .. reqCat .. "':\n")
            for _, cat in ipairs(voceTest.categorie or {}) do
                local catLower = mw.ustring.lower(cat)
                local reqLower = mw.ustring.lower(reqCat)
                local found = mw.ustring.find(catLower, reqLower, 1, true) ~= nil
                if found then
                    table.insert(output, "  ** TROVATO in: " .. cat .. "\n")
                end
            end
        end
    end
    
    return table.concat(output, "")
end

return p
