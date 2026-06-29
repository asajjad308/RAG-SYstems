import re
import pdfplumber


CHUNK_SIZE = 400   # words per text chunk
CHUNK_OVERLAP = 60


def chunk_pdf(pdf_path: str) -> list[dict]:
    chunks = _try_table_chunk(pdf_path)
    if chunks:
        return chunks
    return _text_chunk(pdf_path)


# ── Table chunker (structured PDFs like the remediation task list) ──────────

def _try_table_chunk(pdf_path: str) -> list[dict]:
    chunks = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    if not row or row[0] is None:
                        continue
                    cells = [str(c).strip() if c else "" for c in row]
                    if not cells[0].isdigit():
                        continue

                    task_id     = cells[0]
                    department  = cells[1] if len(cells) > 1 else ""
                    priority    = cells[2] if len(cells) > 2 else ""
                    finding     = cells[3] if len(cells) > 3 else ""
                    file_comp   = cells[4] if len(cells) > 4 else ""
                    action      = cells[5] if len(cells) > 5 else ""
                    est_hours   = cells[6] if len(cells) > 6 else ""
                    status      = cells[7] if len(cells) > 7 else ""

                    text = (
                        f"Task {task_id} [{priority}] — {finding}. "
                        f"Department: {department}. "
                        f"File/Component: {file_comp}. "
                        f"Recommended Action: {action}. "
                        f"Estimated Hours: {est_hours}. "
                        f"Status: {status}."
                    )
                    chunks.append({
                        "id": int(task_id),
                        "text": text,
                        "metadata": {
                            "department": department,
                            "priority": priority,
                            "finding": finding,
                            "file_component": file_comp,
                            "action": action,
                            "est_hours": est_hours,
                            "status": status,
                        },
                    })
    return chunks


# ── Text chunker (sliding window, for any generic PDF) ─────────────────────

def _text_chunk(pdf_path: str) -> list[dict]:
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            full_text += text + "\n"

    full_text = re.sub(r"\n{3,}", "\n\n", full_text).strip()
    words = full_text.split()

    chunks = []
    idx = 0
    chunk_id = 1

    while idx < len(words):
        window = words[idx: idx + CHUNK_SIZE]
        text = " ".join(window)
        chunks.append({
            "id": chunk_id,
            "text": text,
            "metadata": {
                "department": "",
                "priority": "",
                "finding": "",
                "file_component": "",
                "action": "",
                "est_hours": "",
                "status": "",
            },
        })
        chunk_id += 1
        idx += CHUNK_SIZE - CHUNK_OVERLAP

    return chunks
