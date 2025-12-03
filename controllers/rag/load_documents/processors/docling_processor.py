import asyncio
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Any
import re

from .base_processor import BaseDocumentProcessor, DocumentContent, PageContent


class DoclingProcessor(BaseDocumentProcessor):
    def __init__(self):
        super().__init__()
        self.supported_extensions = [
            ".pdf",
            ".docx",
            ".pptx",
            ".xlsx",
            ".html",
            ".htm",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".bmp",
            ".tiff",
        ]

    def can_process(self, file_extension: str) -> bool:
        return file_extension.lower() in self.supported_extensions

    async def extract_content(self, file_path: str, file_data: bytes) -> DocumentContent:
        ext = Path(file_path).suffix.lower()
        if not self.can_process(ext):
            raise ValueError(f"Unsupported file type: {ext}")

        converter = self._build_converter()

        def _convert_with_stream():
            try:
                from docling.datamodel.document import DocumentStream
                stream = DocumentStream(name=Path(file_path).name, stream=BytesIO(file_data))
                return converter.convert(stream)
            except Exception:
                return None

        def _convert_with_tempfile():
            import tempfile, os
            tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
            try:
                tmp.write(file_data)
                tmp.flush()
                tmp.close()
                return converter.convert(tmp.name)
            finally:
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass

        result = await asyncio.to_thread(_convert_with_stream)
        if result is None:
            result = await asyncio.to_thread(_convert_with_tempfile)

        doc = result.document

        try:
            markdown = doc.export_to_markdown()
        except Exception:
            try:
                markdown = result.render_as_markdown()
            except Exception:
                markdown = ""

        text_content = self.clean_text(markdown)

        try:
            meta_dict = doc.export_to_dict()
        except Exception:
            try:
                meta_dict = result.render_as_json()
            except Exception:
                meta_dict = {}

        pages: List[PageContent] = []
        page_count = len(getattr(doc, "pages", []) or getattr(result, "pages", []) or [])
        doctags = ""
        try:
            doctags = doc.export_to_doctags()
        except Exception:
            try:
                doctags = result.render_as_doctags()
            except Exception:
                doctags = ""

        page_texts: List[tuple[int, str]] = []
        if ext == ".pdf":
            tokens = doctags or ""
            if tokens:
                patterns = [
                    r"<page_(\d+)>",
                    r"<page\s+(\d+)>",
                    r"<page[^>]*?(?:id|number)\s*=\s*\"?(\d+)\"?>",
                ]
                matches = []
                for pat in patterns:
                    ms = list(re.finditer(pat, tokens, flags=re.IGNORECASE))
                    if ms:
                        matches = ms
                        break
                if matches:
                    for i, m in enumerate(matches):
                        start = m.end()
                        end = matches[i + 1].start() if i + 1 < len(matches) else len(tokens)
                        segment = tokens[start:end]
                        segment = re.sub(r"<page[^>]*>", "", segment, flags=re.IGNORECASE)
                        plain = re.sub(r"<[^>]+>", " ", segment)
                        plain = self.clean_text(plain)
                        try:
                            page_num = int(m.group(1))
                        except Exception:
                            page_num = i + 1
                        page_texts.append((page_num, plain))
            if not page_texts:
                try:
                    import fitz
                    pdf = fitz.open(stream=file_data, filetype="pdf")
                    for i in range(pdf.page_count):
                        pg = pdf.load_page(i)
                        pg_text = pg.get_text("text") or ""
                        pg_text = self.clean_text(pg_text)
                        page_texts.append((i + 1, pg_text))
                    page_count = pdf.page_count
                except Exception:
                    pass
            if not page_texts:
                try:
                    import pdfplumber
                    with pdfplumber.open(BytesIO(file_data)) as pdf:
                        for i, page in enumerate(pdf.pages):
                            pg_text = page.extract_text() or ""
                            pg_text = self.clean_text(pg_text)
                            page_texts.append((i + 1, pg_text))
                        page_count = len(pdf.pages)
                except Exception:
                    pass
            if not page_texts:
                try:
                    from PyPDF2 import PdfReader
                    reader = PdfReader(BytesIO(file_data))
                    for i, page in enumerate(reader.pages):
                        pg_text = page.extract_text() or ""
                        pg_text = self.clean_text(pg_text)
                        page_texts.append((i + 1, pg_text))
                    page_count = len(reader.pages)
                except Exception:
                    pass

        if page_texts:
            for page_num, page_text in page_texts:
                pages.append(
                    PageContent(
                        page_number=page_num,
                        text_content=page_text,
                        full_content=page_text,
                        images=[],
                        page_metadata={
                            "page_number": page_num,
                            "text_length": len(page_text),
                            "image_count": 0,
                            "parser": "docling",
                        },
                    )
                )
            page_count = len(page_texts)
            total_text = markdown or "\n\n".join([t for _, t in page_texts]).strip()
        else:
            if page_count <= 0:
                page_count = 1
            pages.append(
                PageContent(
                    page_number=1,
                    text_content=text_content,
                    full_content=markdown,
                    images=[],
                    page_metadata={
                        "page_number": 1,
                        "text_length": len(text_content),
                        "image_count": 0,
                        "parser": "docling",
                    },
                )
            )
            total_text = markdown or text_content

        metadata: Dict[str, Any] = {
            "file_name": Path(file_path).name,
            "file_extension": ext,
            "page_count": page_count,
            "parser": "docling",
        }
        if isinstance(meta_dict, dict):
            metadata.update({"docling": meta_dict})
        elif isinstance(meta_dict, str):
            metadata.update({"docling_json": meta_dict})

        return DocumentContent(
            pages=pages,
            total_text_content=total_text,
            total_images=[],
            metadata=metadata,
        )

    def _build_converter(self):
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions

        options = PdfPipelineOptions()
        options.do_ocr = True
        options.do_table_structure = True
        options.table_structure_options.do_cell_matching = True
        try:
            langs = ["vi", "vie", "en"]
            try:
                options.ocr_options.lang = langs
            except Exception:
                try:
                    options.ocr_options.languages = langs
                except Exception:
                    pass
            try:
                options.ocr_options.use_gpu = False
            except Exception:
                pass
            for attr in ("keep_accents", "preserve_accents", "normalize_unicode"):
                try:
                    setattr(options, attr, True)
                except Exception:
                    try:
                        setattr(options.ocr_options, attr, True)
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
            options.accelerator_options = AcceleratorOptions(num_threads=4, device=AcceleratorDevice.AUTO)
        except Exception:
            pass

        return DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
