# WBC-PDV Legacy Knowledge
_Extracted from MEMORY.md Discovered durable knowledge. Historical WBC-PDV project entries._

## Firebird / PostgreSQL Migration

- **Firebird 2.5 date storage (CORRECTED)**: DATE/TIMESTAMP columns accept `datetime.now().date()` natively — fdb handles conversion. Using `float()` for DATE columns causes `'float' object has no attribute 'month'` on read. EXCEPTION: `DOUBLE PRECISION` columns (e.g., `FINANCEIRO_MOV.DT_LANC`) use `float(datetime.now().strftime('%Y%m%d'))`. For reading, use `_fmt_date()` helper that handles float/datetime.date/datetime.time/string. Times as `HH:MM:SS` strings.
- **database.py column casing**: `query_one()` (line 288) and `query_all()` (line 272) lowercase all column names via `[d[0].lower() for d in cur.description]`. Frontend must use lowercase keys for all DB results.
- **_AdaptedCursor pattern**: Custom psycopg2 cursor subclass that auto-converts Firebird SQL to PostgreSQL at execution time. Handles: `?`→`%s`, `CONTAINING ?`→`ILIKE %%value%%`, `SELECT FIRST n`→`LIMIT n`, `ROWS n`→`LIMIT n`.
- **dict(zip(cols, row_item)) broken with RealDictRow**: Original Firebird code used `cols = [d[0].lower() for d in cur.description]; r = dict(zip(cols, row_item))` to convert tuples to dicts. With RealDictRow, `row_item` is already a dict — iterating gives keys not values. Fix: access `row_item['col']` directly.
- **Route files Firebird→PostgreSQL syntax handled by adapter**: `_AdaptedCursor` in `database.py` auto-converts ALL Firebird SQL at the cursor level. 330+ `cur.execute()` calls covered.
- **PostgreSQL transaction abort cascade**: When a query fails in a psycopg2 transaction, ALL subsequent queries fail with "current transaction is aborted" until ROLLBACK. Fix: `conn.rollback()` in exception handlers.
- **RealDictRow doesn't support integer indexing**: psycopg2 `RealDictCursor` returns `RealDictRow` (dict subclass). `row[0]` tries dict key `0` → KeyError. Must use `row['column_name']`.

## Supabase Integration

- **Supabase auth uses hybrid approach**: `App.jsx` `handleLogin` checks if input contains `@` → tries `supabase.auth.signInWithPassword()` first. Falls back to backend `/api/auth/login` for username-based login.
- **All 92 Supabase tables use SERIAL PRIMARY KEY**: Safe to omit ID from INSERT and use RETURNING.
- **Supabase RLS needs auth_uid bridge**: `auth.uid()` returns UUID, USUARIO.ID is integer. Solution: add `auth_uid UUID` column + `get_usuario_id()` function.
- ** clientes table needs 8 extra columns**: Backend INSERT uses RAZ_SOCIAL, LOGRADOURO, MUNICIPIO, CODIGO_MUNICIPIO, STATUS, VENDE_APRAZO, IE_RG, OBS.
- **Supabase Security Advisor**: Red = CRITICAL (RLS disabled), Yellow = WARNING (mutable search path, public-exec SECURITY DEFINER).
- **Supabase project live for WBC-PDV**: Project ref `jgxqgdfkviqjnbjdjzrj`, URL `https://jgxqgdfkviqjnbjdjzrj.supabase.co`, region Leste-americano-2 (Ohio).
- **PEDIDO table actual columns (Supabase)**: `id, id_cliente, id_usuario, id_caixa, id_vendedor, id_movimento, data_emissao, data_entrega, hora_venda, nome_cliente, cpf_cnpj_cliente, fone_cliente, valor_final, desconto, acrescimo, status_venda, situacao`.
- **Information schema empty for Supabase-created tables**: `pg_attribute` works for column discovery but `information_schema.columns` returns empty for tables created via Supabase SQL Editor.
- **Schema needs barras_cx, gtin, descricao_compra columns**: Backend `ALL_COLS` in `produtos.py` references these but original Supabase schema missed them.
- **nfce/nfe/mdfe tables — minimal schema**: All three tables have only `id, numero, serie, data_emissao, chave_acesso, protocolo, status, xml`.
- **Configuração page — tables EMITENTE/CONTADOR missing in Supabase**: EMITENTE needs many extra columns: print settings, fiscal text, `HASH_TRIPA`.

## WBC-PDV 2.0 Deployment

- **C:\WBC-PDV 2.0 directory created**: Contains copied frontend + backend, plus `.env.example`, `Dockerfile`, `supabase/schema.sql`, `supabase/rls.sql`, `backend/database.py` (PostgreSQL).
- **GitHub repo for cloud project**: `https://github.com/wwbcinformatica-gif/wbcpdv-2.0` — private repo, branch `main`.
- **WBC-PDV 2.0 Vercel deployment live**: Project `wbcpdv-2-0` on Vercel. URL: `https://wbcpdv-2-0.vercel.app`. Next.js 16.2.9 + React 19 + Supabase SSR.
- **Dockerfile shell form for Railway**: `CMD uvicorn ... --port ${PORT:-8080}` instead of exec form — exec form doesn't expand shell environment variables.
- **WBC-PDV-Premium.bat tracks backend port**: Startup script must use the same port as the running backend.
- **CORS must include production domain**: `main.py` CORS `allow_origins` only has localhost. Vercel production domain must be added before deploy.
- **Vite proxy + absolute URL conflict**: When `VITE_API_URL` is set to a full URL, `apiUrl()` helper returns absolute URLs bypassing the Vite proxy. For dev mode, `VITE_API_URL` must be empty.
- **Centralized apiUrl pattern**: All 83 frontend fetch calls use `apiUrl()` in `helpers/api.js`.

## Legacy Project Patterns

- **Naming: keep "WBC PDV" in both projects**: Both `C:\WBC-PDV` (original) and `C:\WBC-PDV 2.0` (cloud) keep "WBC PDV" naming.
- **Theme/audio files must be copied directly, never recreated**: `theme.js` (12 themes) and `audio.js` (8 sound profiles) are too complex for AI to recreate.
- **Bottom panel UX pattern (from old desktop project)**: ALL CRUD screens use single-click selects row → bottom panel with item details + action buttons.
- **OrdemServico.jsx detail panel exists**: Lines 570-645 render bottom `<Card>` with detail data.
- **Frontend dist mount blocks /api/health**: When `frontend/dist/` exists, StaticFiles mount catches all unmatched routes.
- **StaticFiles mount collision in dev**: Remove dist/ directory in dev mode.
- **LoginScreen.jsx is thin UI only**: All auth logic lives in `App.jsx` `handleLogin`.
- **USUARIO_MODULOS groups from old project**: Clientes (7), Contas Pagar (2), Contas Receber (2), Estoque (5), Financeiro (4), Fiscal (4), Fornecedores (2), Frentes (8), Geral (4), NFe (3), Resultados (5), Segurança (5).
- **Products table NOT NULL constraints**: Only `produto`, `valor_venda`, `estoque` are NOT NULL.
- **Batch find-replace breaks parentheses**: When replacing `fetch('/api/X')` → `fetch(apiUrl('/api/X')`, must also add closing `)`.
- **User credentials for cloud project**: `wwbc22@gmail.com` / `02040800`, Nivel 3.
- **STATUS.md as resilient progress record**: User has frequent power outages. Keep STATUS.md updated.
- **Connection keepalive params**: `connect_timeout=10`, `keepalives_idle=30`, `keepalives_interval=10`, `keepalives_count=5`.
- **lru_cache connection poison**: `get_connection()` uses `@lru_cache(maxsize=1)`. If query fails mid-transaction, cached connection stays poisoned.
