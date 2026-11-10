"""Local Chat History and active-turn recovery, independent of model lifecycle.

This store owns transcript validation, privacy envelopes, titles/origin/branch
metadata, retention and recovery. Paths, shared locks, document IO, time/UUID
and the narrow settings-only route sanitizer are explicit dependencies. It
never imports the controller, scans a model, allocates a port, starts an agent,
or accepts request-only system prompts/context files into resume persistence.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import threading
from typing import Any, Callable
import uuid
from chat_store_io import StoreReadError, read_document as read_store_document, write_document as write_store_document


@dataclass(frozen=True)
class ChatHistoryLimits:
    store_version: int = 8
    resume_version: int = 1
    max_threads: int = 100
    max_messages: int = 512
    max_characters: int = 4_000_000
    title_max: int = 72
    journal_version: int = 1
    journal_max_entries: int = 8
    journal_max_characters: int = 8_000_000
    journal_max_age_days: int = 7
    branch_kinds: frozenset[str] = frozenset({"branch", "edit", "regenerate", "continue", "recent"})
    metadata_max_bytes: int = 4 * 1024 * 1024

    @property
    def record_max_bytes(self) -> int:
        # JSON may escape one permitted control character into six bytes.
        # Per-message overhead covers flags, dates, usage and pretty printing;
        # the route/metadata allowance also covers the HTTP Chat body budget.
        return self.max_characters * 6 + self.max_messages * 1024 + self.metadata_max_bytes

    @property
    def history_max_bytes(self) -> int:
        return self.max_threads * self.record_max_bytes + 16 * 1024

    @property
    def journal_max_bytes(self) -> int:
        # The existing journal character quota counts content/reasoning only.
        # Bounded interruption failures remain permitted separately (800
        # characters per message) and may also require JSON escaping.
        failure_allowance = self.max_messages * 800 * 6
        return self.journal_max_characters * 6 + self.journal_max_entries * (self.max_messages * 1024 + failure_allowance + self.metadata_max_bytes) + 16 * 1024


class ChatHistoryStore:
    def __init__(
        self, history_path: Path, journal_path: Path, *,
        read_document: Callable[[Path], dict[str, Any]] | None = None,
        write_document: Callable[[Path, Any], None] | None = None,
        route_request_whitelist: Callable[[Any], dict[str, Any]],
        limits: ChatHistoryLimits = ChatHistoryLimits(),
        history_lock: Any = None, journal_lock: Any = None,
        clock: Callable[[], datetime] | None = None,
        new_id: Callable[[], str] | None = None,
    ) -> None:
        self.history_path = history_path
        self.journal_path = journal_path
        self._read_document = read_document if read_document is not None else self._bounded_read
        self._write_document = write_document if write_document is not None else self._bounded_write
        self._route_request_whitelist = route_request_whitelist
        self.limits = limits
        self.history_lock = history_lock if history_lock is not None else threading.Lock()
        self.journal_lock = journal_lock if journal_lock is not None else threading.Lock()
        self._clock = clock if clock is not None else lambda: datetime.now(timezone.utc)
        self._new_id = new_id if new_id is not None else lambda: str(uuid.uuid4())

    def _bounded_read(self, path: Path) -> dict[str, Any]:
        return read_store_document(
            path, collection_key="threads" if path == self.history_path else "entries",
            maximum_bytes=self.limits.history_max_bytes if path == self.history_path else self.limits.journal_max_bytes,
            maximum_record_bytes=self.limits.record_max_bytes,
            maximum_records=self.limits.max_threads if path == self.history_path else self.limits.journal_max_entries,
            validate_record=self._validate_stored_record,
            maximum_structural_tokens=(self.limits.max_messages * 64 + 16_384) * 4,
        )

    def _validate_stored_record(self, record: dict[str, Any]) -> None:
        """Bound decoded schema overhead as well as the encoded byte count."""
        pending = [iter((record,))]
        nodes = 0
        maximum_nodes = self.limits.max_messages * 64 + 16_384
        while pending:
            try:
                value = next(pending[-1])
            except StopIteration:
                pending.pop()
                continue
            nodes += 1
            if nodes > maximum_nodes or len(pending) > 64:
                raise StoreReadError("Saved chats contain excessive structured data; the existing file was kept.")
            if isinstance(value, dict):
                pending.append(iter(value.values()))
            elif isinstance(value, list):
                pending.append(iter(value))
        messages = record.get("messages")
        if messages is None:
            return
        if not isinstance(messages, list) or len(messages) > self.limits.max_messages:
            raise StoreReadError("A saved chat exceeds the supported message count; the existing file was kept.")
        characters = 0
        for message in messages:
            if not isinstance(message, dict):
                raise StoreReadError("A saved chat contains an invalid message; the existing file was kept.")
            for key in ("content", "reasoning", "failure"):
                value = message.get(key, "")
                if not isinstance(value, str):
                    raise StoreReadError("A saved chat contains invalid message text; the existing file was kept.")
                characters += len(value)
                if characters > self.limits.max_characters:
                    raise StoreReadError("A saved chat exceeds the supported character budget; the existing file was kept.")

    def _bounded_write(self, path: Path, value: Any) -> None:
        write_store_document(
            path, value,
            maximum_bytes=self.limits.history_max_bytes if path == self.history_path else self.limits.journal_max_bytes,
        )

    def entry_characters(self, entry: dict[str, Any]) -> int:
        messages = entry.get("messages") if isinstance(entry.get("messages"), list) else []
        return sum(
            len(str(message.get("content") or "")) + len(str(message.get("reasoning") or ""))
            for message in messages if isinstance(message, dict)
        )


    def load_journal_unlocked(self) -> list[dict[str, Any]]:
        stored = self._read_document(self.journal_path)
        if stored == {} and not self.journal_path.exists():
            return []
        if not isinstance(stored, dict) or type(stored.get("version")) is not int or stored["version"] != self.limits.journal_version:
            raise StoreReadError("Active Chat recovery has an unsupported storage format; the existing file was kept.")
        entries = stored.get("entries")
        if not isinstance(entries, list):
            raise StoreReadError("Active Chat recovery has an invalid collection; the existing file was kept.")
        return [copy.deepcopy(item) for item in entries if isinstance(item, dict)]


    def write_journal_unlocked(self, entries: list[dict[str, Any]]) -> None:
        now = self._clock()
        cutoff = now - timedelta(days=self.limits.journal_max_age_days)
        candidates: list[dict[str, Any]] = []
        for entry in entries:
            try:
                updated_at = datetime.fromisoformat(str(entry.get("updatedAt") or ""))
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if updated_at < cutoff:
                continue
            candidates.append(copy.deepcopy(entry))
        candidates.sort(key=lambda item: str(item.get("updatedAt") or ""), reverse=True)
        kept: list[dict[str, Any]] = []
        total_characters = 0
        for entry in candidates:
            if len(kept) >= self.limits.journal_max_entries:
                break
            characters = self.entry_characters(entry)
            if total_characters + characters > self.limits.journal_max_characters:
                continue
            kept.append(entry)
            total_characters += characters
        self._write_document(self.journal_path, {
            "version": self.limits.journal_version,
            "entries": kept,
        })


    def load_history_unlocked(self) -> list[dict[str, Any]]:
        stored = self._read_document(self.history_path)
        if stored == {} and not self.history_path.exists():
            return []
        version = stored.get("version") if isinstance(stored, dict) else None
        if version is not None and (type(version) is not int or not 1 <= version <= self.limits.store_version):
            raise StoreReadError("Chat History has an unsupported storage format; the existing file was kept.")
        records = stored.get("threads") if isinstance(stored, dict) else None
        if not isinstance(records, list):
            raise StoreReadError("Chat History has an invalid collection; the existing file was kept.")
        return [copy.deepcopy(item) for item in records if isinstance(item, dict)]


    def write_history_unlocked(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ordered = sorted(
            records,
            key=lambda item: (
                item.get("pinned") is True,
                str(item.get("updatedAt") or item.get("createdAt") or ""),
            ),
            reverse=True,
        )
        retained = ordered[:self.limits.max_threads]
        self._write_document(self.history_path, {
            "version": self.limits.store_version,
            "threads": retained,
        })
        return retained


    def identifier(self, value: Any) -> str | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            parsed = uuid.UUID(value)
        except (ValueError, AttributeError):
            return None
        return str(parsed) if str(parsed) == value.lower() else None


    def validate_messages(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list) or not value:
            raise ValueError("A saved chat needs at least one completed message.")
        if len(value) > self.limits.max_messages:
            raise ValueError(f"A saved chat may contain at most {self.limits.max_messages:,} messages.")
        total = 0
        messages: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
                raise ValueError("Saved chats may contain only user and assistant messages.")
            role = str(item["role"])
            content = item.get("content")
            reasoning = item.get("reasoning", "")
            interrupted = item.get("interrupted") is True
            truncated = item.get("truncated") is True
            failure = item.get("failure", "")
            if interrupted and role != "assistant":
                raise ValueError("Only an assistant response may be marked as interrupted.")
            if not isinstance(failure, str) or "\x00" in failure or len(failure) > 800:
                raise ValueError("A saved terminal failure must be bounded text.")
            failure = failure.strip()
            if failure and (role != "assistant" or not interrupted):
                raise ValueError("A terminal failure may be stored only on an interrupted assistant response.")
            if (
                not isinstance(content, str) or "\x00" in content
                or (
                    not content.strip() and not interrupted
                    and not (
                        truncated and role == "assistant"
                        and isinstance(reasoning, str) and reasoning.strip()
                    )
                )
            ):
                raise ValueError("Every saved chat message must contain text.")
            if not isinstance(reasoning, str) or "\x00" in reasoning:
                raise ValueError("Displayed model reasoning must be text.")
            total += len(content) + len(reasoning) + len(failure)
            if total > self.limits.max_characters:
                raise ValueError(
                    f"One saved chat may contain at most {self.limits.max_characters:,} characters."
                )
            message: dict[str, Any] = {
                "role": role,
                "content": content,
            }
            if reasoning:
                message["reasoning"] = reasoning
            if item.get("stopped") is True or interrupted:
                message["stopped"] = True
            if item.get("exclude") is True or interrupted:
                message["exclude"] = True
            if interrupted:
                message["interrupted"] = True
            if failure:
                message["failure"] = failure
            if truncated:
                if role != "assistant":
                    raise ValueError("Only an assistant response may be marked as response-limited.")
                message["truncated"] = True
            if item.get("continuation") is True:
                if item.get("role") != "assistant":
                    raise ValueError("Only assistant messages may be marked as continuations.")
                message["continuation"] = True
            raw_created_at = item.get("createdAt")
            if raw_created_at not in (None, ""):
                if (
                    not isinstance(raw_created_at, str) or "\x00" in raw_created_at
                    or len(raw_created_at) > 48
                ):
                    raise ValueError("A saved message timestamp must be bounded ISO-8601 text.")
                try:
                    created_at = datetime.fromisoformat(raw_created_at)
                except (ValueError, OverflowError) as error:
                    raise ValueError("A saved message timestamp must be valid ISO-8601 text.") from error
                if created_at.tzinfo is None or not 2000 <= created_at.year <= 2100:
                    raise ValueError("A saved message timestamp must include a timezone and a sensible year.")
                message["createdAt"] = created_at.astimezone(timezone.utc).isoformat()
            raw_usage = item.get("usage")
            if raw_usage is not None:
                if item.get("role") != "assistant" or not isinstance(raw_usage, dict):
                    raise ValueError("Runtime token usage may be stored only on assistant messages.")

                def usage_integer(key: str, *, required: bool, maximum: int = 2_000_000_000) -> int | None:
                    raw_value = raw_usage.get(key)
                    if raw_value is None and not required:
                        return None
                    if (
                        isinstance(raw_value, bool) or not isinstance(raw_value, int)
                        or raw_value < 0 or raw_value > maximum
                    ):
                        raise ValueError("Runtime token usage must contain bounded whole-number counts.")
                    return raw_value

                prompt_tokens = usage_integer("promptTokens", required=True)
                completion_tokens = usage_integer("completionTokens", required=True)
                cached_tokens = usage_integer("cachedPromptTokens", required=False)
                if prompt_tokens is None or prompt_tokens <= 0:
                    raise ValueError("Runtime prompt-token usage must be greater than zero.")
                if cached_tokens is not None and cached_tokens > prompt_tokens:
                    raise ValueError("Cached prompt tokens cannot exceed total prompt tokens.")
                message["usage"] = {
                    "source": "runtime",
                    "promptTokens": prompt_tokens,
                    "completionTokens": completion_tokens,
                    **({"cachedPromptTokens": cached_tokens} if cached_tokens is not None else {}),
                }
            messages.append(message)
        return messages


    def metadata(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}

        def short_text(key: str, fallback: str, maximum: int = 160) -> str:
            value = raw.get(key, fallback)
            if not isinstance(value, str) or "\x00" in value:
                return fallback
            return value.strip()[:maximum] or fallback

        def bounded_int(key: str) -> int | None:
            value = raw.get(key)
            return value if isinstance(value, int) and not isinstance(value, bool) and 0 < value <= 2_000_000 else None

        metadata: dict[str, Any] = {
            "model": short_text("model", "Local model"),
            "backend": short_text("backend", "local", 40),
            "context": bounded_int("context"),
            "output": bounded_int("output"),
            "reasoning": short_text("reasoning", "auto", 24),
        }
        parent_value = raw.get("branchParentId")
        branch_keys_present = any(
            key in raw for key in (
                "branchParentId", "branchParentTitle", "branchPoint", "branchKind",
            )
        )
        if branch_keys_present:
            parent_id = self.identifier(parent_value)
            if not parent_id:
                raise ValueError("A chat branch needs a valid parent conversation.")
            raw_title = raw.get("branchParentTitle", "Local chat")
            if not isinstance(raw_title, str) or "\x00" in raw_title:
                raise ValueError("A chat branch parent title must be text.")
            parent_title = re.sub(r"\s+", " ", raw_title).strip()[:self.limits.title_max]
            raw_point = raw.get("branchPoint")
            if (
                isinstance(raw_point, bool) or not isinstance(raw_point, int)
                or not 1 <= raw_point <= self.limits.max_messages
            ):
                raise ValueError(
                    f"A chat branch point must be between 1 and {self.limits.max_messages:,}."
                )
            branch_kind = str(raw.get("branchKind") or "branch")
            if branch_kind not in self.limits.branch_kinds:
                raise ValueError("Unknown chat branch type.")
            metadata.update({
                "branchParentId": parent_id,
                "branchParentTitle": parent_title or "Local chat",
                "branchPoint": raw_point,
                "branchKind": branch_kind,
            })
        return metadata


    def validate_resume(self, 
        value: Any, *, strict: bool = False,
    ) -> dict[str, Any] | None:
        """Return a settings-only Chat route snapshot without ever retaining its prompt text."""

        def invalid(message: str) -> None:
            if strict:
                raise ValueError(message)

        if not isinstance(value, dict) or value.get("version") != self.limits.resume_version:
            invalid("The Chat resume route snapshot is invalid.")
            return None
        raw_request = value.get("request")
        if not isinstance(raw_request, dict):
            invalid("The Chat resume route snapshot has no launch contract.")
            return None
        request = self._route_request_whitelist(raw_request)
        if request.get("client") != "chat":
            invalid("The saved resume route is not a built-in Chat surface.")
            return None
        required_text = ("backend", "modelId", "project", "reasoning")
        if any(not isinstance(request.get(key), str) or not request.get(key) for key in required_text):
            invalid("The Chat resume route snapshot is incomplete.")
            return None
        if any(
            isinstance(request.get(key), bool) or not isinstance(request.get(key), int)
            or int(request[key]) <= 0
            for key in ("context", "output")
        ):
            invalid("The Chat resume route limits are invalid.")
            return None
        if not isinstance(request.get("options"), dict):
            invalid("The Chat resume engine controls are invalid.")
            return None
        chat = request.get("chat")
        if not isinstance(chat, dict) or chat.get("sampling") not in {"model", "custom"}:
            invalid("The Chat resume sampling contract is invalid.")
            return None
        if chat.get("systemPrompt") not in (None, ""):
            invalid("A Chat resume route must never contain stored system-prompt text.")
            return None
        request["agentHost"] = "launcher"
        request["mode"] = "custom"
        request["chat"] = {**chat, "systemPrompt": ""}
        captured_at = value.get("capturedAt")
        clean_captured_at = captured_at if isinstance(captured_at, str) and len(captured_at) <= 48 else ""
        return {
            "version": self.limits.resume_version,
            "capturedAt": clean_captured_at,
            "requiresSystemPrompt": value.get("requiresSystemPrompt") is True,
            "request": request,
        }


    def resume_summary(self, record: dict[str, Any]) -> dict[str, Any]:
        contract = self.validate_resume(record.get("resumeContract"))
        request = contract.get("request", {}) if contract else {}
        return {
            "resumeAvailable": contract is not None,
            "resumeNeedsSystemPrompt": bool(contract and contract.get("requiresSystemPrompt")),
            "resumeBackend": str(request.get("backend") or "") if contract else "",
            "resumeModelId": str(request.get("modelId") or "") if contract else "",
        }


    def public_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """Expose transcript content but keep the private route snapshot behind its planner."""
        public = {
            key: copy.deepcopy(value)
            for key, value in record.items() if key != "resumeContract"
        }
        public.update(self.resume_summary(record))
        return public


    def inventory(self) -> dict[str, Any]:
        with self.history_lock:
            records = self.load_history_unlocked()
        return self.inventory_from_records(records)

    def inventory_from_records(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        items = []
        for record in records:
            messages = record.get("messages") if isinstance(record.get("messages"), list) else []
            first_user = next(
                (item.get("content") for item in messages if isinstance(item, dict) and item.get("role") == "user"),
                "",
            )
            items.append({
                key: copy.deepcopy(record.get(key)) for key in (
                    "id", "title", "createdAt", "updatedAt", "model", "backend",
                    "context", "output", "reasoning", "pinned", "branchParentId",
                    "branchParentTitle", "branchPoint", "branchKind", "originModel",
                    "originBackend", "originContext", "originOutput", "originReasoning",
                )
            } | {
                "messageCount": len(messages),
                "preview": re.sub(r"\s+", " ", str(first_user or "")).strip()[:180],
                "hasInterruptedTurn": any(
                    isinstance(item, dict) and item.get("interrupted") is True
                    for item in messages
                ),
                **self.resume_summary(record),
            })
        return {
            "version": self.limits.store_version,
            "threads": items,
            "limit": self.limits.max_threads,
            "privacy": {
                "localOnly": True,
                "storesMessages": True,
                "storesDisplayedReasoning": True,
                "storesRuntimeUsage": True,
                "storesMessageTimestamps": True,
                "storesBranchLineage": True,
                "storesRouteMetadata": True,
                "storesInterruptedRecovery": True,
                "storesResponseLimitState": True,
                "storesResumeRouteSettings": True,
                "storesProjectPathForResume": True,
                "storesSystemPrompt": False,
                "storesProjectData": False,
            },
        }


    def save(self, payload: dict[str, Any], *, resume_contract: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.history_lock:
            return self.save_with_records_unlocked(payload, resume_contract=resume_contract)

    def save_with_records_unlocked(self,
        payload: dict[str, Any], *, resume_contract: dict[str, Any] | None = None,
        records: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        messages = self.validate_messages(payload.get("messages"))
        requested_id = payload.get("id")
        history_id = self.identifier(requested_id) if requested_id not in (None, "") else None
        if requested_id not in (None, "") and not history_id:
            raise ValueError("That saved chat identifier is invalid.")
        raw_metadata_payload = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        metadata = self.metadata(payload)
        first_user = next((item["content"] for item in messages if item["role"] == "user"), None)
        if first_user is None:
            raise ValueError("A saved chat needs at least one user message.")
        generated_title = re.sub(r"\s+", " ", first_user).strip()[:self.limits.title_max]
        requested_title = payload.get("title")
        clean_requested_title = (
            re.sub(r"\s+", " ", requested_title).strip()[:self.limits.title_max]
            if isinstance(requested_title, str) and "\x00" not in requested_title else ""
        )
        now = self._clock().isoformat()
        validated_resume = (
            self.validate_resume(resume_contract, strict=True)
            if resume_contract is not None else None
        )
        records = self.load_history_unlocked() if records is None else records
        existing = next((item for item in records if item.get("id") == history_id), None)
        if existing:
            existing_route = self.metadata({"metadata": existing})
            for key in ("model", "backend", "context", "output", "reasoning"):
                if key not in raw_metadata_payload:
                    metadata[key] = existing_route.get(key)
            for key in (
                "branchParentId", "branchParentTitle", "branchPoint", "branchKind",
            ):
                if key not in metadata and key in existing:
                    metadata[key] = copy.deepcopy(existing[key])
        origin_source = {
            key: (
                existing.get(f"origin{key[0].upper()}{key[1:]}", existing.get(key, metadata.get(key)))
                if existing else metadata.get(key)
            )
            for key in ("model", "backend", "context", "output", "reasoning")
        }
        origin = self.metadata({"metadata": origin_source})
        origin_metadata = {
            f"origin{key[0].upper()}{key[1:]}": origin.get(key)
            for key in ("model", "backend", "context", "output", "reasoning")
        }
        title = clean_requested_title or (
            str(existing.get("title") or "").strip()[:self.limits.title_max]
            if existing else ""
        ) or generated_title or "Local chat"
        record = {
            "id": history_id or self._new_id(),
            "title": title,
            "createdAt": str(existing.get("createdAt")) if existing else now,
            "updatedAt": now,
            "pinned": bool(existing and existing.get("pinned") is True),
            **origin_metadata,
            **metadata,
            "messages": messages,
        }
        preserved_resume = (
            self.validate_resume(existing.get("resumeContract"))
            if existing else None
        )
        effective_resume = validated_resume or preserved_resume
        if effective_resume is not None:
            record["resumeContract"] = effective_resume
        records = [item for item in records if item.get("id") != record["id"]]
        records.insert(0, record)
        retained = self.write_history_unlocked(records)
        return {"thread": self.public_record(record), **self.inventory_from_records(retained)}


    def checkpoint(self, 
        payload: dict[str, Any], *, resume_contract: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist one bounded visible in-flight turn without storing request-only context."""
        tab_id = self.identifier(payload.get("tabId"))
        turn_id = self.identifier(payload.get("turnId"))
        history_id = self.identifier(payload.get("historyId"))
        if not tab_id or not turn_id or not history_id:
            raise ValueError("Active-turn recovery needs valid tab, turn, and conversation identifiers.")
        messages = self.validate_messages(payload.get("messages"))
        interrupted = [message for message in messages if message.get("interrupted") is True]
        if not interrupted or messages[-1].get("interrupted") is not True:
            raise ValueError("An active-turn checkpoint must end with an interrupted assistant response.")
        if not any(message["role"] == "user" for message in messages):
            raise ValueError("An active-turn checkpoint needs at least one user message.")
        metadata = self.metadata(payload)
        validated_resume = (
            self.validate_resume(resume_contract, strict=True)
            if resume_contract is not None else None
        )
        now = self._clock().isoformat()
        with self.journal_lock:
            entries = self.load_journal_unlocked()
            existing = next(
                (entry for entry in entries if entry.get("tabId") == tab_id),
                None,
            )
            entry = {
                "tabId": tab_id,
                "turnId": turn_id,
                "historyId": history_id,
                "createdAt": (
                    str(existing.get("createdAt"))
                    if existing and existing.get("turnId") == turn_id else now
                ),
                "updatedAt": now,
                "metadata": metadata,
                "messages": messages,
            }
            if validated_resume is not None:
                entry["resumeContract"] = validated_resume
            entries = [item for item in entries if item.get("tabId") != tab_id]
            entries.insert(0, entry)
            self.write_journal_unlocked(entries)
        return {
            "checkpoint": {
                "tabId": tab_id,
                "turnId": turn_id,
                "historyId": history_id,
                "updatedAt": now,
                "characters": self.entry_characters(entry),
            },
            "privacy": {
                "localOnly": True,
                "storesVisibleTranscript": True,
                "storesSystemPrompt": False,
                "storesContextFiles": False,
                "storesWorkspaceIndex": False,
                "storesRuntimeSecrets": False,
            },
        }


    def clear_checkpoint(self, payload: dict[str, Any]) -> dict[str, Any]:
        tab_id = self.identifier(payload.get("tabId"))
        turn_id = self.identifier(payload.get("turnId"))
        if not tab_id or not turn_id:
            raise ValueError("Choose a valid active-turn checkpoint to clear.")
        with self.journal_lock:
            entries = self.load_journal_unlocked()
            kept = [
                entry for entry in entries
                if not (entry.get("tabId") == tab_id and entry.get("turnId") == turn_id)
            ]
            removed = len(kept) != len(entries)
            self.write_journal_unlocked(kept)
        return {"cleared": removed}


    def recover_checkpoint(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Promote a checkpoint once, without replacing a newer completed save.

        Recovery consistently takes the journal lock before the history lock.
        Keep the comparison and history write in the same transaction; ordinary
        history mutations never take the journal lock while holding history.
        """
        tab_id = self.identifier(payload.get("tabId"))
        if not tab_id:
            raise ValueError("Active-turn recovery needs a valid browser-tab identifier.")
        with self.journal_lock:
            entries = self.load_journal_unlocked()
            entry = next((item for item in entries if item.get("tabId") == tab_id), None)
            if entry is None:
                return {"recovered": False, "discarded": False, **self.inventory()}
            history_id = self.identifier(entry.get("historyId"))
            turn_id = self.identifier(entry.get("turnId"))
            if not history_id or not turn_id:
                raise ValueError("The saved active-turn checkpoint is invalid.")
            with self.history_lock:
                records = self.load_history_unlocked()
                existing = next((item for item in records if item.get("id") == history_id), None)
                discarded = bool(existing and str(existing.get("updatedAt") or "") >= str(entry.get("updatedAt") or ""))
                saved = None
                if not discarded:
                    saved = self.save_with_records_unlocked({
                        "id": history_id,
                        "metadata": copy.deepcopy(entry.get("metadata") or {}),
                        "messages": copy.deepcopy(entry.get("messages") or []),
                    }, resume_contract=self.validate_resume(entry.get("resumeContract")), records=records)
                    inventory = {key: value for key, value in saved.items() if key != "thread"}
                else:
                    inventory = self.inventory_from_records(records)
            kept = [item for item in entries if not (item.get("tabId") == tab_id and item.get("turnId") == turn_id)]
            self.write_journal_unlocked(kept)
            return {
                "recovered": saved is not None, "discarded": discarded,
                "thread": copy.deepcopy(saved["thread"]) if saved else None,
                **inventory,
            }


    def update(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Update bounded user-managed metadata without rewriting chat content."""
        history_id = self.identifier(payload.get("id"))
        if not history_id:
            raise ValueError("Choose a valid saved chat to update.")
        has_title = "title" in payload
        has_pinned = "pinned" in payload
        if not has_title and not has_pinned:
            raise ValueError("Choose a title or pinned state to update.")
        clean_title: str | None = None
        if has_title:
            raw_title = payload.get("title")
            if not isinstance(raw_title, str) or "\x00" in raw_title:
                raise ValueError("Chat title must be text.")
            clean_title = re.sub(r"\s+", " ", raw_title).strip()
            if not clean_title:
                raise ValueError("Chat title cannot be empty.")
            if len(clean_title) > self.limits.title_max:
                raise ValueError(f"Chat title may contain at most {self.limits.title_max} characters.")
        pinned: bool | None = None
        if has_pinned:
            if not isinstance(payload.get("pinned"), bool):
                raise ValueError("Pinned state must be true or false.")
            pinned = bool(payload["pinned"])
        with self.history_lock:
            records = self.load_history_unlocked()
            existing = next((item for item in records if item.get("id") == history_id), None)
            if existing is None:
                raise ValueError("That saved chat no longer exists.")
            updated = copy.deepcopy(existing)
            if clean_title is not None:
                updated["title"] = clean_title
            if pinned is not None:
                updated["pinned"] = pinned
            updated["updatedAt"] = self._clock().isoformat()
            records = [updated if item.get("id") == history_id else item for item in records]
            retained = self.write_history_unlocked(records)
        return {"thread": self.public_record(updated), **self.inventory_from_records(retained)}


    def get(self, payload: dict[str, Any]) -> dict[str, Any]:
        history_id = self.identifier(payload.get("id"))
        if not history_id:
            raise ValueError("Choose a valid saved chat.")
        with self.history_lock:
            record = next(
                (item for item in self.load_history_unlocked() if item.get("id") == history_id),
                None,
            )
        if record is None:
            raise ValueError("That saved chat no longer exists.")
        return {"thread": self.public_record(record)}


    def delete(self, payload: dict[str, Any]) -> dict[str, Any]:
        history_id = self.identifier(payload.get("id"))
        if not history_id:
            raise ValueError("Choose a valid saved chat to delete.")
        with self.history_lock:
            records = self.load_history_unlocked()
            kept = [item for item in records if item.get("id") != history_id]
            if len(kept) == len(records):
                raise ValueError("That saved chat no longer exists.")
            retained = self.write_history_unlocked(kept)
        return self.inventory_from_records(retained)
