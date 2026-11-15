"""English interpretation output must stay byte-identical across i18n refactors."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from gen_interpret_golden import snapshot  # noqa: E402

GOLDEN = Path(__file__).parent / "golden" / "interpret_en.json"


def test_english_interpretation_is_unchanged() -> None:
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    actual = json.loads(json.dumps(snapshot(), ensure_ascii=False))
    assert actual == expected
