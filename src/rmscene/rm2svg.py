"""Convert blocks to svg file.

Code originally from https://github.com/lschwetlick/maxio through
https://github.com/chemag/maxio .
"""

import io
import logging
import math
import string
import tempfile

from dataclasses import dataclass

from . import read_blocks

from .scene_stream import (
    Block,
    RootTextBlock,
    AuthorIdsBlock,
    MigrationInfoBlock,
    PageInfoBlock,
    SceneTreeBlock,
    TreeNodeBlock,
    SceneGroupItemBlock,
    SceneLineItemBlock,
)

from .writing_tools import (
    Pen,
)

from .utils import (
    run_command,
)

_logger = logging.getLogger(__name__)


SCREEN_WIDTH = 1404
SCREEN_HEIGHT = 1872

SVG_HEADER = string.Template(
    """
<svg xmlns="http://www.w3.org/2000/svg" height="$height" width="$width">
    <script type="application/ecmascript"> <![CDATA[
        var visiblePage = 'p1';
        function goToPage(page) {
            document.getElementById(visiblePage).setAttribute('style', 'display: none');
            document.getElementById(page).setAttribute('style', 'display: inline');
            visiblePage = page;
        }
    ]]>
    </script>
"""
)


XPOS_SHIFT = SCREEN_WIDTH / 2


@dataclass
class PageInfo:
    tnb_dict: dict
    stb_tree: dict
    sgib_tree: dict
    height: int
    width: int
    xpos_delta: float
    ypos_delta: float

    def __init__(self):
        self.tnb_dict = {}
        self.stb_tree = {}
        self.sgib_tree = {}
        self.height = 0
        self.width = 0
        self.xpos_delta = 0
        self.ypos_delta = 0


def rm2pdf(infile, outfile):
    tmp_outfile = tempfile.NamedTemporaryFile().name + ".svg"
    rm2svg(infile, tmp_outfile)
    # use inkscape to convert svg to pdf
    command = "inkscape %s --export-filename=%s" % (tmp_outfile, outfile)
    returncode, out, err = run_command(command)
    assert returncode == 0


def rm2svg(infile, outfile, debug=0):
    # parse the lines (.rm) input file into a series of blocks
    with open(infile, "rb") as infh:
        infile_datastream = io.BufferedReader(infh)
        # we need to process the blocks twice to understand the dimensions, so
        # let's put the iterable into a list
        blocks = list(read_blocks(infile_datastream))

    # get page info
    page_info = get_page_info(blocks, debug)

    with open(outfile, "w") as output:
        # add svg header
        output.write(
            SVG_HEADER.substitute(height=page_info.height, width=page_info.width)
        )
        output.write("\n")

        # add svg page info
        output.write('    <g id="p1" style="display:inline">\n')
        output.write(
            '        <filter id="blurMe"><feGaussianBlur in="SourceGraphic" stdDeviation="10" /></filter>\n'
        )

        for block in blocks:
            if isinstance(block, SceneLineItemBlock):
                draw_slib(block, output, page_info, debug)
            elif isinstance(block, RootTextBlock):
                draw_rtb(block, output, page_info, debug)
            else:
                if debug > 0:
                    print(f"warning: not converting block: {block.__class__}")

        # Overlay the page with a clickable rect to flip pages
        output.write("\n")
        output.write("        <!-- clickable rect to flip pages -->\n")
        output.write(
            f'        <rect x="0" y="0" width="{page_info.width}" height="{page_info.height}" fill-opacity="0"/>\n'
        )
        # Closing page group
        output.write("    </g>\n")
        # END notebook
        output.write("</svg>\n")
        output.close()


def draw_slib(block, output, page_info, debug):
    if debug > 0:
        print("----SceneLineItemBlock")
    # a SceneLineItemBlock contains a stroke
    output.write(f"        <!-- SceneLineItemBlock item_id: {block.item_id} -->\n")

    # make sure the object is not empty
    if block.value is None:
        return

    # initiate the pen
    pen = Pen.create(
        block.value.tool.value, block.value.color.value, block.value.thickness_scale
    )

    # BEGIN stroke
    output.write(
        f"        <!-- Stroke tool: {block.value.tool.name} color: {block.value.color.name} thickness_scale: {block.value.thickness_scale} -->\n"
    )
    output.write("        <polyline ")
    output.write(
        f'style="fill:none;stroke:{pen.stroke_color};stroke-width:{pen.stroke_width};opacity:{pen.stroke_opacity}" '
    )
    output.write(f'stroke-linecap="{pen.stroke_linecap}" ')
    output.write('points="')

    # get the block alignment
    xpos_delta, ypos_delta = get_slib_anchor_info(block, page_info, debug)
    # add the doc alignment
    xpos_delta += page_info.xpos_delta
    ypos_delta += page_info.ypos_delta

    last_xpos = -1.0
    last_ypos = -1.0
    last_segment_width = 0
    # Iterate through the point to form a polyline
    for point_id, point in enumerate(block.value.points):
        # get the block alignment

        # align the original position
        xpos = point.x + xpos_delta
        ypos = point.y + ypos_delta
        # stretch the original position
        # ratio = (page_info.height / page_info.width) / (1872 / 1404)
        # if ratio > 1:
        #    xpos = ratio * ((xpos * page_info.width) / 1404)
        #    ypos = (ypos * page_info.height) / 1872
        # else:
        #    xpos = (xpos * page_info.width) / 1404
        #    ypos = (1 / ratio) * (ypos * page_info.height) / 1872
        # process segment-origination points
        if point_id % pen.segment_length == 0:
            segment_color = pen.get_segment_color(
                point.speed,
                point.direction,
                point.width,
                point.pressure,
                last_segment_width,
            )
            segment_width = pen.get_segment_width(
                point.speed,
                point.direction,
                point.width,
                point.pressure,
                last_segment_width,
            )
            segment_opacity = pen.get_segment_opacity(
                point.speed,
                point.direction,
                point.width,
                point.pressure,
                last_segment_width,
            )
            # print(segment_color, segment_width, segment_opacity, pen.stroke_linecap)
            # UPDATE stroke
            output.write('"/>\n')
            output.write("        <polyline ")
            output.write(
                f'style="fill:none; stroke:{segment_color} ;stroke-width:{segment_width:.3f};opacity:{segment_opacity}" '
            )
            output.write(f'stroke-linecap="{pen.stroke_linecap}" ')
            output.write('points="')
            if last_xpos != -1.0:
                # Join to previous segment
                output.write(f"{last_xpos:.3f},{last_ypos:.3f} ")
        # store the last position
        last_xpos = xpos
        last_ypos = ypos
        last_segment_width = segment_width

        # BEGIN and END polyline segment
        output.write(f"{xpos:.3f},{ypos:.3f} ")

    # END stroke
    output.write('" />\n')


def draw_rtb(block, output, page_info, debug):
    if debug > 0:
        print("----RootTextBlock")
    # a RootTextBlock contains text
    output.write(f"        <!-- RootTextBlock item_id: {block.block_id} -->\n")

    # add some style to get readable text
    text_size = 50
    output.write("        <style>\n")
    output.write("            .default {\n")
    output.write(f"                font: {text_size}px serif\n")
    output.write("            }\n")
    output.write("        </style>\n")

    xpos = block.pos_x + page_info.xpos_delta
    ypos = block.pos_y + page_info.ypos_delta
    for text_item in block.text_items:
        # BEGIN text
        # https://developer.mozilla.org/en-US/docs/Web/SVG/Element/text
        output.write(f"        <!-- TextItem item_id: {text_item.item_id} -->\n")
        if text_item.text.strip():
            output.write(
                f'        <text x="{xpos}" y="{ypos}" class="default">{text_item.text.strip()}</text>\n'
            )
        ypos += text_size * 1.5


def get_limits(blocks, page_info, debug):
    xmin = xmax = None
    ymin = ymax = None
    for block in blocks:
        if debug > 1:
            print(f"-- block: {block}\n")
        # 1. parse block
        if isinstance(block, SceneLineItemBlock):
            xmin_tmp, xmax_tmp, ymin_tmp, ymax_tmp = get_limits_slib(
                block, page_info, debug
            )
        # text blocks use a different xpos/ypos coordinate system
        # elif isinstance(block, RootTextBlock):
        #    xmin_tmp, xmax_tmp, ymin_tmp, ymax_tmp = get_limits_rtb(block, page_info, debug)
        else:
            continue
        # 2. update bounds
        if xmin_tmp is None:
            continue
        xmin = xmin_tmp if (xmin is None or xmin > xmin_tmp) else xmin
        xmax = xmax_tmp if (xmax is None or xmax < xmax_tmp) else xmax
        ymin = ymin_tmp if (ymin is None or ymin > ymin_tmp) else ymin
        ymax = ymax_tmp if (ymax is None or ymax < ymax_tmp) else ymax
        if debug > 1:
            print(
                f"-- block: {type(block)} xmin: {xmin} xmax: {xmax} ymin: {ymin} ymax: {ymax}\n"
            )
    return xmin, xmax, ymin, ymax


def get_slib_anchor_info(block, page_info, debug):
    tnb_id = block.parent_id.part2
    xpos_delta = 0
    ypos_delta = 0
    while tnb_id != 1:
        if (
            page_info.tnb_dict[tnb_id].anchor_type is not None
            and page_info.tnb_dict[tnb_id].anchor_type.value == 2
        ):
            xpos_delta += page_info.tnb_dict[tnb_id].anchor_origin_x.value
        # move to the parent TNB
        tnb_id = page_info.stb_tree[tnb_id]
    return xpos_delta, ypos_delta


def get_limits_slib(block, page_info, debug):
    # make sure the object is not empty
    if block.value is None:
        return None, None, None, None
    xmin = xmax = None
    ymin = ymax = None
    # get the anchor information
    xpos_delta, ypos_delta = get_slib_anchor_info(block, page_info, debug)
    for point in block.value.points:
        xpos, ypos = point.x, point.y
        if xmin is None or xmin > xpos:
            xmin = xpos
        if xmax is None or xmax < xpos:
            xmax = xpos
        if ymin is None or ymin > ypos:
            ymin = ypos
        if ymax is None or ymax < ypos:
            ymax = ypos
    xmin += xpos_delta
    xmax += xpos_delta
    ymin += ypos_delta
    ymax += ypos_delta
    return xmin, xmax, ymin, ymax


def get_limits_rtb(block, page_info, debug):
    xmin = block.pos_x
    xmax = block.pos_x + block.width
    ymin = block.pos_y
    ymax = block.pos_y
    return xmin, xmax, ymin, ymax


def get_dimensions(blocks, page_info, debug):
    # get block limits
    xmin, xmax, ymin, ymax = get_limits(blocks, page_info, debug)
    if debug > 0:
        print(f"xmin: {xmin} xmax: {xmax} ymin: {ymin} ymax: {ymax}\n")
    # {xpos,ypos} coordinates are based on the top-center point
    # of the doc **iff there are no text boxes**. When you add
    # text boxes, the xpos/ypos values change.
    xpos_delta = XPOS_SHIFT
    if xmin is not None and (xmin + XPOS_SHIFT) < 0:
        # make sure there are no negative xpos
        xpos_delta += -(xmin + XPOS_SHIFT)
    # ypos_delta = SCREEN_HEIGHT / 2
    ypos_delta = 0
    # adjust dimensions if needed
    width = int(
        math.ceil(
            max(
                SCREEN_WIDTH,
                xmax - xmin if xmin is not None and xmax is not None else 0,
            )
        )
    )
    height = int(
        math.ceil(
            max(
                SCREEN_HEIGHT,
                ymax - ymin if ymin is not None and ymax is not None else 0,
            )
        )
    )
    if debug > 0:
        print(
            f"height: {height} width: {width} xpos_delta: {xpos_delta} ypos_delta: {ypos_delta}"
        )
    return height, width, xpos_delta, ypos_delta


# only use case for the TNB tree is going from leaf to root, so we can
# just do with the child->parent tuples. For efficiency, we keep the latter
# in a dictionary.
# Note that both the STB and the SGIB objects seem to do the same mappings.
# We will keep both.
def get_page_info(blocks, debug):
    page_info = PageInfo()
    # parse the TNB/STB/SGIB blocks to get the page tree
    for block in blocks:
        if isinstance(block, TreeNodeBlock):
            page_info.tnb_dict[block.node_id.part2] = block
        elif isinstance(block, SceneTreeBlock):
            page_info.stb_tree[block.tree_id.part2] = block.parent_id.part2
        elif isinstance(block, SceneGroupItemBlock):
            page_info.sgib_tree[block.value.part2] = block.parent_id.part2
    # TODO(chema): check the stb_tree and sgib_tree are the same, otherwise
    # print a warning

    # get the dimensions
    (
        page_info.height,
        page_info.width,
        page_info.xpos_delta,
        page_info.ypos_delta,
    ) = get_dimensions(blocks, page_info, debug)

    return page_info
