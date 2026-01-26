"""Test package initialization and imports."""

import sys


def test_package_version():
    """Verify package version is accessible."""
    from mamba import __version__

    assert __version__ == "1.0.0"


def test_python_version():
    """Verify Python version meets minimum requirement (>=3.11)."""
    assert sys.version_info >= (3, 11), "Python 3.11+ is required"


def test_subpackages_importable():
    """Verify all subpackages are importable."""
    import mamba.api
    import mamba.api.handlers
    import mamba.core
    import mamba.middleware
    import mamba.models
    import mamba.utils

    assert mamba.api is not None
    assert mamba.api.handlers is not None
    assert mamba.core is not None
    assert mamba.middleware is not None
    assert mamba.models is not None
    assert mamba.utils is not None
