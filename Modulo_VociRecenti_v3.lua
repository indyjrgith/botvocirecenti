-- Modulo:VociRecenti
-- Versione aggiornata con parametro Disp per diverse modalità di visualizzazione
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

-- Funzione per verificare se una voce è in tutte le categorie (AND)
local function matchesAndCat(categories, andCat)
    if not andCat or andCat == '' then return true end
    
    local requiredCats = split(andCat, ',')
    for _, reqCat in ipairs(requiredCats) do
        local found = false
        for _, cat in ipairs(categories) do
            if cat == reqCat then
                found = true
                break
            end
        end
        if not found then return false end
    end
    return true
end

-- Funzione per verificare se una voce è in almeno una categoria (OR)
local function matchesOrCat(categories, orCat)
    if not orCat or orCat == '' then return true end
    
    local requiredCats = split(orCat, ',')
    for _, reqCat in ipairs(requiredCats) do
        for _, cat in ipairs(categories) do
            if cat == reqCat then return true end
        end
    end
    return false
end

-- Funzione per verificare se il titolo contiene il testo
local function matchesText(title, text)
    if not text or text == '' then return true end
    return mw.ustring.find(mw.ustring.lower(title), mw.ustring.lower(text), 1, true) ~= nil
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
    if num > 100 then num = 100 end
    if num < 1 then num = 1 end
    
    local andCat = args.AndCat or ''
    local orCat = args.OrCat or ''
    local searchText = args.Text or ''
    local regexPattern = args.TextRegExp or ''
    local dataFine = args.DataFine or ''
    local disp = args.Disp or 's'  -- Default: standard
    
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
        
        -- Filtra per categorie AND
        if andCat ~= '' and not matchesAndCat(voce.categorie or {}, andCat) then
            matches = false
        end
        
        -- Filtra per categorie OR
        if orCat ~= '' and not matchesOrCat(voce.categorie or {}, orCat) then
            matches = false
        end
        
        -- Filtra per testo nel titolo
        if searchText ~= '' and not matchesText(voce.titolo, searchText) then
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
        table.insert(output, "\n* Categorie (AND): " .. args.AndCat)
    end
    if args.OrCat and args.OrCat ~= '' then
        table.insert(output, "\n* Categorie (OR): " .. args.OrCat)
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
    
    table.insert(output, "\n\n'''Documentazione completa:''' [[Template:VociRecenti/Documentazione]]")
    table.insert(output, '</div>')
    
    return table.concat(output, '')
end

return p
