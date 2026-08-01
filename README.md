# subclaude

โปรเซิร์ฟเวอร์ FastAPI ที่เปิด endpoint แบบ Anthropic Messages API (`POST /v1/messages`)
โดยใช้โควต้าจาก Claude Pro/Max/Team subscription ของคุณเอง (ผ่าน `claude login`)
แทนการยิง Anthropic API แบบจ่ายต่อ token

## ทำอะไร

- เปิด `POST /v1/messages` ที่มีหน้าตา request/response ตรงกับ Anthropic API จริง
  (มี `model`, `max_tokens`, `messages`, `system`, `stream`) — เอา Anthropic SDK
  client ตัวไหนก็ได้มาชี้ `ANTHROPIC_BASE_URL` มาที่ proxy นี้แล้วใช้งานได้เลย
- แปล request ที่เข้ามาให้กลายเป็นการเรียก `claude-agent-sdk` (ซึ่งไป spawn
  `claude` CLI เป็น subprocess และ auth ด้วยบัญชี claude.ai ที่ล็อกอินไว้)
  แล้วแปลผลลัพธ์กลับมาเป็นรูปแบบ Anthropic response
- v1: **แชทอย่างเดียว** — ปิดการเข้าถึงไฟล์/รันคำสั่ง/เว็บทั้งหมด ไม่มี tool use
  ผ่าน API นี้ (ปลอดภัยกว่า เพราะรันบนเครื่องคุณเองที่มีไฟล์ระบบจริงอยู่)

## แก้ปัญหาอะไร

Anthropic API ปกติคิดเงินตาม token ที่ใช้ แยกจาก Claude Pro/Max/Team
subscription ที่จ่ายรายเดือนไปแล้ว ถ้าอยากเขียนแอป/สคริปต์ของตัวเองที่เรียก
Claude แบบเป็นโปรแกรม แต่ไม่อยากจ่ายซ้ำสองรอบ (ทั้ง subscription และ metered
API) — proxy ตัวนี้เป็นตัวกลางที่ทำให้แอปของคุณคุยกับ Claude ผ่านโควต้า
subscription ที่มีอยู่แล้วแทน โดยยังคงหน้าตา API แบบเดิมที่ SDK/เครื่องมือ
ต่างๆ รู้จักอยู่แล้ว ไม่ต้องเขียนโค้ดเชื่อมต่อแบบเฉพาะกิจ

## ใช้ยังไง

### 1. เตรียมเครื่อง

```bash
claude login   # ล็อกอินด้วยบัญชี claude.ai ที่มี subscription (ทำครั้งเดียว)
```

### 2. ติดตั้ง

macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env
# แก้ PROXY_API_KEYS ใน .env ให้เป็นคีย์จริงของคุณ:
#   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
Copy-Item .env.example .env
# แก้ PROXY_API_KEYS ใน .env ให้เป็นคีย์จริงของคุณ:
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. รันเซิร์ฟเวอร์

```bash
.venv/bin/uvicorn app.composition:app --host 0.0.0.0 --port 8000
```

Windows (PowerShell):

```powershell
.venv\Scripts\uvicorn app.composition:app --host 0.0.0.0 --port 8000
```

### 4. เรียกใช้

```bash
curl http://localhost:8000/v1/messages \
  -H "x-api-key: <ค่าใน PROXY_API_KEYS>" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-opus-4-8",
    "max_tokens": 256,
    "messages": [{"role": "user", "content": "สวัสดีครับ Claude"}]
  }'
```

แบบ streaming (`"stream": true`) จะได้ Anthropic-style SSE
(`message_start` → `content_block_delta` → `message_stop`) กลับมา

> **Windows**: ใน PowerShell คำสั่ง `curl` เป็น alias ของ `Invoke-WebRequest`
> ไม่ใช่ curl จริง (syntax `-d '...'` แบบข้างบนใช้ไม่ได้) ให้เรียก `curl.exe`
> ตรงๆ แทน — ตัว Windows 10 (1803+) มี curl.exe ติดมาให้อยู่แล้ว

### Session memory (opt-in)

ปกติ endpoint นี้ stateless เต็มรูปแบบ (client ถือ history เอง ต้องส่ง
`messages` ทั้งก้อนทุกครั้ง) แต่ถ้าอยากให้ proxy จำบทสนทนาไว้ฝั่งเซิร์ฟเวอร์
ใส่ header `x-session-id: <label ที่ตั้งเอง>` ไปด้วย:

```bash
# เปิด session ใหม่ — ครั้งแรกส่ง messages เต็มก้อนตามปกติ
curl http://localhost:8000/v1/messages \
  -H "x-api-key: <ค่าใน PROXY_API_KEYS>" \
  -H "x-session-id: demo-1" \
  -H "content-type: application/json" \
  -d '{"model":"claude-opus-4-8","max_tokens":256,
       "messages":[{"role":"user","content":"ผมชื่อเอิร์ธนะ"}]}'

# คุยต่อ — ส่งแค่ข้อความล่าสุดพอ ไม่ต้องแนบ history เดิม
curl http://localhost:8000/v1/messages \
  -H "x-api-key: <ค่าใน PROXY_API_KEYS>" \
  -H "x-session-id: demo-1" \
  -H "content-type: application/json" \
  -d '{"model":"claude-opus-4-8","max_tokens":256,
       "messages":[{"role":"user","content":"ผมชื่ออะไรนะ?"}]}'
```

`GET /v1/sessions` ดู session ทั้งหมด, `DELETE /v1/sessions/{id}` ลบทิ้ง —
ทั้งคู่ auth ด้วย `x-api-key` เดียวกัน ไม่มีการแยกสิทธิ์ต่อ key (ดูรายละเอียด
ข้อจำกัดด้านล่าง)

หรือถ้าใช้ Anthropic SDK อยู่แล้ว แค่ตั้งสองตัวแปรนี้แล้วโค้ดเดิมทำงานได้เลย
ไม่ต้องแก้อะไร:

```bash
export ANTHROPIC_BASE_URL=http://localhost:8000
export ANTHROPIC_API_KEY=<ค่าใน PROXY_API_KEYS>
```

## รายละเอียดเป็นแบบไหน

### สถาปัตยกรรม

โครงสร้างแบบ **hexagonal (ports & adapters)** — `app/domain/` และ
`app/use_cases/` ไม่ import FastAPI หรือ `claude_agent_sdk` เลย รู้จักแค่
`ChatBackend` port เท่านั้น ทำให้ฝั่ง HTTP (`adapters/inbound/http/`) กับฝั่ง
SDK (`adapters/outbound/claude_agent_sdk/`) เปลี่ยนแยกจากกันได้ และ logic
หลัก (validate request, map response) เทสต์ได้โดยไม่ต้องมี subprocess หรือ
HTTP server จริง

```
app/
├── domain/            # models, errors, ports (core, ไม่มี dependency ภายนอก)
├── use_cases/          # SendMessageUseCase — validate + delegate ผ่าน port
├── adapters/
│   ├── inbound/http/    # FastAPI: routes, schemas, auth, sse, error_handlers
│   └── outbound/claude_agent_sdk/   # เรียก claude_agent_sdk.query() จริง
├── config.py            # pydantic-settings (อ่านจาก .env)
└── composition.py       # composition root — ผูกทุกชั้นเข้าด้วยกัน, entry point ของ uvicorn
```

### กติกาโค้ด

บังคับด้วย `ruff` (`ruff check .`):

- cyclomatic complexity ต่อ function ไม่เกิน **15**
- parameter ต่อ function ไม่เกิน **7**

### ข้อจำกัดที่รู้อยู่แล้ว (ไม่ใช่บั๊ก แต่เป็นข้อจำกัดของ v1)

- **ไม่มี tool use** — ส่ง `tools`/`tool_choice` มาจะได้ `400
  invalid_request_error` กลับไปทันที (ตั้งใจปฏิเสธ ไม่ใช่เงียบๆ ไม่ทำตาม)
- **ไม่มี session เก็บฝั่งเซิร์ฟเวอร์ ถ้าไม่ใส่ `x-session-id`** — โดย
  default ทุก request ยิง `claude query()` ใหม่หมด โดยเอา `messages` array
  ทั้งก้อนมาเรียงเป็น transcript แบบ `Human:`/`Assistant:` ให้โมเดลอ่าน
  (เหมือน Anthropic API จริงที่ client ถือ history เอง) — ถ้าข้อความผู้ใช้มี
  คำว่า `\n\nHuman:` อยู่ในเนื้อหาจริงๆ อาจทำให้โมเดลสับสนเรื่องขอบเขต turn
  ได้ (ยอมรับได้สำหรับ v1 เพราะ caller คือแอปของคุณเอง ไม่ใช่ input จากคน
  แปลกหน้า)
- **`x-session-id` เปลี่ยนพฤติกรรมจาก stateless Anthropic API จริง** — เมื่อ
  session มีอยู่แล้ว (ไม่ใช่ครั้งแรก) proxy จะอ่านแค่ข้อความล่าสุดใน
  `messages` เท่านั้น ข้อความอื่นที่แนบมาด้วยจะถูกละทิ้งเงียบๆ (ไม่ merge, ไม่
  error) — client ที่ resend history เต็มทุกครั้งตามนิสัย Anthropic SDK ทั่วไป
  จะไม่พังแต่ history ส่วนเกินจะไม่มีผลอะไร
- **memory ผูกกับเครื่อง/ดิสก์นี้เครื่องเดียว** — บทสนทนาจริงเก็บโดย `claude`
  CLI เองที่ local disk (`~/.claude` หรือ `CLAUDE_CONFIG_DIR`) ใต้ working
  directory คงที่ที่ `SESSION_CWD` ชี้ไป, proxy เก็บแค่ mapping label→uuid ไว้
  ที่ `SESSION_STORE_PATH` (ไฟล์ JSON) — ไม่มี retention ของตัวเอง ขึ้นกับ
  ตั้งค่า `cleanupPeriodDays` ของ CLI เอง **`SESSION_CWD` ห้ามเปลี่ยนหลัง
  deploy ไปแล้ว** ไม่งั้น session เก่าทั้งหมดจะหาไม่เจอเงียบๆ (resume ไม่เจอ
  ก็แค่เริ่ม session ใหม่ ไม่ error ให้เห็น)
- **session namespace เป็น global** — ทุก key ใน `PROXY_API_KEYS` เห็นและ
  แก้ไข session เดียวกันหมด ไม่มีการแยกสิทธิ์ต่อ key
- **`max_tokens` ไม่แม่นเป๊ะ** — SDK ไม่มีพารามิเตอร์ตัดจำนวน output token
  ตรงๆ ถ้าคำตอบจริงยาวเกินที่ขอ จะถูกตัดข้อความทีหลัง (proportional
  truncate) แล้วรายงาน `stop_reason: "max_tokens"` — ไม่ใช่การหยุดคิดก่อน
  เหมือน API จริง
- **Streaming เป็นแบบ synthetic** — รอคำตอบเต็มก่อน แล้วค่อยส่งเป็น SSE
  event เดียว ไม่ใช่ token-by-token จริง (แต่หน้าตา event ตรงกับ Anthropic
  SSE ทุกประการ ใช้กับ SSE client ไหนก็ได้)
- **`temperature`/`top_p`/`top_k`/`stop_sequences`** — รับเข้ามาได้แต่ไม่มี
  ผลอะไร (SDK ไม่มีจุดเชื่อมสำหรับพารามิเตอร์พวกนี้)
- **Rate limit ของ subscription เอง** — ไม่มีเอกสารทางการว่า OAuth/subscription
  auth จำกัด concurrency/rate เท่าไหร่ ค่า default `MAX_CONCURRENT_REQUESTS=2`
  เป็นค่าระวังไว้ก่อน ต้องลองปรับเองตามการใช้งานจริง
- **ทุก request spawn subprocess ใหม่** — แต่ละครั้งเปิด `claude` CLI process
  ใหม่ใน temp directory แยกกัน (isolation + ปลอดภัย) แลกมาด้วย latency
  เริ่มต้นต่อ request

### เทสต์

```bash
.venv/bin/pytest              # unit + integration เท่านั้น ไม่มีการเรียก Claude จริง
ruff check .                   # เช็ค complexity/param-count/lint

# เทสต์จริงแบบ end-to-end (ใช้โควต้าจริง) — รันเองหลัง claude login:
RUN_MANUAL_CLAUDE_TEST=1 .venv/bin/pytest -m manual -v -s
```

Windows (PowerShell) — คำสั่งเดียวกัน แค่เปลี่ยน `.venv/bin/` เป็น `.venv\Scripts\`
และตั้ง env var ก่อนรันแทนการ prefix บรรทัดเดียว:

```powershell
.venv\Scripts\pytest
ruff check .

$env:RUN_MANUAL_CLAUDE_TEST = "1"; .venv\Scripts\pytest -m manual -v -s
```
