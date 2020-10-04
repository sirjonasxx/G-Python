import sys

from gextension import Extension


extension_info = {
    "title": "G-Python",
    "description": "Test python extension",
    "version": "1.0",
    "author": "sirjonasxx"
}

extension = Extension(extension_info, sys.argv, None)
extension.start()
