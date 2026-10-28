"""client.spec must ship the seed resources and the icon, and never a real server_config.json."""
import app_paths
from tests.helpers import PROJECT_ROOT

SPEC = (PROJECT_ROOT / "client.spec").read_text(encoding="utf-8")


def test_spec_never_bundles_a_real_server_config():
    assert "('server_config.json'" not in SPEC
    assert "('server_config.example.json', '.')" in SPEC


def test_spec_bundles_icon_and_update_script():
    assert "icon='assets/app.ico'" in SPEC
    assert (PROJECT_ROOT / "assets" / "app.ico").is_file()
    assert "('scripts/apply_patch.bat', 'scripts')" in SPEC


def test_every_seed_item_is_bundled():
    for item in app_paths.SEED_ITEMS:
        folder = item.split("/")[0]
        assert f"('{item}'" in SPEC or f"('{folder}', '{folder}')" in SPEC, item
