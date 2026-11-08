#!/usr/bin/env python3
"""Собрать статический каталог и PDF из локальных учебных курсов.

Исходные курсы остаются нетронутыми. Для недостающих PDF используется Pandoc
и pdflatex, а все файлы публикации помещаются в каталог pdf/ этого проекта.
"""

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
COURSES = Path.home() / "lessons" / "self_cources"
DEST = HERE / "pdf"
KINDS = ("notes", "assignments", "hints", "solutions")

EXISTING_COURSES = {
    "fpt_course": ("fpt", "FPT-алгоритмы", "Параметризованная сложность и алгоритмы"),
    "distributed_algorithms_course": ("distributed", "Распределённые алгоритмы", "Модели, локальные и глобальные алгоритмы, нижние оценки"),
}


def markdown_dir(root: Path, kind: str) -> Path:
    nested = root / "md" / kind
    return nested if nested.is_dir() else root / kind


def course_configs():
    if not COURSES.is_dir():
        raise FileNotFoundError(COURSES)
    roots = sorted((p for p in COURSES.iterdir() if p.is_dir()),
                   key=lambda p: (p.name not in EXISTING_COURSES,
                                  list(EXISTING_COURSES).index(p.name) if p.name in EXISTING_COURSES else p.name))
    seen = set()
    for root in roots:
        notes = markdown_dir(root, "notes")
        if not notes.is_dir() or not list(notes.glob("[0-9]*-*.md")):
            continue
        legacy = EXISTING_COURSES.get(root.name)
        site_metadata = root / "site.json"
        metadata = json.loads(site_metadata.read_text(encoding="utf-8")) if site_metadata.is_file() else {}
        course_id = metadata.get("id") or (legacy[0] if legacy else root.name.removesuffix("_course").replace("_", "-"))
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", course_id) or course_id in seen:
            raise ValueError(f"Некорректный или повторяющийся ID курса: {course_id}")
        seen.add(course_id)
        readme = root / "README.md"
        fallback_name = title_from_markdown(readme) if readme.is_file() else root.name.replace("_", " ")
        name = metadata.get("name") or (legacy[1] if legacy else fallback_name)
        subtitle = metadata.get("subtitle") or (legacy[2] if legacy else "Материалы для самостоятельного изучения")
        yield root, course_id, name, subtitle


def compile_pdf(markdown: Path, output: Path, template: Path) -> None:
    if not shutil.which("pandoc") or not shutil.which("pdflatex"):
        raise RuntimeError("Для сборки новых PDF нужны pandoc и pdflatex")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tcs-pdf-") as tmp:
        tmp = Path(tmp)
        tex = tmp / "document.tex"
        subprocess.run(
            ["pandoc", str(markdown), "--from=markdown+tex_math_dollars", "--to=latex",
             "--standalone", f"--template={template}", "--output", str(tex)],
            check=True, stdout=subprocess.DEVNULL,
        )
        for _ in range(2):
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
                 "-jobname=document", f"-output-directory={tmp}", str(tex)],
                cwd=markdown.parent, text=True, errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            )
            if result.returncode:
                raise RuntimeError(f"Не удалось собрать {markdown}:\n{result.stdout[-3000:]}")
        shutil.copy2(tmp / "document.pdf", output)


def title_from_markdown(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return re.sub(r"^\d{1,3}[.\s]+", "", line[2:].strip())
    return path.stem


def put_pdf(course_root: Path, course_id: str, kind: str, stem: str, template: Path) -> str | None:
    output = DEST / course_id / kind / f"{stem}.pdf"
    source_pdf = course_root / "pdf" / kind / f"{stem}.pdf"
    if not source_pdf.exists():
        source_pdf = course_root / kind / f"{stem}.pdf"
    source_md = markdown_dir(course_root, kind) / f"{stem}.md"
    if source_pdf.exists():
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_pdf, output)
    elif source_md.exists():
        if not output.exists() or output.stat().st_mtime < max(source_md.stat().st_mtime, template.stat().st_mtime):
            compile_pdf(source_md, output, template)
    else:
        return None
    return output.relative_to(HERE).as_posix()


def main() -> None:
    catalogue = []
    for root, course_id, name, subtitle in course_configs():
        template = root / "scripts" / "latex-template.tex"
        if not template.is_file():
            template = HERE / "latex-template.tex"
        fpt_titles = {entry["stem"]: entry["title"] for entry in json.loads((root / "course.json").read_text())} if course_id == "fpt" else {}
        lessons = []
        notes = sorted(markdown_dir(root, "notes").glob("[0-9]*-*.md"), key=lambda p: int(p.stem.split("-", 1)[0]))
        for note in notes:
            stem = note.stem
            number = int(stem.split("-", 1)[0])
            title = fpt_titles.get(stem) or title_from_markdown(note)
            files = {kind: put_pdf(root, course_id, kind, stem, template) for kind in KINDS}
            lessons.append({"number": number, "slug": stem, "title": title, "files": files})
            print(f"{name}: {number:02d} — {title}")
        extras = []
        for filename, label in (("exam", "Экзамен"), ("exam_rubric", "Критерии экзамена")):
            pdf = root / f"{filename}.pdf"
            md = root / f"{filename}.md"
            if pdf.exists() or md.exists():
                output = DEST / course_id / f"{filename}.pdf"
                output.parent.mkdir(parents=True, exist_ok=True)
                if pdf.exists():
                    shutil.copy2(pdf, output)
                elif not output.exists() or output.stat().st_mtime < max(md.stat().st_mtime, template.stat().st_mtime):
                    compile_pdf(md, output, template)
                extras.append({"title": label, "path": output.relative_to(HERE).as_posix()})
        catalogue.append({"id": course_id, "name": name, "subtitle": subtitle, "lessons": lessons, "extras": extras, "hasHints": any(t["files"]["hints"] for t in lessons)})
    payload = json.dumps(catalogue, ensure_ascii=False, indent=2)
    (HERE / "catalogue.json").write_text(payload + "\n", encoding="utf-8")
    (HERE / "catalogue.js").write_text("window.TCS_COURSES = " + payload + ";\n", encoding="utf-8")
    assets = ("styles.css", "catalogue.js", "app.js")
    version = hashlib.sha256(b"".join((HERE / asset).read_bytes() for asset in assets)).hexdigest()[:12]
    index = HERE / "index.html"
    html = index.read_text(encoding="utf-8")
    for asset in assets:
        html = re.sub(rf'(["\']){re.escape(asset)}(?:\?v=[a-f0-9]+)?\1',
                      lambda match: f'{match.group(1)}{asset}?v={version}{match.group(1)}', html)
    index.write_text(html, encoding="utf-8")
    print(f"Готово: {sum(len(c['lessons']) for c in catalogue)} тем, {sum(len(list((DEST / c['id']).rglob('*.pdf'))) for c in catalogue)} PDF")


if __name__ == "__main__":
    main()
