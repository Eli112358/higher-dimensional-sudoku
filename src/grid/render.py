from __future__ import annotations

from asyncio import new_event_loop
from concurrent.futures.thread import ThreadPoolExecutor
from enum import auto
from typing import (
	ForwardRef,
	Optional,
	TYPE_CHECKING,
	Union,
)

from pygame import (
	Color,
	Rect,
	SRCALPHA,
	Surface,
	draw as drawing,
)

from grid import (
	Cell,
	Grid,
	Regioning,
)
from grid.sudoku import SudokuCell
from rendering import (
	Colors,
	Rendering,
	Size,
)
from rendering.graphics import (
	blit_center,
	center,
	render_text,
)
from util.enums import AutoName

if TYPE_CHECKING:
	from rendering.renderer import Renderer


class PencilMarks:
	formulae = [
		('m', 'm'),
		('d.w-m-s.w', 'm'),
		('m', 'd.h-m-s.h'),
		('d.w-m-s.w', 'd.h-m-s.h'),
		('c.x', 'm'),
		('c.x', 'd.h-m-s.h'),
		('m', 'c.y'),
		('d.w-m-s.w', 'c.y'),
		('c.x-m', 'c.y'),
		('c.x+m', 'c.y'),
	]

	def __init__(self, size: Size):
		self.center = Surface(size, flags=SRCALPHA)
		self.corner = Surface(size, flags=SRCALPHA)

	def corner_coordinates(self, texts: list[Surface], margin: Optional[int] = 5) -> list[Rect]:
		coordinates = []
		m = margin
		d = self.corner.get_rect()  # d for destination
		for i, t in enumerate(texts):
			c = center(t, self.corner)
			s = t.get_rect()  # s for source
			formula = PencilMarks.formulae[i]
			coord = [eval(f, loc) for loc in (locals(),) for f in formula]
			coordinates.append(Rect(*coord, 0, 0))
		return coordinates

	def render(self, cell: ForwardRef('CellRenderer')):
		digits_corner = cell.cell.convert(SudokuCell.Field.CONTINGENCY)
		digits_center = cell.cell.convert(SudokuCell.Field.CANDIDATE)
		texts_corner = [render_text(cell.font, str(n), 20, cell.color) for n in digits_corner]
		text_center = render_text(cell.font, ''.join(str(n) for n in digits_center), 25, cell.color)
		coord_corner = self.corner_coordinates(texts_corner)
		self.center.fill(Colors.EMPTY)
		self.corner.fill(Colors.EMPTY)
		blit_center(text_center, self.center)
		self.corner.blits(list(zip(texts_corner, coord_corner)), False)


class CellRenderer(Cell):

	def __init__(self, grid: ForwardRef('GridRenderer')):
		super().__init__(grid)
		self.colors = [Colors.PENCIL, Colors.BLACK]
		self.interacted = False
		self.ready = False
		self.selected = False
		self.background = Surface(self.size, flags=SRCALPHA)
		self.border = Surface(self.size, flags=SRCALPHA)
		self.selection = Surface(self.size, flags=SRCALPHA)
		self.value = Surface(self.size, flags=SRCALPHA)
		self.pencil_marks = PencilMarks(self.size)
		width = self.rendering.width
		size = self.rendering.cell_size
		drawing.rect(self.border, Colors.BLACK, (0, 0, size, size), width)
		self.selection.fill(Colors.SELECTED)

	@property
	def renderer(self) -> Renderer:
		self.grid: GridRenderer
		return self.grid.renderer

	@property
	def rendering(self) -> Rendering:
		return self.renderer.rendering

	@property
	def cell(self) -> SudokuCell:
		return self.renderer.get_cell(self)

	@property
	def color(self) -> Color:
		return self.colors[int(self.cell.given)]

	@property
	def font(self) -> str:
		return self.rendering.font

	@property
	def size(self) -> tuple[int, int]:
		return self.rendering.size()

	def render(self):
		if not self.renderer.game.running:
			return
		self.ready = False
		self.pencil_marks.render(self)
		self.background.fill(Colors.WHITE)
		self.value.fill(Colors.EMPTY)
		blit_center(render_text(self.font, str(self.cell.value), 50, self.color), self.value)
		surfs = [self.border]
		if self.cell.value == '':
			if self.cell.candidates > 0:
				surfs.append(self.pencil_marks.center)
			if self.cell.contingencies > 0:
				surfs.append(self.pencil_marks.corner)
		else:
			surfs.append(self.value)
		if self.selected:
			surfs.append(self.selection)
		for s in surfs:
			if not self.renderer.game.running:
				return
			self.background.blit(s, (0, 0))
		self.ready = True


class GridRenderer(Grid):
	class Clearable(str, AutoName):
		INTERACTIONS = auto()
		SELECTIONS = auto()

		@staticmethod
		def error(name: str):
			ValueError(f'{name} must be one of GridRenderer.Clearable literals')

	def __init__(
			self,
			renderer: Renderer,
			top_left: tuple[int, int],
			regioning: Union[int, Regioning],
	):
		self.renderer = renderer
		super().__init__(2, regioning, CellRenderer)
		self.executor = ThreadPoolExecutor()
		self.loop = new_event_loop()
		margin = self.renderer.grid.regioning.size(extra=(1, 1))
		size_calc = self.renderer.rendering.size(self.size, margin=margin)
		self.surface = Surface(size_calc, flags=SRCALPHA)
		x, y, l, w = top_left + size_calc
		self.rect = Rect(x, y, w + x, l + y)

	def clear(self, target: Clearable):
		for cell in self.iterator():
			if target == GridRenderer.Clearable.INTERACTIONS:
				cell[()].interacted = False
			elif target == GridRenderer.Clearable.SELECTIONS:
				cell[()].selected = False
			else:
				raise GridRenderer.Clearable.error('target')

	def render(self):
		for cell in self.iterator():
			if not self.renderer.game.running:
				return
			self.loop.run_in_executor(self.executor, cell[()].render)
		size = self.renderer.rendering.size
		for coord, cell in self.enumerator:
			if not self.renderer.game.running:
				return
			if cell.ready:
				self.surface.blit(cell.background, Rect(*size(coord), *cell.background.get_rect().size))
