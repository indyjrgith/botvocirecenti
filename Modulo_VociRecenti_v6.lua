-- Modulo:VociRecenti
-- Versione 6.0 - Legge da cache divisa in due pagine
-- Modulo:VociRecenti/Dati1 + Modulo:VociRecenti/Dati2

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

-- Funzione per verificare contenuto in stringa (case-insensitive)
local function contains(haystack, needle)
    if not haystack or not needle then return false end
    haystack = mw.ustring.lower(haystack)
    needle = mw.ustring.lower(needle)
    return mw.ustring.find(haystack, needle, 1, true) ~= nil
end

-- Funzione per verificare categorie AND (match parziale)
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

-- Funzione per verificare categorie OR (match parziale)
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

-- Funzione per verificare il titolo
local function matchesTitle(title, titleSearch)
    if not titleSearch or titleSearch == '' then return true end
    return contains(title, titleSearch)
end

-- Funzione per verificare il contenuto
local function matchesText(content, text)
    if not text or text == '' then return true end
    if not content then return false end
    return contains(content, text)
end

-- Funzione per verificare regex
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
    
    local day, month, year = dateLimit:match('(%d+)/(%d+)/(%d+)')
    if not day then return true end
    
    local limitStr = string.format('%04d%02d%02d', tonumber(year), tonumber(month), tonumber(day))
    local dateStr = timestamp:sub(1, 8)
    
    return dateStr >= limitStr
end

-- Funzione per formattare timestamp
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

-- NUOVA FUNZIONE: Carica e unisce dati da entrambe le pagine
local function loadAllData()
    local allVoci = {}
    local ultimoAggiornamento = nil
    
    -- Carica Dati1
    local data1Page = mw.title.new('Modulo:VociRecenti/Dati1')
    if data1Page and data1Page.exists then
        local success1, data1 = pcall(function()
            return mw.loadData('Modulo:VociRecenti/Dati1')
        end)
        
        if success1 and data1 and data1.voci then
            for _, voce in ipairs(data1.voci) do
                table.insert(allVoci, voce)
            end
            ultimoAggiornamento = data1.ultimo_aggiornamento
        end
    end
    
    -- Carica Dati2
    local data2Page = mw.title.new('Modulo:VociRecenti/Dati2')
    if data2Page and data2Page.exists then
        local success2, data2 = pcall(function()
            return mw.loadData('Modulo:VociRecenti/Dati2')
        end)
        
        if success2 and data2 and data2.voci then
            for _, voce in ipairs(data2.voci) do
                table.insert(allVoci, voce)
            end
        end
    end
    
    return {
        voci = allVoci,
        ultimo_aggiornamento = ultimoAggiornamento
    }
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
    
    disp = mw.text.trim(mw.ustring.lower(disp))
    if disp ~= 's' and disp ~= 'v' and disp ~= 'o' and disp ~= 't' then
        disp = 's'
    end
    
    -- Carica dati da ENTRAMBE le pagine
    local data = loadAllData()
    
    if not data.voci or #data.voci == 0 then
        return p.showSetupInstructions(args)
    end
    
    -- Filtra le voci
    local filtered = {}
    
    for _, voce in ipairs(data.voci) do
        local matches = true
        
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
        
        if regexPattern ~= '' and not matchesRegex(voce.contenuto, regexPattern) then
            matches = false
        end
        
        if matches then
            table.insert(filtered, voce)
            if #filtered >= num then break end
        end
    end
    
    if #filtered == 0 then
        return '<div class="noprint" style="padding:1em; border:1px solid #a2a9b1; background:#f8f9fa;">\'\'Nessuna voce trovata con i criteri specificati.\'\'</div>'
    end
    
    return p.formatOutput(filtered, disp, data.ultimo_aggiornamento)
end

-- Funzione per formattare output
function p.formatOutput(voci, disp, ultimoAggiornamento)
    local output = {}
    
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
    
    if disp ~= 't' and ultimoAggiornamento then
        table.insert(output, '')
        table.insert(output, '<small>Ultimo aggiornamento: ' .. ultimoAggiornamento .. '</small>')
    end
    
    return table.concat(output, '\n')
end

-- Funzione per mostrare istruzioni
function p.showSetupInstructions(args)
    local output = {}
    
    table.insert(output, '<div style="border:2px solid #fc3; background:#ffc; padding:1.5em; margin:1em 0;">')
    table.insert(output, "=== ⚠️ Configurazione necessaria ===\n")
    table.insert(output, "Il template richiede che le pagine '''[[Modulo:VociRecenti/Dati1]]''' e '''[[Modulo:VociRecenti/Dati2]]''' esistano.\n\n")
    table.insert(output, "Esegui il bot v2.3 per creare entrambe le pagine.")
    table.insert(output, '</div>')
    
    return table.concat(output, '')
end

return p
