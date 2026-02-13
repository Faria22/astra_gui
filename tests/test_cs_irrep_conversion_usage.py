"""Tests for Cs irrep conversion usage in TI modules."""

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

try:
    from astra_gui.time_independent.pad import Pad
    from astra_gui.time_independent.scatt_states import ScattStates
    from astra_gui.time_independent.time_independent_notebook import TimeIndependentNotebook
    from astra_gui.utils.symmetry_module import Symmetry
except ModuleNotFoundError:
    SRC_PATH = Path(__file__).resolve().parents[1] / 'src'
    if str(SRC_PATH) not in sys.path:
        sys.path.insert(0, str(SRC_PATH))
    from astra_gui.time_independent.pad import Pad
    from astra_gui.time_independent.scatt_states import ScattStates
    from astra_gui.time_independent.time_independent_notebook import TimeIndependentNotebook
    from astra_gui.utils.symmetry_module import Symmetry


def test_get_computed_syms_converts_ap_folders_to_apostrophes(monkeypatch: Any) -> None:
    """Computed symmetry folders should map Ap/App back to A'/A'' labels."""
    page = cast(Any, Pad.__new__(Pad))
    page.controller = SimpleNamespace(running_directory=Path('/tmp/rundir'))
    page.ssh_client = None
    page.sym = Symmetry('Cs')
    page.path_exists = lambda _path: True

    def fake_glob(_self: Path, _pattern: str) -> list[Path]:
        return [
            Path('store/CloseCoupling/1Ap/aiM'),
            Path('store/CloseCoupling/1App/aiM'),
        ]

    monkeypatch.setattr(Path, 'glob', fake_glob)

    assert page.get_computed_syms() == ["1A'", "1A''"]


def test_pad_checks_close_coupling_paths_with_letter_irrep(monkeypatch: Any) -> None:
    """PAD path checks should use Ap/App folder naming for Cs."""
    page = cast(Any, Pad.__new__(Pad))
    page.sym = Symmetry('Cs')
    page.ket_sym_entry = object()
    page.get_text_from_widget = lambda _widget: "1A'"
    page.check_ket_sym = lambda _ket_sym: True

    checked_paths: list[str] = []

    def fake_path_exists(path: Path) -> bool:
        checked_paths.append(str(path))
        return False

    page.path_exists = fake_path_exists
    monkeypatch.setattr('astra_gui.time_independent.pad.missing_required_calculation_popup', lambda *_args: None)

    assert not page.get_commands()
    assert checked_paths == ['store/CloseCoupling/1Ap/Full/Scattering_States']


def test_scatt_states_checks_close_coupling_paths_with_letter_irrep(monkeypatch: Any) -> None:
    """Scattering-state path checks should use Ap/App folder naming for Cs."""
    page = cast(Any, ScattStates.__new__(ScattStates))
    page.sym = Symmetry('Cs')
    page.ket_sym_entry = object()
    page.get_text_from_widget = lambda _widget: "1A''"
    page.check_ket_sym = lambda _ket_sym: True
    page.unpack_all_symmetry = lambda syms: syms

    checked_paths: list[str] = []

    def fake_path_exists(path: Path) -> bool:
        checked_paths.append(str(path))
        return False

    page.path_exists = fake_path_exists
    monkeypatch.setattr(
        'astra_gui.time_independent.scatt_states.missing_required_calculation_popup',
        lambda *_args: None,
    )

    assert not page.get_commands()
    assert checked_paths == ['store/CloseCoupling/1App/Full/H_Fullc_Fullc_eval']


def test_time_independent_notebook_cap_lookup_uses_letter_irrep_in_paths() -> None:
    """CAP lookup should query folder paths using Ap/App for Cs groups."""

    class FakeSshClient:
        def __init__(self) -> None:
            self.commands: list[str] = []

        def run_remote_command(self, command: str) -> tuple[str, str, int]:
            self.commands.append(command)
            return '', '', 0

    fake_ssh = FakeSshClient()
    page = SimpleNamespace(
        get_computed_syms=lambda: ["1A'"],
        sym=Symmetry('Cs'),
    )
    notebook = cast(Any, TimeIndependentNotebook.__new__(TimeIndependentNotebook))
    notebook.pages = [page]
    notebook.controller = SimpleNamespace(
        running_directory=Path('/tmp/rundir'),
        ssh_client=fake_ssh,
    )

    assert notebook.get_cap_strengths(group_syms=False) == {}
    assert fake_ssh.commands
    assert '/store/CloseCoupling/1Ap/Full' in fake_ssh.commands[0]
