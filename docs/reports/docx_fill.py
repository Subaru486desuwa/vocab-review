"""把内容块写进课程模板“五、实验结果分析”和“六、实验总结与思考”下的空段落。

模板是一个单元格包含全部正文的大表格；只替换这两节下面原有的空段落，其余内容与格式不动
（唯一例外：封面信息栏按模板中的文字重新排版，见 _cover）。
内容块：("h", 文本) 小标题、("p", 文本) 正文、("code", [行]) 代码、("table", 表题, 表头, 行列表[, 列宽比])、
("img", 图片路径, 图题)。

排版与模板第一至四节一致：正文宋体 / Times New Roman 五号、首行缩进两字、单倍行距并对齐模板的行网格；
代码、表格、图片不对齐网格，避免小字号被撑成整行高。表题在表上、图题在图下，均为小五号居中。
"""

import html
import re
import struct
import zipfile
from pathlib import Path

CELL_DXA = 8100
INNER_DXA = 7900
EMU_PER_DXA = 635
# 整页截图可能很高（例如诊断页 1280×3211）；超过一页可容纳的高度时按比例缩小，避免被裁切。
EMU_PER_INCH = 914400
MAX_IMAGE_HEIGHT = int(6.2 * EMU_PER_INCH)
FONT = '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="宋体" w:cs="Times New Roman"/>'
MONO = '<w:rFonts w:ascii="Courier New" w:hAnsi="Courier New" w:eastAsia="宋体" w:cs="Courier New"/>'
BODY, SMALL, CODE = 21, 18, 17  # 半磅：五号、小五、8.5 磅
FIRST_LINE = '<w:ind w:firstLine="420"/>'  # 正文首行缩进两字
HANGING = '<w:ind w:left="340" w:hanging="340"/>'  # 代码折行时缩进，与新行区分


def _esc(text):
    return html.escape(text, quote=False)


def _run(text, size=BODY, bold=False, mono=False):
    # 模板的 Normal 样式自带加粗与 42 磅字号，这里逐项显式覆盖。
    props = (MONO if mono else FONT) + ("<w:b/><w:bCs/>" if bold else '<w:b w:val="0"/><w:bCs w:val="0"/>')
    props += f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
    return f'<w:r><w:rPr>{props}</w:rPr><w:t xml:space="preserve">{_esc(text)}</w:t></w:r>'


def _para(runs, *, grid=True, ind="", shade=False, keep_next=False, align="both", before=0, after=0, mark=BODY):
    # grid=False 时不对齐模板的行网格（每行 15.6 磅），代码、表格和图片按自身行高排列。
    props = '<w:pStyle w:val="Normal"/>'
    props += "<w:keepNext/>" if keep_next else ""
    props += "<w:widowControl/>"
    props += '<w:shd w:val="clear" w:color="auto" w:fill="F2F2F2"/>' if shade else ""
    props += "" if grid else '<w:snapToGrid w:val="0"/>'
    props += f'<w:spacing w:before="{before}" w:after="{after}" w:line="240" w:lineRule="auto"/>'
    props += ind
    props += f'<w:jc w:val="{align}"/>'
    props += f'<w:rPr><w:b w:val="0"/><w:sz w:val="{mark}"/><w:szCs w:val="{mark}"/></w:rPr>'
    return f"<w:p><w:pPr>{props}</w:pPr>{runs}</w:p>"


def _caption(text, keep_next=False, after=0):
    return _para(_run(text, size=SMALL), align="center", keep_next=keep_next, before=60, after=after, mark=SMALL)


def _cell(text, width, header, keep_next):
    shade = '<w:shd w:val="clear" w:color="auto" w:fill="E7EEE9"/>' if header else ""
    para = _para(
        _run(str(text), size=SMALL, bold=header),
        grid=False,
        keep_next=keep_next,
        align="center" if header else "left",
        before=30,
        after=30,
        mark=SMALL,
    )
    return f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{shade}<w:vAlign w:val="center"/></w:tcPr>{para}</w:tc>'


def _table(header, rows, ratios=None):
    ratios = ratios or [1] * len(header)
    widths = [INNER_DXA * r // sum(ratios) for r in ratios]
    widths[-1] += INNER_DXA - sum(widths)
    border = '<w:{0} w:val="single" w:sz="4" w:space="0" w:color="999999"/>'
    borders = "".join(border.format(side) for side in ("top", "left", "bottom", "right", "insideH", "insideV"))
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    # 表格整体不跨页（除最后一行外各行与下一行同页）；万一超过一页，表头行重复。
    body = "".join(
        f'<w:tr><w:trPr><w:cantSplit/>{"<w:tblHeader/>" if k == 0 else ""}</w:trPr>'
        + "".join(_cell(v, widths[i], k == 0, k < len(rows)) for i, v in enumerate(row))
        + "</w:tr>"
        for k, row in enumerate([header, *rows])
    )
    return (
        f'<w:tbl><w:tblPr><w:tblW w:w="{INNER_DXA}" w:type="dxa"/><w:jc w:val="center"/><w:tblBorders>{borders}</w:tblBorders>'
        f'<w:tblLayout w:type="fixed"/><w:tblCellMar><w:left w:w="80" w:type="dxa"/><w:right w:w="80" w:type="dxa"/>'
        f"</w:tblCellMar></w:tblPr><w:tblGrid>{grid}</w:tblGrid>{body}</w:tbl>"
    )


def _image_size(path):
    data = Path(path).read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    i = 2
    while i < len(data):  # JPEG：找 SOF 段
        marker, length = data[i + 1], struct.unpack(">H", data[i + 2 : i + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", data[i + 5 : i + 9])
            return w, h
        i += 2 + length
    raise ValueError(f"无法读取图片尺寸：{path}")


def _drawing(rid, pic_id, name, width_px, height_px):
    cx = INNER_DXA * EMU_PER_DXA
    cy = int(cx * height_px / width_px)
    if cy > MAX_IMAGE_HEIGHT:  # 过高的整页截图缩到一页以内，宽度同比缩小
        cx = int(cx * MAX_IMAGE_HEIGHT / cy)
        cy = MAX_IMAGE_HEIGHT
    return (
        '<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
        f'<wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{pic_id}" name="{_esc(name)}"/>'
        '<wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/></wp:cNvGraphicFramePr>'
        '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        f'<pic:nvPicPr><pic:cNvPr id="{pic_id}" name="{_esc(name)}"/><pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:ln w="6350"><a:solidFill><a:srgbClr val="BBBBBB"/></a:solidFill></a:ln></pic:spPr>'
        "</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>"
    )


class _Doc:
    def __init__(self, files):
        self.files = files
        self.images = []
        self.rels = files["word/_rels/document.xml.rels"].decode()
        self.next_rid = 1 + max(int(n) for n in re.findall(r'Id="rId(\d+)"', self.rels))
        self.next_pic = 5000

    def blocks(self, blocks):
        out = []
        for block in blocks:
            kind = block[0]
            if kind == "h":
                out.append(_para(_run(block[1], bold=True), keep_next=True, align="left", before=120))
            elif kind == "p":
                out.append(_para(_run(block[1]), ind=FIRST_LINE))
            elif kind == "code":
                for line in block[1]:
                    code = _run(line or " ", size=CODE, mono=True)
                    out.append(_para(code, grid=False, ind=HANGING, shade=True, align="left", mark=CODE))
                out.append(_spacer())
            elif kind == "table":
                out.append(_caption(block[1], keep_next=True))
                out.append(_table(block[2], block[3], block[4] if len(block) > 4 else None))
                out.append(_spacer())
            elif kind == "img":
                out.append(self.image(block[1], block[2]))
            else:
                raise ValueError(kind)
        return "".join(out)

    def image(self, path, caption):
        data = Path(path).read_bytes()
        ext = "png" if data[:4] == b"\x89PNG" else "jpeg"
        name = f"media/report_{len(self.images) + 1}.{ext}"
        self.files[f"word/{name}"] = data
        rid = f"rId{self.next_rid}"
        self.next_rid += 1
        self.next_pic += 1
        self.rels = self.rels.replace(
            "</Relationships>",
            f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"'
            f' Target="{name}"/></Relationships>',
        )
        self.images.append(name)
        w, h = _image_size(path)
        picture = _para(_drawing(rid, self.next_pic, Path(path).name, w, h), grid=False, align="center", before=60, keep_next=True)
        return picture + _caption(caption, after=120)


def _spacer():
    return _para("", grid=False, mark=12)


def _text(p):
    return "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p))


PARA = r"<w:p[ >](?:(?!<w:p[ >]).)*?</w:p>"
COVER_FIELDS = (
    "课程名称",
    "实验项目名称",
    "实验学生班级",
    "实验学生姓名",
    "实验学生学号",
    "实验时间",
    "实验地点",
    "实验成绩评定",
    "指导教师签字",
)
COVER_FONT = '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="仿宋" w:cs="Times New Roman"/>'
COVER_SIZE = 32  # 三号
LABEL_DXA, VALUE_DXA = 2300, 4700


def _cover_para(text, align, before=0):
    run = (
        f'<w:r><w:rPr>{COVER_FONT}<w:b w:val="0"/><w:bCs w:val="0"/><w:sz w:val="{COVER_SIZE}"/>'
        f'<w:szCs w:val="{COVER_SIZE}"/></w:rPr><w:t xml:space="preserve">{_esc(text)}</w:t></w:r>'
    )
    # 段落标记也设三号，否则落到 Normal 样式的 42 磅，把行撑高。
    return (
        f'<w:p><w:pPr><w:pStyle w:val="Normal"/><w:snapToGrid w:val="0"/>'
        f'<w:spacing w:before="{before}" w:after="0" w:line="240" w:lineRule="auto"/><w:jc w:val="{align}"/>'
        f'<w:rPr><w:b w:val="0"/><w:sz w:val="{COVER_SIZE}"/><w:szCs w:val="{COVER_SIZE}"/></w:rPr></w:pPr>'
        f'{run if text else ""}</w:p>'
    )


def _cover_table(values):
    """标签两端分散对齐到同一宽度，内容写在下框线上并居中；空值留出整条横线供手填。"""
    none = "".join(f'<w:{side} w:val="nil"/>' for side in ("top", "left", "bottom", "right", "insideH", "insideV"))
    line = '<w:bottom w:val="single" w:sz="6" w:space="0" w:color="000000"/>'
    rows = "".join(
        '<w:tr><w:trPr><w:cantSplit/><w:trHeight w:val="620"/></w:trPr>'
        f'<w:tc><w:tcPr><w:tcW w:w="{LABEL_DXA}" w:type="dxa"/><w:tcMar><w:right w:w="300" w:type="dxa"/></w:tcMar>'
        f'<w:vAlign w:val="bottom"/></w:tcPr>{_cover_para(label, "distribute")}</w:tc>'
        f'<w:tc><w:tcPr><w:tcW w:w="{VALUE_DXA}" w:type="dxa"/><w:tcBorders>{line}</w:tcBorders>'
        f'<w:vAlign w:val="bottom"/></w:tcPr>{_cover_para(value, "center")}</w:tc></w:tr>'
        for label, value in values
    )
    return (
        f'<w:tbl><w:tblPr><w:tblW w:w="{LABEL_DXA + VALUE_DXA}" w:type="dxa"/><w:jc w:val="center"/>'
        f'<w:tblBorders>{none}</w:tblBorders><w:tblLayout w:type="fixed"/>'
        '<w:tblCellMar><w:left w:w="0" w:type="dxa"/><w:right w:w="0" w:type="dxa"/></w:tblCellMar></w:tblPr>'
        f'<w:tblGrid><w:gridCol w:w="{LABEL_DXA}"/><w:gridCol w:w="{VALUE_DXA}"/></w:tblGrid>{rows}</w:tbl>'
    )


def _cover(xml):
    """重排封面信息栏（课程名称至日期）。

    模板用空格撑下划线、各行缩进不一、段落标记缺字号，Word 中标签不齐、空栏没有横线、封面溢到第二页。
    这里从模板文字中取出各栏的值（如课程名称、指导教师），改为无边框表格，日期居中，之后分页。
    """
    cover_end = xml.index("<w:tbl")
    paras = list(re.finditer(PARA, xml[:cover_end], flags=re.S))
    texts = [_text(m.group(0)).strip() for m in paras]
    first = next(i for i, t in enumerate(texts) if t.startswith(COVER_FIELDS[0]))
    values = [(label, next(t for t in texts[first:] if t.startswith(label))[len(label) :].strip()) for label in COVER_FIELDS]
    last = next(i for i in range(first, len(texts)) if re.fullmatch(r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日", texts[i]))
    if last != len(paras) - 1:
        raise ValueError("封面日期之后、正文表格之前还有内容，模板结构与预期不符")
    date = re.sub(r"\s", "", texts[last])
    page_break = (
        '<w:p><w:pPr><w:pStyle w:val="Normal"/><w:snapToGrid w:val="0"/>'
        '<w:spacing w:before="0" w:after="0" w:line="20" w:lineRule="exact"/><w:rPr><w:sz w:val="2"/></w:rPr></w:pPr>'
        '<w:r><w:rPr><w:sz w:val="2"/></w:rPr><w:br w:type="page"/></w:r></w:p>'
    )
    block = _cover_table(values) + _cover_para(date, "center", before=480) + page_break
    return xml[: paras[first].start()] + block + xml[paras[last].end() :]


def fill(template_docx, output_docx, section5, section6):
    with zipfile.ZipFile(template_docx) as z:
        files = {n: z.read(n) for n in z.namelist()}
    xml = files["word/document.xml"].decode()
    paras = list(re.finditer(PARA, xml, flags=re.S))
    heads = [m for m in paras if _text(m.group(0)).startswith(("五、", "五")) and "实验结果分析" in _text(m.group(0))]
    sixes = [m for m in paras if _text(m.group(0)).startswith("六、")]
    if len(heads) != 1 or len(sixes) != 1:
        raise ValueError(f"{template_docx}：找不到唯一的五、六节标题")
    five, six = heads[0], sixes[0]
    cell_end = xml.index("</w:tc>", six.end())
    between = xml[five.end() : six.start()]
    after = xml[six.end() : cell_end]
    for segment in (between, after):
        if _text(segment).strip() or "<w:tbl" in segment or "<w:drawing" in segment:
            raise ValueError(f"{template_docx}：五、六节下面已有内容，拒绝覆盖")
    doc = _Doc(files)
    filled = (
        xml[: five.end()]
        + doc.blocks(section5)
        + xml[six.start() : six.end()]
        + doc.blocks(section6)
        + _spacer()
        + xml[cell_end:]
    )
    files["word/document.xml"] = _cover(filled).encode()
    files["word/_rels/document.xml.rels"] = doc.rels.encode()
    with zipfile.ZipFile(output_docx, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
