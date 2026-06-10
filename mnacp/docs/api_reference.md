# MNACP API Referansı

---

## Registry API — `http://localhost:8000`

### POST `/agents/register`

Yeni ajan kaydeder.

**İstek:**
```json
{
  "name": "DataAgent",
  "description": "CSV dosyaları yükleyen ve analiz eden ajan",
  "host": "localhost",
  "port": 9001,
  "tools": [
    {
      "name": "load_csv",
      "description": "CSV metin içeriğini satır listesine dönüştürür",
      "parameters": {"content": "string", "delimiter": "string"}
    }
  ],
  "tags": ["data", "csv"]
}
```

**Yanıt:** `200 OK` — `AgentInfo`
```json
{
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "DataAgent",
  "description": "...",
  "host": "localhost",
  "port": 9001,
  "tools": [...],
  "status": "online",
  "trust_score": 1.0,
  "tags": ["data", "csv"]
}
```

---

### DELETE `/agents/{agent_id}`

Ajanı registry'den siler.

**Yanıt:** `200 OK`
```json
{"status": "ok"}
```

---

### PATCH `/agents/{agent_id}/status`

Ajan durumunu günceller.

**Query Params:** `status=online|offline|busy`

**Yanıt:** `200 OK`
```json
{"status": "ok"}
```

---

### GET `/agents`

Tüm kayıtlı ajanları listeler.

**Yanıt:** `200 OK` — `AgentInfo[]`

---

### GET `/agents/{agent_id}`

Belirli bir ajanın bilgilerini getirir.

**Yanıt:** `200 OK` — `AgentInfo` | `404 Not Found`

---

### POST `/discover`

Görev açıklamasına göre en uygun ajanları bulur.

**İstek:**
```json
{
  "task_description": "CSV dosyasını yükle ve istatistik hesapla",
  "required_capabilities": ["load_csv"],
  "top_k": 3,
  "exclude_agent_ids": []
}
```

**Yanıt:** `200 OK` — `DiscoveryResult[]`
```json
[
  {
    "agent": { "agent_id": "...", "name": "DataAgent", ... },
    "similarity_score": 0.92,
    "matched_tools": ["load_csv", "compute_statistics"]
  }
]
```

---

### POST `/trust/record`

Güven olayı kaydeder.

**İstek:**
```json
{
  "agent_id": "550e8400-...",
  "event_type": "tool_call",
  "success": true,
  "latency_ms": 150.5
}
```

**Yanıt:** `200 OK`

---

### POST `/reset`

Registry'yi sıfırlar (tüm ajanları siler).

**Yanıt:** `200 OK`

---

### GET `/health`

Sağlık kontrolü.

**Yanıt:**
```json
{"status": "ok", "agent_count": 3}
```

---

## Agent API — `http://localhost:{9001-9003}`

### GET `/tools`

Ajanın araç listesini döndürür.

**Yanıt:**
```json
[
  {
    "name": "load_csv",
    "description": "CSV metin içeriğini satır listesine dönüştürür",
    "parameters": {"content": "string", "delimiter": "string"}
  }
]
```

---

### POST `/tools/{tool_name}`

Belirtilen aracı çalıştırır.

**İstek:**
```json
{
  "parameters": {
    "content": "ad,yas\nAli,25\nVeli,30",
    "delimiter": ","
  }
}
```

**Yanıt:**
```json
{
  "result": [
    {"ad": "Ali", "yas": "25"},
    {"ad": "Veli", "yas": "30"}
  ]
}
```

---

### POST `/delegate`

Delegasyon isteğini işler.

**İstek:**
```json
{
  "request": {
    "from_agent_id": "...",
    "to_agent_id": "...",
    "task": "CSV verilerinin istatistiklerini hesapla",
    "context": {"rows": [...]},
    "delegation_chain": ["..."],
    "max_depth": 5
  }
}
```

**Yanıt:** `DelegationResponse`

---

## Orchestrator API — `http://localhost:8002`

### POST `/run`

Görevi orkestratöre gönderir.

**İstek:**
```json
{"task": "Hisse senedi verilerini analiz et ve rapor oluştur"}
```

**Yanıt:**
```json
{
  "result": "Analiz sonuçlarına göre...",
  "stats": {
    "total": 3,
    "completed": 3,
    "success_rate": 1.0,
    "avg_latency_ms": 450.2
  }
}
```

---

### GET `/stats`

Delegasyon istatistiklerini döndürür.

---

### GET `/history`

Delegasyon geçmişini döndürür.

---

## Role Builder API — `http://localhost:8001`

### POST `/suggest`

Doğal dil açıklamasından araç önerileri üretir.

**İstek:**
```json
{"description": "Finansal raporları analiz eden bir ajan istiyorum"}
```

**Yanıt:**
```json
{
  "agent_name": "FinanceAgent",
  "agent_description": "Finansal verileri analiz eden ve raporlayan ajan",
  "tags": ["finance", "analysis"],
  "tools": [
    {
      "name": "analyze_balance_sheet",
      "description": "Bilanço analizi yapar",
      "parameters": {"data": "object"}
    }
  ],
  "rationale": "Finansal analiz için temel araçlar önerildi"
}
```

---

### POST `/create`

Onaylanan teklifi registry'ye kaydeder.

**İstek:** Aynı `/suggest` yanıt formatında

**Yanıt:** `AgentInfo`

---

## Hata Kodları

| Kod | Anlamı |
|-----|--------|
| 200 | Başarılı |
| 400 | Geçersiz istek |
| 404 | Ajan bulunamadı |
| 422 | Doğrulama hatası |
| 500 | Sunucu hatası |
