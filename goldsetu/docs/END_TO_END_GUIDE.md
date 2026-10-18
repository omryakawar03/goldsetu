# GOLDSETU — End-to-End Step-by-Step Guide

**Guide updated: 14 October 2026.** Is guide ko order mein follow karein. Har step mein diya hai kya karna hai, kaise check karna hai, aur GOLDSETU mein abhi kya available hai.

> **Project status saaf-saaf:** FastAPI backend ka foundation aur kuch starter endpoints maujood hain. 15 synthetic domain/security tests pass hue hain. Live Atlas/API integration test abhi nahi hua. Dono Next.js/Android apps, offline SQLite sync, complete billing/tax/accounting, customer login, pledge servicing aur APKs abhi delivered nahi hain. Brochure ke phone screens sample mockups hain, running apps ke screenshots nahi.

## Project ka end-to-end flow

```text
Owner/Staff/Customer apps  →  HTTPS API  →  MongoDB Atlas
        (abhi pending)        (starter)       (dev DB)
```

Jab mobile apps banenge, SQLite har phone ka offline data/outbox rakhega. Atlas URI sirf API server mein rahega—Android app ya brochure mein kabhi nahi.

## Step 1 — Developer tools taiyar karein

Windows par yeh tools install karein:

1. Python 3.12 ya newer.
2. Git.
3. Optional: MongoDB Database Tools, agar `mongodump`/`mongorestore` backup drill karni hai.
4. Later Android work ke liye Node.js, `pnpm`, Android Studio, Android SDK aur supported JDK.

**Check:** PowerShell mein `python --version` chalakar version dekhein. Frontend ke liye repo mein abhi `package.json`/Next.js apps nahi hain, isliye `pnpm dev` filhaal chalne wala command nahi hai.

## Step 2 — GOLDSETU folder kholein

PowerShell se project API folder mein jaayein:

```powershell
Set-Location "<workspace>\goldsetu\apps\api"
```

`<workspace>` ko apne computer par project ke actual path se replace karein. Is checkout mein example path hai:

```powershell
Set-Location "C:\Users\omrya\OneDrive\Documents\New project\goldsetu\apps\api"
```

## Step 3 — Python environment aur dependencies install karein

Virtual environment banayein, activate karein, aur API dependencies install karein:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

**Check:** `python -m pip show fastapi pymongo pydantic` se packages listed dikhne chahiye. Agar PowerShell activation script block kare, policy change mat karein—direct interpreter use karein, jaise `.\.venv\Scripts\python.exe -m pip show fastapi`; tests bhi `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` se chala sakte hain.

## Step 4 — MongoDB Atlas Free dev cluster banayein

Atlas Free ko sirf **synthetic development/demo data** ke liye use karein. MongoDB docs ke mutabik Free cluster mein 512 MB data + indexes, 100 read/write operations/sec, 10 GB in/out data transfer per rolling 7 days, backups enabled nahi hote, aur 30 din zero connections par cluster auto-pause ho sakta hai. Limits badal sakti hain; setup ke din official [Free cluster limits](https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/) check karein. Tier comparison ke liye [Atlas cluster guide](https://www.mongodb.com/docs/atlas/manage-clusters/) dekhein.

Atlas website mein:

1. Atlas account mein `GOLDSETU-dev` naam ka project banayein.
2. **Create/Deploy Database** mein **Free** cluster chunein. Free tier ke liye available cloud aur region list mein se API/development location ke nazdeek option lein.
3. **Database Access** mein application ke liye alag database user banayein. Sirf `goldsetu_dev` database par required read/write role dein. Atlas website ka login is user ke roop mein use na karein.
4. **Network Access** mein abhi development machine ka current IP allow karein. `0.0.0.0/0` se duniya bhar ka access kholkar shortcut na lein.
5. Cluster **Connect → Drivers → Python/PyMongo** se connection string copy karein.
6. Password mein `@`, `:`, `/`, `#` jaise special characters hon toh URI ke andar URL-encode karein. Atlas ke placeholder host/user/password ko apne values se badlein.
7. Is cluster mein sirf fake names, fake phone numbers aur test products rakhein. Real customer, payment, tax, invoice ya pledge/collateral data bilkul nahi.

**Note:** Free cluster shared replica set hai, production availability/backup promise nahi. [Free tier ke detailed constraints](https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/) aur [inactive cluster pause behavior](https://www.mongodb.com/docs/atlas/backup/restore-free-tier-cluster/) padhein.

## Step 5 — API ka local environment configure karein

`apps/api` folder mein example copy karein:

```powershell
Copy-Item .env.example .env
notepad .env
```

`.env` ke placeholders ko apni dev values se replace karein:

```dotenv
GOLDSETU_ENV=development
MONGODB_URI=mongodb+srv://<db-user>:<encoded-password>@<cluster-host>/goldsetu_dev?retryWrites=true&w=majority
MONGODB_DATABASE=goldsetu_dev
GOLDSETU_ENABLE_PLEDGE_RECORDS=false
```

`.env` Git mein commit nahi hoti. URI ko chat, source code, browser page, app bundle, Android APK ya brochure mein mat daalein. Pledge flag `false` hi rehne dein—pledge endpoint abhi lending ke liye complete nahi hai.

## Step 6 — Pehle local tests chalayein

`apps/api` directory se:

```powershell
python -m unittest discover -s tests -v
```

**Expected:** 15 synthetic unit tests pass. Yeh money/domain/password/permission checks hain; Atlas se connect nahi hote aur API routes ki integration prove nahi karte.

## Step 7 — Dev database par migrations apply karein

Pehle `.env` mein database ka naam `goldsetu_dev` aur synthetic dev URI verify karein. Phir:

```powershell
goldsetu-migrate
```

Yeh command configured database mein versioned indexes/migration record likhti hai. Isse pehle `.env` sahi hai, aur target disposable dev database hai, yeh confirm karein. Production URI ya kisi existing customer DB par bina reviewed rollout plan ke na chalayein.

**Expected:** pehli run missing migrations apply kare; agli run “already current” bataye. Migration fail ho toh API start karne se pehle error resolve karein. API workers khud migration nahi chalate.

## Step 8 — Local API start karein aur health check karein

```powershell
uvicorn app.main:app --reload
```

Is PowerShell window ko khula rakhein. Nayi window mein:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/live
Invoke-RestMethod http://127.0.0.1:8000/health/ready
```

API documentation: [http://127.0.0.1:8000/api/v1/docs](http://127.0.0.1:8000/api/v1/docs). `ready` endpoint abhi startup ke waqt Atlas ping ke baad static ready response deta hai; ise full production monitoring na samjhein.

## Step 9 — Sirf synthetic owner account se API smoke check karein (optional)

Yeh POST Atlas dev database mein shop/user/session records banata hai. Sirf apne `goldsetu_dev` par fake details ke saath karein. Real password/email use na karein.

```powershell
$payload = @{
  full_name = "Demo Owner"
  email = "demo-owner@example.invalid"
  password = "Demo-Only-Password-Change-Me-123"
  shop_name = "Demo Jewellery Shop"
  shop_slug = "demo-jewellery-shop"
  branch_name = "Main Branch"
  branch_code = "MAIN"
} | ConvertTo-Json

$session = Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/auth/register-owner" `
  -ContentType "application/json" `
  -Body $payload

$session | Select-Object role, expires_at, shop
```

Apni session identity check karein:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/v1/auth/me" `
  -Headers @{ Authorization = "Bearer $($session.access_token)" }
```

Registration dobara chalane par same email/slug ke kaaran conflict expected hai. Reusable dev data ke liye naya synthetic slug/email dein; production database par smoke-test records na banayein.

## Step 10 — Kaun se backend pieces abhi try kiye ja sakte hain

Swagger UI (`/api/v1/docs`) current endpoints dikhata hai. Starter routes mein owner signup/login, branch/staff management, products, manual rates, customers, item intake/barcode lookup, stock adjustment/balances, invoice **drafts**, cash/pending payment records aur pledge-record endpoint shamil hain.

Yeh **complete shop workflow nahi** hai:

- Invoice endpoint sirf draft banata hai. Client ke bheje price/tax values proposal hain; final bill, official invoice number, GST calculation, inventory deduction, receipt/PDF/printing implemented nahi.
- Payment route sirf posted invoice accept karta hai; current invoice drafts posted nahi hote. UPI/card/bank records pending verification mein rehte hain; gateway webhook/reconciliation implemented nahi.
- Pledge endpoint `GOLDSETU_ENABLE_PLEDGE_RECORDS=false` par disabled hai. Is flag ko enable karke lending na karein.
- Atlas transactions/routes ko live MongoDB integration tests se verify nahi kiya gaya.

## Step 11 — Development backup/restore drill

Atlas Free par managed backups available nahi. Free cluster limits ke mutabik `mongodump`/`mongorestore` se manual backup/restore ki ja sakti hai. Command-line tools sirf **synthetic dev DB** ke saath test karein, backup folder ko Git se bahar rakhein, aur sensitive data ho toh encrypted storage use karein.

`mongodump` installed ho toh `.env` se URI current PowerShell process mein load karein (yeh command value print nahi karti):

```powershell
$uriLine = Get-Content .env | Where-Object { $_ -match '^MONGODB_URI=' }
$env:MONGODB_URI = $uriLine.Substring('MONGODB_URI='.Length).Trim().Trim('"')
$backupPath = Join-Path $env:TEMP 'goldsetu-backup-dev'
```

Ab dump banayein:

```powershell
mongodump --uri "$env:MONGODB_URI" --db goldsetu_dev --out $backupPath
```

Restore ko alag disposable database mein test karein—original ko overwrite na karein:

```powershell
mongorestore --uri "$env:MONGODB_URI" `
  --nsFrom "goldsetu_dev.*" `
  --nsTo "goldsetu_restore_check.*" `
  (Join-Path $backupPath 'goldsetu_dev')
```

**Check:** restore complete ho, collections/indexes dikh rahe hon, aur sample record counts expected hon. Backup tabhi useful hai jab restore bhi verify hua ho. Production ke liye managed backup wala suitable paid tier aur documented restore drills chahiye.

## Step 12 — App build status samjhein

Business aur Customer Android apps ke liye Next.js source, `pnpm-workspace.yaml`, Capacitor Android projects, SQLite plugin, signing setup ya APK abhi maujood nahi. Isliye yeh commands **abhi mat chalayein**:

```text
pnpm install
pnpm dev
./gradlew assembleDebug
```

Yeh tabhi runnable honge jab app manifests, actual screens, dependencies, Android projects aur plugin choices repository mein add aur verify ho jayenge. Brochure ke `assets/business-app-screen.svg` aur `assets/customer-app-screen.svg` sirf sample screen art hain.

## Step 13 — Production deploy se pehle gate

Abhi is repo ko real jewellery shop ke live financial/customer records ke liye deploy na karein. Production-ready deploy se pehle yeh sab complete aur test hona chahiye:

1. API route/import/integration tests disposable replica-set MongoDB par.
2. Server-side configured pricing + reviewed GST/tax; invoice posting, inventory deduction aur accounting ek atomic transaction mein.
3. Payment gateway signatures/reconciliation; duplicate webhook aur refund/reversal tests.
4. Customer identity verification aur har customer query par ownership checks.
5. Pledge lifecycle/custody/release/interest implementation, legal/compliance sign-off; tab tak feature disabled.
6. Role/tenant isolation, audit, backup/restore, vulnerability and load checks.
7. Next.js Business + Customer apps, local SQLite persistence/outbox/sync, native Android permissions, signing and device/printer QA.
8. Atlas Free se production-appropriate tier par move, secret manager, HTTPS, monitoring, backup policy, rollback and restore runbook.

Indian GST treatment, lending eligibility, privacy/retention aur payment provider setup ke liye qualified professional review lena hoga.

## Step 14 — Backend ko low/no downtime mein update kaise karein

Zero downtime sirf compatible backend releases aur multi-instance hosting mein target karein; har deployment ke liye guarantee nahi. Atlas Free production availability/backups provide nahi karta.

1. Production jaisa **staging** environment rakhein. Pehle restored staging data par migration, integration aur rollback/forward-fix rehearse karein.
2. API stateless rakhein, kam-se-kam 2 healthy instances load balancer ke peeche chalayein, liveness/readiness aur monitoring configure karein.
3. Schema/index changes **expand → deploy → backfill → verify → contract** order mein karein:
   - **Expand:** optional fields/new indexes add karein; purana aur naya API/client dono compatible rakhein.
   - **Deploy:** pehle canary/new instance; health check pass hone par traffic dein. Naya instance healthy hue bina old instance remove na karein.
   - **Backfill:** resumable batches mein; progress aur errors record karein.
   - **Verify:** record counts, financial balances, error rate, sync queue aur old client compatibility check karein.
   - **Contract:** old fields/routes tabhi remove karein jab supported app-version window guzar chuki ho.
4. Migration ko ek release job se ek hi baar run karein—har API worker startup par nahi. Unique index se pehle duplicate records inspect/resolve karein.
5. Error spike/health failure par app code ko previous release par rollback karein. Destructive schema changes ke liye pehle se tested restore/forward fix rakhein.
6. Atlas change/upgrade se pehle applicable backup aur restore verify karein. Mongo document updates additive rakhein; deploy, backfill aur verify ke baad purana field remove karein.

Single-instance/free host par restart ke dauran requests interrupt ho sakti hain; sleep/cold-start bhi ho sakta hai. Aise setup ko “zero downtime” na kahein.

## Step 15 — Android app updates ko users tak kaise pahunchayein

Android installed app update server rollout jaisa nahi: user install postpone kar sakta hai, offline reh sakta hai, aur installation app restart kar sakta hai. Har phone par literal zero downtime possible nahi.

1. API ko purane supported app versions ke saath backward compatible rakhein.
2. Business aur Customer packages alag IDs, versioning aur staged rollout se release karein.
3. Local SQLite schema migration additive/restart-safe ho; migration transaction pass hone ke baad version commit karein.
4. Pending offline outbox ko update ke waqt clear/discard na karein. Sync-conflict/retry status preserve karein.
5. Internal testers ke baad staged rollout; crash, failed sync, payment reconciliation aur API error metrics dekhein.
6. Native plugin, permission, signing ya Android code badla ho toh naya signed store build/APK release karein. Tested device/printer matrix ke bahar compatibility promise na karein.

## Step 16 — Brochure aur latest project status

- [Hinglish brochure](brochure-hinglish.html) mein Business aur Customer dono screen mockups hain. Numbers/names synthetic demo content hain—live application screenshots nahi.
- [Business screen asset](assets/business-app-screen.svg)
- [Customer screen asset](assets/customer-app-screen.svg)
- Phase-wise actual implementation: [implementation plan](implementation-plan.md)

Brochure mein apna actual contact, domain aur confirmed package pricing hi publish karein. Fake testimonials, certification, GST/legal approval, market rate, uptime ya savings claims add na karein.

## Sources

- MongoDB: [Atlas Free Cluster Limits](https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/)
- MongoDB: [Manage Clusters and tier comparison](https://www.mongodb.com/docs/atlas/manage-clusters/)
- MongoDB: [Restore data from a paused Free cluster](https://www.mongodb.com/docs/atlas/backup/restore-free-tier-cluster/)
