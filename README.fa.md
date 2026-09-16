# IDKMesh

[![PR Gate](https://github.com/MSKazemi/idkmesh/actions/workflows/pr-gate.yml/badge.svg?branch=main)](https://github.com/MSKazemi/idkmesh/actions/workflows/pr-gate.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](pyproject.toml)
[![good first issues](https://img.shields.io/github/issues/MSKazemi/idkmesh/good%20first%20issue?label=good%20first%20issues&color=7057ff)](https://github.com/MSKazemi/idkmesh/issues?q=is%3Aissue+state%3Aopen+label%3A%22good+first+issue%22)

**زبان:** [English](README.md) · فارسی

> **وضعیت ترجمه:** این فایل ترجمهٔ README انگلیسی در commit `d8669e3b47275a538477fe45e490840a6509ef8d` است. ترجمه با کمک هوش مصنوعی تهیه شده و هنوز نباید به‌عنوان ترجمه‌ای با کیفیت زبانیِ تأییدشده تلقی شود؛ پیش از چنین ادعایی، بازبینی مستقل یک فارسی‌زبان لازم است.

> **من نمی‌دانم. شما نمی‌دانید. با هم، mesh می‌تواند کشف کند، بسازد، راستی‌آزمایی کند و یاد بگیرد.**

IDKMesh یک پروژهٔ متن‌باز پژوهشی و مهندسی است که بررسی می‌کند انسان‌ها، عامل‌های هوش مصنوعی، ابزارهای نرم‌افزاری و منابع محاسباتی ناهمگون چگونه می‌توانند برای هدف‌های نامطمئن هماهنگ شوند و پیشنهادها را به **کار مفیدِ راستی‌آزمایی‌شده** تبدیل کنند.

این پروژه عمداً بلندپروازانه است، اما این مخزن ادعا نمی‌کند که یک سامانهٔ سیاره‌مقیاسِ کامل ساخته شده است. امروز، IDKMesh یک **آزمایشگاه پژوهشی مبتنی بر GitHub با یک زیربنای اجرایی برای هماهنگی/شواهد** و یک هدف محصول مرجع است: Git-native Verified Swarm Runner.

**یک پرسش مشخص که این مخزن همین حالا می‌تواند پاسخ دهد:** *پنل بازبینی شما واقعاً معادل چند رأی مستقل است؟* در بسیاری از موارد، بسیار کمتر از تعداد بازبین‌های حاضر در پنل. در [E017](experiments/E017-item-difficulty-and-quorum.md)، یک پنل ۲۵ راستی‌آزما — که هر راستی‌آزما یک برنامه بود و هر خطا یک نقصِ مشاهده‌شده و از‌دست‌رفته بود — اندازهٔ مؤثر **1.00 از 25** را نشان داد: در رأی‌گیری اکثریت، ارزش پنل از یک عضو بیشتر نبود، در حالی که تصحیح پرکاربرد `N/(1+(N-1)rho)` مقدار 1.66 را پیش‌بینی می‌کرد. [`idkmesh gate-audit`](#در-پنج-دقیقه-امتحان-کنید-ممیزی-یک-دروازهٔ-بازبینی) این اندازه‌گیری را روی رأی‌هایی که از قبل جمع‌آوری کرده‌اید اجرا می‌کند و نامزدهای عمداً معیوبی را که پنل شما از آن‌ها عبور داده است گزارش می‌کند.

## دموی قرارداد را امتحان کنید

با Git و Python 3.11 یا 3.13، از یک محیط مجازی استفاده کنید. نمونه برای Linux/macOS:

```bash
git clone https://github.com/MSKazemi/idkmesh && cd idkmesh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-phase0.txt
python scripts/demo.py
```

برای Windows، از دستورالعمل محیط در [CONTRIBUTING.md](CONTRIBUTING.md) استفاده کنید.
هیچ حساب مدل یا API key لازم نیست. زمان نصب به محیط شما بستگی دارد.

این دمو، **fixtureهای مصنوعی** ثبت‌شده را با validatorهای واقعی و schemaهای موجود در [`schemas/`](schemas/) و ورودی‌های [`examples/`](examples/) اعتبارسنجی می‌کند.
این دمو سه بررسی مثبت و چهار بررسی ردِ عمدی انجام می‌دهد:

| fixture نامعتبر | دلیل رد شدن |
| --- | --- |
| task بدون قرارداد امنیتی | یک قرارداد قابل dispatch باید محدودیت‌های امنیتی خود را اعلام کند |
| نتیجهٔ worker که خودش را می‌پذیرد | تکمیل کار توسط worker به معنای پذیرش نیست |
| verifier که از هویت worker استفاده می‌کند | worker نمی‌تواند خودش قرارداد verifier مستقل را برآورده کند |
| verification با provenance ناسازگار | شواهد باید به artifactهای ارائه‌شده متصل باشند |

**هیچ worker زنده یا verifier خارجی اجرا نمی‌شود.** عبور یک fixture از اعتبارسنجی، اثباتی برای استقلال در دنیای واقعی، درستی کار، یا مجوز merge نیست.
خطاهای غیرمنتظرهٔ فرایندی یا برنامه‌نویسی باعث شکست دمو می‌شوند و به‌عنوان شواهد موفقِ رد شدن شمرده نمی‌شوند.

پرسش‌ها و «چرا این‌گونه انجام شده؟» به [Discussions](https://github.com/MSKazemi/idkmesh/discussions) تعلق دارند؛ issue tracker برای نقص‌ها و قطعات محدود و مشخص کار است. برای یک task مشخص یا مسئولیت فنی مشترک، [دعوت از مشارکت‌کنندگان](https://github.com/MSKazemi/idkmesh/issues/407) را ببینید.

## پرسش مرکزی

> **آیا یک جامعهٔ بزرگ و باز از انسان‌ها و عامل‌های هوش مصنوعی می‌تواند هدف‌ها را کشف کند، کار را تجزیه کند، taskهای محدود را اجرا کند، نتایج را مستقل راستی‌آزمایی کند و سامانه‌های پیچیده را بهتر از توسعه‌دهندگان یا عامل‌های منفرد نگهداری کند؟**

IDKMesh این را یک پرسش تجربی می‌داند. عامل بیشتر، فعالیت بیشتر، commit بیشتر یا رأی بیشتر به‌طور خودکار به معنای بهتر بودن نیست.

## وضعیت فعلی

**زیربنای پژوهشی اجرایی است؛ runner مرجع هنوز کامل نیست.**

مواردی که اکنون روی `main` وجود دارند:

- قراردادهای نسخه‌بندی‌شدهٔ WorkUnit، با `work-unit-v0.2.schema.json` به‌عنوان قرارداد معنایی فعلی task؛
- قراردادهای ResultManifest، EvaluatorPlan و VerificationResult که ادعاهای worker، شواهد verifier و اختیار integration را از هم جدا می‌کنند؛
- اعتبارسنجی provenance و integrity میان‌شیئی؛
- قرارداد benchmark پنج‌مسیره برای تجزیهٔ WorkUnit و مرز سخت‌گیرانه میان شواهد مصنوعی و مشاهده‌شده؛
- کد worker-adapter مستقل از پروتکل، به‌همراه bindingهای A2A/MCP و helperهای SDK/conformance در [`interop/`](interop/)؛
- کد simulation و experiment در [`sim/`](sim/) و [`experiments/`](experiments/)؛
- آزمایش‌های admission و routing محاسباتی با هزینهٔ پروژهٔ صفر؛
- مدل‌سازی مخزن IDKGraph، observability، یکپارچگی link و سازوکارهای warning/review؛
- آزمایش‌های GitHub-native برای رشد جامعه با ACE و ابزارهای کنترل تکامل مخزن؛
- نخستین سطح محصولِ قابل نصب: `pip install .`، CLI با نام `idkmesh` را فراهم می‌کند که فرمان `gate-audit` آن نتایج اندازه‌گیری‌شدهٔ پنل verifier (E015/E016/E017) را به‌صورت یک ابزار تشخیصی برای review gate بسته‌بندی می‌کند؛
- `main` محافظت‌شده با PR gate پایدارِ اجباری روی Python 3.11 و 3.13.

مواردی که **هنوز قابلیت کامل‌شده نیستند**:

- هیچ ادعایی وجود ندارد که IDKMesh می‌تواند هزاران یا میلیون‌ها ماشین واقعی را با ایمنی هماهنگ کند؛
- Verified Swarm Runner مرجع هنوز یک محصول صیقل‌یافتهٔ install-and-run با چند worker adapter تولیدی نیست؛
- integration با real-node مرجع همچنان منوط به gateهای بازبینی مستقل/شواهد خود است و از prototypeهای تاریخی استنباط نمی‌شود؛
- پشتیبانی A2A/MCP یک لایهٔ interoperability است، نه ادعایی مبنی بر اینکه همهٔ frameworkهای عامل خارجی به‌صورت production-integrated هستند؛
- actuation خودکار مخزن/جامعه همچنان به policy و authority محدود است؛
- زیرساخت benchmark تا زمانی که runهای کنترل‌شدهٔ مشاهده‌شده وجود نداشته باشند، اثبات علمی نیست.

این تمایز مهم است: **وجود زیرساخت پیاده‌سازی‌شده، شاهدی بر توانایی اجرای آزمایش‌هاست، نه شاهدی بر درست بودن فرضیه‌های پژوهشی.**

## در پنج دقیقه امتحان کنید: ممیزی یک دروازهٔ بازبینی

نخستین ابزار قابل نصب که از این پژوهش استخراج شده `idkmesh gate-audit` است. این ابزار اندازه‌گیری می‌کند یک پنل بازبین/verifier واقعاً چه ارزشی دارد: رأی‌های مستقل مؤثر (نه صرفاً تعداد اسمی)، ساختار هم‌بستگی خطا، و نرخ breach در probe candidateهای عمداً معیوب.

```bash
git clone https://github.com/MSKazemi/idkmesh
cd idkmesh
pip install .
idkmesh gate-audit examples/gate-audit/panel-votes.example.json --pretty
```

نمونهٔ همراه گزارش می‌کند که یک پنل پنج-verifier معادل حدود **1.69 رأی مستقل مؤثر** است و heuristic رایج `N/(1+(N-1)ρ)` آن را بیش‌برآورد می‌کند — همان پدیده‌ای که روی یک پنل واقعی ۲۵-verifier در [E017](experiments/E017-item-difficulty-and-quorum.md) اندازه‌گیری شد و در [E015](experiments/E015-verification-phase-diagram.md) به‌عنوان یک قاعدهٔ sizing ابطال شد. قرارداد در [`docs/specifications/GATE_AUDIT_V0_1.md`](docs/specifications/GATE_AUDIT_V0_1.md) مشخص شده است.
این audit فقط تشخیصی است: رأی‌هایی را که شما جمع‌آوری کرده‌اید مصرف می‌کند و هیچ اختیار پذیرش یا merge اعطا نمی‌کند. در CI، همین audit به‌صورت GitHub Action اجرا می‌شود:

```yaml
- uses: MSKazemi/idkmesh/actions/gate-audit@main
  with:
    votes-file: path/to/panel-votes.json
```

## از اینجا شروع کنید

لازم نیست پیش از مشارکت کل مخزن را درک کنید.

1. این README را بخوانید.
2. [`CONTRIBUTING.md`](CONTRIBUTING.md) را بخوانید.
3. یک مسیر مشارکت در [`COMMUNITY.md`](COMMUNITY.md) انتخاب کنید.
4. فهرست زندهٔ [`good first issue`](https://github.com/MSKazemi/idkmesh/issues?q=is%3Aissue+state%3Aopen+label%3A%22good+first+issue%22) و [`help wanted`](https://github.com/MSKazemi/idkmesh/issues?q=is%3Aissue+state%3Aopen+label%3A%22help+wanted%22) را مرور کنید.
5. پیش از شروع، assigneeها، commentهای اخیر و pull requestهای مرتبط را بررسی کنید، سپس تغییر محدود و مشخصی را که قصد دارید انجام دهید اعلام کنید.

دو نمونهٔ زنده در زمان این ممیزی:

- [#167 — بازبینی مستقل IDKGraph orphan cohort 1](https://github.com/MSKazemi/idkmesh/issues/167)، یک task محدود و مناسب تازه‌واردها برای شواهد/بازبینی؛
- [#151 — ممیزی مستقل mathematical evolution control plane](https://github.com/MSKazemi/idkmesh/issues/151)، یک task بازبینی با مهارت بالاتر در امنیت/control systems.

[ACE Bootstrap Cohort Observatory](https://github.com/MSKazemi/idkmesh/issues/109) منبع زندهٔ شواهد برای growth-seed cohort اولیه است. این observatory عمداً activity را از مشارکت خارجیِ راستی‌آزمایی‌شده جدا می‌کند.

اگر چیزی گیج‌کننده، قدیمی، متناقض یا دشوار برای یافتن است، گزارش یا اصلاح آن کار مفیدی برای پروژه است.

## IDKMesh در ۶۰ ثانیه

- **IDK** یعنی *I Don't Know*: عدم‌قطعیت، اختلاف، فرض‌ها و فرضیه‌های رقیب، stateهای درجه‌اول هستند.
- **Mesh** یعنی شبکه‌ای از افراد، عامل‌ها، ابزارها، شواهد، taskها و compute، نه یک عامل monolithic.
- workerها باید **Work Unit**های محدود دریافت کنند، نه اختیار نامحدود پروژه.
- تکمیل کار توسط worker به معنای پذیرش نیست؛ توصیهٔ verifier به معنای اختیار merge نیست.
- verification، provenance، reproducibility و security باید هم‌گام با حجم generation مقیاس‌پذیر شوند.
- diversity فقط وقتی ارزش دارد که شواهد مفید و به‌اندازهٔ کافی مستقل اضافه کند.
- Git/GitHub در حال حاضر بستر collaboration و canonical history است.
- A2A و MCP سطح‌های integration هستند؛ IDKMesh نباید transport protocolهای عمومی را بی‌دلیل از نو اختراع کند.
- مخزن عمومی همچنین حافظهٔ پروژه است: تصمیم‌ها، یافته‌ها، شواهد و تاریخچهٔ مهم همکاری باید به‌صورت پایدار قابل بررسی بمانند.

## محصول مرجع

نخستین application مرجع یک **Git-native Verified Swarm Runner** است.

چرخهٔ هدف چنین است:

```text
bounded repository task
        |
        v
   WorkUnit v0.2
        |
        v
 replaceable worker adapters
        |
        v
 candidate artifacts + ResultManifest
        |
        v
 verifier-owned EvaluatorPlan
        |
        v
 independent VerificationResult
        |
        v
 non-selecting evidence/reporting
        |
        v
 explicit human/governance integration decision
```

قاعدهٔ کلیدی authority این است:

```text
worker success != acceptance
verification recommendation != merge authority
CI success != independent human review
```

کد فعلی بخش‌های قابل‌توجهی از این trust path را از قبل پیاده‌سازی کرده است، اما محصول end-to-end برای تازه‌واردها هنوز در حال همگرا شدن و اعتبارسنجی تجربی است. برای gateهای زنده، [`EVOLUTION.md`](EVOLUTION.md)، [`ROADMAP.md`](ROADMAP.md) و issueهای باز پروژه را ببینید.

## بررسی‌های مخزن را اجرا کنید

برای کد پژوهشی/کنترلی Python در مخزن:

```bash
python -m pip install --disable-pip-version-check pytest
python -m pip install --disable-pip-version-check -r requirements-phase0.txt
PYTHONPATH=. python -m pytest -q
```

قراردادهای اصلی Phase 0 را مستقیماً با این فرمان اعتبارسنجی کنید:

```bash
python experiments/harness.py validate
```

Pull requestها به `main` محافظت‌شده، PR gate پایدار را روی Python 3.11 و 3.13 به‌همراه بررسی قطعی یکپارچگی linkهای Markdown اجرا می‌کنند. subsystemهای جداگانه workflowهای محدودتر خود را نیز دارند.

## معماری اصلی

بهترین راه درک IDKMesh دیدن آن به‌عنوان یک سامانهٔ لایه‌ای واحد است:

```text
human constitution / governance
           |
           v
 goals + questions + evidence
           |
           v
       Work Units
           |
           v
 capability/resource matching
           |
           v
 isolated humans / agents / tools / compute
           |
           v
 candidate artifacts + provenance
           |
           v
 independent verification / criticism
           |
           v
 explicit integration decision
           |
           v
 canonical state + outcome evidence
           |
           +------> next goals / policy learning
```

واژگان مرجع چرخهٔ حیات — event، action، candidate، iteration، generation، learning و improvement — در [`ITERATION_MODEL.md`](ITERATION_MODEL.md) تعریف شده‌اند.

برای مرزهای سطح implementation، [`ARCHITECTURE.md`](ARCHITECTURE.md) و فهرست گردآوری‌شدهٔ [`docs/architecture/`](docs/architecture/README.md) را ببینید.

## IDKMesh چه چیزی می‌سازد و چه چیزی را بازاستفاده می‌کند

IDKMesh باید بودجهٔ پیچیدگی خود را صرف بخش‌هایی کند که thesis پژوهشی آن را بیان می‌کنند:

- goalها، uncertainty و evidence؛
- Work Unitهای محدود و authority؛
- decomposition و ساختار dependency؛
- capability/resource matching؛
- verification مستقل و evidence aggregation؛
- provenance و reproducibility؛
- machinery مربوط به experiment/benchmark؛
- feedback loopهای community و governance؛
- self-improvement اندازه‌گیری‌شده تحت محدودیت‌های authority خارجی.

زیرساخت‌های عمومی معمولاً باید integrate شوند، نه اینکه دوباره اختراع شوند. نمونه‌های فعلی شامل Git/GitHub، الگوهای isolation به سبک OCI، A2A، MCP و رویکردهای جاافتادهٔ provenance/supply-chain هستند.

## انضباط پژوهشی

مخزن دست‌کم چهار state را از هم متمایز می‌کند:

1. **مکانیزم پیاده‌سازی‌شده** — code/schema/workflow وجود دارد؛
2. **اعتبارسنجی مصنوعی** — fixture/simulationهای قطعی mechanics را آزمایش می‌کنند؛
3. **شواهد مشاهده‌شده** — runهای کنترل‌شده رفتار واقعی را اندازه‌گیری کرده‌اند؛
4. **نتیجهٔ پذیرفته‌شده** — شواهد برای تصمیم محدود موردنظر به‌اندازهٔ کافی قوی است.

این stateها را با هم یکی نکنید. یک simulator می‌تواند implementation یک algorithm را اعتبارسنجی کند، بدون اینکه ثابت کند آن algorithm همکاری واقعی را بهتر می‌کند.

یک خانوادهٔ پژوهشی شاخص، تحت budgetهای همسان، این موارد را مقایسه می‌کند:

```text
one strong worker
vs one small worker
vs replicated workers
vs heterogeneous workers
vs specialized roles
vs task/evidence DAG teams
```

outcomeهای مهم شامل correctness، موفقیت hidden-test، regressionها، error correlation، reviewer time، مصرف compute/resource، latency، integration conflict، کیفیت provenance و کار مفیدِ راستی‌آزمایی‌شده به‌ازای هر واحد attention/cost کمیاب است.

[`RESEARCH_QUESTIONS.md`](RESEARCH_QUESTIONS.md)، [`docs/research/`](docs/research/README.md) و [`experiments/`](experiments/) را ببینید.

## اصول پروژه

**جامعه در اولویت است.** تجربهٔ مشارکت‌کننده، ظرفیت بازبینی و مقیاس‌پذیری leadership محدودیت‌های مهندسی هستند.

**پیشنهاد، اثبات نیست.** اطمینان انسان یا هوش مصنوعی جایگزین شواهد نمی‌شود.

**محبوبیت، درستی نیست.** رأی، star، reputation یا توافق هم‌بستهٔ مدل‌ها نمی‌تواند checkهای شکست‌خورده را نادیده بگیرد.

**عامل‌های بیشتر به‌طور خودکار بهتر نیستند.** diversity، independence، کیفیت decomposition و ظرفیت verification از تعداد خام مهم‌ترند.

**عدم‌قطعیت داده است.** goalهای رقیب و hypothesisهای حل‌نشده باید وقتی شواهد کافی نیست به‌صورت صریح باقی بمانند.

**generation نباید از verification جلو بزند.** اگر پروژه نتواند خروجی‌ها را بازبینی، بازتولید و نگهداری کند، حجم خروجی زیان‌آور است.

**پیش از اختراع دوباره، integrate کنید.** برای قابلیت‌های عمومی از استانداردهای باز استفاده کنید و معناشناسی ویژهٔ IDKMesh را در لایهٔ coordination/evidence نگه دارید.

**scale باید به‌دست آید.** نتایج شبیه‌سازی‌شده یا کوچک‌مقیاس نباید به‌عنوان تضمین Internet-scale تبلیغ شوند.

**provenance رمزنگاری‌شده پیش از blockchain می‌آید.** زیرساخت trust سنگین‌تر را فقط زمانی اضافه کنید که threat model اثبات‌شده به آن نیاز داشته باشد.

**authority مرجع خارج از generatorها و verifierها باقی می‌ماند.** integration محافظت‌شده یک مرز تصمیم جداگانه است.

## راهنمای مخزن

### مشارکت‌کنندهٔ جدید

- [`CONTRIBUTING.md`](CONTRIBUTING.md) — workflow مشارکت و checkها.
- [`COMMUNITY.md`](COMMUNITY.md) — مسیرهای مشارکت و contributor ladder.
- [`SUPPORT.md`](SUPPORT.md) — نحوهٔ درخواست کمک.
- [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) — انتظارات جامعه.
- [`SECURITY.md`](SECURITY.md) — گزارش آسیب‌پذیری.

### درک سامانه

- [`docs/WHAT_IS_IDKMESH.md`](docs/WHAT_IS_IDKMESH.md) — framework، research، community، application مرجع و لایه‌های self-hosting.
- [`ITERATION_MODEL.md`](ITERATION_MODEL.md) — واژگان مرجع evolution و جریان authority.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — نقشهٔ معماری فعلی.
- [`EVOLUTION.md`](EVOLUTION.md) — strategy، زیربنای پیاده‌سازی‌شده و gateهای بعدی.
- [`ROADMAP.md`](ROADMAP.md) — پیشرفت evidence-gated از وضعیت فعلی.
- [`docs/README.md`](docs/README.md) — navigation گردآوری‌شدهٔ مستندات.

### قراردادها و interoperability

- [`schemas/README.md`](schemas/README.md) — قراردادهای machine-readable فعلی و قواعد versioning.
- [`docs/specifications/`](docs/specifications/README.md) — فهرست protocol/specification.
- [`interop/`](interop/) — مرز adapter مستقل از پروتکل، mappingهای A2A/MCP، identity binding و helperهای conformance.
- [`IDKIPS.md`](IDKIPS.md) — فرایند اصلی improvement proposal.

### پژوهش و شواهد

- [`docs/research/`](docs/research/README.md) — برنامه‌های پژوهشی و شواهد.
- [`sim/`](sim/) — کد deterministic simulation/analysis.
- [`experiments/`](experiments/) — تعریف experimentها، harnessها و ابزارهای نتایج.
- [`docs/audits/`](docs/audits/) — auditهای محدود و شواهد سلامت مخزن.
- [`docs/findings/`](docs/findings/) — یافته‌های پژوهشی و مهندسی.

### جامعه، governance و حافظهٔ پروژه

- [`GOVERNANCE.md`](GOVERNANCE.md) و [`CONSTITUTION.md`](CONSTITUTION.md) — authority و اصول محافظت‌شده.
- [`COMMUNITY_GROWTH_ENGINE.md`](COMMUNITY_GROWTH_ENGINE.md) — آزمایش رشد جامعه با ACE و safeguardها.
- [`PROJECT_RULES.md`](PROJECT_RULES.md) — قواعد عملیاتی سراسر مخزن.
- [`docs/conversations/`](docs/conversations/README.md) — تاریخچهٔ ساختاریافته و append-only همکاری.

## سابقهٔ عمومی پروژه

مخزن، سابقهٔ پایدار پروژه است. نتیجه‌های مهم حاصل از کار پروژه باید به معماری، specificationها، decisionها، findingها، شواهد پژوهشی، governance یا implementation جاری منتقل شوند — نه اینکه فقط در chatها بمانند یا در یادداشت‌های تاریخی دفن شوند.

سوابق تاریخی همچنان ارزشمندند، اما نباید بی‌سروصدا اسناد مرجع فعلی را override کنند. برای hierarchy مستندات، [`PROJECT_RULES.md`](PROJECT_RULES.md) و [`docs/README.md`](docs/README.md) را ببینید.

## مجوز

Apache License 2.0. فایل [`LICENSE`](LICENSE) را ببینید.

## دعوت

IDKMesh از یک پذیرش ساده شروع می‌کند: **ما هنوز بهترین راه هماهنگ کردن هوشمندی در این مقیاس را نمی‌دانیم.**

اگر می‌توانید پرسشی را بهتر کنید، فرضی را ابطال کنید، آزمایشی را بازتولید کنید، test بنویسید، مشکل امنیتی پیدا کنید، قراردادی را روشن‌تر کنید، بار بازبین را کاهش دهید، onboarding را بهتر کنید، یا یک component را به‌صورت راستی‌آزمایی‌شده بسازید، می‌توانید مشارکت کنید.

> **از عدم‌قطعیت تا هوش جمعی — از مسیر شواهد.**
