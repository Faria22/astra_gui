"""Time-independent notebook wiring structural, scattering, and PAD pages."""

import logging
import re
from collections import defaultdict
from tkinter import ttk
from typing import TYPE_CHECKING, cast

import numpy as np

from astra_gui.utils.notebook_module import Notebook

from .pad import Pad
from .scatt_states import ScattStates
from .structural import Structural
from .ti_notebook_page_module import TiNotebookPage

if TYPE_CHECKING:
    from astra_gui.app import Astra

logger = logging.getLogger(__name__)


class TimeIndependentNotebook(Notebook[TiNotebookPage]):
    """Coordinate the time-independent calculation pages."""

    def __init__(self, parent: ttk.Frame, controller: 'Astra') -> None:
        """Initialise the notebook and register default pages."""
        super().__init__(parent, controller, 'Run Time Independent Programs')

        self.reset()

        self.add_pages([Structural, ScattStates, Pad])

    def erase_cc_data(self) -> None:
        """Clear stored close-coupling data from every page."""
        for notebook_page in self.pages:
            notebook_page.erase_cc_data()

    def show_cap_radii(self, radii: list[str]) -> None:
        """Propagate CAP radii values to each child page."""
        for notebook_page in self.pages:
            notebook_page.show_cap_radii(radii)

    def get_cap_strengths(self, group_syms: bool = True, return_float: bool = False) -> dict[str, list]:
        """Read CAP strengths from disk and optionally group them by symmetry.

        Returns
        -------
        dict[str, list]
            CAP strengths grouped by symmetry label.
        """
        cap_strengths: dict[str, list] = defaultdict(list)

        state_syms = self.pages[0].get_computed_syms()
        if not state_syms:
            return {}

        mult = state_syms[0][0]

        file_pattern = r'zH_Fullc_Fullc_eval*-*'
        file_pattern_regex = re.compile(r'zH_Fullc_Fullc_eval([-+]?\d*\.\d+D[-+]?\d+)-([-+]?\d*\.\d+D[-+]?\d+)')

        assert self.controller.running_directory is not None, 'Running directory is not set.'
        for state_sym in state_syms:
            state_sym_path = self.pages[0].sym.convert_cs_irreps_to_letter(state_sym)
            base_path = self.controller.running_directory / f'store/CloseCoupling/{state_sym_path}/Full/'

            paths = []
            if self.controller.ssh_client:
                stdout, _, exit_code = self.controller.ssh_client.run_remote_command(
                    f"find '{base_path}' -name {file_pattern} -print",
                )
                if exit_code:
                    logger.warning('Error finding computed cap strengths: %d', exit_code)
                if stdout:
                    paths = stdout.splitlines()
            else:
                paths = list(base_path.glob(file_pattern))

            if paths:
                for path in paths:
                    str_path = str(path).strip()
                    if any(s in str_path for s in ['MinImag', 'MaxImag', 'MinReal', 'MaxReal', 'cropped']):
                        continue

                    match = file_pattern_regex.search(str_path)
                    if match:
                        strengths = match.groups()
                        strengths = []
                        for group in match.groups():
                            strength = group.strip().replace('D', 'e')
                            strength = float(strength)
                            if not return_float:
                                if strength == 0:
                                    strengths.append('0')
                                else:
                                    strengths.append(str(f'{strength:.1e}'))
                            else:
                                strengths.append(strength)
                        cap_strengths[state_sym].append(strengths)

        if group_syms:
            cap_strengths = self.group_cap_strengths_by_sym(cap_strengths, mult=mult)

        return cap_strengths

    def show_cap_strengths(self) -> None:
        """Broadcast CAP strengths to every notebook page."""
        cap_strengths = self.get_cap_strengths()
        for notebook_page in self.pages:
            notebook_page.show_cap_strengths(cap_strengths)

    @staticmethod
    def group_cap_strengths_by_sym(cap_strengths: dict[str, list], mult: str) -> dict[str, list]:
        """Group CAP strengths by symmetry, consolidating shared values.

        Returns
        -------
        dict[str, list]
            CAP strengths reorganised by symmetry, including shared entries.
        """
        new_cap_strengths: dict[str, list] = defaultdict(list)

        all_strengths = []
        other_sym_strengths = defaultdict(list)

        for i_sym, i_strengths_list in cap_strengths.items():
            flag = True
            for i_strengths in i_strengths_list:
                for j_sym, j_strengths_list in cap_strengths.items():
                    if i_sym == j_sym:
                        continue

                    if i_strengths not in j_strengths_list:
                        flag = False
                        if i_strengths not in other_sym_strengths[i_sym]:
                            other_sym_strengths[i_sym].append(i_strengths)

                if flag and i_strengths not in all_strengths:
                    all_strengths.append(i_strengths)

        new_cap_strengths[f'{mult}ALL'] = all_strengths
        return new_cap_strengths | other_sym_strengths

    def show_cc_data(self, cc_syms: list[str], target_states_data: np.ndarray, open_channels: list[bool]) -> None:
        """Update all pages with the latest close-coupling target states."""
        TiNotebookPage.cc_syms = cc_syms
        TiNotebookPage.computed_syms = self.pages[0].get_computed_syms()

        for notebook_page in self.pages:
            notebook_page.show_cc_data(target_states_data, open_channels)

    def reset(self) -> None:
        """Refresh cached close-coupling data and reset each page."""
        create_cc_notebook = self.controller.get_cc_notebook()
        TiNotebookPage.cc_syms = cast(
            list[str],
            create_cc_notebook.cc_data['total_syms'],
        )

        self.erase()
