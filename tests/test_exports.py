"""Tests for the pandoc export wrapper.

Regression guard for BUG-1: binary formats (PDF, DOCX) were converted with
``pypandoc.convert_text`` and **no** ``outputfile``. Pandoc can write text
formats to stdout but refuses binary ones::

    RuntimeError: Output to docx only works by using a outputfile.

so every PDF/DOCX export returned HTTP 500. These tests patch
``pypandoc.convert_text`` (the host venv has no pandoc binary) and assert the
conversion contract rather than pandoc's rendering.
"""

import os
from unittest.mock import patch

import pytest

from app.output import pdf_exporter
from app.output.pdf_exporter import ExportFormat, export_markdown_to_format


@pytest.fixture()
def pandoc_available():
    """Bypass the real pandoc-binary probe so the conversion path runs."""
    with patch.object(
        pdf_exporter, "check_pandoc_installed", return_value=True
    ):
        yield


def make_fake_convert(writes: bytes, captured: dict):
    """A stand-in for ``pypandoc.convert_text`` that writes a real file.

    Pandoc's binary contract is "write to outputfile and return None", so the
    fake mirrors that: it records the call and writes ``writes`` to the path.
    """
    def fake_convert(text, fmt, format=None, extra_args=None, outputfile=None):
        captured["fmt"] = fmt
        captured["text"] = text
        captured["extra_args"] = list(extra_args or [])
        captured["outputfile"] = outputfile
        if outputfile is not None:
            with open(outputfile, "wb") as handle:
                handle.write(writes)
            return None
        return writes.decode("utf-8")

    return fake_convert


class TestBinaryFormatsUseOutputfile:
    """PDF and DOCX must be written through a temp file, then read back."""

    @pytest.mark.parametrize(
        "export_format,expected_suffix",
        [(ExportFormat.PDF, ".pdf"), (ExportFormat.DOCX, ".docx")],
    )
    def test_outputfile_is_passed_and_bytes_returned(
        self, pandoc_available, export_format, expected_suffix
    ):
        captured = {}
        with patch.object(
            pdf_exporter.pypandoc,
            "convert_text",
            side_effect=make_fake_convert(b"BINARY-DOCUMENT", captured),
        ):
            result = export_markdown_to_format(
                "# Title\n\nbody", output_format=export_format
            )

        assert result == b"BINARY-DOCUMENT"
        assert captured["fmt"] == export_format.value
        assert captured["outputfile"] is not None
        assert captured["outputfile"].endswith(expected_suffix)

    @pytest.mark.parametrize(
        "export_format", [ExportFormat.PDF, ExportFormat.DOCX]
    )
    def test_temporary_file_is_removed(self, pandoc_available, export_format):
        captured = {}
        with patch.object(
            pdf_exporter.pypandoc,
            "convert_text",
            side_effect=make_fake_convert(b"BYTES", captured),
        ):
            export_markdown_to_format("body", output_format=export_format)

        assert captured["outputfile"] is not None
        assert not os.path.exists(captured["outputfile"])

    def test_temporary_file_is_removed_on_failure(self, pandoc_available):
        captured = {}

        def failing_convert(
            text, fmt, format=None, extra_args=None, outputfile=None
        ):
            captured["outputfile"] = outputfile
            raise RuntimeError(
                "Output to pdf only works by using a outputfile."
            )

        with patch.object(
            pdf_exporter.pypandoc, "convert_text", side_effect=failing_convert
        ):
            with pytest.raises(ValueError):
                export_markdown_to_format(
                    "body", output_format=ExportFormat.PDF
                )

        assert not os.path.exists(captured["outputfile"])

    def test_docx_does_not_pass_an_invalid_reference_doc(self, pandoc_available):
        """``--reference-doc=default`` is not a path pandoc accepts."""
        captured = {}
        with patch.object(
            pdf_exporter.pypandoc,
            "convert_text",
            side_effect=make_fake_convert(b"BYTES", captured),
        ):
            export_markdown_to_format("body", output_format=ExportFormat.DOCX)

        assert not any(
            "reference-doc" in arg for arg in captured["extra_args"]
        )


class TestTextFormatsUseStdout:
    """HTML and Markdown keep the stdout path (no outputfile)."""

    @pytest.mark.parametrize(
        "export_format,stdout_payload",
        [
            (ExportFormat.HTML, "<html><body>hi</body></html>"),
            (ExportFormat.MARKDOWN, "# Title"),
        ],
    )
    def test_no_outputfile_and_utf8_bytes(
        self, pandoc_available, export_format, stdout_payload
    ):
        captured = {}
        with patch.object(
            pdf_exporter.pypandoc,
            "convert_text",
            side_effect=make_fake_convert(
                stdout_payload.encode("utf-8"), captured
            ),
        ):
            result = export_markdown_to_format(
                "body", output_format=export_format
            )

        assert captured["outputfile"] is None
        assert result == stdout_payload.encode("utf-8")


class TestRealPandocIntegration:
    """Only runs where a pandoc binary actually exists (i.e. Docker)."""

    @pytest.mark.skipif(
        not pdf_exporter.check_pandoc_installed(),
        reason="pandoc binary not available on this host",
    )
    def test_docx_round_trip_produces_a_zip_container(self):
        result = export_markdown_to_format(
            "# Title\n\nSome body text.", output_format=ExportFormat.DOCX
        )
        # .docx is an OOXML zip container.
        assert result[:2] == b"PK"
