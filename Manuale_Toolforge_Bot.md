# Manuale Toolforge — BotVociRecenti

Questa guida spiega come trasferire, configurare e gestire BotVociRecenti su Wikimedia Toolforge, partendo da zero. È pensata per chiunque debba prendere in mano il bot, anche senza esperienza pregressa con Toolforge.

---

## Indice

1. [Cos'è Toolforge](#1-cosè-toolforge)
2. [Prerequisiti](#2-prerequisiti)
3. [Creazione account Wikimedia Developer](#3-creazione-account-wikimedia-developer)
4. [Configurazione SSH](#4-configurazione-ssh)
5. [Creazione del tool su Toolforge](#5-creazione-del-tool-su-toolforge)
6. [Configurazione GitHub](#6-configurazione-github)
7. [Primo accesso a Toolforge](#7-primo-accesso-a-toolforge)
8. [Caricamento del codice](#8-caricamento-del-codice)
9. [Configurazione credenziali](#9-configurazione-credenziali)
10. [Variabili d'ambiente](#10-variabili-dambiente)
11. [Build del container](#11-build-del-container)
12. [Primo avvio e test](#12-primo-avvio-e-test)
13. [Schedulazione](#13-schedulazione)
14. [Monitoraggio](#14-monitoraggio)
15. [Aggiornamento del bot](#15-aggiornamento-del-bot)
16. [Script avvia_bot_toolforge.sh](#16-script-avvia_bot_toolforgest)
17. [Struttura dei file su Toolforge](#17-struttura-dei-file-su-toolforge)
18. [Troubleshooting](#18-troubleshooting)
19. [Riferimenti utili](#19-riferimenti-utili)

---

## 1. Cos'è Toolforge

Toolforge è l'infrastruttura cloud di Wikimedia Foundation per ospitare bot, script e strumenti a supporto dei progetti Wikimedia. Il bot gira su Kubernetes: ogni esecuzione avviene in un container isolato che viene creato all'avvio e distrutto alla fine. I file persistenti vengono salvati nella home del tool su un volume NFS condiviso.

**Differenze rispetto a Termux:**
- Non c'è un processo sempre attivo: il bot viene lanciato da uno scheduler (cron Kubernetes)
- L'output non è visibile in tempo reale a meno di abilitare il file log
- Le dipendenze Python vanno installate in un container (build image)
- I file locali sopravvivono solo se scritti nella home del tool (`/data/project/<toolname>/`)

---

## 2. Prerequisiti

Prima di iniziare, assicurarsi di avere:

- **Account Wikipedia italiano** — l'account `BotVociRecenti` deve già esistere con il flag bot
- **Client SSH** — su Windows: PowerShell 7+ (OpenSSH incluso) o PuTTY; su Android: Termux
- **Git** — su Windows: installabile con `winget install Git.Git`
- **Account GitHub** — per ospitare il codice sorgente

---

## 3. Creazione account Wikimedia Developer

Se non esiste ancora, creare un account su:

👉 https://toolsadmin.wikimedia.org

Durante la registrazione vengono richiesti:
- **LDAP username** — usato per accedere a Gerrit e Toolsadmin
- **UNIX shell username** — usato per SSH e nei percorsi dei file (es. `indyjr`)
- **Email** e password

Dopo la registrazione, richiedere l'accesso a Toolforge:
- Toolsadmin → **Projects** → **Toolforge** → **Request membership**
- L'approvazione avviene in genere entro 24-48 ore

> **Nota:** Dopo l'approvazione, fare logout e login su Toolsadmin affinché la membership sia attiva.

---

## 4. Configurazione SSH

### Generare una coppia di chiavi SSH

Su Windows (PowerShell) o Termux:

```bash
ssh-keygen -t ed25519 -C "tua@email.com"
```

Accettare il percorso predefinito. Impostare una passphrase (consigliata).

### Aggiungere la chiave pubblica a Toolforge

Copiare il contenuto della chiave pubblica:

```powershell
# Windows
Get-Content ~/.ssh/id_ed25519.pub | clip

# Termux/Linux
cat ~/.ssh/id_ed25519.pub
```

Poi andare su **Toolsadmin → SSH Keys → Add SSH key** e incollare la chiave.

### Aggiungere la chiave pubblica a GitHub

Andare su **GitHub → Settings → SSH and GPG keys → New SSH key** e incollare la stessa chiave pubblica.

### Verificare i fingerprint

Prima di connettersi per la prima volta, verificare i fingerprint ufficiali:

- **Toolforge:** https://wikitech.wikimedia.org/wiki/Help:SSH_Fingerprints/login.toolforge.org
  - ED25519: `SHA256:0i1eqK9uOYmCjOe5a0oAWTmnEPUh0b7h2Flm1IDl0sg`
- **GitHub:** https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints
  - ED25519: `SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU`

### File `~/.ssh/config` (opzionale ma comodo)

```
Host toolforge
    HostName login.toolforge.org
    User tuoshelluser
    IdentityFile ~/.ssh/id_ed25519

Host github
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519
```

Con questo file ci si connette semplicemente con `ssh toolforge`.

---

## 5. Creazione del tool su Toolforge

Ogni bot deve avere il proprio **tool account** separato. Creare il tool su:

👉 https://toolsadmin.wikimedia.org/tools/create

- **Tool name:** `botvocirecenti` (o il nome scelto — sarà parte del percorso dei file)
- Dopo la creazione, il tool è accessibile dal bastion con il comando `become botvocirecenti`

---

## 6. Configurazione GitHub

### Creare il repository

Su https://github.com/new:
- **Repository name:** `botvocirecenti`
- **Visibility:** Public o Private
- **License:** MIT
- Spuntare "Add a README"

### Inizializzare il repo locale (Windows)

```powershell
cd C:\percorso\della\cartella\bot
git init
git remote add origin git@github.com:tuouser/botvocirecenti.git
```

### File `.gitignore`

Creare un file `.gitignore` per escludere file sensibili e temporanei:

```
# Credenziali - NON caricare mai
user-config.py
user-password.py

# Pywikibot
apicache/
throttle.ctrl
pywikibot-*.lwp

# Cache locali
moves_cache.json

# Log
bot_log.txt
bot_voci_recenti.log

# Python
__pycache__/
*.pyc

# Backup
backup/
```

### File `.gitattributes`

Per evitare problemi di fine riga tra Windows e Linux:

```
*.sh text eol=lf
*.py text eol=lf
```

### Primo push

```powershell
git add .
git commit -m "Prima versione BotVociRecenti"
git push -u origin main
```

---

## 7. Primo accesso a Toolforge

```bash
ssh tuoshelluser@login.toolforge.org
```

Alla prima connessione, verificare il fingerprint (vedi sezione 4) e digitare `yes`.

Una volta connessi, entrare nel contesto del tool:

```bash
become botvocirecenti
```

Il prompt cambierà in `tools.botvocirecenti@tools-bastion-XX:~$`.

> **Importante:** Tutti i comandi relativi al bot (git, toolforge jobs, ecc.) devono essere eseguiti dopo `become botvocirecenti`.

---

## 8. Caricamento del codice

### Clonare il repository GitHub

```bash
cd ~
git clone https://github.com/tuouser/botvocirecenti.git
```

Il codice sarà in `~/botvocirecenti/`.

### Aggiornare il codice in futuro

```bash
cd ~/botvocirecenti
git pull origin main
```

Se ci sono modifiche locali non committate che confliggono:

```bash
git checkout -- nomefile.py
git pull origin main
```

---

## 9. Configurazione credenziali

Le credenziali **non devono mai essere nel repository GitHub**. Vanno create direttamente su Toolforge nella cartella del bot.

### user-config.py

```bash
cat > ~/botvocirecenti/user-config.py << 'EOF'
# -*- coding: utf-8 -*-
family = 'wikipedia'
mylang = 'it'
usernames['wikipedia']['it'] = 'BotVociRecenti'
password_file = '/data/project/botvocirecenti/botvocirecenti/user-password.py'
put_throttle = 1
maxlag = 5
console_encoding = 'utf-8'
EOF
```

### user-password.py

```bash
printf "('BotVociRecenti', BotPassword('BotVociRecenti', 'la_tua_password_bot'))\n" > ~/botvocirecenti/user-password.py
```

> **Nota:** La password bot si ottiene da Wikipedia → Speciale:Password bot. Il formato è `NomeUtente@NomeBot` / `password`.

### Variabile d'ambiente per pywikibot

```bash
toolforge envvars create PYWIKIBOT_DIR /data/project/botvocirecenti/botvocirecenti
```

---

## 10. Variabili d'ambiente

Le variabili d'ambiente vengono iniettate automaticamente in ogni job del tool e sopravvivono tra le esecuzioni.

### Variabili necessarie

```bash
# Indica a pywikibot dove trovare user-config.py e user-password.py
toolforge envvars create PYWIKIBOT_DIR /data/project/botvocirecenti/botvocirecenti

# Indica al bot dove salvare i file JSON persistenti (moves_cache, cleanup_state)
toolforge envvars create BOT_DATA_DIR /data/project/botvocirecenti/botvocirecenti
```

### Verificare le variabili

```bash
toolforge envvars list
```

### Modificare una variabile

```bash
toolforge envvars delete NOME_VARIABILE
toolforge envvars create NOME_VARIABILE nuovo_valore
```

---

## 11. Build del container

Toolforge usa un sistema a container: il codice viene compilato in un'immagine Docker che include Python e tutte le dipendenze. Il build legge `requirements.txt` dal repository GitHub.

### requirements.txt

Il file deve essere presente nel repository:

```
pywikibot
```

### Avviare il build

```bash
cd ~/botvocirecenti
toolforge build start 'https://github.com/tuouser/botvocirecenti'
```

Il build mostra i log in tempo reale e impiega 1-3 minuti. Al termine compare:

```
Built image tools-harbor.wmcloud.org/tool-botvocirecenti/tool-botvocirecenti:latest
```

### Quando eseguire il rebuild

Il rebuild è necessario ogni volta che:
- Si modificano le dipendenze in `requirements.txt`
- Si aggiorna il codice Python nel repository (anche se le variabili d'ambiente non richiedono rebuild)

---

## 12. Primo avvio e test

### Avvio manuale (one-off)

```bash
cd ~/botvocirecenti
./avvia_bot_toolforge.sh
```

Oppure direttamente:

```bash
toolforge jobs run test-run \
    --command "python3 bot_voci_recenti_v30.py" \
    --image tool-botvocirecenti/tool-botvocirecenti:latest \
    --mount all \
    --filelog \
    --wait
```

### Monitorare l'output in tempo reale

```bash
./avvia_bot_toolforge.sh logs
```

Oppure direttamente:

```bash
tail -f ~/bot-oneoff.out
```

### Verificare lo stato del job

```bash
toolforge jobs show test-run
```

### Verificare i log

```bash
toolforge jobs logs test-run
```

### Verificare che i file persistenti siano stati creati

```bash
ls -la /data/project/botvocirecenti/botvocirecenti/*.json
```

Dopo la prima esecuzione completa dovrebbero esserci:
- `moves_cache.json` — cache degli spostamenti elaborati
- `cleanup_state.json` — stato della pulizia giornaliera

---

## 13. Schedulazione

### Schedulare il bot ogni ora

```bash
./avvia_bot_toolforge.sh 0h0m
```

Oppure direttamente con espressione cron:

```bash
toolforge jobs run botvocirecenti \
    --command "python3 bot_voci_recenti_v30.py" \
    --image tool-botvocirecenti/tool-botvocirecenti:latest \
    --mount all \
    --filelog \
    --schedule "0 * * * *"
```

### Sintassi dello script avvia_bot_toolforge.sh

```bash
./avvia_bot_toolforge.sh              # Lancio immediato (one-off)
./avvia_bot_toolforge.sh 5m           # Ogni ora, al minuto attuale+5
./avvia_bot_toolforge.sh 0h0m         # Ogni ora, al minuto 0
./avvia_bot_toolforge.sh 2h30m        # Ogni 2 ore, al minuto 30
./avvia_bot_toolforge.sh stop         # Ferma il bot in modo sicuro
./avvia_bot_toolforge.sh logs         # Monitora i log in tempo reale
```

### Verificare i job attivi

```bash
toolforge jobs list
```

### Note sul fuso orario

Toolforge usa **UTC** internamente. La schedulazione `0 * * * *` fa girare il bot alle ore UTC. Il bot imposta automaticamente il fuso orario `Europe/Rome` all'avvio, quindi i timestamp nelle pagine Wikipedia saranno in ora italiana.

---

## 14. Monitoraggio

### Log in tempo reale

```bash
./avvia_bot_toolforge.sh logs
```

Il log del job schedulato è in `~/botvocirecenti.out`, quello del job one-off in `~/bot-oneoff.out`.

### Log degli errori

```bash
cat ~/botvocirecenti.err
```

### Stato del job schedulato

```bash
toolforge jobs show botvocirecenti
```

### Tempi di esecuzione per step

```bash
grep "Tempo:" ~/botvocirecenti.out | tail -20
```

### Verifica file persistenti

```bash
ls -la /data/project/botvocirecenti/botvocirecenti/*.json
```

I file devono essere aggiornati all'ora dell'ultima esecuzione.

### Semaforo su Wikipedia

Nella pagina del bot su Wikipedia è presente un semaforo che mostra lo stato operativo:

```
{{#ifexpr: {{#time: U}} - {{#time: U | {{REVISIONTIMESTAMP:Modulo:VociRecenti/Dati1}}}} > 10800
  | 🔴 Offline
  | 🟢 Operativo
}}
```

Se il semaforo è rosso, il bot non ha aggiornato la cache da più di 3 ore.

---

## 15. Aggiornamento del bot

### Flusso di aggiornamento standard

1. Modificare i file sul PC locale
2. Push su GitHub:

```powershell
cd C:\percorso\bot
git add .
git commit -m "Descrizione delle modifiche"
git push origin main
```

3. Su Toolforge, aggiornare il codice locale e rebuilddare:

```bash
cd ~/botvocirecenti
git pull origin main
toolforge build start 'https://github.com/tuouser/botvocirecenti'
```

> **Nota:** Il rebuild non è necessario se si modificano solo le variabili d'ambiente o i file di credenziali.

### Aggiornare solo le credenziali

Le credenziali si rigenerano direttamente su Toolforge senza rebuild:

```bash
printf "('BotVociRecenti', BotPassword('BotVociRecenti', 'nuova_password'))\n" > ~/botvocirecenti/user-password.py
```

---

## 16. Script avvia_bot_toolforge.sh

Lo script automatizza le operazioni più comuni. Si trova nella cartella del bot e deve avere i permessi di esecuzione:

```bash
chmod +x ~/botvocirecenti/avvia_bot_toolforge.sh
```

### Comandi disponibili

| Comando | Descrizione |
|---|---|
| `./avvia_bot_toolforge.sh` | Lancia il bot una volta (chiede conferma) |
| `./avvia_bot_toolforge.sh Nm` | Schedula ogni ora al minuto attuale+N |
| `./avvia_bot_toolforge.sh XhYm` | Schedula ogni X ore al minuto Y |
| `./avvia_bot_toolforge.sh stop` | Ferma il bot in modo sicuro |
| `./avvia_bot_toolforge.sh logs` | Monitora i log in tempo reale |

### Stop sicuro

Il comando `stop` verifica se il bot sta scrivendo la cache su Wikipedia prima di fermarlo, evitando la corruzione dei dati. Controlla il timestamp dell'ultima modifica di `Modulo:VociRecenti/Dati1`: se è stata modificata meno di 5 minuti fa, aspetta 30 secondi e ricontrolla.

---

## 17. Struttura dei file su Toolforge

```
/data/project/botvocirecenti/          ← Home del tool (persistente)
├── botvocirecenti/                    ← Cartella del repo (clonata da GitHub)
│   ├── bot_voci_recenti_v30.py        ← Script principale del bot
│   ├── PuliziaCache.py                ← Script pulizia cache
│   ├── avvia_bot_toolforge.sh         ← Script di gestione
│   ├── requirements.txt               ← Dipendenze Python
│   ├── user-config.py                 ← Configurazione pywikibot (NON nel repo)
│   ├── user-password.py               ← Credenziali (NON nel repo)
│   ├── moves_cache.json               ← Cache spostamenti (persistente)
│   └── cleanup_state.json             ← Stato pulizia (persistente)
├── botvocirecenti.out                 ← Log output job schedulato
└── botvocirecenti.err                 ← Log errori job schedulato
```

> **Nota:** Nel container Kubernetes il codice viene copiato in `/workspace/`. I file JSON vengono scritti nella cartella del repo grazie alla variabile `BOT_DATA_DIR`.

---

## 18. Troubleshooting

### Il bot non si connette a Wikipedia

Verificare le credenziali:
```bash
cat ~/botvocirecenti/user-config.py
cat ~/botvocirecenti/user-password.py
toolforge envvars list  # PYWIKIBOT_DIR deve essere impostata
```

### Il bot parte da zero ogni volta (moves_cache non aggiornato)

Verificare che `BOT_DATA_DIR` sia impostata:
```bash
toolforge envvars list  # BOT_DATA_DIR deve essere impostata
ls -la /data/project/botvocirecenti/botvocirecenti/*.json
```

Se i file JSON non vengono aggiornati, la variabile non viene letta correttamente. Verificare:
```bash
toolforge jobs logs botvocirecenti | grep "WARNING\|moves_cache"
```

### Il job non parte alla schedulazione

```bash
toolforge jobs show botvocirecenti
```

Se lo stato è `No pods were created`, potrebbe essere un problema temporaneo di Toolforge. Attendere la prossima esecuzione o ricreare il job:
```bash
toolforge jobs delete botvocirecenti
./avvia_bot_toolforge.sh 0h0m
```

### Errore "Logged in as '172.16.x.x' instead of 'BotVociRecenti'"

Questo è un **warning normale** di pywikibot su Toolforge, causato dal NAT della rete interna. Non è un errore reale — le pagine vengono salvate correttamente e può essere ignorato.

### Il build fallisce

```bash
toolforge build logs
```

Verificare che `requirements.txt` esista nel repository e che il codice Python non abbia errori di sintassi.

### La pulizia cache avviene più volte per notte

Verificare che `cleanup_state.json` venga aggiornato correttamente dopo ogni pulizia:
```bash
cat /data/project/botvocirecenti/botvocirecenti/cleanup_state.json
```

Deve contenere `"cleaned_today": true` dopo l'esecuzione nella fascia notturna. Se non viene aggiornato, verificare `BOT_DATA_DIR`.

### Il semaforo su Wikipedia è rosso

Il bot non ha aggiornato la cache da più di 3 ore. Verificare:
```bash
toolforge jobs list                    # Il job è schedulato?
toolforge jobs logs botvocirecenti     # Ci sono errori?
cat ~/botvocirecenti.err               # Errori critici?
```

---

## 19. Riferimenti utili

| Risorsa | URL |
|---|---|
| Toolsadmin (gestione tool e chiavi SSH) | https://toolsadmin.wikimedia.org |
| Documentazione Toolforge | https://wikitech.wikimedia.org/wiki/Help:Toolforge |
| SSH Fingerprints Toolforge | https://wikitech.wikimedia.org/wiki/Help:SSH_Fingerprints/login.toolforge.org |
| Quickstart Toolforge | https://wikitech.wikimedia.org/wiki/Help:Toolforge/Quickstart |
| Jobs framework | https://wikitech.wikimedia.org/wiki/Help:Toolforge/Jobs_framework |
| Repository GitHub del bot | https://github.com/indyjrgith/botvocirecenti |
| Pagina del bot su Wikipedia | https://it.wikipedia.org/wiki/Utente:BotVociRecenti |
