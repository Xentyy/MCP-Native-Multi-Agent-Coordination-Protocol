# MNACP Protokol Spesifikasyonu
> MCP-Native Multi-Agent Coordination Protocol — v0.1.0

---

## 1. Genel Bakış

MNACP, MCP (Model Context Protocol) üzerine inşa edilen bir ajan-ajan koordinasyon protokolüdür. Mevcut MCP ekosistemi yalnızca `insan → ajan → araç` etkileşimini desteklerken, MNACP `ajan → ajan → araç` zincirini protokol düzeyinde tanımlar.

### 1.1 Temel Kavramlar

| Kavram | Tanım |
|--------|-------|
| **Agent** | Bir dizi MCP aracını sunan ve başka ajanlarla iletişim kurabilen otonom birim |
| **Registry** | Ajanların kaydolduğu ve keşfedildiği merkezi dizin servisi |
| **Delegation** | Bir ajanın görevi başka bir ajana devretme eylemi |
| **Discovery** | Bir görev için en uygun ajanın bulunması süreci |
| **Orchestrator** | Kullanıcı görevini ayrıştıran ve delegasyonu yöneten üst düzey ajan |
| **Trust Score** | Ajanın güvenilirliğini gösteren [0, 1] aralığında dinamik skor |

### 1.2 Tasarım Prensipleri

1. **Çalışma zamanı keşfi:** Ajanlar birbirini compile-time'da değil, runtime'da keşfeder
2. **Protokol uyumluluğu:** MCP standardına uyumlu, ek katman olarak çalışır
3. **Döngü güvenliği:** Delegasyon döngüleri ve kilitlenmeler otomatik tespit edilir
4. **Güven tabanlı seçim:** Ajan seçimi yetenek benzerliği + güven skoruna dayanır
5. **No-code genişletilebilirlik:** Teknik olmayan kullanıcılar doğal dille yeni rol tanımlayabilir

---

## 2. Mesaj Şemaları

Tüm mesajlar Pydantic v2 modelleri ile tanımlanır ve JSON-over-HTTP ile taşınır.

### 2.1 Ajan Kaydı

```json
{
  "agent_id": "uuid",
  "name": "string",
  "description": "string",
  "host": "string",
  "port": "integer",
  "tools": [
    {
      "name": "string",
      "description": "string",
      "parameters": {"param_name": "param_type"}
    }
  ],
  "status": "online | offline | busy",
  "trust_score": "float [0.0, 1.0]",
  "tags": ["string"]
}
```

### 2.2 Keşif İsteği

```json
{
  "task_description": "string",
  "required_capabilities": ["string"],
  "top_k": "integer [1, 10]",
  "exclude_agent_ids": ["uuid"]
}
```

### 2.3 Keşif Sonucu

```json
{
  "agent": "AgentInfo",
  "similarity_score": "float",
  "matched_tools": ["string"]
}
```

### 2.4 Delegasyon İsteği

```json
{
  "request_id": "uuid",
  "from_agent_id": "uuid",
  "to_agent_id": "uuid",
  "task": "string",
  "context": {},
  "delegation_chain": ["uuid"],
  "max_depth": "integer",
  "created_at": "datetime"
}
```

### 2.5 Delegasyon Yanıtı

```json
{
  "request_id": "uuid",
  "status": "pending | in_progress | completed | failed | rejected",
  "result": "any",
  "error": "string | null",
  "delegated_to": "uuid | null",
  "completed_at": "datetime | null"
}
```

### 2.6 Güven Olayı

```json
{
  "agent_id": "uuid",
  "event_type": "string",
  "success": "boolean",
  "latency_ms": "float | null",
  "timestamp": "datetime"
}
```

---

## 3. Protokol Akışları

### 3.1 Ajan Kaydı

```
Agent                    Registry
  │                         │
  │── POST /agents/register ─→│
  │  (AgentRegistration)     │
  │                         │── TF-IDF embedding hesapla
  │                         │── Güven skoru başlat (1.0)
  │←── AgentInfo ───────────│
  │                         │
```

### 3.2 Görev Keşfi ve Delegasyonu

```
User → Orchestrator → Registry → Agent Selection → Delegation → Result Aggregation
```

Detaylı akış:

```
Kullanıcı          Orkestratör           Registry            Hedef Ajan
   │                    │                    │                    │
   │── görev ──────────→│                    │                    │
   │                    │── decompose ───→   │                    │
   │                    │  (Claude API)      │                    │
   │                    │                    │                    │
   │                    │── POST /discover ──→│                    │
   │                    │  (task_desc)       │                    │
   │                    │                    │── TF-IDF match     │
   │                    │                    │── trust weighting  │
   │                    │←── [DiscoveryResult]│                    │
   │                    │                    │                    │
   │                    │── safety check ──→ │                    │
   │                    │  (cycle, depth)    │                    │
   │                    │                    │                    │
   │                    │── POST /delegate ──────────────────────→│
   │                    │  (DelegationReq)   │                    │
   │                    │                    │               execute_tool()
   │                    │←── DelegationResp ──────────────────────│
   │                    │                    │                    │
   │                    │── aggregate ───→   │                    │
   │                    │  (Claude API)      │                    │
   │←── final answer ──│                    │                    │
```

### 3.3 Döngü Tespiti

İki seviyede döngü kontrolü yapılır:

1. **Zincir kontrolü:** `delegation_chain` listesinde hedef ajan zaten varsa → RED
2. **Global graf kontrolü:** DFS ile tüm aktif delegasyon grafında döngü aranır

```python
def is_safe_to_delegate(from_id, to_id, chain):
    # 1. Zincir kontrolü
    if to_id in chain:
        return False, "Döngüsel delegasyon"
    
    # 2. Geçici kenar ekle → global döngü kontrol → kaldır
    add_edge(from_id, to_id)
    has_cycle = dfs_cycle_check()
    remove_edge(from_id, to_id)
    
    if has_cycle:
        return False, "Global döngü tespit edildi"
    
    return True, ""
```

### 3.4 Deadlock Tespiti

Kosaraju algoritması ile güçlü bağlantılı bileşenler (SCC) bulunur. Birden fazla düğüm içeren SCC'ler deadlock'u gösterir.

---

## 4. Yetenek Eşleştirme

### 4.1 Embedding

Her ajan kaydolduğunda, açıklaması ve araç listesi bir metin vektörüne dönüştürülür:

```
text = agent.name + agent.description + Σ(tool.name + tool.description) + Σ(tags)
```

TF-IDF + Truncated SVD (256 boyut) ile gömme yapılır. Her yeni ajan kaydında tüm embedding'ler yeniden hesaplanır.

### 4.2 Skor Hesaplama

```
final_score = 0.7 × cosine_similarity + 0.3 × trust_score
```

En yüksek `final_score`'a sahip ajan seçilir.

---

## 5. Güven Skoru

### 5.1 Formül

```
score = success_rate × latency_factor × failure_penalty

success_rate = successes / total
latency_factor = 1 / (1 + avg_latency / 2000ms)
failure_penalty = 0.9 ^ consecutive_failures
```

### 5.2 Özellikler

- Başlangıç skoru: 1.0
- Minimum skor: 0.05
- Ardışık hatalar skoru hızla düşürür
- Başarılı çağrılar ardışık hata sayacını sıfırlar

---

## 6. API Endpoint'leri

### 6.1 Registry API (port 8000)

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| POST | `/agents/register` | Ajan kaydı |
| DELETE | `/agents/{id}` | Ajan silme |
| PATCH | `/agents/{id}/status` | Durum güncelleme |
| GET | `/agents` | Ajan listesi |
| GET | `/agents/{id}` | Tek ajan detayı |
| POST | `/discover` | Yetenek keşfi |
| POST | `/trust/record` | Güven olayı kaydet |
| POST | `/reset` | Registry sıfırla |
| GET | `/health` | Sağlık kontrolü |

### 6.2 Agent API (port 9001-9003)

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| GET | `/tools` | Araç listesi |
| POST | `/tools/{name}` | Araç çağrısı |
| POST | `/delegate` | Delegasyon al |
| GET | `/health` | Sağlık kontrolü |

### 6.3 Orchestrator API (port 8002)

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| POST | `/run` | Görev çalıştır |
| GET | `/stats` | İstatistikler |
| GET | `/history` | Delegasyon geçmişi |
| GET | `/health` | Sağlık kontrolü |

### 6.4 Role Builder API (port 8001)

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| POST | `/suggest` | Araç önerisi |
| POST | `/create` | Ajan oluştur |
| GET | `/health` | Sağlık kontrolü |

---

## 7. Güvenlik Kısıtları

1. **Maksimum delegasyon derinliği:** Varsayılan 5
2. **Döngü tespiti:** Zincir + graf bazlı çift katmanlı
3. **Timeout:** HTTP istekleri 30s (araç) / 60s (delegasyon)
4. **Güven eşiği:** Skor 0.05'in altına düşmez (ajan tamamen dışlanmaz)

---

## 8. Orkestratör State Machine

LangGraph ile implement edilen durum makinesi:

```
START → decompose → execute ←→ (loop) → aggregate → END
```

| Durum | Açıklama |
|-------|----------|
| `decompose` | Claude API ile görevi alt görevlere ayır |
| `execute` | Her alt görev için ajan bul ve delege et |
| `aggregate` | Sonuçları Claude API ile birleştir |

Geçiş koşulu: Tüm alt görevler tamamlanmışsa veya kilitlenme varsa → `aggregate`

---

## 9. Sürüm Geçmişi

| Sürüm | Tarih | Değişiklik |
|-------|-------|------------|
| 0.1.0 | 2026-04 | İlk sürüm — temel keşif, delegasyon, no-code |
