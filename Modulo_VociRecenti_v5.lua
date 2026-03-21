-- Modulo:VociRecenti
-- Versione 5.0 con parametro Title e Text sul contenuto completo
-- Basato su cache aggiornata da bot in Modulo:VociRecenti/Dati

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

-- Funzione per verificare se una stringa contiene un'altra (case-insensitive)
local function contains(haystack, needle)
    if not haystack or not needle then return false end
    haystack = mw.ustring.lower(haystack)
    needle = mw.ustring.lower(needle)
    return mw.ustring.find(haystack, needle, 1, true) ~= nil
end

-- Funzione per verificare se una voce è in tutte le categorie (AND) - RICERCA PARZIALE
local function matchesAndCat(categories, andCat)
    if not andCat or andCat == '' then return true end
    
    local requiredCats = split(andCat, ',')
    
    -- Per ogni categoria richiesta
    for _, reqCat in ipairs(requiredCats) do
        local found = false
        
        -- Cerca tra le categorie della pagina
        for _, cat in ipairs(categories) do
            -- Match parziale: cerca se reqCat è contenuto in cat
            if contains(cat, reqCat) then
                found = true
                break
            end
        end
        
        -- Se non trovata, la voce non passa il filtro AND
        if not found then return false end
    end
    
    return true
end

-- Funzione per verificare se una voce è in almeno una categoria (OR) - RICERCA PARZIALE
local function matchesOrCat(categories, orCat)
    if not orCat or orCat == '' then return true end
    
    local requiredCats = split(orCat, ',')
    
    -- Per ogni categoria richiesta
    for _, reqCat in ipairs(requiredCats) do
        -- Cerca tra le categorie della pagina
        for _, cat in ipairs(categories) do
            -- Match parziale: cerca se reqCat è contenuto in cat
            if contains(cat, reqCat) then
                return true
            end
        end
    end
    
    return false
end

-- NOVITÀ: Funzione per verificare il TITOLO (parametro Title)
local function matchesTitle(title, titleSearch)
    if not titleSearch or titleSearch == '' then return true end
    return contains(title, titleSearch)
end

-- NOVITÀ: Funzione per verificare il CONTENUTO COMPLETO (parametro Text)
local function matchesText(content, text)
    if not text or text == '' then return true end
    if not content then return false end
    return contains(content, text)
end

-- Funzione per verificare se il contenuto soddisfa la regex
local function matchesRegex(content, pattern)
    if not pattern or pattern == '' then return true end
    if not content then return false end
    
    local success, result = pcall(function()
        return mw.ustring.find(content, pattern) ~= nil
    end)
    
    return success and result
end

-- Funzione per comparare date
local function isAfterDate(timestamp, dateLimit)
    if not dateLimit or dateLimit == '' then return true end
    
    -- Converti dateLimit da GG/MM/AAAA a AAAAMMGG
    local day, month, year = dateLimit:match('(%d+)/(%d+)/(%d+)')
    if not day then return true end
    
    local limitStr = string.format('%04d%02d%02d', tonumber(year), tonumber(month), tonumber(day))
    
    -- Estrai data da timestamp (formato: AAAAMMGGHHMMSS)
    local dateStr = timestamp:sub(1, 8)
    
    return dateStr >= limitStr
end

-- Funzione per formattare timestamp in formato leggibile
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

-- Funzione principale
function p.main(frame)
    local args = getArgs(frame)
    
    local num = tonumber(args.num) or 10
    if num < 1 then num = 10 end
    -- Nessun limite massimo - dipende solo dalla cache del bot
    
    local andCat = args.AndCat or ''
    local orCat = args.OrCat or ''
    local titleSearch = args.Title or ''  -- NUOVO parametro Title
    local searchText = args.Text or ''    -- Ora cerca nel contenuto completo
    local regexPattern = args.TextRegExp or ''
    local dataFine = args.DataFine or ''
    local disp = args.Disp or 's'
    
    -- Normalizza disp
    disp = mw.text.trim(mw.ustring.lower(disp))
    if disp ~= 's' and disp ~= 'v' and disp ~= 'o' and disp ~= 't' then
        disp = 's'  -- Fallback su standard
    end
    
    -- Carica i dati dalla pagina dati
    local dataPage = mw.title.new('Modulo:VociRecenti/Dati')
    
    if not dataPage or not dataPage.exists then
        return p.showSetupInstructions(args)
    end
    
    -- Carica il modulo dati
    local success, data = pcall(function()
        return mw.loadData('Modulo:VociRecenti/Dati')
    end)
    
    if not success or not data or not data.voci then
        return p.showSetupInstructions(args)
    end
    
    -- Filtra le voci
    local filtered = {}
    
    for _, voce in ipairs(data.voci) do
        local matches = true
        
        -- Filtra per categorie AND (con match parziale)
        if andCat ~= '' and not matchesAndCat(voce.categorie or {}, andCat) then
            matches = false
        end
        
        -- Filtra per categorie OR (con match parziale)
        if orCat ~= '' and not matchesOrCat(voce.categorie or {}, orCat) then
            matches = false
        end
        
        -- NUOVO: Filtra per titolo (match parziale, case-insensitive)
        if titleSearch ~= '' and not matchesTitle(voce.titolo, titleSearch) then
            matches = false
        end
        
        -- AGGIORNATO: Filtra per testo nel CONTENUTO COMPLETO (non più solo titolo)
        if searchText ~= '' and not matchesText(voce.contenuto, searchText) then
            matches = false
        end
        
        -- Filtra per data
        if dataFine ~= '' and not isAfterDate(voce.timestamp, dataFine) then
            matches = false
        end
        
        -- Filtra per regex
        if regexPattern ~= '' and not matchesRegex(voce.contenuto, regexPattern) then
            matches = false
        end
        
        if matches then
            table.insert(filtered, voce)
            if #filtered >= num then break end
        end
    end
    
    -- Genera output
    if #filtered == 0 then
        return '<div class="noprint" style="padding:1em; border:1px solid #a2a9b1; background:#f8f9fa;">\'\'Nessuna voce trovata con i criteri specificati.\'\'</div>'
    end
    
    return p.formatOutput(filtered, disp, data.ultimo_aggiornamento)
end

-- Funzione per formattare l'output in base alla modalità Disp
function p.formatOutput(voci, disp, ultimoAggiornamento)
    local output = {}
    
    if disp == 't' then
        -- Modalità t: solo titolo voce, senza nient'altro
        for i, voce in ipairs(voci) do
            table.insert(output, '* [[' .. voce.titolo .. ']]')
        end
        
    elseif disp == 'o' then
        -- Modalità o: voce e data in piccolo tra parentesi, senza numero d'ordine
        for i, voce in ipairs(voci) do
            local dateStr = formatTimestamp(voce.timestamp)
            table.insert(output, '* [[' .. voce.titolo .. ']] <small>(' .. dateStr .. ')</small>')
        end
        
    elseif disp == 'v' then
        -- Modalità v: numero d'ordine, voce e data in piccolo tra parentesi
        for i, voce in ipairs(voci) do
            local dateStr = formatTimestamp(voce.timestamp)
            table.insert(output, '# [[' .. voce.titolo .. ']] <small>(' .. dateStr .. ')</small>')
        end
        
    else
        -- Modalità s (standard): solo voce con numero d'ordine
        for i, voce in ipairs(voci) do
            table.insert(output, '# [[' .. voce.titolo .. ']]')
        end
    end
    
    -- Aggiungi nota sull'ultimo aggiornamento (solo per modalità non 't')
    if disp ~= 't' and ultimoAggiornamento then
        table.insert(output, '')
        table.insert(output, '<small>Ultimo aggiornamento dati: ' .. ultimoAggiornamento .. '</small>')
    end
    
    return table.concat(output, '\n')
end

-- Funzione per mostrare istruzioni di setup
function p.showSetupInstructions(args)
    local output = {}
    
    table.insert(output, '<div style="border:2px solid #fc3; background:#ffc; padding:1.5em; margin:1em 0;">')
    table.insert(output, "=== ⚠️ Configurazione necessaria ===\n")
    table.insert(output, "Il template '''VociRecenti''' richiede che un bot aggiorni periodicamente la pagina '''[[Modulo:VociRecenti/Dati]]'''.\n\n")
    
    table.insert(output, "'''Istruzioni per configurare il bot:'''\n")
    table.insert(output, "# Crea un bot con le credenziali appropriate")
    table.insert(output, "\n# Scarica lo script bot dalla documentazione")
    table.insert(output, "\n# Configura il bot per aggiornare [[Modulo:VociRecenti/Dati]] ogni ora")
    table.insert(output, "\n# Il bot deve usare l'API MediaWiki per recuperare le pagine recenti")
    
    table.insert(output, "\n\n'''Alternative senza bot:'''\n")
    table.insert(output, "* [[Speciale:PaginePiùRecenti]] - Visualizza manualmente le pagine recenti")
    
    if args.AndCat and args.AndCat ~= '' then
        local firstCat = args.AndCat:match('[^,]+')
        if firstCat then
            table.insert(output, "\n* [[Categoria:" .. mw.text.trim(firstCat) .. "]] - Naviga nella categoria")
        end
    end
    
    table.insert(output, "\n\n'''Parametri ricevuti:'''")
    table.insert(output, "\n* Numero voci: " .. (args.num or '10'))
    if args.AndCat and args.AndCat ~= '' then
        table.insert(output, "\n* Categorie (AND - match parziale): " .. args.AndCat)
    end
    if args.OrCat and args.OrCat ~= '' then
        table.insert(output, "\n* Categorie (OR - match parziale): " .. args.OrCat)
    end
    if args.Text and args.Text ~= '' then
        table.insert(output, "\n* Testo: " .. args.Text)
    end
    if args.TextRegExp and args.TextRegExp ~= '' then
        table.insert(output, "\n* RegExp: " .. args.TextRegExp)
    end
    if args.DataFine and args.DataFine ~= '' then
        table.insert(output, "\n* Data fine: " .. args.DataFine)
    end
    if args.Disp and args.Disp ~= '' then
        table.insert(output, "\n* Modalità visualizzazione: " .. args.Disp)
    end
    
    table.insert(output, "\n\n'''Nota:''' La ricerca nelle categorie ora supporta match parziali (case-insensitive).")
    table.insert(output, "\n\n'''Documentazione completa:''' [[Template:VociRecenti/Documentazione]]")
    table.insert(output, '</div>')
    
    return table.concat(output, '')
end

return p
