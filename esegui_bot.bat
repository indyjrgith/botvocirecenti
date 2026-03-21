@echo off
REM ========================================
REM Script per eseguire Bot VociRecenti
REM Versione: 2.5
REM Ultimo aggiornamento: 2025-02-22
REM ========================================

echo.
echo ============================================
echo Bot VociRecenti - Avvio automatico
echo ============================================
echo Data inizio: %date% %time%
echo.

REM Vai nella directory del bot
cd /d C:\Users\theil\Desktop\BotVociRecenti

REM Verifica che il file bot esista
if not exist "bot_voci_recenti_v30.py" (
    echo ERRORE: bot_voci_recenti_v30.py non trovato!
    echo Verifica il percorso della cartella
    pause
    exit /b 1
)

REM Crea cartella backup se non esiste
if not exist "backup" mkdir backup

REM Rotazione log se supera 5MB
for %%A in (bot_log.txt) do (
    if %%~zA gtr 5242880 (
        echo Log troppo grande, archivio...
        set TIMESTAMP=%date:~-4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%
        move bot_log.txt "backup\bot_log_%TIMESTAMP%.txt" >nul
    )
)

REM Esegui il bot e salva output nel log
echo Esecuzione bot in corso...
echo.
python bot_voci_recenti_v30.py >> bot_log.txt 2>&1

REM Salva codice di uscita
set EXITCODE=%ERRORLEVEL%

REM Mostra risultato
echo.
echo ============================================
if %EXITCODE%==0 (
    echo COMPLETATO CON SUCCESSO
    echo Codice uscita: %EXITCODE%
) else (
    echo ERRORE DURANTE L'ESECUZIONE
    echo Codice uscita: %EXITCODE%
    echo Controlla bot_log.txt per dettagli
)
echo Data fine: %date% %time%
echo ============================================
echo.

REM Scrivi separatore nel log
echo. >> bot_log.txt
echo ======================================== >> bot_log.txt
echo [%date% %time%] Esecuzione completata - Codice: %EXITCODE% >> bot_log.txt
echo ======================================== >> bot_log.txt
echo. >> bot_log.txt

REM Esci con il codice del bot
exit /b %EXITCODE%
