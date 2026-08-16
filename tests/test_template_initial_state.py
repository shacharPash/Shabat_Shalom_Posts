"""Regression tests for the initial state of the HTML template."""

from html.parser import HTMLParser
from pathlib import Path
import unittest


class _ElementByIdParser(HTMLParser):
    def __init__(self, target_id: str) -> None:
        super().__init__()
        self.target_id = target_id
        self.attributes: dict[str, str | None] | None = None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        if attributes.get("id") == self.target_id:
            self.attributes = attributes


class TemplateInitialStateTests(unittest.TestCase):
    def test_omer_selector_is_hidden_until_availability_is_known(self) -> None:
        template_path = Path(__file__).parents[1] / "api" / "template.html"
        parser = _ElementByIdParser("modeSelectorSection")
        parser.feed(template_path.read_text(encoding="utf-8"))

        self.assertIsNotNone(parser.attributes)
        style = (parser.attributes or {}).get("style") or ""
        declarations = {
            name.strip(): value.strip()
            for declaration in style.split(";")
            if ":" in declaration
            for name, value in [declaration.split(":", 1)]
        }
        self.assertEqual(declarations.get("display"), "none")


if __name__ == "__main__":
    unittest.main()
