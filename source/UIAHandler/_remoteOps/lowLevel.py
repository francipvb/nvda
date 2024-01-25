# A part of NonVisual Desktop Access (NVDA)
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2023-2023 NV Access Limited

from __future__ import annotations
from ctypes import (
	oledll,
	byref,
	c_void_p,
	c_long,
	c_ulong,
	c_bool
)
from comtypes.automation import VARIANT
import os
import enum
from UIAHandler import UIA
import NVDAHelper


"""
This module contains classes and constants for the low-level Windows UI Automation Remote Operations API,
I.e. Windows.UI.UIAutomation.core.
The low-level UI Automation Remote Operations API is a binary API
that allows for the execution of special byte code specific to uI Automation,
allowing for the execution of multiple UI Automation operations in a remote provider,
via one cross-process call.
"""


class OperandId(c_ulong):
	"""
	An operand ID is a unique identifier for an operand (or register) in the remote operation VM.
	It is an unsigned 32 bit integer.
	"""

	def __eq__(self, other: object) -> bool:
		if type(other) is OperandId:
			return self.value == other.value
		return False

	def __repr__(self) -> str:
		return f"OperandId {self.value}"


class RelativeOffset(c_long):
	"""
	A relative offset is a signed 32 bit integer that represents an offset from the current instruction pointer.
	"""

	def __repr__(self) -> str:
		return f"RelativeOffset {self.value}"


_dll = oledll[os.path.join(NVDAHelper.versionedLibPath, "UIARemote.dll")]


class RemoteOperationResultSet:
	"""
	Wraps a Windows.UI.UIAutomation.Core.AutomationRemoteOperationResultSet.
	"""

	def __init__(self, pResults: c_void_p):
		if not pResults or not isinstance(pResults, c_void_p):
			raise RuntimeError("Invalid results pointer")
		self._pResults = pResults

	@property
	def errorLocation(self) -> int:
		""" The index of the instruction where the error occured."""
		val = c_long()
		_dll.remoteOpResult_getErrorLocation(self._pResults, byref(val))
		return val.value

	@property
	def extendedError(self) -> int:
		"""
		The error HRESULT produced by the instruction that caused the error.
		"""
		val = c_long()
		_dll.remoteOpResult_getExtendedError(self._pResults, byref(val))
		return val.value

	@property
	def status(self) -> RemoteOperationStatus:
		"""
		The status of the remote operation.
		E.g. success, malformed bytecode, etc.
		"""
		val = c_long()
		_dll.remoteOpResult_getStatus(self._pResults, byref(val))
		return RemoteOperationStatus(val.value)

	def hasOperand(self, operandId: OperandId) -> bool:
		"""
		Returns true if the result set contains an operand with the given ID.
		I.e. The operand was requested as a result before execution,
		and the remote operation successfully produced a value for it.
		"""
		val = c_bool()
		_dll.remoteOpResult_hasOperand(self._pResults, operandId, byref(val))
		return val.value

	def getOperand(self, operandId: OperandId) -> VARIANT:
		"""
		Returns the value of the operand with the given ID.
		In order to succeed,
		the operand must have been requested as a result before execution,
		and the remote operation must have successfully produced a value for it.
		"""
		val = VARIANT()
		_dll.remoteOpResult_getOperand(self._pResults, operandId, byref(val))
		return val

	def __del__(self):
		_dll.remoteOpResult_free(self._pResults)


class RemoteOperation:
	"""
	Creats and wraps a Windows.UI.UIAutomation.Core.CoreAutomationRemoteOperation.
	"""

	def __init__(self):
		self._pRemoteOperation = c_void_p()
		_dll.remoteOp_create(byref(self._pRemoteOperation))

	def importElement(self, operandId: OperandId, element: UIA.IUIAutomationElement):
		"""
		Imports a UI automation element into the remote operation VM at the given operand ID.
		:param operandId: The operand ID to import the element into.
		:param element: The element to import.
		"""
		_dll.remoteOp_importElement(self._pRemoteOperation, operandId, element)

	def importTextRange(self, operandId: OperandId, textRange: UIA.IUIAutomationTextRange):
		"""
		Imports a UI automation text range into the remote operation VM at the given operand ID.
		:param operandId: The operand ID to import the text range into.
		:param textRange: The text range to import.
		"""
		_dll.remoteOp_importTextRange(self._pRemoteOperation, operandId, textRange)

	def addToResults(self, operandId: OperandId):
		"""
		Requests that an operand be made available after execution in the results set.
		:param operandId: The operand ID to add to the results.
		"""
		_dll.remoteOp_addToResults(self._pRemoteOperation, operandId)

	def isOpcodeSupported(self, opcode: InstructionType) -> bool:
		"""
		Returns true if the given opcode (instruction) is supported by the remote operation VM.
		:param opcode: The opcode to check.
		"""
		val = c_bool()
		_dll.remoteOp_isOpcodeSupported(self._pRemoteOperation, opcode, byref(val))
		return val.value

	def execute(self, byteCode: bytes):
		"""
		Executes the given byte code in the remote operation VM.
		:param byteCode: The byte code array to execute.
		"""
		pResults = c_void_p()
		_dll.remoteOp_execute(self._pRemoteOperation, byteCode, len(byteCode), byref(pResults))
		return RemoteOperationResultSet(pResults)

	def __del__(self):
		_dll.remoteOp_free(self._pRemoteOperation)


class RemoteOperationStatus(enum.IntEnum):
	Success = 0
	MalformedBytecode = 1
	InstructionLimitExceeded = 2
	UnhandledException = 3
	ExecutionFailure = 4


class InstructionType(enum.IntEnum):
	Nop = 0x00
	Set = 0x01

	# Control flow
	ForkIfTrue = 0x02
	ForkIfFalse = 0x03
	Fork = 0x04
	Halt = 0x05

	# Loops
	NewLoopBlock = 0x06
	EndLoopBlock = 0x07
	BreakLoop = 0x08
	ContinueLoop = 0x09

	# Error handling
	NewTryBlock = 0x0a
	EndTryBlock = 0x0b
	SetOperationStatus = 0x0c
	GetOperationStatus = 0x0d

	# Arithmetic
	Add = 0x0e
	Subtract = 0x0f
	Multiply = 0x10
	Divide = 0x11
	BinaryAdd = 0x12
	BinarySubtract = 0x13
	BinaryMultiply = 0x14
	BinaryDivide = 0x15

	# Boolean operators
	InPlaceBoolNot = 0x16
	InPlaceBoolAnd = 0x17
	InPlaceBoolOr = 0x18

	BoolNot = 0x19
	BoolAnd = 0x1a
	BoolOr = 0x1b

	# Generic comparison
	Compare = 0x1c

	# New object constructors
	NewInt = 0x1d
	NewUint = 0x1e
	NewBool = 0x1f
	NewDouble = 0x20
	NewChar = 0x21
	NewString = 0x22
	NewPoint = 0x23
	NewRect = 0x24
	NewArray = 0x25
	NewStringMap = 0x26
	NewNull = 0x27

	# Point and Rect methods
	GetPointProperty = 0x28
	GetRectProperty = 0x29

	# RemoteArray methods
	RemoteArrayAppend = 0x2a
	RemoteArraySetAt = 0x2b
	RemoteArrayRemoveAt = 0x2c
	RemoteArrayGetAt = 0x2d
	RemoteArraySize = 0x2e

	# RemoteStringMap methods
	RemoteStringMapInsert = 0x2f
	RemoteStringMapRemove = 0x30
	RemoteStringMapHasKey = 0x31
	RemoteStringMapLookup = 0x32
	RemoteStringMapSize = 0x33

	# RemoteString methods
	RemoteStringGetAt = 0x34
	RemoteStringSubstr = 0x35
	RemoteStringConcat = 0x36
	RemoteStringSize = 0x37

	# UIA element methods
	GetPropertyValue = 0x38
	Navigate = 0x39

	# Type interrogation methods
	IsNull = 0x3a
	IsNotSupported = 0x3b
	IsMixedAttribute = 0x3c
	IsBool = 0x3d
	IsInt = 0x3e
	IsUint = 0x3f
	IsDouble = 0x40
	IsChar = 0x41
	IsString = 0x42
	IsPoint = 0x43
	IsRect = 0x44
	IsArray = 0x45
	IsStringMap = 0x46
	IsElement = 0x47

	# GUID support
	NewGuid = 0x48
	IsGuid = 0x49
	LookupId = 0x4a
	LookupGuid = 0x4b

	# Cache requests
	NewCacheRequest = 0x4c
	IsCacheRequest = 0x4d
	CacheRequestAddProperty = 0x4e
	CacheRequestAddPattern = 0x4f
	PopulateCache = 0x50

	Stringify = 0x51
	GetMetadataValue = 0x52

	# Extensibility
	CallExtension = 0x53
	IsExtensionSupported = 0x54

	# text ranges
	TextRangeClone = 0x271e0103
	TextRangeCompare = 0x271e0104
	TextRangeCompareEndpoints = 0x271e0105
	TextRangeExpandToEnclosingUnit = 0x271e0106
	TextRangeFindAttribute = 0x271e0107
	TextRangeFindText = 0x271e0108,
	TextRangeGetAttributeValue = 0x271e0109
	TextRangeGetBoundingRectangles = 0x271e010a
	TextRangeGetEnclosingElement = 0x271e010b
	TextRangeGetText = 0x271e010c
	TextRangeMove = 0x271e010d
	TextRangeMoveEndpointByUnit = 0x271e010e
	TextRangeMoveEndpointByRange = 0x271e010f
	TextRangeSelect = 0x271e0110
	TextRangeAddToSelection = 0x271e0111
	TextRangeRemoveFromSelection = 0x271e0112
	TextRangeScrollIntoView = 0x271e0113
	TextRangeGetChildren = 0x271e0114
	TextRangeShowContextMenu = 0x271e0115


class ComparisonType(enum.IntEnum):
	Equal = 0
	NotEqual = 1
	GreaterThan = 2
	LessThan = 3
	GreaterThanOrEqual = 4
	LessThanOrEqual = 5


class NavigationDirection(enum.IntEnum):
	Parent = 0
	NextSibling = 1
	PreviousSibling = 2
	FirstChild = 3
	LastChild = 4


class TextUnit(enum.IntEnum):
	Character = 0
	Format = 1
	Word = 2
	Line = 3
	Paragraph = 4
	Page = 5
	Document = 6


class TextPatternRangeEndpoint(enum.IntEnum):
	Start = 0
	End = 1


PropertyId = enum.IntEnum(
	"PropertyId",
	{k[4:-10]: v for k, v in vars(UIA).items() if k.endswith("PropertyId")}
)


AttributeId = enum.IntEnum(
	"AttributeId",
	{k[4:-11]: v for k, v in vars(UIA).items() if k.endswith("AttributeId")}
)

StyleId = enum.IntEnum(
	"StyleId",
	{k[8:]: v for k, v in vars(UIA).items() if k.startswith("StyleId")}
)
