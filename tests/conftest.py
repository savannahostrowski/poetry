import os
import shutil
import tempfile

import httpretty
import pytest

try:
    import urllib.parse as urlparse
except ImportError:
    import urlparse

from tomlkit import parse

from poetry.config.config import Config
from poetry.utils._compat import PY2
from poetry.utils._compat import WINDOWS
from poetry.utils._compat import Path
from poetry.utils.helpers import merge_dicts
from poetry.utils.toml_file import TomlFile


@pytest.fixture
def config_document():
    content = """cache-dir = "/foo"
"""
    doc = parse(content)

    return doc


@pytest.fixture
def config_source(config_document, mocker):
    file = TomlFile(Path(tempfile.mktemp()))
    mocker.patch.object(file, "exists", return_value=True)
    mocker.patch.object(file, "read", return_value=config_document)
    mocker.patch.object(
        file, "write", return_value=lambda new: merge_dicts(config_document, new)
    )
    mocker.patch(
        "poetry.config.config_source.ConfigSource.file",
        new_callable=mocker.PropertyMock,
        return_value=file,
    )


@pytest.fixture
def config(config_source):
    c = Config()

    return c


def mock_clone(_, source, dest):
    # Checking source to determine which folder we need to copy
    parts = urlparse.urlparse(source)

    folder = (
        Path(__file__).parent.parent
        / "fixtures"
        / "git"
        / parts.netloc
        / parts.path.lstrip("/").rstrip(".git")
    )

    if dest.exists():
        shutil.rmtree(str(dest))

    shutil.rmtree(str(dest))
    shutil.copytree(str(folder), str(dest))


def mock_download(self, url, dest):
    parts = urlparse.urlparse(url)

    fixtures = Path(__file__).parent / "fixtures"
    fixture = fixtures / parts.path.lstrip("/")

    if dest.exists():
        os.unlink(str(dest))

    # Python2 does not support os.symlink on Windows whereas Python3 does.  os.symlink requires either administrative
    # privileges or developer mode on Win10, throwing an OSError is neither is active.
    if WINDOWS:
        if PY2:
            shutil.copyfile(str(fixture), str(dest))
        else:
            try:
                os.symlink(str(fixture), str(dest))
            except OSError:
                shutil.copyfile(str(fixture), str(dest))
    else:
        os.symlink(str(fixture), str(dest))


@pytest.fixture(autouse=True)
def download_mock(mocker):
    # Patch download to not download anything but to just copy from fixtures
    mocker.patch("poetry.utils.inspector.Inspector.download", new=mock_download)


@pytest.fixture
def environ():
    original_environ = dict(os.environ)

    yield

    os.environ.clear()
    os.environ.update(original_environ)


@pytest.fixture(autouse=True)
def git_mock(mocker):
    # Patch git module to not actually clone projects
    mocker.patch("poetry.vcs.git.Git.clone", new=mock_clone)
    mocker.patch("poetry.vcs.git.Git.checkout", new=lambda *_: None)
    p = mocker.patch("poetry.vcs.git.Git.rev_parse")
    p.return_value = "9cf87a285a2d3fbb0b9fa621997b3acc3631ed24"


@pytest.fixture
def http():
    httpretty.enable()

    yield httpretty

    httpretty.disable()


@pytest.fixture
def fixture_dir():
    def _fixture_dir(name):
        return Path(__file__).parent / "fixtures" / name

    return _fixture_dir


@pytest.fixture
def tmp_dir():
    dir_ = tempfile.mkdtemp(prefix="poetry_")

    yield dir_

    shutil.rmtree(dir_)