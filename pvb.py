import asyncio
import json
from pathlib import Path


class DoclingPDFProcessor:
    def __init__(self, languages=None, use_gpu=False, threads=4):
        self.languages = languages or ["vi", "en"]
        self.use_gpu = use_gpu
        self.threads = threads

    def _build_converter(self):
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        try:
            from docling.datamodel.accelerator_options import (
                AcceleratorDevice,
                AcceleratorOptions,
            )
        except Exception:
            AcceleratorDevice = None
            AcceleratorOptions = None

        options = PdfPipelineOptions()
        options.do_ocr = True
        options.do_table_structure = True
        options.table_structure_options.do_cell_matching = True
        try:
            options.ocr_options.lang = self.languages
            options.ocr_options.use_gpu = self.use_gpu
        except Exception:
            pass
        try:
            if AcceleratorOptions and AcceleratorDevice:
                options.accelerator_options = AcceleratorOptions(
                    num_threads=self.threads, device=AcceleratorDevice.AUTO
                )
        except Exception:
            pass

        converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
        )
        return converter

    def _convert_sync(self, pdf_path: str):
        converter = self._build_converter()
        try:
            return converter.convert(pdf_path)
        except Exception:
            return converter.convert_single(pdf_path)

    async def convert(self, pdf_path: str):
        result = await asyncio.to_thread(self._convert_sync, pdf_path)
        markdown = ""
        doctags = ""
        data_json_str = "{}"

        try:
            markdown = result.document.export_to_markdown()
            doctags = result.document.export_to_document_tokens()
            data_dict = result.document.export_to_dict()
            data_json_str = json.dumps(data_dict, ensure_ascii=False)
        except Exception:
            try:
                markdown = result.render_as_markdown()
            except Exception:
                markdown = ""
            try:
                doctags = result.render_as_doctags()
            except Exception:
                doctags = ""
            try:
                data_json_str = result.render_as_json()
            except Exception:
                data_json_str = "{}"

        return {
            "markdown": markdown,
            "doctags": doctags,
            "json": data_json_str,
            "raw": result,
        }


async def main():
    pdf_path = Path(
        r"d:\Document\Python_project\thuquynh-chatbot-facebook\1. CTDT chuyen nganh TIN HOC KINH TE Cap nhat 2020.pdf"
    )
    if not pdf_path.exists():
        print(f"File không tồn tại: {pdf_path}")
        return
    try:
        processor = DoclingPDFProcessor()
        out = await processor.convert(str(pdf_path))
    except ImportError:
        print(
            "Docling chưa được cài đặt. Vui lòng cài đặt: python -m pip install docling"
        )
        return
    md = out.get("markdown", "")
    js = out.get("json", "")
    print(md[:2000])
    print(js[:1000])

    out_dir = Path("docling_output")
    out_dir.mkdir(parents=True, exist_ok=True)
    name = pdf_path.stem
    md_path = out_dir / f"{name}.md"
    txt_path = out_dir / f"{name}.txt"
    md_path.write_text(md, encoding="utf-8")
    txt_path.write_text(md, encoding="utf-8")
    print(str(md_path))
    print(str(txt_path))


if __name__ == "__main__":
    asyncio.run(main())
