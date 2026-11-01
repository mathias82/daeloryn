"""Open an owner-only Windows audit file without inheriting directory ACLs.

Windows mode bits cannot attest privacy. Check the protected DACL on the open
handle instead; reject existing files with any other DACL or a reparse point.
"""
import ctypes
import os
from ctypes import wintypes


def open_private_append(path):
    if os.name != "nt":
        raise OSError("Windows file API required")
    import msvcrt

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    security = ctypes.WinDLL("advapi32", use_last_error=True)
    pointer = ctypes.c_void_p

    class Attributes(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("descriptor", pointer),
                    ("inherit", wintypes.BOOL)]

    class Tags(ctypes.Structure):
        _fields_ = [("attributes", wintypes.DWORD), ("tag", wintypes.DWORD)]

    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.POINTER(Attributes), wintypes.DWORD,
                                  wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [pointer]
    kernel.LocalFree.restype = pointer
    kernel.GetFileType.argtypes = [wintypes.HANDLE]
    kernel.GetFileType.restype = wintypes.DWORD
    kernel.GetFileInformationByHandleEx.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                   pointer, wintypes.DWORD]
    kernel.GetFileInformationByHandleEx.restype = wintypes.BOOL
    security.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(pointer), pointer]
    security.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL
    security.GetSecurityInfo.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                        wintypes.DWORD, pointer, pointer, pointer,
                                        pointer, ctypes.POINTER(pointer)]
    security.GetSecurityInfo.restype = wintypes.DWORD
    security.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [
        pointer, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(pointer), pointer]
    security.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype = wintypes.BOOL

    # OW is the owner-rights SID. P disables inheritance, including broad
    # permissions inherited from a user's temporary directory.
    private_dacl = "D:P(A;;FA;;;OW)"
    descriptor = pointer()
    if not security.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            private_dacl, 1, ctypes.byref(descriptor), None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        attributes = Attributes(ctypes.sizeof(Attributes), descriptor, False)
        # APPEND_DATA | READ_ATTRIBUTES | READ_CONTROL; share read/write/delete.
        # OPEN_ALWAYS with OPEN_REPARSE_POINT never follows the final symlink.
        handle = kernel.CreateFileW(str(path), 0x20084, 7,
                                    ctypes.byref(attributes), 4, 0x200080, None)
    finally:
        kernel.LocalFree(descriptor)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        tags = Tags()
        if not kernel.GetFileInformationByHandleEx(handle, 9, ctypes.byref(tags),
                                                  ctypes.sizeof(tags)):
            raise ctypes.WinError(ctypes.get_last_error())
        if tags.attributes & 0x400 or kernel.GetFileType(handle) != 1:
            raise PermissionError("receipt must be a regular non-reparse file")
        actual = pointer()
        error = security.GetSecurityInfo(handle, 1, 4, None, None, None, None,
                                         ctypes.byref(actual))
        if error:
            raise ctypes.WinError(error)
        text = pointer()
        try:
            if not security.ConvertSecurityDescriptorToStringSecurityDescriptorW(
                    actual, 1, 4, ctypes.byref(text), None):
                raise ctypes.WinError(ctypes.get_last_error())
            if ctypes.wstring_at(text) != private_dacl:
                raise PermissionError("receipt file must have an owner-only protected DACL")
        finally:
            if text:
                kernel.LocalFree(text)
            kernel.LocalFree(actual)
        fd = msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_APPEND)
        handle = None  # The file descriptor now owns the Windows handle.
        return fd
    finally:
        if handle is not None:
            kernel.CloseHandle(handle)
