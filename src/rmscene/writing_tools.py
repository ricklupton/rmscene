"""Common code for writing tools.

Code originally from https://github.com/lschwetlick/maxio through
https://github.com/chemag/maxio .
"""

import logging
import math

_logger = logging.getLogger(__name__)


# color_id to RGB conversion
# 1. we use "color_id" for a unique, proprietary ID for colors,
#   (see scene_stream.py):
remarkable_palette = {
    # BLACK = 0
    0: [0, 0, 0],
    # GRAY = 1
    1: [125, 125, 125],
    # WHITE = 2
    2: [255, 255, 255],
    # https://www.color-name.com/highlighter-yellow.color
    # YELLOW = 3
    3: [251, 247, 25],
    # GREEN = 4
    4: [0, 255, 0],
    # PINK = 5
    # https://www.rapidtables.com/web/color/pink-color.html
    5: [255, 192, 203],
    # BLUE = 6
    6: [0, 0, 255],
    # RED = 7
    7: [255, 0, 0],
    # GRAY_OVERLAP = 8
    8: [125, 125, 125],
}


class Pen:
    def __init__(self, base_width, base_color_id):
        self.base_width = base_width
        self.base_color = remarkable_palette[base_color_id]
        self.segment_length = 1000
        self.base_opacity = 1
        self.name = "Basic Pen"
        # initial stroke values
        self.stroke_linecap = "round"
        self.stroke_opacity = 1
        self.stroke_width = base_width
        self.stroke_color = base_color_id

    # note that the units of the points have had their units converted
    # in scene_stream.py
    # speed = d.read_float32() * 4
    # ---> replace speed with speed / 4 [input]
    # direction = 255 * d.read_float32() / (math.pi * 2)
    # ---> replace tilt with direction_to_tilt() [input]
    @classmethod
    def direction_to_tilt(cls, direction):
        return direction * (math.pi * 2) / 255
    # width = int(round(d.read_float32() * 4))
    # ---> replace width with width / 4 [input]
    # ---> replace width with 4 * width [output]
    # pressure = d.read_float32() * 255
    # ---> replace pressure with pressure / 255 [input]

    def get_segment_width(self, speed, direction, width, pressure, last_width):
        return self.base_width

    def get_segment_color(self, speed, direction, width, pressure, last_width):
        return "rgb"+str(tuple(self.base_color))

    def get_segment_opacity(self, speed, direction, width, pressure, last_width):
        return self.base_opacity

    def cutoff(self, value):
        """must be between 1 and 0"""
        value = 1 if value > 1 else value
        value = 0 if value < 0 else value
        return value

    @classmethod
    def create(cls, pen_nr, color_id, width):
        # print(f'----> create(cls, pen_nr: {pen_nr}, color_id: {color_id}, width: {width})')
        # Brush
        if pen_nr == 0 or pen_nr == 12:
            return Brush(width, color_id)
        # caligraphy
        elif pen_nr == 21:
            return Caligraphy(width, color_id)
        # Marker
        elif pen_nr == 3 or pen_nr == 16:
            return Marker(width, color_id)
        # BallPoint
        elif pen_nr == 2 or pen_nr == 15:
            return Ballpoint(width, color_id)
        # Fineliner
        elif pen_nr == 4 or pen_nr == 17:
            return Fineliner(width, color_id)
        # Pencil
        elif pen_nr == 1 or pen_nr == 14:
            return Pencil(width, color_id)
        # Mechanical Pencil
        elif pen_nr == 7 or pen_nr == 13:
            return Mechanical_Pencil(width, color_id)
        # Highlighter
        elif pen_nr == 5 or pen_nr == 18:
            width = 15
            return Highlighter(width, color_id)
        # Erase area
        elif pen_nr == 8:
            return Erase_Area(width, color_id)
        # Eraser
        elif pen_nr == 6:
            color_id = 2
            return Eraser(width, color_id)
        raise Exception(f'Unknown pen_nr: {pen_nr}')


class Fineliner(Pen):
    def __init__(self, base_width, base_color_id):
        super().__init__(base_width, base_color_id)
        self.base_width = (base_width ** 2.1) * 1.3
        self.name = "Fineliner"


class Ballpoint(Pen):
    def __init__(self, base_width, base_color_id):
        super().__init__(base_width, base_color_id)
        self.segment_length = 5
        self.name = "Ballpoint"

    def get_segment_width(self, speed, direction, width, pressure, last_width):
        segment_width = (0.5 + pressure / 255) + (1 * width / 4) - 0.5*((speed / 4)/50)
        return segment_width

    def get_segment_color(self, speed, direction, width, pressure, last_width):
        intensity = (0.1 * - ((speed / 4) / 35)) + (1.2 * pressure / 255) + 0.5
        intensity = self.cutoff(intensity)
        # using segment color not opacity because the dots interfere with each other.
        # Color must be 255 rgb
        segment_color = [int(abs(intensity - 1) * 255)] * 3
        return "rgb"+str(tuple(segment_color))

    # def get_segment_opacity(self, speed, direction, width, pressure, last_width):
    #     segment_opacity = (0.2 * - ((speed / 4) / 35)) + (0.8 * pressure / 255)
    #     segment_opacity *= segment_opacity
    #     segment_opacity = self.cutoff(segment_opacity)
    #     return segment_opacity


class Marker(Pen):
    def __init__(self, base_width, base_color_id):
        super().__init__(base_width, base_color_id)
        self.segment_length = 3
        self.name = "Marker"

    def get_segment_width(self, speed, direction, width, pressure, last_width):
        segment_width = 0.9 * ((width / 4) - 0.4 * self.direction_to_tilt(direction)) + (0.1 * last_width)
        return segment_width


class Pencil(Pen):
    def __init__(self, base_width, base_color_id):
        super().__init__(base_width, base_color_id)
        self.segment_length = 2
        self.name = "Pencil"

    def get_segment_width(self, speed, direction, width, pressure, last_width):
        segment_width = 0.7 * ((((0.8*self.base_width) + (0.5 * pressure / 255)) * (width / 4)) - (0.25 * self.direction_to_tilt(direction)**1.8) - (0.6 * (speed / 4) / 50))
        # segment_width = 1.3*(((self.base_width * 0.4) * pressure) - 0.5 * ((self.direction_to_tilt(direction) ** 0.5)) + (0.5 * last_width))
        max_width = self.base_width * 10
        segment_width = segment_width if segment_width < max_width else max_width
        return segment_width

    def get_segment_opacity(self, speed, direction, width, pressure, last_width):
        segment_opacity = (0.1 * - ((speed / 4) / 35)) + (1 * pressure / 255)
        segment_opacity = self.cutoff(segment_opacity) - 0.1
        return segment_opacity


class Mechanical_Pencil(Pen):
    def __init__(self, base_width, base_color_id):
        super().__init__(base_width, base_color_id)
        self.base_width = self.base_width ** 2
        self.base_opacity = 0.7
        self.name = "Mechanical Pencil"


class Brush(Pen):
    def __init__(self, base_width, base_color_id):
        super().__init__(base_width, base_color_id)
        self.segment_length = 2
        self.stroke_linecap = "round"
        self.opacity = 1
        self.name = "Brush"

    def get_segment_width(self, speed, direction, width, pressure, last_width):
        segment_width = 0.7 * (((1 + (1.4 * pressure / 255)) * (width / 4)) - (0.5 * self.direction_to_tilt(direction)) - ((speed / 4) / 50))  # + (0.2 * last_width)
        return segment_width

    def get_segment_color(self, speed, direction, width, pressure, last_width):
        intensity = ((pressure / 255) ** 1.5 - 0.2 * ((speed / 4) / 50)) * 1.5
        intensity = self.cutoff(intensity)
        # using segment color not opacity because the dots interfere with each other.
        # Color must be 255 rgb
        rev_intensity = abs(intensity - 1)
        segment_color = [int(rev_intensity * (255 - self.base_color[0])),
                         int(rev_intensity * (255 - self.base_color[1])),
                         int(rev_intensity * (255 - self.base_color[2]))]

        return "rgb"+str(tuple(segment_color))


class Highlighter(Pen):
    def __init__(self, base_width, base_color_id):
        super().__init__(base_width, base_color_id)
        self.stroke_linecap = "square"
        self.base_opacity = 0.3
        self.stroke_opacity = 0.2
        self.name = "Highlighter"


class Eraser(Pen):
    def __init__(self, base_width, base_color_id):
        super().__init__(base_width, base_color_id)
        self.stroke_linecap = "square"
        self.base_width = self.base_width * 2
        self.name = "Eraser"


class Erase_Area(Pen):
    def __init__(self, base_width, base_color_id):
        super().__init__(base_width, base_color_id)
        self.stroke_linecap = "square"
        self.base_opacity = 0
        self.name = "Erase Area"


class Caligraphy(Pen):
    def __init__(self, base_width, base_color_id):
        super().__init__(base_width, base_color_id)
        self.segment_length = 2
        self.name = "Calligraphy"

    def get_segment_width(self, speed, direction, width, pressure, last_width):
        segment_width = 0.9 * (((1 + pressure / 255) * (width / 4)) - 0.3 * self.direction_to_tilt(direction)) + (0.1 * last_width)
        return segment_width
