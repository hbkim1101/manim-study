from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pymupdf
from manim import BLACK, WHITE, Group, ImageMobject, Text, VGroup, VMobject, config


__all__ = [
    "auto_problem_region",
    "pdf_problem_image",
    "pdf_problem_chars",
    "pdf_page_to_manim_group",
    "handwritten_text",
]


def auto_problem_region(
    pdf_path: str | Path,
    page_number: int = 0,
    problem_number: int = 1,
    padding_x: float = 10,
    padding_y: float = 20,
    paragraph_gap: float = 80,
) -> pymupdf.Rect:
    """문제 번호와 2단 편집 열을 기준으로 문제 영역을 자동 검출합니다."""
    doc = pymupdf.open(str(pdf_path))
    page = doc[page_number]
    lines = []

    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            text = "".join(span["text"] for span in line["spans"])
            lines.append((pymupdf.Rect(line["bbox"]), text))

    problem_lines = []
    for rect, text in lines:
        match = re.match(r"\s*(\d+)\.", text)
        if match:
            problem_lines.append((int(match.group(1)), rect))

    matches = [rect for number, rect in problem_lines if number == problem_number]
    if not matches:
        doc.close()
        raise ValueError(f"문제 번호 {problem_number}번을 찾지 못했습니다.")

    start_rect = matches[0]
    vertical_boundaries = []
    for drawing in page.get_drawings():
        rect = drawing["rect"]
        if rect.width <= 5 and rect.height > page.rect.height * 0.5:
            vertical_boundaries.append(rect.x0)

    left_boundary = max(
        [x for x in vertical_boundaries if x < start_rect.x0],
        default=page.rect.x0,
    )
    right_boundary = min(
        [x for x in vertical_boundaries if x > start_rect.x1],
        default=page.rect.x1,
    )
    column_band = pymupdf.Rect(
        left_boundary,
        page.rect.y0,
        right_boundary,
        page.rect.y1,
    )

    next_starts = [
        rect.y0
        for number, rect in problem_lines
        if rect.y0 > start_rect.y1 + 10
        and number != problem_number
        and rect.intersects(column_band)
    ]
    next_y = min(next_starts, default=page.rect.y1)
    column_lines = sorted(
        [
            rect
            for rect, _ in lines
            if rect.y1 >= start_rect.y0
            and rect.y0 < next_y
            and rect.intersects(column_band)
        ],
        key=lambda rect: (rect.y0, rect.x0),
    )

    selected_lines = []
    previous_y1 = start_rect.y0
    for rect in column_lines:
        if selected_lines and rect.y0 - previous_y1 > paragraph_gap:
            break
        selected_lines.append(rect)
        previous_y1 = max(previous_y1, rect.y1)

    if not selected_lines:
        doc.close()
        raise ValueError(f"문제 {problem_number}번의 내용을 찾지 못했습니다.")

    band = pymupdf.Rect(
        left_boundary,
        start_rect.y0,
        right_boundary,
        max(rect.y1 for rect in selected_lines),
    )
    content = list(selected_lines)
    for drawing in page.get_drawings():
        original = drawing["rect"]
        if original.height > band.height * 0.8 or original.width > page.rect.width * 0.8:
            continue
        clipped = original & band
        if not clipped.is_empty:
            content.append(clipped)

    result = pymupdf.Rect(
        min(rect.x0 for rect in content) - padding_x,
        min(rect.y0 for rect in content) - padding_y,
        max(rect.x1 for rect in content) + padding_x,
        max(rect.y1 for rect in content) + padding_y,
    ) & page.rect
    doc.close()
    return result


def pdf_problem_image(
    pdf_path: str | Path,
    problem_number: int = 1,
    page_number: int = 0,
    output_path: str | Path | None = None,
    dpi: int = 300,
    target_width: float | None = None,
) -> ImageMobject:
    """문항 번호로 문제를 자동 검출하고 원본 PDF 글꼴 그대로 ImageMobject로 반환합니다."""
    region = auto_problem_region(pdf_path, page_number, problem_number)
    if target_width is None:
        target_width = config.frame_width - 1
    if output_path is None:
        output_path = f"pdf_problem_{problem_number}.png"

    doc = pymupdf.open(str(pdf_path))
    pixmap = doc[page_number].get_pixmap(
        matrix=pymupdf.Matrix(dpi / 72, dpi / 72),
        clip=region,
        alpha=False,
    )
    pixmap.save(str(output_path))
    doc.close()

    image = ImageMobject(str(output_path))
    image.scale_to_fit_width(target_width)
    image.move_to([0, 0, 0])
    return image


def pdf_page_to_manim_group(
    pdf_path: str | Path,
    page_number: int = 0,
    region: tuple[float, float, float, float] | pymupdf.Rect | None = None,
    target_width: float | None = None,
    target_height: float | None = None,
    dpi: int = 300,
    line_padding: float = 0.15,
) -> Group:
    """PDF를 텍스트 줄 단위 ImageMobject 그룹으로 추출합니다."""
    doc = pymupdf.open(str(pdf_path))
    page = doc[page_number]
    bounds = pymupdf.Rect(region) if region is not None else page.rect
    area_width, area_height = bounds.width, bounds.height
    target_width = target_width or config.frame_width - 1
    target_height = target_height or config.frame_height - 0.5
    scale = min(target_width / area_width, target_height / area_height)
    zoom = dpi / 72

    def to_manim_xy(x: float, y: float) -> tuple[float, float]:
        center_x = (bounds.x0 + bounds.x1) / 2
        center_y = (bounds.y0 + bounds.y1) / 2
        return (x - center_x) * scale, (center_y - y) * scale

    def crop(rect: pymupdf.Rect, tag: str) -> ImageMobject:
        image_path = f"pdf_crop_{page_number}_{tag}.png"
        pixmap = page.get_pixmap(
            matrix=pymupdf.Matrix(zoom, zoom),
            clip=rect,
            alpha=True,
        )
        pixmap.save(image_path)
        image = ImageMobject(image_path)
        image.scale_to_fit_width(max(rect.width * scale, 0.01))
        x, y = to_manim_xy((rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2)
        image.move_to([x, y, 0])
        return image

    group = Group()
    line_index = 0
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            text = "".join(span["text"] for span in line["spans"])
            if not text.strip():
                continue
            x0, y0, x1, y1 = line["bbox"]
            pad_y = (y1 - y0) * line_padding + 1
            rect = pymupdf.Rect(x0 - 1, y0 - pad_y, x1 + 1, y1 + pad_y) & page.rect
            if region is not None:
                rect &= bounds
            if not rect.is_empty:
                group.add(crop(rect, f"line{line_index}"))
                line_index += 1

    doc.close()
    return group


def pdf_problem_chars(
    pdf_path: str | Path,
    problem_number: int = 1,
    page_number: int = 0,
    dpi: int = 300,
    char_padding: float = 0.15,
    target_width: float | None = None,
) -> Group:
    """문항 번호로 찾은 문제를 PDF 문자 단위 ImageMobject 그룹으로 추출합니다."""
    region = auto_problem_region(pdf_path, page_number, problem_number)
    doc = pymupdf.open(str(pdf_path))
    page = doc[page_number]
    target_width = target_width or config.frame_width - 1
    scale = target_width / region.width
    zoom = dpi / 72

    def to_manim_xy(x: float, y: float) -> tuple[float, float]:
        center_x = (region.x0 + region.x1) / 2
        center_y = (region.y0 + region.y1) / 2
        return (x - center_x) * scale, (center_y - y) * scale

    group = Group()
    char_index = 0
    for block in page.get_text("rawdict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                for char in span["chars"]:
                    if not char["c"].strip():
                        continue
                    x0, y0, x1, y1 = char["bbox"]
                    rect = pymupdf.Rect(
                        x0 - 1,
                        y0 - (y1 - y0) * char_padding - 1,
                        x1 + 1,
                        y1 + (y1 - y0) * char_padding + 1,
                    ) & region
                    if rect.is_empty:
                        continue
                    image_path = f"pdf_problem_{problem_number}_char{char_index}.png"
                    pixmap = page.get_pixmap(
                        matrix=pymupdf.Matrix(zoom, zoom),
                        clip=rect,
                        alpha=True,
                    )
                    pixmap.save(image_path)
                    image = ImageMobject(image_path)
                    image.scale_to_fit_width(max(rect.width * scale, 0.01))
                    x, y = to_manim_xy((rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2)
                    image.move_to([x, y, 0])
                    image.char_index = char_index
                    image.pdf_char = char["c"]
                    group.add(image)
                    char_index += 1

    doc.close()
    return group


def handwritten_text(
    content: str,
    font: str = "NanumGothic",
    font_size: float = 72,
    color=WHITE,
    **text_kwargs,
) -> VGroup:
    """글자와 글자 내부 획을 정렬한 VGroup을 반환합니다."""
    text = Text(content, font=font, font_size=font_size, color=color, **text_kwargs)
    pieces = []
    for char_index, char in enumerate(text.family_members_with_points()):
        subpaths = sorted(
            char.get_subpaths(),
            key=lambda path: (-path[:, 1].mean(), path[:, 0].mean()),
        )
        for subpath in subpaths:
            piece = VMobject(color=color).set_points_as_corners(subpath)
            piece.char_index = char_index
            pieces.append(piece)
    return VGroup(*pieces)
