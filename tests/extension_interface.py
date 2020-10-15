import sys

from gextension import Extension

extension_info = {
    "title": "Extension stuff",
    "description": "G-Python test",
    "version": "1.0",
    "author": "sirjonasxx"
}

extension_settings = {
    "use_click_trigger": True,
    "can_leave": True,
    "can_delete": True
}

ext = Extension(extension_info, sys.argv, extension_settings)

def on_connection_start():
    print('Connected with: {}:{}'.format(ext.connection_info['host'], ext.connection_info['port']))
    print(ext.harble_api)

ext.on_event('double_click', lambda: print('Extension has been clicked'))
ext.on_event('init', lambda: print('Initialized with g-earth'))
ext.on_event('connection_start', on_connection_start)
ext.on_event('connection_end', lambda: print('Connection ended'))

ext.start()

print(ext.request_flags())