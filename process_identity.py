"""Best-effort macOS display name; never changes the shared Python install."""
import ctypes
import sys


def set_controller_display_name() -> bool:
    """Name this controller in Activity Monitor without adding a Dock icon.

    macOS exposes this through optional Launch Services symbols, as used by
    libuv and py-setproctitle. Missing symbols must not prevent startup.
    https://github.com/dvarrazzo/py-setproctitle/blob/master/src/darwin_set_process_name.c
    Call once on the main thread, before starting controller workers.
    """
    if sys.platform != "darwin":
        return False
    refs = []
    try:
        cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        services = ctypes.CDLL(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
        )
        pointer = ctypes.c_void_p

        def bind(library, name, result, *arguments):
            function = getattr(library, name)
            function.restype = result
            function.argtypes = list(arguments)
            return function

        make_string = bind(cf, "CFStringCreateWithCString", pointer,
                           pointer, ctypes.c_char_p, ctypes.c_uint32)
        release = bind(cf, "CFRelease", None, pointer)

        def string(value):
            ref = make_string(None, value.encode("utf-8"), 0x08000100)
            if not ref:
                raise ValueError("Could not allocate display name")
            refs.append(ref)
            return ref

        get_bundle = bind(cf, "CFBundleGetBundleWithIdentifier", pointer, pointer)
        bundle = get_bundle(string("com.apple.LaunchServices"))
        if not bundle:
            return False
        get_function = bind(cf, "CFBundleGetFunctionPointerForName", pointer, pointer, pointer)

        def service(name, result, *arguments):
            address = get_function(bundle, string(name))
            if not address:
                raise ValueError("Process display names unavailable")
            return ctypes.CFUNCTYPE(result, *arguments)(address)

        get_asn = service("_LSGetCurrentApplicationASN", pointer)
        check_in = service("_LSApplicationCheckIn", pointer, ctypes.c_int, pointer)
        connect = service("_LSSetApplicationLaunchServicesServerConnectionStatus", None,
                          ctypes.c_uint64, pointer)
        set_name = service("_LSSetApplicationInformationItem", ctypes.c_int,
                           ctypes.c_int, pointer, pointer, pointer, pointer)
        get_data = bind(cf, "CFBundleGetDataPointerForName", pointer, pointer, pointer)
        name_address = get_data(bundle, string("_kLSDisplayNameKey"))
        if not name_address:
            return False
        name_key = pointer.from_address(name_address).value
        if not name_key:
            return False

        main_bundle = bind(cf, "CFBundleGetMainBundle", pointer)()
        info = bind(cf, "CFBundleGetInfoDictionary", pointer, pointer)(main_bundle)
        if not info:
            return False
        settings = bind(cf, "CFDictionaryCreateMutableCopy", pointer,
                        pointer, ctypes.c_long, pointer)(None, 0, info)
        if not settings:
            return False
        refs.append(settings)
        bind(cf, "CFDictionarySetValue", None, pointer, pointer, pointer)(
            settings, string("LSUIElement"), pointer.in_dll(cf, "kCFBooleanTrue").value,
        )
        connect(0, None)
        check_in(-2, settings)
        asn = get_asn()
        return bool(asn and set_name(-2, asn, name_key, string("LLM Launcher"), None) == 0)
    except (AttributeError, OSError, ValueError):
        return False
    finally:
        for ref in reversed(refs):
            release(ref)
