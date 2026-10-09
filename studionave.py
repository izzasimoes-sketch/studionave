"""Studio Nave: uma sala local para visualizar sessoes e subagentes do Claude Code.

Uso:
    python studionave.py instalar        registra os hooks no Claude Code
    python studionave.py remover         remove os hooks deste projeto
    python studionave.py iniciar         abre a sala em http://127.0.0.1:8765
    python studionave.py demo            abre a sala com dados de exemplo

Usa somente a biblioteca padrao do Python 3.10+.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import uuid
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
CAPTURE = ROOT / "hooks" / "capture.py"
HOOK_EVENTS = ("SessionStart", "UserPromptSubmit", "Stop", "SubagentStart", "SubagentStop", "SessionEnd")
ACTIVE = {"trabalhando", "delegando", "aguardando"}
WINDOW_HOURS = 24          # eventos mais antigos que isso sao ignorados
ROOM_HOURS = 12            # concluidas aparecem na sala por ate 12 horas
SILENCE_MINUTES = 30       # sem sinal e sem registro de processo -> orfa


# ---------------------------------------------------------------- pastas

def data_dir(demo: bool = False) -> Path:
    base = os.environ.get("STUDIONAVE_DATA_DIR") or Path.home() / ".studionave"
    base = Path(base).expanduser()
    return base.with_name(base.name + "-demo") if demo else base


def settings_path() -> Path:
    return Path.home() / ".claude" / "settings.json"


def sessions_dir() -> Path:
    return Path.home() / ".claude" / "sessions"


# ---------------------------------------------------------------- hooks

def hook_command() -> str:
    invocation = f'"{sys.executable}" "{CAPTURE}"'
    return f"& {invocation}" if os.name == "nt" else invocation


def is_our_hook(item: dict) -> bool:
    value = item.get("command")
    if not isinstance(value, str):
        return False
    match = re.fullmatch(r'\s*(?:&\s*)?"[^"]+"\s+"([^"]+)"\s*', value)
    return bool(match) and os.path.normcase(os.path.normpath(match.group(1))) == \
        os.path.normcase(os.path.normpath(str(CAPTURE)))


def load_settings(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig") or "{}")
    if not isinstance(data, dict):
        raise SystemExit("O arquivo de configuracoes do Claude Code precisa ser um objeto JSON.")
    return data


def save_settings(path: Path, settings: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_name(path.name + ".studionave-backup")
        backup.write_bytes(path.read_bytes())
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def install_hooks(path: Path) -> None:
    settings = load_settings(path)
    hooks = settings.setdefault("hooks", {})
    for event in HOOK_EVENTS:
        groups = hooks.setdefault(event, [])
        mine = [item for group in groups for item in group.get("hooks", []) if is_our_hook(item)]
        for item in mine:
            item["command"] = hook_command()
        if not mine:
            hook = {"type": "command", "command": hook_command(), "timeout": 5}
            if os.name == "nt":
                hook["shell"] = "powershell"
            groups.append({"hooks": [hook]})
    save_settings(path, settings)
    print(f"Hooks registrados em {path}")
    print("Abra uma NOVA sessao do Claude Code para que eles passem a valer.")


def remove_hooks(path: Path) -> None:
    settings = load_settings(path)
    hooks = settings.get("hooks", {})
    for event in list(hooks):
        kept_groups = []
        for group in hooks[event]:
            kept = [item for item in group.get("hooks", []) if not is_our_hook(item)]
            if kept:
                kept_groups.append({**group, "hooks": kept})
        if kept_groups:
            hooks[event] = kept_groups
        else:
            hooks.pop(event)
    if not hooks:
        settings.pop("hooks", None)
    save_settings(path, settings)
    print(f"Hooks do Studio Nave removidos de {path}")


# ---------------------------------------------------------------- leitura e projecao

def parse_time(value: str) -> datetime:
    try:
        moment = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return datetime.fromtimestamp(0, timezone.utc)
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def read_events(folder: Path, now: datetime) -> list[dict]:
    path = folder / "events.jsonl"
    if not path.exists():
        return []
    limit = now - timedelta(hours=WINDOW_HOURS)
    events, seen = [], set()
    with path.open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue  # linha incompleta: sera lida na proxima consulta
            if not isinstance(event, dict) or not event.get("session_id") or event.get("id") in seen:
                continue
            seen.add(event.get("id"))
            if parse_time(event.get("t", "")) >= limit:
                events.append(event)
    events.sort(key=lambda item: parse_time(item.get("t", "")))
    return events


def project(events: list[dict]) -> dict[str, dict]:
    """Transforma a sequencia de eventos no estado atual de cada agente."""
    runs: dict[str, dict] = {}

    def upsert(key, event, state, parent=None, kind=None, ended=None):
        run = runs.get(key)
        if run is None:
            run = runs[key] = {
                "chave": key, "session_id": event["session_id"], "agent_id": None, "pai": parent,
                "tipo": kind or "principal", "cwd": "", "estado": state, "encerramento": None,
                "inicio": event["t"], "atualizado": event["t"],
            }
        run["estado"], run["atualizado"] = state, event["t"]
        if ended:
            run["encerramento"] = ended
        if event.get("cwd"):
            run["cwd"] = event["cwd"]
        return run

    def children(session_id, active_only=True):
        return [run for run in runs.values() if run["session_id"] == session_id and run["pai"]
                and (run["estado"] in ACTIVE or not active_only)]

    for event in events:
        sid, name = event["session_id"], event.get("evento")
        main = f"session:{sid}"
        if name == "SessionStart":
            upsert(main, event, "aguardando")
        elif name == "UserPromptSubmit":
            upsert(main, event, "trabalhando")
        elif name == "SubagentStart":
            upsert(main, event, "delegando")
            child = upsert(f"agent:{event.get('agent_id') or event['id']}", event, "trabalhando",
                           parent=main, kind=event.get("agent_type") or "subagente")
            child["agent_id"] = event.get("agent_id")
        elif name == "SubagentStop":
            if main not in runs:
                upsert(main, event, "aguardando")
            upsert(f"agent:{event.get('agent_id') or event['id']}", event, "concluida", parent=main,
                   kind=event.get("agent_type") or "subagente", ended="SubagentStop")
            if runs[main]["estado"] == "delegando" and not children(sid):
                upsert(main, event, "trabalhando")
        elif name == "Stop":
            tasks = event.get("background_tasks")
            if isinstance(tasks, list):
                listed = {str(task.get("id")) for task in tasks if isinstance(task, dict)}
                for child in children(sid):
                    if str(child["agent_id"]) not in listed:
                        child.update(estado="concluida", encerramento="interrompida", atualizado=event["t"])
            upsert(main, event, "delegando" if children(sid) else "aguardando")
        elif name == "SessionEnd":
            upsert(main, event, "concluida", ended=event.get("reason") or "SessionEnd")
            for child in children(sid):
                child.update(estado="concluida", encerramento="SessionEnd", atualizado=event["t"])
    return runs


def process_alive(pid: object) -> bool:
    try:
        number = int(pid)
    except (TypeError, ValueError):
        return False
    if number <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(number, 0)
        except PermissionError:
            return True
        except OSError:
            return False
        return True
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.windll.kernel32
    handle = kernel.OpenProcess(0x1000, False, number)
    if not handle:
        return False
    try:
        code = wintypes.DWORD()
        return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
    finally:
        kernel.CloseHandle(handle)


def living_sessions() -> dict[str, bool]:
    """Le ~/.claude/sessions apenas para saber se o processo de cada sessao segue vivo."""
    found: dict[str, bool] = {}
    folder = sessions_dir()
    if not folder.is_dir():
        return found
    for path in folder.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and isinstance(data.get("sessionId"), str):
            found[data["sessionId"]] = found.get(data["sessionId"], False) or process_alive(data.get("pid"))
    return found


def reconcile(runs: dict[str, dict], now: datetime, demo: bool) -> None:
    if demo:
        return
    alive = living_sessions()
    for run in runs.values():
        if run["pai"] or run["estado"] not in ACTIVE:
            continue
        sid = run["session_id"]
        silent = now - parse_time(run["atualizado"]) > timedelta(minutes=SILENCE_MINUTES)
        if (sid in alive and not alive[sid]) or (sid not in alive and silent):
            run.update(estado="orfa", encerramento="sem sinal")
            for child in runs.values():
                if child["session_id"] == sid and child["pai"] and child["estado"] in ACTIVE:
                    child.update(estado="orfa", encerramento="sem sinal")


def snapshot(folder: Path, demo: bool, hours: int) -> dict:
    now = datetime.now(timezone.utc)
    runs = project(read_events(folder, now))
    reconcile(runs, now, demo)
    for run in runs.values():
        run["projeto"] = Path(run["cwd"]).name if run["cwd"] else "sem projeto"
    room_limit = now - timedelta(hours=ROOM_HOURS)
    sessions = []
    for main in sorted((r for r in runs.values() if not r["pai"]), key=lambda r: r["inicio"]):
        kids = sorted((r for r in runs.values() if r["pai"] == main["chave"]), key=lambda r: r["inicio"])
        recent = main["estado"] in ACTIVE or parse_time(main["atualizado"]) >= room_limit
        short = (main["estado"] == "concluida" and not kids and
                 parse_time(main["atualizado"]) - parse_time(main["inicio"]) < timedelta(seconds=30))
        if recent and not short:
            sessions.append({**main, "subagentes": kids})
    panel_limit = now - timedelta(hours=hours)
    in_panel = [r for r in runs.values() if parse_time(r["atualizado"]) >= panel_limit or r["estado"] in ACTIVE]
    counts = {state: sum(1 for r in in_panel if r["estado"] == state)
              for state in ("trabalhando", "delegando", "aguardando", "concluida", "orfa")}
    by_type: dict[str, int] = {}
    for run in in_panel:
        if run["pai"]:
            by_type[run["tipo"]] = by_type.get(run["tipo"], 0) + 1
    return {
        "agora": now.isoformat(timespec="seconds"), "demo": demo, "horas": hours,
        "sessoes": sessions, "contagem": counts, "por_tipo": by_type,
        "execucoes": sorted(in_panel, key=lambda r: r["atualizado"], reverse=True),
    }


# ---------------------------------------------------------------- demonstracao

def write_demo(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    rng = random.Random()
    events = []

    def add(minutes_ago, name, sid, cwd, **extra):
        moment = now - timedelta(minutes=minutes_ago)
        events.append({"evento": name, "session_id": sid, "cwd": cwd, "id": str(uuid.uuid4()),
                       "t": moment.isoformat(timespec="seconds"), **extra})

    plans = [
        ("/projetos/uzu-home", ["Explore", "revisor-de-entrega", "Plan"], True),
        ("/projetos/guidu", ["pesquisador", "camis"], True),
        ("/projetos/studionave", ["Explore"], False),
        ("/projetos/carrosseis", ["general-purpose", "Explore", "pesquisador", "Plan"], True),
    ]
    for index, (cwd, kinds, open_session) in enumerate(plans):
        sid = str(uuid.uuid4())
        start = 90 - index * 15
        add(start, "SessionStart", sid, cwd)
        add(start - 1, "UserPromptSubmit", sid, cwd)
        for number, kind in enumerate(kinds):
            agent = f"demo-{index}-{number}"
            begin = start - 2 - number * 3
            add(begin, "SubagentStart", sid, cwd, agent_id=agent, agent_type=kind)
            still_running = open_session and number >= len(kinds) - 2 and rng.random() > 0.3
            if not still_running:
                add(begin - rng.randint(1, 4), "SubagentStop", sid, cwd, agent_id=agent, agent_type=kind)
        if not open_session:
            add(10, "Stop", sid, cwd)
            add(8, "SessionEnd", sid, cwd, reason="logout")
    idle = str(uuid.uuid4())
    add(20, "SessionStart", idle, "/projetos/bod")
    add(19, "UserPromptSubmit", idle, "/projetos/bod")
    add(5, "Stop", idle, "/projetos/bod")
    with (folder / "events.jsonl").open("w", encoding="utf-8") as stream:
        for event in events:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
    print(f"Dados de exemplo gravados em {folder}")


# ---------------------------------------------------------------- servidor

def make_handler(folder: Path, demo: bool):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(WEB), **kwargs)

        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path.startswith("/api/estado"):
                match = re.search(r"horas=(\d+)", self.path)
                hours = int(match.group(1)) if match and match.group(1) in {"6", "12", "24"} else 12
                body = json.dumps(snapshot(folder, demo, hours), ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            super().do_GET()

    return Handler


def serve(port: int, demo: bool, open_browser: bool) -> None:
    folder = data_dir(demo)
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(folder, demo))
    except OSError:
        raise SystemExit(f"A porta {port} ja esta em uso. Tente: python studionave.py iniciar --porta 8877")
    url = f"http://127.0.0.1:{port}"
    print(f"Studio Nave {'(demonstracao) ' if demo else ''}aberto em {url}")
    print("Deixe este terminal aberto. Para encerrar, pressione Ctrl+C.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStudio Nave encerrado.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="studionave", description="Sala para visualizar seus agentes.")
    commands = parser.add_subparsers(dest="acao", required=True)
    commands.add_parser("instalar", help="registra os hooks no Claude Code")
    commands.add_parser("remover", help="remove os hooks do Studio Nave")
    for name in ("iniciar", "demo"):
        item = commands.add_parser(name)
        item.add_argument("--porta", type=int, default=8765)
        item.add_argument("--sem-navegador", action="store_true")
    args = parser.parse_args(argv)
    if args.acao == "instalar":
        install_hooks(settings_path())
    elif args.acao == "remover":
        remove_hooks(settings_path())
    elif args.acao == "demo":
        write_demo(data_dir(demo=True))
        serve(args.porta, True, not args.sem_navegador)
    else:
        serve(args.porta, False, not args.sem_navegador)


if __name__ == "__main__":
    main()
