"""Add authoritative source-text JSON sidecars to synthetic PDF ZIP archives.

The script is intentionally limited to referral PDFs produced by the deterministic
stress generator. It reconstructs each clean, pre-degradation document from the
case index and seed, then packages the untouched archived PDF with the lean
``*.metadata.json`` evaluator sidecar.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
import re
import shutil
import sys
import tempfile
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from referral_pipeline.synthetic_data.metadata import write_pdf_metadata  # noqa: E402
from referral_pipeline.synthetic_data.render import render_referral  # noqa: E402
from referral_pipeline.synthetic_data.stress import (  # noqa: E402
    DEFAULT_PROFILES,
    LAYOUTS,
    PAGE_RANGES,
    _expand_packet,
    _pick_scan_profile,
    synthetic_case,
)


LOGGER = logging.getLogger("synthetic-metadata-archives")
PDF_NAME = re.compile(
    r"^referral-case-(?P<index>\d{9})-"
    r"(?P<layout>[a-z_]+)-(?P<profile>[a-z_]+)\.pdf$"
)


def _archive_pdfs(archive: Path) -> list[zipfile.ZipInfo]:
    with zipfile.ZipFile(archive) as source:
        return [
            info
            for info in source.infolist()
            if not info.is_dir()
            and not info.filename.startswith("__MACOSX/")
            and info.filename.lower().endswith(".pdf")
        ]


def _parse_and_validate_name(filename: str, *, seed: int) -> int:
    match = PDF_NAME.fullmatch(Path(filename).name)
    if match is None:
        raise ValueError(f"unsupported synthetic PDF filename: {filename}")

    index = int(match.group("index"))
    expected_layout = LAYOUTS[index % len(LAYOUTS)]
    expected_profile = _pick_scan_profile(
        index,
        seed=seed,
        profiles=DEFAULT_PROFILES,
    )
    actual = (match.group("layout"), match.group("profile"))
    expected = (expected_layout, expected_profile)
    if actual != expected:
        raise ValueError(
            f"{filename} does not match seed {seed}: "
            f"expected {expected_layout}-{expected_profile}"
        )
    return index


def _build_sidecar(task: tuple[int, str, int, str]) -> tuple[str, str]:
    index, pdf_filename, seed, metadata_directory = task
    case = synthetic_case(index, seed=seed)
    rng = random.Random(f"{seed}:pages:{index}")
    page_min, page_max = PAGE_RANGES[case.layout]
    target_pages = rng.randint(page_min, page_max)
    layout_variant = int(
        hashlib.sha256(f"{seed}:{index}:layout".encode()).hexdigest()[:8],
        16,
    ) % 6

    metadata_path = Path(metadata_directory) / Path(pdf_filename).with_suffix(
        ".metadata.json"
    ).name
    with tempfile.TemporaryDirectory(prefix="synthetic-source-") as temporary:
        temporary_dir = Path(temporary)
        base = render_referral(
            case,
            temporary_dir / "base.pdf",
            variant=layout_variant,
        )
        expanded = temporary_dir / "expanded.pdf"
        _expand_packet(
            base,
            expanded,
            case=case,
            target_pages=target_pages,
            seed=f"{seed}:{index}",
        )
        write_pdf_metadata(
            metadata_path,
            source_pdf=expanded,
            final_pdf=Path(pdf_filename),
            case=case,
        )
    return pdf_filename, str(metadata_path)


def _generate_sidecars(
    pdf_names: list[str],
    *,
    seed: int,
    workers: int,
    metadata_directory: Path,
) -> dict[str, Path]:
    tasks = [
        (
            _parse_and_validate_name(name, seed=seed),
            name,
            seed,
            str(metadata_directory),
        )
        for name in pdf_names
    ]
    generated: dict[str, Path] = {}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_build_sidecar, task): task[1] for task in tasks}
        for completed, future in enumerate(as_completed(futures), start=1):
            pdf_name, metadata_path = future.result()
            generated[pdf_name] = Path(metadata_path)
            if completed % 100 == 0 or completed == len(tasks):
                LOGGER.info("Generated %d/%d JSON sidecars", completed, len(tasks))
    return generated


def _copy_pdf(
    source: zipfile.ZipFile,
    destination: zipfile.ZipFile,
    source_info: zipfile.ZipInfo,
    output_name: str,
) -> None:
    output_info = zipfile.ZipInfo(output_name, date_time=source_info.date_time)
    output_info.compress_type = zipfile.ZIP_DEFLATED
    output_info.external_attr = source_info.external_attr
    with source.open(source_info) as input_stream, destination.open(output_info, "w") as output_stream:
        shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)


def enrich_archive(
    archive: Path,
    *,
    output_dir: Path,
    seed: int,
    workers: int,
) -> Path:
    pdf_entries = _archive_pdfs(archive)
    if not pdf_entries:
        raise ValueError(f"no PDFs found in {archive}")
    pdf_names = [Path(info.filename).name for info in pdf_entries]
    if len(pdf_names) != len(set(pdf_names)):
        raise ValueError(f"duplicate PDF basenames found in {archive}")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{archive.stem}-with-json.zip"
    temporary_output = output_path.with_suffix(".zip.incomplete")
    if output_path.exists() or temporary_output.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output_path}")

    LOGGER.info("Enriching %s (%d PDFs)", archive.name, len(pdf_entries))
    with tempfile.TemporaryDirectory(prefix=f"{archive.stem}-metadata-") as temporary:
        sidecars = _generate_sidecars(
            pdf_names,
            seed=seed,
            workers=workers,
            metadata_directory=Path(temporary),
        )
        root = archive.stem
        with (
            zipfile.ZipFile(archive) as source,
            zipfile.ZipFile(
                temporary_output,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=1,
                allowZip64=True,
            ) as destination,
        ):
            for completed, info in enumerate(pdf_entries, start=1):
                pdf_name = Path(info.filename).name
                _copy_pdf(source, destination, info, f"{root}/{pdf_name}")
                metadata_path = sidecars[pdf_name]
                destination.write(
                    metadata_path,
                    arcname=f"{root}/{metadata_path.name}",
                    compress_type=zipfile.ZIP_DEFLATED,
                    compresslevel=6,
                )
                if completed % 100 == 0 or completed == len(pdf_entries):
                    LOGGER.info("Packaged %d/%d PDF/JSON pairs", completed, len(pdf_entries))

    temporary_output.replace(output_path)
    _validate_output(output_path, expected_pdfs=len(pdf_entries))
    LOGGER.info("Created %s", output_path)
    return output_path


def _validate_output(archive: Path, *, expected_pdfs: int) -> None:
    with zipfile.ZipFile(archive) as zf:
        bad_entry = zf.testzip()
        if bad_entry is not None:
            raise ValueError(f"CRC validation failed for {bad_entry}")
        files = [info for info in zf.infolist() if not info.is_dir()]
        pdfs = {Path(info.filename).name for info in files if info.filename.endswith(".pdf")}
        jsons = {
            Path(info.filename).name
            for info in files
            if info.filename.endswith(".metadata.json")
        }
        if len(pdfs) != expected_pdfs or len(jsons) != expected_pdfs:
            raise ValueError(
                f"pair count mismatch: expected {expected_pdfs}, "
                f"found {len(pdfs)} PDFs and {len(jsons)} JSON files"
            )
        for pdf_name in pdfs:
            sidecar = Path(pdf_name).with_suffix(".metadata.json").name
            if sidecar not in jsons:
                raise ValueError(f"missing sidecar for {pdf_name}")
            payload_name = next(
                info.filename for info in files if Path(info.filename).name == sidecar
            )
            payload = json.loads(zf.read(payload_name))
            if payload.get("pdf_filename") != pdf_name:
                raise ValueError(f"sidecar filename mismatch for {pdf_name}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Add lean source-text JSON sidecars to deterministic synthetic PDF ZIPs."
    )
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260826)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    outputs = [
        enrich_archive(
            archive.resolve(),
            output_dir=args.output_dir.resolve(),
            seed=args.seed,
            workers=args.workers,
        )
        for archive in args.archives
    ]
    print(json.dumps({"archives": [str(path) for path in outputs]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
