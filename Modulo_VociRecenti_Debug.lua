-- Modulo:VociRecenti/Debug
-- Versione debug per diagnosticare problemi con TextRegExp

local p = {}

function p.testRegex(frame)
    local args = frame:getParent().args
    -- Accetta sia parametro posizionale che nominato
    local pattern = args.TextRegExp or args[1] or ''
    
    local output = {}
    table.insert(output, "=== DEBUG COMPLETO ===\n")
    table.insert(output, "'''Pattern RICEVUTO (raw):''' <code>" .. mw.text.encode(pattern) .. "</code>\n")
    table.insert(output, "'''Lunghezza:''' " .. mw.ustring.len(pattern) .. "\n")
    
    -- Mostra caratteri uno per uno
    table.insert(output, "'''Caratteri:''' ")
    for i = 1, mw.ustring.len(pattern) do
        local char = mw.ustring.sub(pattern, i, i)
        local code = mw.ustring.codepoint(char)
        table.insert(output, string.format("%s(U+%04X) ", char, code))
    end
    table.insert(output, "\n\n")
    
    -- Mostra tutti i parametri ricevuti
    table.insert(output, "'''Tutti i parametri ricevuti:'''\n")
    for k, v in pairs(args) do
        table.insert(output, "* " .. tostring(k) .. " = " .. tostring(v) .. "\n")
    end
    table.insert(output, "\n")
    
    -- Sostituisci marcatori
    local patternProcessed = pattern
    if patternProcessed ~= '' then
        patternProcessed = mw.ustring.gsub(patternProcessed, 'PIPE', '|')
        patternProcessed = mw.ustring.gsub(patternProcessed, '_OR_', '|')
        patternProcessed = mw.ustring.gsub(patternProcessed, '§', '|')
        patternProcessed = mw.ustring.gsub(patternProcessed, '¦', '|')
        patternProcessed = mw.ustring.gsub(patternProcessed, '<pipe>', '|')
    end
    
    table.insert(output, "'''Pattern DOPO sostituzione:''' <code>" .. mw.text.encode(patternProcessed) .. "</code>\n\n")
    
    -- Carica una voce di test
    local success, data = pcall(function()
        return require('Modulo:VociRecenti/Dati1')
    end)
    
    if not success then
        table.insert(output, "ERRORE loadData: " .. tostring(data))
        return table.concat(output, "")
    end
    
    if not data or not data.voci or #data.voci == 0 then
        table.insert(output, "ERRORE: Nessuna voce nel cache")
        return table.concat(output, "")
    end
    
    local voce = data.voci[1]
    
    table.insert(output, "'''Titolo voce test:''' " .. voce.titolo .. "\n")
    table.insert(output, "'''Contenuto presente:''' " .. (voce.contenuto and "SÌ" or "NO") .. "\n")
    
    if voce.contenuto then
        local len = mw.ustring.len(voce.contenuto)
        table.insert(output, "'''Lunghezza contenuto:''' " .. len .. " caratteri\n")
    end
    
    if patternProcessed ~= '' then
        -- Test regex sul contenuto (case-insensitive)
        if voce.contenuto then
            local contentLower = mw.ustring.lower(voce.contenuto)
            local patternLower = mw.ustring.lower(patternProcessed)
            local success2, matchContent = pcall(function()
                return mw.ustring.find(contentLower, patternLower) ~= nil
            end)
            
            if success2 then
                table.insert(output, "'''Match sul CONTENUTO:''' " .. (matchContent and "✓ SÌ" or "✗ NO") .. "\n")
            else
                table.insert(output, "'''ERRORE regex:''' " .. tostring(matchContent) .. "\n")
            end
        end
    end
    
    return table.concat(output, "")
end

return p
