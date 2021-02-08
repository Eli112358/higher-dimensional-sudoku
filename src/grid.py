from __future__ import annotations

from typing import (
	Iterable,
	Optional,
	TYPE_CHECKING,
	Tuple,
)

import numpy as np

from tuple_util import formula

if TYPE_CHECKING:
	from rendering import Size

Coordinates = Tuple[int, ...]
Flags = Optional[Iterable[str]]


class Regioning:

	def __init__(self, regular: bool = True, size: Size = None):
		self.regular = regular
		self._size = size
		if self.regular:
			self._size = (3, 3)

	def load(self, file):
		# implement later to support irregular sudoku
		pass

	def size(self, scale: Size = (1, 1), extra: Size = (0, 0)):
		return formula(self._size, scale, extra, lambda ss, s, e: (ss * s) + e)


class CellBase:

	def __init__(self, grid: GridBase):
		self.grid = grid


class GridBase:

	def __init__(
			self,
			dimensions: int = 2,
			size: int = 9,
			cell_type: type = CellBase,
	):
		self.dimensions = dimensions
		self.size = size
		self.cells = np.empty([self.size] * self.dimensions, cell_type)
		for cell in self.iterator(op_flags=['writeonly']):
			cell[...] = cell_type(self)

	@property
	def enumerator(self):
		return np.ndenumerate(self.cells)

	def get_coordinates(self, target: CellBase) -> Coordinates:
		for coordinates, cell in self.enumerator:
			if cell == target:
				return coordinates
		raise KeyError('target cell is not in grid')

	def iterator(self, flags: Flags = None, op_flags: Flags = None) -> np.nditer:
		if flags is None:
			flags = ['refs_ok']
		if op_flags is None:
			op_flags = ['readonly']
		return np.nditer(self.cells, flags=flags, op_flags=op_flags)


class Cell(CellBase):
	class Field:
		CANDIDATE = 'candidate'
		CONTINGENCY = 'contingency'

		@staticmethod
		def error(name):
			return ValueError(f'{name} should be one of Cell.Field literals')

	def __init__(self, grid: Grid):
		super().__init__(grid)
		self.candidates = 0
		self.contingencies = 0
		self.given = False
		self.region = None
		self.value = ''

	def set_given(self, value: int):
		self.value = value
		self.given = value != ''

	def set_guess(self, value: int):
		if not self.given:
			self.value = value

	def is_set(self, digit: int, field: Field):
		_field = self.candidates if field is Cell.Field.CANDIDATE else self.contingencies
		return _field & (1 << digit)

	def set(self, digit: int, field: Field):
		bit = 1 << digit
		if field is Cell.Field.CANDIDATE:
			self.candidates &= bit
		elif field is Cell.Field.CONTINGENCY:
			self.contingencies &= bit
		else:
			raise Cell.Field.error('field')

	def clear(self, digit: int, field: Field):
		if self.is_set(digit, field):
			self.toggle(digit, field)

	def toggle(self, digit: int, field: Field):
		bit = 1 << digit
		if field is Cell.Field.CANDIDATE:
			self.candidates ^= bit
		elif field is Cell.Field.CONTINGENCY:
			self.contingencies ^= bit
		else:
			raise Cell.Field.error('field')


class Grid(GridBase):

	def __init__(
			self,
			dimensions: int = 2,
			regioning: Regioning = Regioning(),
	):
		self.regioning = regioning
		size = self.regioning.size()[0] * self.regioning.size()[1]
		super().__init__(dimensions, size, Cell)
