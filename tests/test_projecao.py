import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import studionave  # noqa: E402


def ev(t, name, sid="s1", **extra):
    return {"id": f"{name}-{t}-{extra.get('agent_id', '')}", "t": f"2026-10-09T10:{t:02d}:00+00:00",
            "evento": name, "session_id": sid, "cwd": "/p/app", **extra}


class ProjecaoTest(unittest.TestCase):
    def test_ciclo_com_subagente(self):
        runs = studionave.project([ev(1, "SessionStart"), ev(2, "UserPromptSubmit"),
                                   ev(3, "SubagentStart", agent_id="a1", agent_type="Explore")])
        self.assertEqual(runs["session:s1"]["estado"], "delegando")
        self.assertEqual(runs["agent:a1"]["estado"], "trabalhando")
        runs = studionave.project([ev(1, "SessionStart"), ev(2, "UserPromptSubmit"),
                                   ev(3, "SubagentStart", agent_id="a1", agent_type="Explore"),
                                   ev(4, "SubagentStop", agent_id="a1", agent_type="Explore")])
        self.assertEqual(runs["session:s1"]["estado"], "trabalhando")
        self.assertEqual(runs["agent:a1"]["estado"], "concluida")

    def test_stop_encerra_filha_fora_da_lista(self):
        runs = studionave.project([ev(1, "SessionStart"),
                                   ev(2, "SubagentStart", agent_id="a1", agent_type="X"),
                                   ev(3, "Stop", background_tasks=[])])
        self.assertEqual(runs["agent:a1"]["encerramento"], "interrompida")
        self.assertEqual(runs["session:s1"]["estado"], "aguardando")

    def test_session_end(self):
        runs = studionave.project([ev(1, "SessionStart"),
                                   ev(2, "SubagentStart", agent_id="a1", agent_type="X"),
                                   ev(3, "SessionEnd", reason="logout")])
        self.assertEqual(runs["session:s1"]["estado"], "concluida")
        self.assertEqual(runs["agent:a1"]["estado"], "concluida")

    def test_hook_grava_apenas_metadados(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = {"hook_event_name": "UserPromptSubmit", "session_id": "s1", "cwd": "/p",
                       "prompt": "segredo", "transcript_path": "/x"}
            subprocess.run([sys.executable, str(ROOT / "hooks" / "capture.py")], input=json.dumps(payload),
                           text=True, check=True, env={"STUDIONAVE_DATA_DIR": tmp})
            line = json.loads((Path(tmp) / "events.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(line["evento"], "UserPromptSubmit")
            self.assertNotIn("prompt", line)
            self.assertNotIn("transcript_path", line)

    def test_instalar_e_remover_preserva_outros_hooks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            other = {"type": "command", "command": "echo oi"}
            path.write_text(json.dumps({"model": "x", "hooks": {"Stop": [{"hooks": [other]}]}}))
            studionave.install_hooks(path)
            studionave.install_hooks(path)  # repetir nao duplica
            data = json.loads(path.read_text())
            self.assertEqual(len(data["hooks"]["Stop"]), 2)
            self.assertEqual(len(data["hooks"]["SessionStart"]), 1)
            studionave.remove_hooks(path)
            data = json.loads(path.read_text())
            self.assertEqual(data, {"model": "x", "hooks": {"Stop": [{"hooks": [other]}]}})


if __name__ == "__main__":
    unittest.main()
