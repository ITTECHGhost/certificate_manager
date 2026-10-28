"""In-app update: one version source, patch lands next to the exe, the .bat copes with any path."""
import json
import os
import subprocess
import zipfile

import app_paths
import app_version
import services.updater as updater
from tests.helpers import PROJECT_ROOT

APPLY_PATCH = PROJECT_ROOT / "scripts" / "apply_patch.bat"


def test_version_single_source():
    assert updater.CURRENT_APP_VERSION == app_version.APP_VERSION
    assert "app_version.py" in (PROJECT_ROOT / "scripts" / "make_client_patch.ps1").read_text(encoding="utf-8")


def test_patch_targets_install_dir_and_runs_temp_copy(monkeypatch):
    calls = []
    monkeypatch.setattr(updater.subprocess, "Popen", lambda command, **kwargs: calls.append(command))
    assert updater.apply_patch_and_restart(r"C:\patches\patch_v9.zip") is True
    temp_script = updater.build_temp_patch_script_path(str(os.getpid()))
    assert os.path.isfile(temp_script)
    command = calls[0]
    assert command.startswith(f'cmd.exe /s /c ""{temp_script}" ')
    assert f'"{app_paths.INSTALL_DIR}"' in command
    assert f'"{app_paths.data_path("logs")}"' in command
    os.remove(temp_script)


def test_apply_patch_handles_space_and_arabic_paths(tmp_path):
    base = tmp_path / "برنامج الشهادات 1"
    app_dir = base / "app"
    log_dir = base / "logs"
    app_dir.mkdir(parents=True)
    log_dir.mkdir()
    (app_dir / "server_config.json").write_text('{"host": "keep"}', encoding="utf-8")
    zip_path = base / "patch v1.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("a.txt", "new file")
        archive.writestr("server_config.json", '{"host": "lose"}')
    command = updater.build_patch_command(str(APPLY_PATCH), "999999", str(zip_path), str(app_dir),
                                          "CertificateManager.exe", str(log_dir))
    env = {**os.environ, "CM_PATCH_NO_RELAUNCH": "1"}
    result = subprocess.run(command, env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=180)
    output = result.stdout.decode("mbcs", "replace") + result.stderr.decode("mbcs", "replace")
    assert result.returncode == 0, output
    assert (app_dir / "a.txt").read_text(encoding="utf-8") == "new file"
    assert json.loads((app_dir / "server_config.json").read_text(encoding="utf-8"))["host"] == "keep"
    assert not zip_path.exists()
    assert (log_dir / "system_log.txt").is_file()
