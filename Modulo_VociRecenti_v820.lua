-- Modulo:VociRecenti
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

-- Memoizzazione: i dati cache vengono caricati una sola volta per pagina.
-- Le chiamate successive a loadAllData() riusano questo risultato,
-- evitando di ricaricare tutti i file Dati da zero per ogni template.
local _cachedData = nil

-- Funzione per ottenere gli argomenti
local function getArgs(frame)
    local args = {}
    for k, v in pairs(frame:getParent().args) do
        if v ~= '' then
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

-- Funzione contains (case-insensitive)
local function contains(haystack, needle)
    if not haystack or not needle then return false end
    haystack = mw.ustring.lower(haystack)
    needle = mw.ustring.lower(needle)
    return mw.ustring.find(haystack, needle, 1, true) ~= nil
end

-- Verifica se haystack contiene almeno uno dei termini separati da ";" (OR).
-- Usata internamente dalle funzioni di matching per supportare il separatore ;.
local function matchesAnyInGroup(haystack, group)
    if mw.ustring.find(group, ';', 1, true) then
        for _, term in ipairs(split(group, ';')) do
            if contains(haystack, term) then return true end
        end
        return false
    end
    return contains(haystack, group)
end

-- Funzioni di matching

local function matchesAndCat(categories, andCat)
    if not andCat or andCat == '' then return true end
    -- Virgola = AND tra gruppi; punto e virgola = OR dentro ogni gruppo
    -- Es: "parte1;parte2,parte3" -> (parte1 OR parte2) AND parte3
    local groups = split(andCat, ',')
    for _, group in ipairs(groups) do
        local found = false
        for _, cat in ipairs(categories) do
            if matchesAnyInGroup(cat, group) then
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
    -- Virgola = OR tra gruppi; punto e virgola = OR dentro ogni gruppo
    local groups = split(orCat, ',')
    for _, group in ipairs(groups) do
        for _, cat in ipairs(categories) do
            if matchesAnyInGroup(cat, group) then
                return true
            end
        end
    end
    return false
end

local function matchesNoCat(categories, noCat)
    if not noCat or noCat == '' then return true end
    -- Valore speciale '*': esclude voci che hanno almeno una categoria
    if mw.text.trim(noCat) == '*' then
        return #categories == 0
    end
    -- Virgola = AND tra esclusioni; punto e virgola = OR dentro ogni gruppo
    local groups = split(noCat, ',')
    for _, group in ipairs(groups) do
        for _, cat in ipairs(categories) do
            if matchesAnyInGroup(cat, group) then
                return false
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
    local groups = split(normalized, ';')
    if #groups == 0 then groups = {normalized} end
    for _, group in ipairs(groups) do
        group = mw.text.trim(group)
        if group ~= '' then
            -- Verifica AND tra tutti i termini del gruppo
            local andTerms = split(group, '+')
            if #andTerms == 0 then andTerms = {group} end
            local allMatch = true
            for _, term in ipairs(andTerms) do
                term = mw.text.trim(term)
                if term ~= '' and not contains(title, term) then
                    allMatch = false
                    break
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
    if mw.ustring.find(text, '|', 1, true) or mw.ustring.find(text, ';', 1, true) then
        local normalized = text:gsub('|', ';')
        local terms = split(normalized, ';')
        for _, term in ipairs(terms) do
            if contains(content, term) then return true end
        end
        return false
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
    return string.format('%s/%s/%s %s:%s UTC', day, month, year, hour, min)
end

local function matchesSingleTemplate(templates, tmplName, requiredParams)
    tmplName = mw.ustring.lower(mw.text.trim(tmplName))
    for _, tmpl in ipairs(templates) do
        local nome = mw.ustring.lower(tmpl[1] or '')
        if mw.ustring.find(nome, tmplName, 1, true) then
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
local function matchesNoTemplate(templates, noTmpl)
    if not noTmpl or noTmpl == '' then return true end
    -- Valore speciale '*': esclude voci che hanno almeno un template
    if mw.text.trim(noTmpl) == '*' then
        return #templates == 0
    end
    local groups = split(noTmpl, ',')
    for _, group in ipairs(groups) do
        for spec in (group .. ';'):gmatch('([^;]*);') do
            spec = mw.text.trim(spec)
            if spec ~= '' then
                local nome, params = parseTemplateSpec(spec)
                if matchesSingleTemplate(templates, nome, params) then
                    return false
                end
            end
        end
    end
    return true
end

-- AndTemplate: tutti i template elencati devono essere presenti
-- Virgola = AND tra gruppi; punto e virgola = OR dentro ogni gruppo
-- Es: "Bio;Wrestler,Portale" -> (Bio OR Wrestler) AND Portale
local function matchesAndTemplate(templates, andTmpl)
    if not andTmpl or andTmpl == '' then return true end
    for group in (andTmpl .. ','):gmatch('([^,]*),') do
        group = mw.text.trim(group)
        if group ~= '' then
            local found = false
            for spec in (group .. ';'):gmatch('([^;]*);') do
                spec = mw.text.trim(spec)
                if spec ~= '' then
                    local nome, params = parseTemplateSpec(spec)
                    if matchesSingleTemplate(templates, nome, params) then
                        found = true
                        break
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
local function matchesOrTemplate(templates, orTmpl)
    if not orTmpl or orTmpl == '' then return true end
    for group in (orTmpl .. ','):gmatch('([^,]*),') do
        group = mw.text.trim(group)
        if group ~= '' then
            for spec in (group .. ';'):gmatch('([^;]*);') do
                spec = mw.text.trim(spec)
                if spec ~= '' then
                    local nome, params = parseTemplateSpec(spec)
                    if matchesSingleTemplate(templates, nome, params) then
                        return true
                    end
                end
            end
        end
    end
    return false
end

-- Portali=p1,p2: AND su tutti i portali (tutti devono essere presenti)
local function matchesPortali(templates, portali)
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

-- OrPortali=p1,p2: OR sui portali (basta almeno uno presente)
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

-- Carica automaticamente TUTTI i file Dati (Dati1, Dati2, ...)
-- Il risultato viene memoizzato in _cachedData: se chiamata più volte
-- nella stessa pagina (es. più template VociRecenti), i file vengono
-- letti una sola volta riducendo significativamente il consumo di memoria.
local function loadAllData()
    if _cachedData then return _cachedData end
    local allVoci = {}
    local ultimoAggiornamento = nil
    local filesLoaded = 0
    local errors = {}
    local i = 1
    while i <= 100 do
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
                else
                    table.insert(errors, pageName .. ': formato non valido')
                end
            else
                table.insert(errors, pageName .. ': errore caricamento')
            end
        else
            break
        end
        i = i + 1
    end
    _cachedData = {
        voci = allVoci,
        ultimo_aggiornamento = ultimoAggiornamento,
        num_files = filesLoaded,
        errors = errors
    }
    return _cachedData
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
        local ts = voce[2] or ''
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

local function buildTimestampLine(timestampParam, ultimoAggiornamento, numFiles, voci, cacheVoci)
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
    if timestampParam == 'cachedays' and cacheVoci and #cacheVoci > 0 then
        local days = calcDaysRange(cacheVoci)
        if days then
            local daysLabel = days == 1 and '1 giorno nella cache' or (days .. ' giorni nella cache')
            line = line .. ', ' .. daysLabel
        end
    end
    return '<small>' .. line .. '</small>'
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
    local titleSearch = normFilter(args.title)
    local searchText = normFilter(args.text)
    local regexPattern = normFilter(args.textregexp)
    local andTemplate = normFilter(args.andtemplate)
    local orTemplate = normFilter(args.ortemplate)
    local portali = normFilter(args.portali)
    local orPortali = normFilter(args.orportali)
    local dataFine = normFilter(args.datafine)
    local noTemplate = normFilter(args.notemplate)

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

    local data = loadAllData()

    if not data or not data.voci or #data.voci == 0 then
        local msg = '<div class="noprint" style="padding:1em; border:2px solid #fc3; background:#ffc;">'
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

    local filtered = {}

    for _, voce in ipairs(data.voci) do
        local matches = true

        if useAndLogic then
            if andCat ~= '' and not matchesAndCat(voce[3] or {}, andCat) then matches = false end
            if orCat ~= '' and not matchesOrCat(voce[3] or {}, orCat) then matches = false end
            if titleSearch ~= '' and not matchesTitle(voce[1], titleSearch) then matches = false end
            if searchText ~= '' and not matchesText(voce[5], searchText) then matches = false end
            if dataFine ~= '' and not isAfterDate(voce[2], dataFine) then matches = false end
            if regexPattern ~= '' and not matchesRegex(buildSearchable(voce), regexPattern, useCaseSensitive) then matches = false end
            if andTemplate ~= '' and not matchesAndTemplate(voce[4] or {}, andTemplate) then matches = false end
            if orTemplate ~= '' and not matchesOrTemplate(voce[4] or {}, orTemplate) then matches = false end
            if portali ~= '' and not matchesPortali(voce[4] or {}, portali) then matches = false end
            if orPortali ~= '' and not matchesOrPortali(voce[4] or {}, orPortali) then matches = false end
            if noCat ~= '' and not matchesNoCat(voce[3] or {}, noCat) then matches = false end
            if noTemplate ~= '' and not matchesNoTemplate(voce[4] or {}, noTemplate) then matches = false end
        else
            matches = false
            local hasPositiveFilters = (andCat ~= '' or orCat ~= '' or titleSearch ~= '' or searchText ~= '' or regexPattern ~= '' or andTemplate ~= '' or orTemplate ~= '' or portali ~= '' or orPortali ~= '')
            local hasNegativeFilters = (noCat ~= '' or noTemplate ~= '')
            local hasFilters = hasPositiveFilters or hasNegativeFilters
            if not hasFilters then
                matches = true
            elseif not hasPositiveFilters then
                -- Solo filtri negativi: includi tutto, poi i No* filtrano sotto
                matches = true
            else
                if andCat ~= '' and matchesAndCat(voce[3] or {}, andCat) then matches = true end
                if orCat ~= '' and matchesOrCat(voce[3] or {}, orCat) then matches = true end
                if titleSearch ~= '' and matchesTitle(voce[1], titleSearch) then matches = true end
                if searchText ~= '' and matchesText(voce[5], searchText) then matches = true end
                if regexPattern ~= '' and matchesRegex(buildSearchable(voce), regexPattern, useCaseSensitive) then matches = true end
                if andTemplate ~= '' and matchesAndTemplate(voce[4] or {}, andTemplate) then matches = true end
                if orTemplate ~= '' and matchesOrTemplate(voce[4] or {}, orTemplate) then matches = true end
                if portali ~= '' and matchesPortali(voce[4] or {}, portali) then matches = true end
                if orPortali ~= '' and matchesOrPortali(voce[4] or {}, orPortali) then matches = true end
            end
            if dataFine ~= '' and not isAfterDate(voce[2], dataFine) then matches = false end
            if noCat ~= '' and not matchesNoCat(voce[3] or {}, noCat) then matches = false end
            if noTemplate ~= '' and not matchesNoTemplate(voce[4] or {}, noTemplate) then matches = false end
        end

        if matches then
            table.insert(filtered, voce)
        end
    end

    if order == 'dataold' then
        table.sort(filtered, function(a, b) return (a[2] or '') < (b[2] or '') end)
    elseif order == 'alpha' then
        table.sort(filtered, function(a, b)
            return normalizeForSort(a[1] or '') < normalizeForSort(b[1] or '')
        end)
    end

    if #filtered > num then
        local truncated = {}
        for i = 1, num do truncated[i] = filtered[i] end
        filtered = truncated
    end

    if #filtered == 0 then
        local msg = [=[<div class="noprint" style="padding:1em; border:1px solid #a2a9b1; background:#f8f9fa;">''Nessuna voce trovata con i criteri specificati.''</div>]=]
        if timestampParam ~= 'off' and data.ultimo_aggiornamento then
            msg = msg .. '\n' .. buildTimestampLine(timestampParam, data.ultimo_aggiornamento, data.num_files, nil, data.voci)
        end
        return msg
    end

    local result
    if scrollHeight then
        local listWiki = p.formatOutput(filtered, disp, nil, nil, 'off', nil)
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
                     data.ultimo_aggiornamento, data.num_files, filtered, data.voci)
        end
    else
        result = p.formatOutput(filtered, disp, data.ultimo_aggiornamento, data.num_files, timestampParam, data.voci)
    end
    return result
end

-- Formattazione output wikitext
function p.formatOutput(voci, disp, ultimoAggiornamento, numFiles, timestampParam, cacheVoci)
    local output = {}
    if timestampParam == nil then timestampParam = 'cachedays' end

    if disp == 'h' then
        local items = {}
        for i, voce in ipairs(voci) do
            table.insert(items, '[[' .. voce[1] .. ']]')
        end
        local listHtml = table.concat(items, ' · ')
        if timestampParam ~= 'off' and ultimoAggiornamento then
            return listHtml .. '<br/>' .. buildTimestampLine(timestampParam, ultimoAggiornamento, numFiles, voci, cacheVoci)
        end
        return listHtml
    elseif disp == 't' then
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

    return table.concat(output, "")
end

return p
