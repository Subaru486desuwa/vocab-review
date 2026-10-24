"""把内容块写进课程模板“五、实验结果分析”和“六、实验总结与思考”下的空段落。

模板是一个单元格包含全部正文的大表格；只替换这两节下面原有的空段落，其余内容与格式不动。
内容块：("h", 文本) 小标题、("p", 文本) 正文、("code", [行]) 代码、("table", 表头, 行列表)、
("img", 图片路径, 图题)、("note", 文本) 说明。
"""

import html
import re
import struct
import zipfile
from pathlib import Path

CELL_DXA = 8100
INNER_DXA = 7900
EMU_PER_DXA = 635
FONT = '<w:rFonts w:ascii="宋体" w:hAnsi="宋体" w:eastAsia="宋体" w:cs="宋体"/>'
MONO = '<w:rFonts w:ascii="Courier New" w:hAnsi="Courier New" w:eastAsia="宋体" w:cs="Courier New"/>'


def _esc(text):
    return html.escape(text, quote=False)


def _run(text, size=24, bold=False, mono=False, italic=False, color=None):
    # 模板的 Normal 样式自带加粗与 42 磅字号，这里逐项显式覆盖。
    props = (MONO if mono else FONT) + ("<w:b/><w:bCs/>" if bold else '<w:b w:val="0"/><w:bCs w:val="0"/>')
    props += "<w:i/>" if italic else ""
    props += f'<w:color w:val="{color}"/>' if color else ""
    props += f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
    return f'<w:r><w:rPr>{props}</w:rPr><w:t xml:space="preserve">{_esc(text)}</w:t></w:r>'


def _para(runs, *, line=360, indent=False, shade=False, keep_next=False, center=False, after=0, mark=24):
    props = '<w:pStyle w:val="Normal"/><w:widowControl/>'
    props += "<w:keepNext/>" if keep_next else ""
    props += f'<w:spacing w:before="0" w:after="{after}" w:lineRule="auto" w:line="{line}"/>'
    props += '<w:ind w:firstLine="480"/>' if indent else ""
    props += '<w:shd w:val="clear" w:color="auto" w:fill="F2F2F2"/>' if shade else ""
    props += f'<w:jc w:val="{"center" if center else "start"}"/>'
    props += f'<w:rPr><w:b w:val="0"/><w:sz w:val="{mark}"/><w:szCs w:val="{mark}"/></w:rPr>'
    return f"<w:p><w:pPr>{props}</w:pPr>{runs}</w:p>"


def _cell(text, width, header):
    shade = '<w:shd w:val="clear" w:color="auto" w:fill="E7EEE9"/>' if header else ""
    runs = _run(str(text), size=18, bold=header)
    return (
        f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{shade}</w:tcPr>'
        f'<w:p><w:pPr><w:spacing w:before="20" w:after="20" w:line="260" w:lineRule="auto"/><w:jc w:val="start"/>'
        f'<w:rPr><w:sz w:val="18"/></w:rPr></w:pPr>{runs}</w:p></w:tc>'
    )


def _table(header, rows, ratios=None):
    ratios = ratios or [1] * len(header)
    widths = [INNER_DXA * r // sum(ratios) for r in ratios]
    widths[-1] += INNER_DXA - sum(widths)
    border = '<w:{0} w:val="single" w:sz="4" w:space="0" w:color="999999"/>'
    borders = "".join(border.format(side) for side in ("top", "left", "bottom", "right", "insideH", "insideV"))
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    body = "".join(
        "<w:tr>" + "".join(_cell(v, widths[i], k == 0) for i, v in enumerate(row)) + "</w:tr>"
        for k, row in enumerate([header, *rows])
    )
    return (
        f'<w:tbl><w:tblPr><w:tblW w:w="{INNER_DXA}" w:type="dxa"/><w:tblBorders>{borders}</w:tblBorders>'
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
                out.append(_para(_run(block[1], bold=True), keep_next=True))
            elif kind == "p":
                out.append(_para(_run(block[1]), indent=True))
            elif kind == "note":
                out.append(_para(_run(block[1], size=21, color="555555"), indent=True, mark=21))
            elif kind == "code":
                for line in block[1]:
                    out.append(_para(_run(line or " ", size=17, mono=True), line=240, shade=True, mark=17))
                out.append(_para("", line=240, mark=12))
            elif kind == "table":
                out.append(_table(block[1], block[2], block[3] if len(block) > 3 else None))
                out.append(_para("", line=240, mark=12))
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
        picture = _para(_drawing(rid, self.next_pic, Path(path).name, w, h), line=240, center=True, keep_next=True)
        return picture + _para(_run(caption, size=21), line=300, center=True, after=120, mark=21)


def _text(p):
    return "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p))


def fill(template_docx, output_docx, section5, section6):
    with zipfile.ZipFile(template_docx) as z:
        files = {n: z.read(n) for n in z.namelist()}
    xml = files["word/document.xml"].decode()
    paras = list(re.finditer(r"<w:p[ >](?:(?!<w:p[ >]).)*?</w:p>", xml, flags=re.S))
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
        + _para("", line=240, mark=12)
        + xml[cell_end:]
    )
    files["word/document.xml"] = filled.encode()
    files["word/_rels/document.xml.rels"] = doc.rels.encode()
    with zipfile.ZipFile(output_docx, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
