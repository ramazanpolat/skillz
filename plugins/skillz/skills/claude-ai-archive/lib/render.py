"""Render export records (conversation, design_chat, project) to Markdown."""
import json


def _msg_block(m: dict) -> str:
    sender = m.get("sender", "?")
    ts = m.get("created_at", "")
    text = m.get("text") or ""
    if not text:
        parts = []
        for blk in m.get("content") or []:
            if blk.get("type") == "text":
                parts.append(blk.get("text", ""))
            else:
                parts.append(f"[{blk.get('type', 'block')}]")
        text = "\n".join(parts)
    extras = []
    if m.get("attachments"):
        extras.append(f"_attachments: {len(m['attachments'])}_")
    if m.get("files"):
        extras.append(f"_files: {len(m['files'])}_")
    header = f"## {sender} — {ts}"
    if extras:
        header += "  " + "  ".join(extras)
    return f"{header}\n\n{text}\n"


def render_conversation(conv: dict, archived: bool = False) -> str:
    uuid = conv.get("uuid", "")
    name = conv.get("name") or "untitled"
    msgs = conv.get("chat_messages") or []
    lines = [
        "---",
        f"uuid: {uuid}",
        f"title: {json.dumps(name, ensure_ascii=False)[1:-1]}",
        f"created_at: {conv.get('created_at', '')}",
        f"updated_at: {conv.get('updated_at', '')}",
        f"message_count: {len(msgs)}",
    ]
    if conv.get("summary"):
        s = conv["summary"].replace("\n", " ").strip()
        lines.append(f"summary: {json.dumps(s, ensure_ascii=False)[1:-1]}")
    if archived:
        lines.append("archived: true")
    lines.extend(["---", "", f"# {name}", ""])
    for m in msgs:
        lines.append(_msg_block(m))
    return "\n".join(lines)


def render_design_chat(d: dict) -> str:
    uuid = d.get("uuid", "")
    title = d.get("title") or "design-chat"
    msgs = d.get("messages") or []
    lines = [
        "---",
        f"uuid: {uuid}",
        f"title: {json.dumps(title, ensure_ascii=False)[1:-1]}",
        f"created_at: {d.get('created_at', '')}",
        f"updated_at: {d.get('updated_at', '')}",
        f"project: {(d.get('project') or {}).get('uuid', '')}",
        f"message_count: {len(msgs)}",
        "---",
        "",
        f"# {title}",
        "",
    ]
    for m in msgs:
        role = m.get("role", "?")
        ts = m.get("created_at", "")
        content = m.get("content")
        if isinstance(content, list):
            text = "\n".join(
                b.get("text", "") if isinstance(b, dict) else str(b) for b in content
            )
        else:
            text = str(content or "")
        lines.append(f"## {role} — {ts}\n\n{text}\n")
    return "\n".join(lines)


def render_project(p: dict, memory: str, archived: bool = False) -> str:
    uuid = p["uuid"]
    name = p["name"]
    docs = p.get("docs", []) or []
    lines = [
        "---",
        f"uuid: {uuid}",
        f"name: {json.dumps(name, ensure_ascii=False)[1:-1]}",
        f"created_at: {p.get('created_at', '')}",
        f"updated_at: {p.get('updated_at', '')}",
        f"is_private: {p.get('is_private')}",
        f"is_starter_project: {p.get('is_starter_project')}",
        f"doc_count: {len(docs)}",
        f"has_project_memory: {bool(memory)}",
    ]
    if archived:
        lines.append("archived: true")
    lines.extend(["---", "", f"# {name}", ""])
    if p.get("description"):
        lines.extend(["## Description", "", p["description"], ""])
    if p.get("prompt_template"):
        lines.extend(["## Prompt template", "", p["prompt_template"], ""])
    if memory:
        lines.extend(["## Project memory", "", memory.strip(), ""])
    if not (p.get("description") or p.get("prompt_template") or memory):
        lines.extend(["_(empty project — no description, prompt template, docs, or memory)_", ""])
    return "\n".join(lines)
