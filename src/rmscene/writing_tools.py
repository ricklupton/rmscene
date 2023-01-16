"""Common code for writing tools.

"""

import logging

_logger = logging.getLogger(__name__)


stroke_color = {
    'gray': {
        0: [0, 0, 0],
        1: [125, 125, 125],
        2: [255, 255, 255],
    },
    'rgb': {
        0: [0, 0, 0],
        1: [255, 0, 0],
        2: [255, 255, 255],
        3: [150, 0, 0],
        4: [0, 0, 125],
    },
}

color_type = 'gray'
# color_type = 'rgb'


class Pen:
    def __init__(self, base_width, base_color):
        self.base_width = base_width
        self.base_color = stroke_color[color_type][base_color]
        self.segment_length = 1000
        self.base_opacity = 1
        self.name = "Basic Pen"
        # initial stroke values
        self.stroke_linecap = "round"
        self.stroke_opacity = 1
        self.stroke_width = base_width
        self.stroke_color = base_color

    def get_segment_width(self, speed, tilt, width, pressure, last_width):
        return self.base_width

    def get_segment_color(self, speed, tilt, width, pressure, last_width):
        return "rgb"+str(tuple(self.base_color))

    def get_segment_opacity(self, speed, tilt, width, pressure, last_width):
        return self.base_opacity

    def cutoff(self, value):
        """must be between 1 and 0"""
        value = 1 if value > 1 else value
        value = 0 if value < 0 else value
        return value

    @classmethod
    def create(cls, pen_nr, color, width):
        # Brush
        if pen_nr == 0 or pen_nr == 12:
            return Brush(width, color)
        # caligraphy
        elif pen_nr == 21:
            return Caligraphy(width, color)
        # Marker
        elif pen_nr == 3 or pen_nr == 16:
            return Marker(width, color)
        # BallPoint
        elif pen_nr == 2 or pen_nr == 15:
            if color_type == 'rgb':
                color = 4
            return Ballpoint(width, color)
        # Fineliner 
        elif pen_nr == 4 or pen_nr == 17:
            return Fineliner(width, color)
        # pencil
        elif pen_nr == 1 or pen_nr == 14: 
            return Pencil(width, color)
        # mech
        elif pen_nr == 7 or pen_nr == 13:
            return Mechanical_Pencil(width, color)
        # Highlighter
        elif pen_nr == 5 or pen_nr == 18:
            width = 15
            if color_type == 'rgb':
                color = 3
            return Highlighter(width, color)
        # Erase area
        elif pen_nr == 8:
            return Erase_Area(width, color)
        # Eraser
        elif pen_nr == 6:
            color = 2
            return Eraser(width, color)
        raise Exception(f'Unknown pen_nr: {pen_nr}')


class Fineliner(Pen):
    def __init__(self, base_width, base_color):
        super().__init__(base_width, base_color)
        self.base_width = (base_width ** 2.1) * 1.3
        self.name = "Fineliner"


class Ballpoint(Pen):
    def __init__(self, base_width, base_color):
        super().__init__(base_width, base_color)
        self.segment_length = 5
        self.name = "Ballpoint"

    def get_segment_width(self, speed, tilt, width, pressure, last_width):
        segment_width = (0.5 + pressure) + (1 * width) - 0.5*(speed/50)
        return segment_width

    def get_segment_color(self, speed, tilt, width, pressure, last_width):
        intensity = (0.1 * -(speed / 35)) + (1.2 * pressure) + 0.5
        intensity = self.cutoff(intensity)
        # using segment color not opacity because the dots interfere with each other.
        # Color must be 255 rgb
        segment_color = [int(abs(intensity - 1) * 255)] * 3
        return "rgb"+str(tuple(segment_color))

    # def get_segment_opacity(self, speed, tilt, width, pressure, last_width):
    #     segment_opacity = (0.2 * -(speed / 35)) + (0.8 * pressure)
    #     segment_opacity *= segment_opacity
    #     segment_opacity = self.cutoff(segment_opacity)
    #     return segment_opacity


class Marker(Pen):
    def __init__(self, base_width, base_color):
        super().__init__(base_width, base_color)
        self.segment_length = 3
        self.name = "Marker"

    def get_segment_width(self, speed, tilt, width, pressure, last_width):
        segment_width = 0.9 * (((1 * width)) - 0.4 * tilt) + (0.1 * last_width)
        return segment_width


class Pencil(Pen):
    def __init__(self, base_width, base_color):
        super().__init__(base_width, base_color)
        self.segment_length = 2
        self.name = "Pencil"

    def get_segment_width(self, speed, tilt, width, pressure, last_width):
        segment_width = 0.7 * ((((0.8*self.base_width) + (0.5 * pressure)) * (1 * width)) - (0.25 * tilt**1.8) - (0.6 * speed / 50))
        # segment_width = 1.3*(((self.base_width * 0.4) * pressure) - 0.5 * ((tilt ** 0.5)) + (0.5 * last_width))
        max_width = self.base_width * 10
        segment_width = segment_width if segment_width < max_width else max_width
        return segment_width

    def get_segment_opacity(self, speed, tilt, width, pressure, last_width):
        segment_opacity = (0.1 * -(speed / 35)) + (1 * pressure)
        segment_opacity = self.cutoff(segment_opacity) - 0.1
        return segment_opacity


class Mechanical_Pencil(Pen):
    def __init__(self, base_width, base_color):
        super().__init__(base_width, base_color)
        self.base_width = self.base_width ** 2
        self.base_opacity = 0.7
        self.name = "Mechanical Pencil"


class Brush(Pen):
    def __init__(self, base_width, base_color):
        super().__init__(base_width, base_color)
        self.segment_length = 2
        self.stroke_linecap = "round"
        self.opacity = 1
        self.name = "Brush"

    def get_segment_width(self, speed, tilt, width, pressure, last_width):
        segment_width = 0.7 * (((1 + (1.4 * pressure)) * (1 * width)) - (0.5 * tilt) - (0.5 * speed / 50))  # + (0.2 * last_width)
        return segment_width

    def get_segment_color(self, speed, tilt, width, pressure, last_width):
        intensity = (pressure ** 1.5 - 0.2 * (speed / 50)) * 1.5
        intensity = self.cutoff(intensity)
        # using segment color not opacity because the dots interfere with each other.
        # Color must be 255 rgb
        rev_intensity = abs(intensity - 1)
        segment_color = [int(rev_intensity * (255 - self.base_color[0])),
                         int(rev_intensity * (255 - self.base_color[1])),
                         int(rev_intensity * (255 - self.base_color[2]))]

        return "rgb"+str(tuple(segment_color))


class Highlighter(Pen):
    def __init__(self, base_width, base_color):
        super().__init__(base_width, base_color)
        self.stroke_linecap = "square"
        self.base_opacity = 0.3
        self.stroke_opacity = 0.2
        self.name = "Highlighter"


class Eraser(Pen):
    def __init__(self, base_width, base_color):
        super().__init__(base_width, base_color)
        self.stroke_linecap = "square"
        self.base_width = self.base_width * 2
        self.name = "Eraser"


class Erase_Area(Pen):
    def __init__(self, base_width, base_color):
        super().__init__(base_width, base_color)
        self.stroke_linecap = "square"
        self.base_opacity = 0
        self.name = "Erase Area"


class Caligraphy(Pen):
    def __init__(self, base_width, base_color):
        super().__init__(base_width, base_color)
        self.segment_length = 2
        self.name = "Calligraphy"

    def get_segment_width(self, speed, tilt, width, pressure, last_width):
        segment_width = 0.9 * (((1 + pressure) * (1 * width)) - 0.3 * tilt) + (0.1 * last_width)
        return segment_width
