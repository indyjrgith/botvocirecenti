-- Modulo:VociRecenti
-- Versione 8.0 - Parametro Order (ordinamento) + parametro Timestamp
-- Legge automaticamente Dati1, Dati2, Dati3, ... (quanti ce ne sono)

local p = {}

-- Funzione per ottenere gli argomenti
local function getArgs(frame)
    local args = {}
    for k, v in pairs(frame:getParent().args) do
        if v ~= '' then
            args[k] = v
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

local function matchesRegex(content, pattern, caseSensitive)
    if not pattern or pattern == '' then return true end
    if not content then return false end
    
    local searchContent = content
    local searchPattern = pattern
    
    -- Se NON case-sensitive, converti tutto in lowercase
    if not caseSensitive then
        searchContent = mw.ustring.lower(content)
        searchPattern = mw.ustring.lower(pattern)
    end
    
    local success, result = pcall(function()
        return mw.ustring.find(searchContent, searchPattern) ~= nil
    end)
    
    return success and result
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
                    -- Verifica che abbia il campo voci
                    if data.voci and type(data.voci) == 'table' and #data.voci > 0 then
                        for _, voce in ipairs(data.voci) do
                            table.insert(allVoci, voce)
                        end
                        
                        if i == 1 and data.ultimo_aggiornamento then
                            ultimoAggiornamento = data.ultimo_aggiornamento
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
        local ts = voce.timestamp or ''
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

-- Funzione principale
function p.main(frame)
    local args = getArgs(frame)
    
    local num = tonumber(args.num) or 10
    if num < 1 then num = 10 end
    
    local andCat = args.AndCat or ''
    local orCat = args.OrCat or ''
    local titleSearch = args.Title or ''
    local searchText = args.Text or ''
    local regexPattern = args.TextRegExp or ''
    local dataFine = args.DataFine or ''
    local disp = args.Disp or 's'
    
    -- NOVITÀ: Parametro CaseSensitive (default 'off' per compatibilità)
    local caseSensitive = args.CaseSensitive or 'off'
    caseSensitive = mw.text.trim(mw.ustring.lower(caseSensitive))
    local useCaseSensitive = (caseSensitive == 'on' or caseSensitive == 'true' or caseSensitive == '1' or caseSensitive == 'yes')
    
    -- NOVITÀ: Parametro And (default 'on')
    local andMode = args.And or 'on'
    andMode = mw.text.trim(mw.ustring.lower(andMode))
    local useAndLogic = (andMode == 'on' or andMode == 'true' or andMode == '1' or andMode == 'yes')

    -- NOVITÀ: Parametro Order (default 'data')
    -- 'data'    = data decrescente (più recente prima, comportamento storico)
    -- 'dataold' = data crescente (più vecchia prima)
    -- 'alpha'   = ordine alfabetico crescente sul titolo
    local order = args.Order or 'data'
    order = mw.text.trim(mw.ustring.lower(order))
    if order ~= 'data' and order ~= 'dataold' and order ~= 'alpha' then
        order = 'data'
    end

    -- NOVITÀ: Parametro Timestamp (default 'cachedays')
    -- 'cachedays' = (default) aggiornamento + file cache + giorni nella cache
    -- 'on'        = aggiornamento + file cache + giorni nelle voci filtrate
    -- 'off'       = nessuna informazione
    -- 'date'      = solo aggiornamento (senza file cache e senza giorni)
    -- 'days'      = aggiornamento + giorni nelle voci filtrate (senza file cache)
    local timestampParam = args.Timestamp or 'cachedays'
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
            if andCat ~= '' and not matchesAndCat(voce.categorie or {}, andCat) then
                matches = false
            end
            
            if orCat ~= '' and not matchesOrCat(voce.categorie or {}, orCat) then
                matches = false
            end
            
            if titleSearch ~= '' and not matchesTitle(voce.titolo, titleSearch) then
                matches = false
            end
            
            if searchText ~= '' and not matchesText(voce.contenuto, searchText) then
                matches = false
            end
            
            if dataFine ~= '' and not isAfterDate(voce.timestamp, dataFine) then
                matches = false
            end
            
            if regexPattern ~= '' and not matchesRegex(voce.contenuto, regexPattern, useCaseSensitive) then
                matches = false
            end
        else
            -- MODALITÀ OR: ALMENO UNO dei filtri deve essere soddisfatto
            matches = false
            
            -- Se nessun filtro è specificato, mostra comunque le voci
            local hasFilters = (andCat ~= '' or orCat ~= '' or titleSearch ~= '' or searchText ~= '' or regexPattern ~= '')
            
            if not hasFilters then
                matches = true
            else
                if andCat ~= '' and matchesAndCat(voce.categorie or {}, andCat) then
                    matches = true
                end
                
                if orCat ~= '' and matchesOrCat(voce.categorie or {}, orCat) then
                    matches = true
                end
                
                if titleSearch ~= '' and matchesTitle(voce.titolo, titleSearch) then
                    matches = true
                end
                
                if searchText ~= '' and matchesText(voce.contenuto, searchText) then
                    matches = true
                end
                
                if regexPattern ~= '' and matchesRegex(voce.contenuto, regexPattern, useCaseSensitive) then
                    matches = true
                end
            end
            
            -- DataFine è sempre applicato in AND anche in modalità OR
            if dataFine ~= '' and not isAfterDate(voce.timestamp, dataFine) then
                matches = false
            end
        end
        
        if matches then
            table.insert(filtered, voce)
        end
    end

    -- Ordinamento
    if order == 'dataold' then
        -- Data crescente: dal timestamp più piccolo al più grande
        table.sort(filtered, function(a, b)
            return (a.timestamp or '') < (b.timestamp or '')
        end)
    elseif order == 'alpha' then
        -- Alfabetico crescente sul titolo, ignorando diacritici e maiuscole
        table.sort(filtered, function(a, b)
            return normalizeForSort(a.titolo) < normalizeForSort(b.titolo)
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

    return p.formatOutput(filtered, disp, data.ultimo_aggiornamento, data.num_files, timestampParam, data.voci)
end


-- Formattazione output
function p.formatOutput(voci, disp, ultimoAggiornamento, numFiles, timestampParam, cacheVoci)
    local output = {}

    -- timestampParam: default 'on' se non passato (compatibilità chiamate dirette)
    if timestampParam == nil then timestampParam = 'cachedays' end

    if disp == 't' then
        for i, voce in ipairs(voci) do
            table.insert(output, '* [[' .. voce.titolo .. ']]')
        end
    elseif disp == 'o' then
        for i, voce in ipairs(voci) do
            local dateStr = formatTimestamp(voce.timestamp)
            table.insert(output, '* [[' .. voce.titolo .. ']] <small>(' .. dateStr .. ')</small>')
        end
    elseif disp == 'v' then
        for i, voce in ipairs(voci) do
            local dateStr = formatTimestamp(voce.timestamp)
            table.insert(output, '# [[' .. voce.titolo .. ']] <small>(' .. dateStr .. ')</small>')
        end
    else
        for i, voce in ipairs(voci) do
            table.insert(output, '# [[' .. voce.titolo .. ']]')
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
    local orCatTest = args.OrCat or ''
    
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
        if voce.titolo == titoloTest then
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
