"""Knowledge bases — collections of documents injected into the call prompt."""
from __future__ import annotations

import mimetypes
import os
import time
import warnings
from typing import Any, BinaryIO, List, Optional, Union

from ..models import DeletedResource, KnowledgeBase, KnowledgeDocument, Page
from ._base import BaseResource, unwrap

#: Uploading 50MB and waiting for the server to store it takes far longer than
#: a normal API call.
UPLOAD_TIMEOUT = 300.0


class DocumentsResource(BaseResource):
    """Documents inside one knowledge base."""

    def list(self, kb_id: str) -> List[KnowledgeDocument]:
        raw = self._t.request("GET", f"/knowledge-bases/{kb_id}/documents")
        rows = raw.get("data", raw) if isinstance(raw, dict) else raw
        return [KnowledgeDocument.model_validate(d) for d in rows]

    def create(self, kb_id: str, *, name: str, content: str) -> KnowledgeDocument:
        """Create a Markdown document (ready immediately)."""
        return KnowledgeDocument.model_validate(
            unwrap(self._t.request(
                "POST", f"/knowledge-bases/{kb_id}/documents",
                json={"name": name, "content": content},
            ))
        )

    def upload(
        self,
        kb_id: str,
        file: Union[str, os.PathLike, BinaryIO],
        *,
        name: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> KnowledgeDocument:
        """Upload a file into the knowledge base (async extraction).

        Returns with ``status="processing"``. Poll :meth:`KnowledgeBasesResource.wait`
        on the parent knowledge base (or :meth:`get` on this document) until ready.
        """
        upload_name, payload = _read_upload(file, filename)
        mime = mimetypes.guess_type(upload_name)[0] or "application/octet-stream"
        raw = self._t.request(
            "POST",
            f"/knowledge-bases/{kb_id}/documents",
            files={"file": (upload_name, payload, mime)},
            data={"name": name} if name else None,
            timeout=UPLOAD_TIMEOUT,
        )
        return KnowledgeDocument.model_validate(unwrap(raw))

    def get(self, kb_id: str, doc_id: str) -> KnowledgeDocument:
        return KnowledgeDocument.model_validate(
            unwrap(self._t.request("GET", f"/knowledge-bases/{kb_id}/documents/{doc_id}"))
        )

    def update(self, kb_id: str, doc_id: str, **fields: Any) -> KnowledgeDocument:
        """Patch ``name``, ``enabled``, and/or ``content``."""
        return KnowledgeDocument.model_validate(
            unwrap(self._t.request(
                "PATCH", f"/knowledge-bases/{kb_id}/documents/{doc_id}", json=fields,
            ))
        )

    def delete(self, kb_id: str, doc_id: str) -> DeletedResource:
        return DeletedResource.model_validate(
            unwrap(self._t.request("DELETE", f"/knowledge-bases/{kb_id}/documents/{doc_id}"))
        )


class KnowledgeBasesResource(BaseResource):
    def __init__(self, transport: Any) -> None:
        super().__init__(transport)
        self.documents = DocumentsResource(transport)

    def create(
        self,
        *,
        name: str,
        description: Optional[str] = None,
        content: Optional[str] = None,
    ) -> KnowledgeBase:
        """Create a knowledge base.

        Pass ``content`` to also add a ready Markdown document in one step.
        To upload a PDF/DOCX/… instead, create an empty base then
        :meth:`DocumentsResource.upload`, or use :meth:`create_with_upload`.
        """
        body: dict = {"name": name}
        if description is not None:
            body["description"] = description
        if content is not None:
            body["content"] = content
        return KnowledgeBase.model_validate(
            unwrap(self._t.request("POST", "/knowledge-bases", json=body))
        )

    def create_with_upload(
        self,
        file: Union[str, os.PathLike, BinaryIO],
        *,
        name: Optional[str] = None,
        filename: Optional[str] = None,
        description: Optional[str] = None,
        wait: bool = True,
        timeout: float = 900.0,
    ) -> KnowledgeBase:
        """Create a knowledge base and upload a document into it.

        By default waits until extraction finishes (``processing_count == 0``).
        """
        upload_name = filename
        if not upload_name:
            if isinstance(file, (str, os.PathLike)):
                upload_name = os.path.basename(os.fspath(file))
            else:
                upload_name = os.path.basename(getattr(file, "name", "") or "") or "document"
        kb_name = name or os.path.splitext(upload_name)[0] or "Knowledge base"
        kb = self.create(name=kb_name, description=description)
        self.documents.upload(kb.id, file, name=name, filename=filename or upload_name)
        if wait:
            return self.wait(kb.id, timeout=timeout)
        return self.get(kb.id)

    def upload(
        self,
        file: Union[str, os.PathLike, BinaryIO],
        *,
        name: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> KnowledgeBase:
        """Deprecated — use :meth:`create_with_upload` or ``documents.upload``."""
        warnings.warn(
            "knowledge_bases.upload() is deprecated; use create_with_upload() "
            "or knowledge_bases.documents.upload(kb_id, file)",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.create_with_upload(file, name=name, filename=filename, wait=False)

    def wait(self, kb_id: str, *, timeout: float = 900.0, poll_interval: float = 3.0) -> KnowledgeBase:
        """Block until no document is still ``processing``.

        Returns even when some documents ``failed`` — check ``failed_count``.
        """
        deadline = time.monotonic() + timeout
        while True:
            kb = self.get(kb_id)
            if kb.processing_count == 0:
                return kb
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Knowledge base {kb_id} still processing after {timeout}s")
            time.sleep(poll_interval)

    def list(self, *, page: int = 1, limit: int = 50) -> Page[KnowledgeBase]:
        return Page[KnowledgeBase].model_validate(
            self._t.request("GET", "/knowledge-bases", params={"page": page, "limit": limit})
        )

    def get(self, kb_id: str) -> KnowledgeBase:
        return KnowledgeBase.model_validate(unwrap(self._t.request("GET", f"/knowledge-bases/{kb_id}")))

    def update(self, kb_id: str, **fields: Any) -> KnowledgeBase:
        """Patch ``name`` and/or ``description``."""
        return KnowledgeBase.model_validate(
            unwrap(self._t.request("PATCH", f"/knowledge-bases/{kb_id}", json=fields))
        )

    def delete(self, kb_id: str) -> DeletedResource:
        return DeletedResource.model_validate(unwrap(self._t.request("DELETE", f"/knowledge-bases/{kb_id}")))


def _read_upload(
    file: Union[str, os.PathLike, BinaryIO],
    filename: Optional[str],
) -> tuple[str, bytes]:
    if isinstance(file, (str, os.PathLike)):
        path = os.fspath(file)
        upload_name = filename or os.path.basename(path)
        with open(path, "rb") as fh:
            payload = fh.read()
    else:
        # create_with_upload may pass the same file handle twice — re-read from start
        if hasattr(file, "seek"):
            try:
                file.seek(0)
            except Exception:
                pass
        payload = file.read()
        upload_name = filename or os.path.basename(getattr(file, "name", "") or "") or "document"
    return upload_name, payload
