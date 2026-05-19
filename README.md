# MNACP — MCP-Native Multi-Agent Coordination Protocol

[![CI](https://github.com/Xentyy/MCP-Native-Multi-Agent-Coordination-Protocol/actions/workflows/ci.yml/badge.svg)](https://github.com/Xentyy/MCP-Native-Multi-Agent-Coordination-Protocol/actions/workflows/ci.yml)

Bilgisayar mühendisliği bitirme projesi. Birden fazla yapay zeka ajanının birbirinin araçlarını çalışma zamanında keşfedip kullanabildiği, bir ajanın çözemediği görevi başka bir ajana delege ettiği bir koordinasyon protokolü ve referans uygulaması.

Kullanıcı "şu CSV'yi temizle, istatistik çıkar, sonra rapor yaz" deyince bir orkestratör görevi parçalıyor, her parçayı kayıt defterindeki en uygun ajana gönderiyor, sonuçları toplayıp tek bir cevaba çeviriyor. Tüm bunlar canlı izlenebiliyor.

> Bu repo bir öğrenci bitirme projesidir, ürün değildir. Bazı yerlerde "yeterince iyi" çözümler bilerek tercih edildi (örn. tek-süreçli in-memory registry). Ne, neden böyle yapıldığını ilgili bölümlerde açıkladım.

---

## İçindekiler

1. [Neden Bu Proje?](#neden-bu-proje)
2. [Daha Önce Yapılmış mı? Farkımız Ne?](#daha-önce-yapılmış-mı-farkımız-ne)
3. [Neyi Çözüyor, Nasıl Çözüyor](#neyi-çözüyor-nasıl-çözüyor)
4. [Kullanılan Teknolojiler](#kullanılan-teknolojiler)
5. [Mimari ve Servisler](#mimari-ve-servisler)
6. [Bileşenler — Modül Modül Detay](#bileşenler--modül-modül-detay)
7. [Ajanlar ve Araçları](#ajanlar-ve-araçları)
8. [Arayüz — Sayfa Sayfa Açıklama](#arayüz--sayfa-sayfa-açıklama)
9. [Algoritmalar](#algoritmalar)
10. [Bir Görev Baştan Sona — Veri Akışı](#bir-görev-baştan-sona--veri-akışı)
11. [Kurulum ve Çalıştırma](#kurulum-ve-çalıştırma)
12. [Test Senaryosu — Adım Adım](#test-senaryosu--adım-adım)
13. [Testler](#testler)
14. [API Referansı](#api-referansı)
15. [CI/CD ve Docker](#cicd-ve-docker)
16. [Yol Haritası ve Bilinen Sınırlar](#yol-haritası-ve-bilinen-sınırlar)
17. [Değerlendirme — Baseline Karşılaştırması](#değerlendirme--baseline-karşılaştırması)
18. [Dizin Yapısı](#dizin-yapısı)

---

## Neden Bu Proje?

Bitirme konusu seçerken iki şey aklımdaydı:

1. **Güncel olsun.** Yapay zeka ajanları (LLM agents) son 1-2 yılın en aktif konularından biri. LangChain, AutoGen, CrewAI gibi framework'ler ortaya çıktı, Anthropic Kasım 2024'te **MCP (Model Context Protocol)** standardını yayınladı. Ortam yeni, araştırılacak çok şey var.

2. **Tek başına altından kalkabileceğim ölçekte olsun ama klişe olmasın.** "Klasik bir CRUD web sitesi yaparım" demek istemedim; "kendi LLM'imi eğiteceğim" gibi gerçekçi olmayan şeylere de girmedim. Mevcut LLM'leri araç olarak kullanan, **etrafında bir sistem inşa edilen** bir konu aradım.

MCP protokolü dikkatimi çekti çünkü standart oturmamıştı: bir LLM uygulaması "buralarda şu araçlar var" diye sunucuya bağlanıyor, kullanıyor. Ama **bir ajanın başka bir ajanı kullanması** kapsam dışında. Bu boşluğa dokunan bir tez konusu çıkardım: *"Ajanların birbirini keşfedip görev devredebilmesi için MCP'yi nasıl genişletebiliriz?"*

---

## Daha Önce Yapılmış mı? Farkımız Ne?

| Sistem | Yaklaşımı | MNACP'ten Farkı |
|---|---|---|
| **LangChain Agents** | Tek LLM, dinamik araç seçimi (ReAct). | Tek ajan, tek süreç. Ajanlar birbirini keşfetmez. |
| **Microsoft AutoGen** | Çok ajanlı sohbet (`GroupChat`). | Konuşma odaklı; araç keşfi ve delegasyon zinciri birinci sınıf değil. |
| **CrewAI** | Roller ve görevler önceden tanımlanır (statik). | Çalışma zamanında ajan keşfi yok; deadlock/güven gibi protokol katmanı yok. |
| **MCP (Anthropic, 2024)** | İstemci ↔ sunucu: ajan araç sunucularına bağlanır. | İnsan→ajan→araç tek yönlü. Ajan→ajan zinciri yok. |
| **FIPA-ACL (90'lar)** | Konuşma aktları tanımlar. | Ağır, eski, LLM ve semantik keşif yok. |

**Bu projenin ayırıcı yanları:**

1. **Çalışma zamanı semantik keşif.** Ajanları doğal dil görev tanımıyla TF-IDF + SVD cosine benzerliği ile bulan bir registry. Orkestratör görevi okur, kayıtlı tüm ajanlardan en uygun olanı kendi seçer.

2. **Delegasyon zinciri + döngü tespiti.** Üç katmanlı güvenlik: maksimum derinlik, zincir tekrar tespiti (O(n)), Kosaraju SCC ile global döngü analizi. "A→B→C→A" gibi sonsuz döngülere karşı sistemi sıkı tutar.

3. **Davranışsal güven skoru.** Başarı oranı × gecikme faktörü × ardışık hata cezası ile dinamik skor. Aynı görevi yapabilen iki ajan varsa geçmişte daha güvenilir olan tercih edilir.

4. **MCP-uyumlu.** Bu proje MCP'yi *değiştirmiyor*, ajan→ajan katmanını onun üstüne ekliyor.

5. **No-code rol oluşturucu.** Doğal dilde "satış verilerini analiz eden bir ajan istiyorum" deyince Claude API uygun araç önerilerini üretiyor.

---

## Neyi Çözüyor, Nasıl Çözüyor

Standart MCP'de kullanıcı hangi sunucuya bağlanacağını **biliyor**, hangi araçların olduğunu **gözüyle görüyor**, çağrıyı **kendi başlatıyor**.

MNACP bunun yerine:

- Ajanlar **kendilerini bir registry'ye kayıt eder**.
- Kullanıcı serbest metinle görev verir.
- **Orkestratör** görevi alt parçalara böler, her parçayı en uygun ajana yollar.
- Ajanlar kendi çözemedikleri alt parçaları başka ajanlara **delege edebilir**.
- Sonuçlar toplanıp tek cevaba dönüşür.
- Döngüler tespit edilir, başarısız ajanların güven skoru düşer, belirsizlik graceful ele alınır.

---

## Kullanılan Teknolojiler

### Backend (Python 3.11)

| Teknoloji | Ne için |
|---|---|
| **FastAPI** | Tüm HTTP servisleri (registry, agent, orchestrator, role-builder) |
| **Uvicorn** | ASGI sunucusu |
| **Pydantic v2** | Tip güvenli mesaj şemaları |
| **httpx** | Async HTTP istemci (servisler arası iletişim) |
| **LangGraph** | Orkestratörün state machine'i (decompose → execute → aggregate) |
| **anthropic SDK** | Claude API erişimi (görev parçalama, sonuç birleştirme, rol önerme) |
| **scikit-learn** | TF-IDF vectorizer + TruncatedSVD (semantik keşif) |
| **numpy** | Vektör işlemleri |
| **pytest + pytest-asyncio** | Testler |
| **ruff** | Lint + format |

### Frontend (TypeScript)

| Teknoloji | Ne için |
|---|---|
| **Next.js 14** | React framework (App Router) |
| **Tailwind CSS** | Stil |
| **ReactFlow** | Ajan ağı görselleştirmesi |
| **Recharts** | İstatistik kartları |

### Altyapı

| Teknoloji | Ne için |
|---|---|
| **Docker + docker-compose** | 8 servis tek komutla |
| **GitHub Actions** | CI: lint + testler + Docker smoke + frontend build |

### Neden bu seçimler?

- **FastAPI** — async destekli, Pydantic ile entegre, ajanlar arası eş zamanlı çağrılar için gerekli.
- **LangGraph** — orkestratör doğal olarak state machine: ayrıştır → çalıştır → tamamlandı mı? → birleştir.
- **TF-IDF + SVD** — embedding API'ye bağımlılık yok, lokal çalışıyor, yorumlanabilir.
- **Next.js + ReactFlow** — ajan ağını canlı göstermek için node-edge tabanlı görselleştirici.
- **Docker** — 8 servisi elle ayağa kaldırmak yerine tek komut.

---

## Mimari ve Servisler

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js 14)                         │
│   /             /chat         /agents        /roles      /monitor    │
└────────┬─────────┬────────────────────────────────────┬─────────────┘
         │ REST    │ SSE (text/event-stream)            │ REST
┌────────▼─────────▼──┐                       ┌─────────▼──────────┐
│   Orchestrator      │                       │   Role Builder      │
│   :8002             │                       │   :8001             │
└────────┬────────────┘                       └──────────┬──────────┘
         │ discover / delegate                           │ register
         │                                               │
┌────────▼───────────────────────────────────────────────▼──────────┐
│                       Agent Registry  :8000                         │
│  POST /agents/register · POST /discover · POST /trust/record        │
│  GET  /agents · GET /agents/{id} · GET /health                      │
└─────────┬───────────┬───────────────┬────────────────┬─────────────┘
          │           │               │                │
  ┌───────▼─────┐ ┌───▼──────┐ ┌─────▼──────┐ ┌──────▼──────┐
  │  DataAgent  │ │SearchAgent│ │AnalysisAgent│ │  CodeAgent  │
  │   :9001     │ │  :9002    │ │   :9003     │ │   :9004     │
  │             │ │           │ │             │ │             │
  │ load_csv    │ │ web_search│ │trend_analysis│ │execute_python│
  │ clean_data  │ │ fetch_page│ │ compare      │ │analyze_code │
  │ statistics  │ │ summarize │ │generate_report│ │format_code  │
  │ filter_rows │ │ext_links  │ │ correlation  │ │ext_functions│
  └─────────────┘ └───────────┘ └─────────────┘ └─────────────┘
```

**Her ajanın HTTP API'si:**
- `GET  /health` — durum + agent_id + name
- `GET  /tools` — araç şeması listesi
- `POST /tools/{name}` — tek araç çağrısı
- `POST /delegate` — delegasyon al, içeride çöz veya devret

**Registry (8000)** — In-memory, heartbeat ile canlı tutulan. Aynı host:port'tan yeniden kayıt gelince eski kayıt otomatik silinir (container restart'larında duplikasyon olmaz).

**Orchestrator (8002)** — LangGraph state machine. `/run/stream` endpoint'i her aşamada SSE event yayınlar.

**Role Builder (8001)** — Doğal dil → araç önerisi. Claude API + registry doğrulaması.

---

## Bileşenler — Modül Modül Detay

### `mnacp/protocol/`

Sistemin sözleşmeleri. Pydantic v2 modelleri.

| Tip | Ne işe yarar |
|---|---|
| `AgentRegistration` | Registry'ye kayıt body'si |
| `AgentInfo` | Registry'den okunan ajan — status + trust_score eklenmiş |
| `ToolSchema` | Araç adı, açıklaması, parametre tipleri |
| `DelegationRequest` | Ajan→ajan görev zarfı (request_id, task, context, chain) |
| `DelegationResponse` | Cevap (status, result, error, latency_ms) |
| `DiscoveryRequest` | "Bu görev için kim uygun?" (task, required_capabilities, top_k) |
| `DiscoveryResult` | Ajan + similarity_score + matched_tools |
| `TrustEvent` | Tool çağrısı sonrası kaydedilen olay |

**`delegation.py`** — `DelegationManager`: derinlik kontrolü → deadlock tespiti → HTTP POST → geçmiş kaydı.

**`deadlock_detector.py`** — Üç katman: zincir taraması (O(n)) + DFS + Kosaraju SCC.

### `mnacp/registry/`

**`agent_registry.py`** — `discover()` çağrıldığında: TF-IDF vektörleme → SVD 256 boyut → cosine similarity → `final_score = 0.7×sim + 0.3×trust`.

**`capability_embedder.py`** — TF-IDF + TruncatedSVD(256) pipeline.

**`tool_index.py`** — Araç adlarına göre ters indeks (hızlı araç adı → ajan araması için).

**`trust_scorer.py`** — Güven skoru (formülü Algoritmalar bölümünde).

### `mnacp/agents/base_agent/`

**`agent.py`** — `BaseAgent` (abstract). Alt sınıflar `define_tools()` ve `execute_tool()` override eder. Sağladıkları:
- `start()` / `stop()` — kayıt ve silme
- `_heartbeat_loop()` — 15s'de bir registry'de hala var mı kontrol, yoksa yeniden kayıt
- `handle_delegation()` — gelen istek → derinlik/döngü kontrolü → `_process_delegated_task()`
- `build_http_app()` — FastAPI uygulaması

### `mnacp/agents/orchestrator/`

**`decomposer.py`** — Önce registry kataloğunu çeker, Claude API'ye "sadece bu ajanların yapabileceği alt görevler üret" diye gönderir. Uydurma yetenek üretilmez.

**`delegator.py`** — Top-3 aday çeker; araç adı eşleşmesini description substring eşleşmesinden üstün tutar (capability-aware fallback).

### `mnacp/no_code/`

**`role_builder.py`** — Claude API ile araç önerisi. **`validator.py`** — Önerilen araçları registry'deki gerçek araçlarla karşılaştırır.

---

## Ajanlar ve Araçları

### DataAgent (port 9001)

CSV işleme ve istatistik. Tags: `data`, `csv`, `statistics`, `etl`, `load_csv`, `compute_statistics`, `filter_rows`, `clean_data`.

| Araç | Parametreler |
|---|---|
| `load_csv` | `content: str`, `delimiter: str = ","` |
| `clean_data` | `rows: list[dict]`, `drop_empty: bool`, `strip_whitespace: bool` |
| `compute_statistics` | `rows: list[dict]`, `column: str` → mean, median, std, min, max |
| `filter_rows` | `rows`, `column`, `value`, `operator` (eq/neq/gt/lt/contains) |

### SearchAgent (port 9002)

Gerçek DuckDuckGo araması — API key gerektirmez. Tags: `search`, `research`, `web`, `summarization`, `literature_review`, `web_search`.

| Araç | Parametreler |
|---|---|
| `web_search` | `query: str`, `max_results: int = 5` → DuckDuckGo HTML endpoint |
| `fetch_page` | `url: str` → sayfa içeriği + script/style temizlenmiş düz metin |
| `summarize` | `text: str`, `max_sentences: int = 5` |
| `extract_links` | `html: str` |

### AnalysisAgent (port 9003)

Trend, karşılaştırma, raporlama. Tags: `analysis`, `trend`, `report`, `comparison`, `reasoning`, `generate_report`, `synthesis`.

| Araç | Parametreler |
|---|---|
| `trend_analysis` | `values: list[float]`, `window: int = 3` → eğim + hareketli ortalama |
| `compare` | `baseline: dict`, `current: dict` → % değişim |
| `generate_report` | `title: str`, `sections: list[dict]`, `format: str` |
| `correlation` | `x: list[float]`, `y: list[float]` → Pearson r |

### CodeAgent (port 9004)

Python sandbox çalıştırma — AST tabanlı güvenlik filtresi. Tags: `code`, `python`, `execute_python`, `algorithm`, `calculate`, `script`.

| Araç | Parametreler |
|---|---|
| `execute_python` | `code: str`, `timeout: int = 10` → stdout/stderr/exit_code |
| `analyze_code` | `code: str` → fonksiyonlar, sınıflar, döngüsel karmaşıklık |
| `format_code` | `code: str` → ast.unparse ile normalize |
| `extract_functions` | `code: str` → fonksiyon adları + kaynak |

**Güvenlik:** `os`, `sys`, `subprocess`, `socket`, `shutil`, `ctypes` vb. modüller yasaklı. `eval()`, `exec()`, `__import__()` çağrıları AST'da tespit edilip reddedilir.

**Şablon üretimi:** "Fibonacci 10. terim hesapla" gibi doğrudan tarif verildiğinde ajan tanınan kalıplar için (fibonacci, bubble/quick/merge sort, asal sayı, faktöriyel) otomatik kod şablonu üretip çalıştırır.

---

## Arayüz — Sayfa Sayfa Açıklama

### `/` — Dashboard

- Sağ üstte registry health rozeti (yeşil OK / kırmızı).
- 3 metrik kartı: Toplam Ajan, Çevrimiçi, Toplam Araç. 5s polling.
- **Ajan Ağı** (ReactFlow): Her ajan bir daire, kenarı durumuna göre renk (yeşil=online, sarı=busy, kırmızı=offline). İçinde ajan adı, araç sayısı, güven %.

### `/chat` — Orkestratör Sohbeti

Projenin ana sayfası. SSE ile canlı izleme.

- 3 hazır görev şablonu (preset chip).
- Textarea + Çalıştır/İptal butonu.
- Plan geldikten sonra "PARALEL / SIRALI" rozeti.

Ekran ikiye bölünür:

**Sol — Alt Görev kartları:** Her kart için açıklama, gerekli yetenekler (gri etiketler), bağımlılık rozeti, durum (PENDING→RUNNING→DONE/FAILED), hangi ajan UUID'sine gittiği, sonuç önizlemesi.

**Sağ — Canlı Akış konsolu + Nihai Cevap kutusu.**

**Teknik:** `fetch` + `ReadableStream` ile SSE parse (EventSource POST desteklemediği için).

### `/agents` — Ajan Yönetimi

3 sütunlu grid. Karta tıklayınca detay panel: host:port, tüm araç adları + açıklamaları. 5s polling.

### `/roles` — No-Code Rol Oluşturucu

Tarif yaz → Claude API + registry doğrulaması → önerilen araçlar + gerekçe.

### `/monitor` — Delegasyon Monitörü

İzleme odaklı sayfa, görev çalıştırma yok (chat sayfasına yönlendirir). 3 saniyede bir polling ile şunları gösterir:

- **4 KPI kartı:** Toplam / Başarılı / Reddedilen / Başarı %
- **Ajan Bazlı Performans** (recharts BarChart) — her hedef ajan için yığılmış başarı/hata barı + tablo (toplam çağrı, başarı %, ortalama gecikme, **trend ikonu ↑ ↓ —**). Veri: `GET /stats/by_agent`
- **Delegasyon Yoğunluğu** (AreaChart) — dakika başına toplam ve başarılı delegasyon sayısı. Veri: `GET /stats/timeseries`
- **Gecikme Trendi** (LineChart) — son 30 delegasyonun gecikmesi, zamansal sıra
- **Baseline Karşılaştırması** — `mnacp/evaluation/results/`'dan üretilmiş 3 PNG (görev tamamlama bar, senaryo×sistem heatmap, P50/P90/P99 dağılımı) gömülü görüntü olarak
- **Delegasyon Geçmişi** — son N delegasyon kartı (kim → kime, görev özeti, gecikme, durum)

---

## Algoritmalar

### 1. Semantik Keşif (TF-IDF + SVD + Cosine)

1. Her ajan için temsil metni: `name + description + tools(name+desc) + tags`.
2. `TfidfVectorizer` → sözcük-belge matrisi.
3. `TruncatedSVD(n_components=256)` → 256 boyutlu LSA vektörü.
4. Görev metni aynı pipeline'dan geçer.
5. Cosine similarity ile sıralama.
6. `final_score = 0.7 × similarity + 0.3 × trust_score`.

### 2. Güven Skoru

```
trust = success_rate × latency_factor × failure_penalty

latency_factor  = 1 / (1 + latency_ms / 2000)
failure_penalty = 0.9 ^ ardışık_hata_sayısı
```

İlk kayıtta `trust = 1.0`. 5 ardışık hatada `0.9⁵ ≈ 0.59`. Skor `[0.05, 1.0]` aralığında tutulur.

### 3. Deadlock Tespiti — Üç Katman

**Katman 1 — Zincir taraması (O(n), her delegasyonda):**
```python
return target_id in delegation_chain
```

**Katman 2 — DFS (her delegasyondan önce):**
Aktif delegasyon grafı + yeni kenar → döngü var mı?

**Katman 3 — Kosaraju SCC (periyodik):**
Tüm grafı tara, güçlü bağlı bileşenleri bul. Boyutu > 1 olanlar döngü içerir.

### 4. LangGraph State Machine

```
START → decompose → execute → should_continue?
                       ↑──────────── execute
                                  └─ aggregate → END
```

`should_continue`: tüm subtask'lar done/failed → `aggregate`. Ready task var → `execute`. Ready yok ama bekleyenler var (bağımlılık kilidi) → `aggregate` (graceful).

### 5. Capability-Aware Delegasyon

Top-3 aday çekilir. Her aday için `_agent_has_tool()` kontrolü: yetenek adı ajanın gerçek araç isimlerinden biriyle eşleşiyor mu? İlk eşleşen seçilir. Eşleşen yoksa similarity en yüksek ilk aday alınır.

Bu, "statistics" kelimesi açıklamasında geçtiği için AnalysisAgent'ın CSV görevlerini kapmasını önler.

### 6. Decomposer Registry Farkındalığı

`decompose()` her çağrıldığında önce `GET /agents` çekerek kataloğu alır ve bunu Claude'un sistem promptuna gömer: "sadece bu ajanların yapabileceği alt görevler üret". Bu sayede sistemde olmayan yetenekler icat edilmez.

---

## Bir Görev Baştan Sona — Veri Akışı

Örnek: `/chat`'te CSV analiz görevi verildi.

```
Browser
  │
  │  POST /run/stream {"task": "...CSV..."}
  ▼
Orchestrator
  │
  ├─ decomposer.decompose(task)
  │    ├─ GET registry/agents          → katalog çek
  │    ├─ Claude API                   → JSON plan üret
  │    └─ SSE: decompose_done (3 subtask)
  │
  ├─ execute: t1 (bağımlılıksız)
  │    ├─ delegator.pick_candidate(t1) → DataAgent (score=0.91)
  │    ├─ SSE: subtask_start
  │    ├─ POST data-agent:9000/delegate
  │    │    └─ DataAgent._process_delegated_task()
  │    │         └─ execute_tool("load_csv") → rows[]
  │    └─ SSE: subtask_done
  │
  ├─ execute: t2 (t1 tamamlandı)
  │    └─ DataAgent → compute_statistics → {mean, std, ...}
  │
  ├─ execute: t3 (t2 tamamlandı)
  │    └─ AnalysisAgent → generate_report → markdown
  │
  ├─ aggregate
  │    ├─ SSE: aggregate_start
  │    ├─ Claude API → sonuçları birleştir
  │    └─ SSE: final_answer
  │
  └─ Stream kapanır
```

---

## Kurulum ve Çalıştırma

### Docker ile (önerilen)

```bash
git clone https://github.com/Xentyy/MCP-Native-Multi-Agent-Coordination-Protocol.git
cd MCP-Native-Multi-Agent-Coordination-Protocol

# .env dosyası oluştur
echo "ANTHROPIC_API_KEY=sk-ant-..." > mnacp/docker/.env

# Stack'i ayağa kaldır
docker compose -f mnacp/docker/docker-compose.yml up -d --build
```

| Servis | Port | Sağlık |
|---|---|---|
| registry | 8000 | http://localhost:8000/health |
| data-agent | 9001 | http://localhost:9001/health |
| search-agent | 9002 | http://localhost:9002/health |
| analysis-agent | 9003 | http://localhost:9003/health |
| code-agent | 9004 | http://localhost:9004/health |
| orchestrator | 8002 | http://localhost:8002/health |
| role-builder | 8001 | http://localhost:8001/health |
| frontend | 3000 | http://localhost:3000 |

### Manuel (geliştirme)

```bash
cd mnacp
pip install -r requirements.txt

# 7 ayrı terminal
python registry/server.py
python orchestrator_server.py
python role_builder_server.py
python -m mnacp.agents.example_agents.data_agent.agent
python -m mnacp.agents.example_agents.search_agent.agent
python -m mnacp.agents.example_agents.analysis_agent.agent
python -m mnacp.agents.example_agents.code_agent.agent

# Frontend
cd frontend && npm install && npm run dev
```

---

## Test Senaryosu — Adım Adım

### Adım 1 — Saf bilgi sorusu

`/chat`'te:
```
Yapay zeka etiği konusunda 3 temel ilke listele.
```

**Beklenen:** Alt görev kartı çıkmaz. Decomposer kataloğa bakıp "bu görev mevcut araçlarla parçalanamaz" kararı verir, aggregate Claude kendi bilgisinden yanıtlar.

### Adım 2 — CSV analizi

```
Şu CSV verisini analiz et:
ad,yas,maas
Ali,25,5000
Ayse,30,7500
Mehmet,28,6000
Fatma,35,9000

Maaş ortalaması ve standart sapmasını hesapla, rapor formatında sun.
```

**Beklenen:** 3 alt görev kartı (SIRALI), DataAgent + AnalysisAgent'a delegasyon, nihai raporda ortalama ≈ 6.875, std ≈ 1.653.

### Adım 3 — Kod çalıştırma

```
Python'da bubble sort algoritması yaz ve çalıştır, zaman karmaşıklığını araştır.
```

**Beklenen:** CodeAgent (bubble sort) + SearchAgent (DuckDuckGo araması) paralel çalışır. Nihai cevap gerçek çalıştırma çıktısı + web kaynağı içerir.

### Adım 4 — Fibonacci

```
Python ile Fibonacci dizisinin 10. terimini hesapla.
```

**Beklenen:** CodeAgent şablon üretir, çalıştırır, stdout: `Fibonacci(10) = 55`.

### Adım 5 — İptal butonu

Adım 2'yi başlat, bir kart RUNNING'dayken **İptal**'e bas. AbortController stream'i temiz sonlandırır.

---

## Testler

| Kategori | Yer | Ne test eder |
|---|---|---|
| Unit | `tests/unit/` | Registry, delegation, deadlock, tüm ajanlar, no-code, decomposer |
| Integration | `tests/integration/` | Gerçek HTTP: registry + 4 ajan ayağa kalkıyor, uçtan uca delegasyon |
| Evaluation | `tests/evaluation/` | Performans metrikleri (latency, throughput) |

```bash
cd mnacp
pytest                             # hepsi
pytest tests/unit                  # sadece unit
pytest -k "code_agent"             # filtre
pytest --cov=mnacp --cov-report=html
```

Integration testleri mock kullanmaz — gerçek uvicorn sunucuları daemon thread'de ayağa kalkar.

---

## API Referansı

### Registry (8000)

| Method | Path | Açıklama |
|---|---|---|
| POST | `/agents/register` | Ajan kayıt |
| DELETE | `/agents/{id}` | Ajan sil |
| GET | `/agents` | Tüm ajanlar |
| POST | `/discover` | Semantik keşif |
| POST | `/trust/record` | Güven olayı kaydet |
| GET | `/agents/trends` | Her ajan için güven skoru trendi |
| GET | `/health` | `{"status","agent_count"}` |

### Agent (9001–9004)

| Method | Path | Açıklama |
|---|---|---|
| GET | `/health` | `{"status","agent_id","name"}` |
| GET | `/tools` | Araç şema listesi |
| POST | `/tools/{name}` | Araç çağrısı |
| POST | `/delegate` | Delegasyon al |

### Orchestrator (8002)

| Method | Path | Açıklama |
|---|---|---|
| POST | `/run` | Görev çalıştır (tek seferlik) |
| POST | `/run/stream` | SSE stream |
| GET | `/history` | Delegasyon geçmişi |
| GET | `/stats` | Toplam istatistikler |
| GET | `/stats/by_agent` | Hedef ajan bazlı kırılım (toplam, başarılı, hata, gecikme, trend) |
| GET | `/stats/timeseries` | Dakikalık delegasyon yoğunluğu (AreaChart için) |

**SSE event tipleri:**
```
decompose_start  decompose_done  subtask_start  subtask_done
subtask_failed   peer_delegation  aggregate_start  final_answer  error
```

`peer_delegation` eventi: bir ajan başka bir ajana delege ettiğinde yayınlanır (örn. DataAgent→AnalysisAgent). AgentGraph'ta ajan→ajan kenarı olarak çizilir.

### Role Builder (8001)

| Method | Path | Açıklama |
|---|---|---|
| POST | `/suggest` | Araç önerisi üret (Claude) |
| POST | `/create` | GenericAgent başlat ve registry'e kaydet |
| POST | `/agents/{id}/delegate` | No-code üretilmiş ajana delegasyon |
| POST | `/agents/{id}/tools/{tool}` | No-code üretilmiş ajanın aracını çağır |
| GET | `/agents` | Aktif generic ajanları listele |
| GET | `/health` | Durum |

---

## CI/CD ve Docker

### GitHub Actions

Üç paralel iş:

1. **Python tests** (3.10 + 3.11 matrisi) — ruff lint → pytest → coverage
2. **Docker build smoke test** — imajlar derlenir, registry `/health` 200 dönene kadar beklenir
3. **Frontend build** — npm ci → tsc --noEmit → npm run build

### Docker Compose

- **Healthcheck'ler:** Her servis `httpx.get('/health')` ile.
- **PYTHONPATH:** `COPY . /app/mnacp/` + `ENV PYTHONPATH=/app` → `import mnacp.xxx` çalışır.
- **Advertise host:** `ADVERTISE_HOST=<type>-agent` env var ile ajanlar Docker DNS adıyla kayıt olur (`data-agent:9000`). Orkestratör bu hostname ile ulaşır.
- **Upsert kayıt:** Aynı host:port'tan yeni kayıt gelince eski kayıt silinir — container rebuild'lerde ajan duplikasyonu olmaz.

---

## Bilinen Sınırlar

- Registry in-memory — heartbeat ile ajan kayıtları korunuyor ama delegasyon geçmişi restart'ta sıfırlanır.
- `REGISTRY_API_KEY` boş bırakılırsa ajan kayıt doğrulaması devre dışıdır.
- Distributed deployment değil — tek host varsayımı.

---

## Değerlendirme — Baseline Karşılaştırması

5 senaryo × 3 tekrar = 15 koşum/sistem ile MNACP, statik atama ve merkezi (delegasyonsuz) baseline'larla karşılaştırıldı. MNACP gerçek HTTP üzerinden orkestratöre çağrı yapar; baseline'lar kural bazlı simülasyondur.

| Sistem | Görev Tamamlama | Ajan Seçim Doğruluğu | Ortalama Delegasyon | P50 Gecikme |
|---|---|---|---|---|
| **MNACP (bizim)** | **100%** | **96.7%** | 4.27 (1 derinlik) | 18.6 s |
| Merkezi (delegasyonsuz) | 100% | 72.2% | 3.6 araç | sim. |
| Statik Atama | 60% | 30.0% | 1 ajan | sim. |

**Yorumlar:**
- **Doğruluk farkı:** MNACP %96.7'lik ajan seçim doğruluğu ile statik atamanın 3 katı, merkezi baseline'ın 1.34 katı. Embedding tabanlı dinamik keşif, anahtar kelime eşleşmesinden anlamlı şekilde iyi.
- **Statik atama 2 senaryoda fail oldu** (S3, S5) — keyword eşleşmesi olmadığında "DataAgent"e fallback yapıyor, AnalysisAgent'a düşmesi gereken görev başarısız sayılıyor.
- **Gecikme:** MNACP gerçek Claude API + delegasyon zinciri kullandığı için ~18.6s P50 gösteriyor; baseline'lar simülasyon olduğu için 0 ms görünüyor (adil karşılaştırma için onları da gerçek koşturmak gerek).
- **Delegasyon derinliği = 1** her senaryoda → orkestratör direkt ajanlara dağıtıyor. **Peer delegasyon zincirleri** (DataAgent→AnalysisAgent) `_peer_delegations` metadatası üzerinden kayıtlı; senaryo metinleri stat+rapor tetiklemediği için 2 derinlik bu koşuda yakalanmadı.

**Üretilen grafikler** (`mnacp/evaluation/results/`):
- `completion_rate.png` — sistem başına tamamlama oranı bar chart
- `latency_distribution.png` — P50/P90/P99 yan yana barlar
- `scenario_heatmap.png` — senaryo × sistem ısı haritası

**Yeniden çalıştırmak için:**
```bash
# Docker ayakta olmalı (orkestratör + 4 ajan)
cd mnacp
PYTHONPATH=$PWD python -m mnacp.evaluation.run_evaluation --repeat 3

# Sadece baseline (Claude API çağrısı yok, hızlı)
PYTHONPATH=$PWD python -m mnacp.evaluation.run_evaluation --skip-mnacp
```

---

## Dizin Yapısı

```
MCP-Native-Multi-Agent-Coordination-Protocol/
├── README.md
├── .github/workflows/ci.yml
│
└── mnacp/
    ├── requirements.txt
    ├── orchestrator_server.py
    ├── role_builder_server.py
    │
    ├── protocol/
    │   ├── schemas.py              # Pydantic modeller
    │   ├── delegation.py           # DelegationManager
    │   ├── discovery.py            # DiscoveryProtocol
    │   └── deadlock_detector.py    # 3 katmanlı döngü tespiti
    │
    ├── registry/
    │   ├── server.py               # FastAPI (port 8000)
    │   ├── agent_registry.py       # In-memory store + discover()
    │   ├── capability_embedder.py  # TF-IDF + SVD pipeline
    │   ├── tool_index.py           # Araç ters indeksi
    │   └── trust_scorer.py         # Güven skoru
    │
    ├── agents/
    │   ├── base_agent/
    │   │   ├── agent.py            # BaseAgent (abstract) + heartbeat
    │   │   └── registry_client.py
    │   ├── orchestrator/
    │   │   ├── agent.py            # OrchestratorAgent (LangGraph)
    │   │   ├── decomposer.py       # Görev parçalama (Claude + registry katalog)
    │   │   └── delegator.py        # Capability-aware ajan seçimi
    │   └── example_agents/
    │       ├── data_agent/         # CSV, istatistik
    │       ├── search_agent/       # DuckDuckGo araması, fetch, özet
    │       ├── analysis_agent/     # Trend, karşılaştırma, rapor
    │       └── code_agent/         # Python sandbox, AST analizi
    │
    ├── mcp_servers/
    │   ├── data_tools/tools.py
    │   ├── search_tools/tools.py   # Gerçek DuckDuckGo HTTP araması
    │   ├── analysis_tools/tools.py
    │   └── code_tools/tools.py     # subprocess sandbox + AST güvenlik
    │
    ├── no_code/
    │   ├── role_builder.py
    │   └── validator.py
    │
    ├── docker/
    │   ├── docker-compose.yml      # 8 servis
    │   ├── registry.Dockerfile
    │   ├── agent.Dockerfile
    │   ├── frontend.Dockerfile
    │   └── agent_entrypoint.py     # AGENT_TYPE → doğru sınıf
    │
    ├── tests/
    │   ├── unit/
    │   ├── integration/
    │   └── evaluation/
    │
    └── frontend/
        ├── app/
        │   ├── page.tsx            # Dashboard
        │   ├── chat/page.tsx       # SSE sohbet
        │   ├── agents/page.tsx
        │   ├── roles/page.tsx
        │   └── monitor/page.tsx
        ├── components/
        │   ├── AgentGraph.tsx      # ReactFlow + canlı kenar animasyonu
        │   ├── DelegationFlow.tsx
        │   └── RoleBuilder.tsx
        └── lib/
            └── api.ts              # streamRunTask() + fetch wrapper'ları
```
