---
name: latex-workshop
description: Create, edit, structure, and compile LaTeX projects in Cursor using the LaTeX Workshop extension. Use this skill for papers, reports, dissertations, thesis templates, bibliography setup, and LaTeX project layouts that should live under a latex_code folder with modular chapter files and a reusable .bib database.
metadata:
  short-description: LaTeX workflow in Cursor
---

# LaTeX Workshop

Use this skill for LaTeX papers, reports, coursework, theses, dissertations,
bibliography setup, or Cursor/VS Code LaTeX workflows.

## Defaults

- Put all LaTeX files under `latex_code/`.
- Preserve supplied templates instead of rewriting class or style files.
- Use Cursor with the LaTeX Workshop extension and a local `.vscode/settings.json`.
- Prefer `latexmk`, editor-tab PDF preview, and a local `build/` directory.
- Hide hyperlink borders with `\hypersetup{hidelinks}` unless the user asks otherwise.
- Do not use `\textit{}` for emphasis.
- If the repository should stay clean, ignore `build/` and auxiliary files.

## Pick the starting point

- `Dissertation / thesis`: use the official institutional template if available and place it under `latex_code/thesis/`. If no template is provided, start from `assets/minimal-thesis/`.
- `Report / coursework / lab write-up`: start from `assets/sec-coursework-report/`, a cleaned asset copied from `/Users/lyw/Desktop/SEC/CW/latex_code`.
- `Small paper / short report`: keep one root file under `latex_code/` unless the document is large enough to justify `preface/`, `body/`, and `bibliography/`.

## Root files

- Use `thesis.tex` for dissertations and theses.
- Use `main.tex` for reports, coursework, and shorter documents.

## Bibliography

- Keep a `.bib` file inside the LaTeX project.
- Preserve the template's existing citation stack when one already exists.
- If starting from scratch, default to `biblatex` with `biber`, plus `\textcite{}` and `\parencite{}`.

## Assets

- `assets/minimal-thesis/`: minimal modular thesis skeleton.
- `assets/sec-coursework-report/`: article-style coursework/report asset with title page, appendices, figures, `natbib`, and report-oriented layout.
