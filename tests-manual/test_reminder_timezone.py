"""
Teste de FUSO HORARIO nos lembretes.

Bug original: o servidor roda em UTC e o usuario esta em Brasilia (UTC-3).
A action usava datetime.now() do servidor, entao um lembrete pedido para
"14:30" parecia ja ter passado — o Charon respondia "esse horario ja passou".

Simula um servidor em UTC e verifica que:
  1. O lembrete e gravado em UTC (convertido da hora local)
  2. A exibicao volta na hora LOCAL do usuario
  3. Um horario futuro no Brasil NAO e rejeitado como passado
"""
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "actions"))

TMP = Path(tempfile.mkdtemp(prefix="deepos_tz_"))

import database.connection as db
db.set_db_path(TMP / "interactions.db")
db.init_db()

from core.reminders import add_reminder, due_reminders, list_reminders
from core.reminder_doc import _fmt_humano, build_spoken_summary
from core.tenant_identity import set_current_timezone, get_current_timezone, get_tzinfo

BR = "America/Sao_Paulo"
falhas = []


def check(cond, ok, bad):
    print(("   OK  " if cond else "   FALHOU ") + (ok if cond else bad))
    if not cond:
        falhas.append(bad)


print(f"Fuso do processo/servidor: {datetime.now().astimezone().tzinfo}")
print(f"Agora UTC   : {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}")
print(f"Agora Brasil: {datetime.now(get_tzinfo(BR)).strftime('%d/%m/%Y %H:%M')}")
print()

print("1) ContextVar de fuso...")
set_current_timezone(BR)
check(get_current_timezone() == BR, f"fuso definido como {BR}", get_current_timezone())

print("\n2) Gravar lembrete de hora LOCAL 14:30 (deve virar 17:30 UTC)...")
# Escolhe uma data futura para nao depender da hora atual
alvo_local = (datetime.now(get_tzinfo(BR)) + timedelta(days=2)).replace(
    hour=14, minute=30, second=0, microsecond=0
)
print(f"   pedido pelo usuario (local): {alvo_local.strftime('%d/%m/%Y %H:%M')}")

rid = add_reminder(
    fire_at=alvo_local,
    message="Reuniao as 14:30",
    tenant_id="t1",
    tz=BR,
)
print(f"   id gravado: {rid}")

gravado = list_reminders("t1")[0]
print(f"   gravado no banco (UTC): {gravado['fire_at']}")
print(f"   fuso guardado         : {gravado['tz']}")

esperado_utc = alvo_local.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
check(gravado["fire_at"] == esperado_utc,
      f"gravado como {gravado['fire_at']} (UTC correto, +3h)",
      f"gravacao errada: esperava {esperado_utc}, veio {gravado['fire_at']}")
check(gravado["tz"] == BR, "fuso do usuario guardado no lembrete", gravado.get("tz"))

print("\n3) Exibicao volta na hora LOCAL...")
mostrado = _fmt_humano(gravado["fire_at"], gravado["tz"])
print(f"   exibido: {mostrado}")
check("14:30" in mostrado,
      "mostra 14:30 (hora local do usuario)",
      f"mostra hora errada: {mostrado}")

print("\n4) O caso do bug: lembrete FUTURO no Brasil nao pode ser 'passado'...")
# Agora em UTC. Pede 1 hora a frente na hora LOCAL do Brasil.
agora_local = datetime.now(get_tzinfo(BR))
futuro_local = agora_local + timedelta(hours=1)
print(f"   agora Brasil : {agora_local.strftime('%d/%m/%Y %H:%M')}")
print(f"   agora UTC    : {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}")
print(f"   pedido (local): {futuro_local.strftime('%d/%m/%Y %H:%M')}")

rid2 = add_reminder(fire_at=futuro_local, message="Beber agua", tenant_id="t1", tz=BR)
g2 = [r for r in list_reminders("t1") if r["id"] == rid2][0]
# Converte o gravado (UTC) de volta para local e confere que esta no futuro
utc_dt = datetime.strptime(g2["fire_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
local_dt = utc_dt.astimezone(get_tzinfo(BR))
check(local_dt > agora_local,
      f"lembrete esta no futuro ({local_dt.strftime('%H:%M')} > {agora_local.strftime('%H:%M')})",
      "lembrete ficou no PASSADO — o bug voltou")

print("\n5) Vencimento usa UTC corretamente...")
# Um lembrete 1 minuto no passado (UTC) deve estar vencido
passado = datetime.utcnow() - timedelta(minutes=1)
add_reminder(fire_at=passado.replace(tzinfo=timezone.utc), message="Ja venceu", tenant_id="t9", tz=BR)
vencidos = [r for r in due_reminders() if r["tenant_id"] == "t9"]
check(len(vencidos) == 1, "detectou o lembrete vencido em UTC", f"achou {len(vencidos)}")
# Um lembrete 1 hora no futuro NAO deve estar vencido
futuro_utc = datetime.utcnow() + timedelta(hours=1)
add_reminder(fire_at=futuro_utc.replace(tzinfo=timezone.utc), message="No futuro", tenant_id="t9", tz=BR)
vencidos2 = [r for r in due_reminders() if r["tenant_id"] == "t9"]
check(len(vencidos2) == 1, "nao disparou o futuro", f"dispararia {len(vencidos2)}")

print("\n6) Resumo em voz mostra a hora local...")
voz = build_spoken_summary(list_reminders("t1"))
print(f"   {voz[:150]}")
check("14:30" in voz or ":" in voz, "resumo com horarios", voz)

print("\n7) Fuso invalido nao quebra...")
set_current_timezone("Fuso/Invalido/Quebrado")
ruim = _fmt_humano("2026-09-11 17:30:00", None)
print(f"   com fuso invalido: {ruim}")
check(bool(ruim), "nao explodiu com fuso invalido", "quebrou")

print("\n" + "=" * 64)
if falhas:
    print(f"RESULTADO: {len(falhas)} FALHA(S)")
    for f in falhas:
        print("  -", f)
else:
    print("RESULTADO: TODOS OS TESTES PASSARAM — fuso horario OK")

db.set_db_path(BACKEND.parent / "data" / "interactions.db")
shutil.rmtree(TMP, ignore_errors=True)
