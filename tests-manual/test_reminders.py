"""Teste do servico de lembretes — persistencia, vencimento, isolamento e a action."""
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "actions"))

TMP = Path(tempfile.mkdtemp(prefix="deepos_reminders_"))

import database.connection as db
db.set_db_path(TMP / "interactions.db")
db.init_db()

from core.reminders import add_reminder, list_reminders, due_reminders, mark_fired, cancel_reminder
from core.tenant_identity import set_current_tenant

falhas = []


def check(cond, msg_ok, msg_fail):
    if cond:
        print(f"   OK  {msg_ok}")
    else:
        print(f"   FALHOU {msg_fail}")
        falhas.append(msg_fail)


print("1) Criando lembretes...")
# CONTRATO DE FUSO: `fire_at` naive e interpretado como hora LOCAL do usuario
# e convertido para UTC ao gravar. Para este teste controlar o vencimento com
# precisao, usamos a base em UTC de verdade (datetime.now(utc)).
#
# ATENCAO: `datetime.now()` devolve a hora LOCAL da maquina, que NAO e UTC.
# Combinar `datetime.now()` com `.replace(tzinfo=utc)` marca a hora local como
# se fosse UTC e desloca tudo em 3h no Brasil.
UTC = timezone.utc
agora_utc = datetime.now(UTC)
futuro = agora_utc + timedelta(hours=2)
passado = agora_utc - timedelta(minutes=1)

r1 = add_reminder(futuro, "Tomar remedio", tenant_id="t1", tz="UTC")
r2 = add_reminder(futuro, "Reuniao", tenant_id="t2", tz="UTC")
r3 = add_reminder(passado, "Ja venceu", tenant_id="t1", tz="UTC")
print(f"   agora UTC: {agora_utc.strftime('%Y-%m-%d %H:%M')}")
print(f"   ids criados: {r1}, {r2}, {r3}")
check(all(isinstance(x, int) and x > 0 for x in (r1, r2, r3)), "3 lembretes criados", "ids invalidos")

print("\n2) Isolamento: cada tenant ve so os seus...")
t1 = list_reminders("t1")
t2 = list_reminders("t2")
check(len(t1) == 2, f"t1 tem 2 lembretes ({[r['message'] for r in t1]})", f"t1 deveria ter 2, tem {len(t1)}")
check(len(t2) == 1, f"t2 tem 1 lembrete ({[r['message'] for r in t2]})", f"t2 deveria ter 1, tem {len(t2)}")
check(all(r["tenant_id"] == "t1" for r in t1), "t1 nao vaza lembretes de t2", "VAZAMENTO entre tenants")

print("\n3) Vencimento (due_reminders)...")
due = due_reminders()
check(len(due) == 1, f"1 lembrete vencido detectado: {[d['message'] for d in due]}",
      f"esperava 1 vencido, achou {len(due)}")

print("\n4) Marcar como disparado...")
mark_fired(r3)
check(len(due_reminders()) == 0, "nada mais vencido apos disparar", "ainda ha vencidos")
check(len(list_reminders("t1")) == 1, "t1 agora tem 1 pendente (o disparado saiu)", "contagem de pendentes errada")
check(len(list_reminders("t1", include_fired=True)) == 2, "include_fired mostra os 2", "include_fired nao funcionou")

print("\n5) Cancelar...")
check(cancel_reminder(r2) is True, "cancelou lembrete do t2", "nao conseguiu cancelar")
check(len(list_reminders("t2")) == 0, "t2 ficou sem pendentes", "t2 ainda tem pendente")
check(cancel_reminder(r2) is False, "cancelar de novo retorna False (ja cancelado)", "cancelou duas vezes")

print("\n6) A action `reminder` grava no banco?")
set_current_tenant("t1")
import reminder as reminder_action

resposta = reminder_action.reminder({"date": "amanha", "time": "14:30", "message": "Testar action"})
print(f"   resposta: {resposta}")
check("Lembrete criado" in resposta, "action respondeu sucesso (nao mais o erro do agendador)",
      f"action falhou: {resposta}")
check("agendador do sistema" not in resposta, "NAO caiu no erro 'agendador do sistema'",
      "ainda cai no erro antigo")

pend = list_reminders("t1")
check(any("Testar action" in r["message"] for r in pend), "lembrete da action esta no banco",
      "lembrete da action nao foi persistido")

print("\n7) A action respeita o tenant? (deve gravar em t1, nao em t2)")
check(not any("Testar action" in r["message"] for r in list_reminders("t2")),
      "nao vazou para t2", "VAZOU para outro tenant")

print("\n8) Casos de borda da action...")
print(f"   passado   : {reminder_action.reminder({'date': 'hoje', 'time': '00:01', 'message': 'x'})}")
print(f"   sem data  : {reminder_action.reminder({'message': 'x'})}")
print(f"   'em 2 horas': {reminder_action.reminder({'time': 'em 2 horas', 'message': 'Beber agua'})}")

print("\n" + "=" * 62)
if falhas:
    print(f"RESULTADO: {len(falhas)} FALHA(S)")
    for f in falhas:
        print("  -", f)
else:
    print("RESULTADO: TODOS OS TESTES PASSARAM — lembretes OK")

db.set_db_path(Path(__file__).resolve().parent.parent / "data" / "interactions.db")
shutil.rmtree(TMP, ignore_errors=True)
