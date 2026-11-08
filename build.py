#!/usr/bin/env python3
"""Собрать статический каталог и PDF из локальных учебных курсов.

Исходные курсы остаются нетронутыми. Для недостающих PDF используется Pandoc
и pdflatex, а все файлы публикации помещаются в каталог pdf/ этого проекта.
"""

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

CONFIG = (
    ("fpt", "fpt_course", "FPT-алгоритмы", "Параметризованная сложность и алгоритмы", False),
    ("distributed", "distributed_algorithms_course", "Распределённые алгоритмы", "Модели, локальные и глобальные алгоритмы, нижние оценки", True),
)


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
            return re.sub(r"^\d{1,2}[.\s]+", "", line[2:].strip())
    return path.stem


def put_pdf(course_root: Path, course_id: str, kind: str, stem: str, template: Path) -> str | None:
    output = DEST / course_id / kind / f"{stem}.pdf"
    source_pdf = course_root / "pdf" / kind / f"{stem}.pdf"
    source_md = course_root / "md" / kind / f"{stem}.md"
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
    for course_id, folder, name, subtitle, has_hints in CONFIG:
        root = COURSES / folder
        if not root.is_dir():
            raise FileNotFoundError(root)
        template = root / "scripts" / "latex-template.tex"
        fpt_titles = {entry["stem"]: entry["title"] for entry in json.loads((root / "course.json").read_text())} if course_id == "fpt" else {}
        lessons = []
        for note in sorted((root / "md" / "notes").glob("[0-9][0-9]-*.md")):
            stem = note.stem
            number = int(stem[:2])
            title = fpt_titles.get(stem) or title_from_markdown(note)
            files = {kind: put_pdf(root, course_id, kind, stem, template) for kind in KINDS}
            lessons.append({"number": number, "slug": stem, "title": title, "files": files})
            print(f"{name}: {number:02d} — {title}")
        if len(lessons) != 16:
            raise RuntimeError(f"Ожидалось 16 тем в {root}, найдено {len(lessons)}")
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
        catalogue.append({"id": course_id, "name": name, "subtitle": subtitle, "lessons": lessons, "extras": extras, "hasHints": has_hints})
    payload = json.dumps(catalogue, ensure_ascii=False, indent=2)
    (HERE / "catalogue.json").write_text(payload + "\n", encoding="utf-8")
    (HERE / "catalogue.js").write_text("window.TCS_COURSES = " + payload + ";\n", encoding="utf-8")
    print(f"Готово: {sum(len(c['lessons']) for c in catalogue)} тем, {sum(len(list((DEST / c['id']).rglob('*.pdf'))) for c in catalogue)} PDF")


if __name__ == "__main__":
    main()
