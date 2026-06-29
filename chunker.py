import pdfplumber


def chunk_pdf(pdf_path: str) -> list[dict]:
    chunks = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    # Skip header rows
                    if not row or row[0] is None or str(row[0]).strip() == "#":
                        continue

                    # Clean up cell values
                    cells = [str(c).strip() if c else "" for c in row]

                    # Skip rows that don't start with a task number
                    if not cells[0].isdigit():
                        continue

                    task_id = cells[0]
                    department = cells[1] if len(cells) > 1 else ""
                    priority = cells[2] if len(cells) > 2 else ""
                    finding = cells[3] if len(cells) > 3 else ""
                    file_component = cells[4] if len(cells) > 4 else ""
                    action = cells[5] if len(cells) > 5 else ""
                    est_hours = cells[6] if len(cells) > 6 else ""
                    status = cells[7] if len(cells) > 7 else ""

                    # Build a readable text chunk for embedding/retrieval
                    text = (
                        f"Task {task_id} [{priority}] — {finding}. "
                        f"Department: {department}. "
                        f"File/Component: {file_component}. "
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
                            "file_component": file_component,
                            "action": action,
                            "est_hours": est_hours,
                            "status": status,
                        },
                    })

    return chunks
