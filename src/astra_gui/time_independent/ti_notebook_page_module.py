"""Base class for time-independent notebook pages and helpers."""

import logging
import tkinter as tk
from abc import ABC, abstractmethod
from operator import itemgetter
from pathlib import Path
from tkinter import ttk
from typing import TYPE_CHECKING

import numpy as np

from astra_gui.utils.font_module import bold_font
from astra_gui.utils.notebook_module import NotebookPage
from astra_gui.utils.popup_module import missing_symmetry_popup, required_field_popup, save_success_popup
from astra_gui.utils.scrollable_module import ScrollableFrame, ScrollableTreeview

if TYPE_CHECKING:
    from .time_independent_notebook import TimeIndependentNotebook

logger = logging.getLogger(__name__)


class TiNotebookPage(NotebookPage['TimeIndependentNotebook'], ABC):
    """Shared UI and validation logic for time-independent workflows."""

    cc_syms: list[str] = []
    computed_syms: list[str] = []
    SCRIPT_FILE: Path
    SCRIPT_COMMANDS: list[str]
    KET_SYM_HOVER_TEXT = (
        'Multiplicity and symmetry of ket state (comma separated list).\n'
        'If all symmetries of the group are desired, {Mult}ALL can be used instead.'
    )

    def __init__(self, notebook: 'TimeIndependentNotebook', label: str = '', show_cap_radii: bool = False) -> None:
        self.show_cap_radii_bool = show_cap_radii
        super().__init__(notebook, label, two_screens=True)

    @abstractmethod
    def left_screen_def(self) -> None:
        """Populate the controls that live on the left-hand side."""
        ...

    @abstractmethod
    def get_commands(self) -> str:
        """Return the command string required to run the calculation."""
        ...

    @abstractmethod
    def load(self) -> None:
        """Load persisted data into the widgets."""
        ...

    def right_screen_def(self) -> None:
        """Create the right-hand panels used across TI notebook pages."""
        self.right_screen.pack(side=tk.LEFT, anchor=tk.W, fill=tk.BOTH, expand=True, padx=10)

        left_frame = ttk.Frame(self.right_screen)
        left_frame.pack(side=tk.LEFT, anchor=tk.W, fill=tk.BOTH, expand=True, padx=10)

        symmetries_frame = ttk.Frame(left_frame)
        symmetries_frame.pack(padx=5, pady=5)

        columns = ['Symmetry']
        widths = [100]

        self.syms_tv = ScrollableTreeview(symmetries_frame, columns=columns, show='headings', height=20)
        for col, w in zip(columns, widths):
            self.syms_tv.heading(col, text=col)
            self.syms_tv.column(col, width=w)

        self.syms_tv.pack(side=tk.LEFT)

        # CAP radii and strengths
        cap_frame = ScrollableFrame(left_frame, height=200)

        self.cap_radii_label = ttk.Label(cap_frame.inner_frame, text='CAP radii:')
        self.cap_strenghts_label = ttk.Label(cap_frame.inner_frame, text='CAP strengths:')
        self.cap_radii_label.pack()
        self.cap_strenghts_label.pack()

        if self.show_cap_radii_bool:
            cap_frame.pack()

        right_frame = ttk.Frame(self.right_screen)
        right_frame.pack(side=tk.LEFT, anchor=tk.W, fill=tk.BOTH, expand=True, padx=10)

        ttk.Label(right_frame, text='CC basis', font=bold_font).pack(padx=5, pady=5)

        # Target States
        symmetries_frame = ttk.Frame(right_frame)
        symmetries_frame.pack(padx=5, pady=5)

        columns = ['Index', 'Target States', 'Energy [au]', 'Relative Energy [au]']
        widths = [50, 80, 150, 200]

        self.target_states_tv = ScrollableTreeview(symmetries_frame, columns=columns, show='headings', height=10)
        for col, w in zip(columns, widths):
            self.target_states_tv.heading(col, text=col)
            self.target_states_tv.column(col, width=w)

        self.target_states_tv.pack(side=tk.LEFT)

        # Computed symmetries
        computed_syms_frame = ttk.Frame(right_frame)
        computed_syms_frame.pack(padx=5, pady=5)

        columns = ['Computed Symmetries']
        widths = [200]

        self.computed_syms_tv = ScrollableTreeview(computed_syms_frame, columns=columns, show='headings', height=10)
        for col, w in zip(columns, widths):
            self.computed_syms_tv.heading(col, text=col)
            self.computed_syms_tv.column(col, width=w)

        self.computed_syms_tv.pack(side=tk.LEFT)

    @staticmethod
    def get_caps_from_line(line: str) -> list[str]:
        """Get caps strength list from script line.

        Returns
        -------
        list[str]
            CAP strengths parsed from the command line.
        """
        keyword = '-cap'
        if keyword not in line:
            return []

        caps = NotebookPage.get_keyword_from_line(line, keyword).split(',')
        if len(caps) == 1:
            caps.append('0.0')

        return caps

    @staticmethod
    def get_ecs_params_from_line(line: str) -> list[str]:
        """Get ECS parameters list from script line.

        Returns
        -------
        list[str]
            Radius and angle values if present; empty list otherwise.
        """
        ecs_params = []

        keyword = '-ECSradius'
        if keyword not in line:
            return []
        param = NotebookPage.get_keyword_from_line(line, keyword)
        ecs_params.append(param)

        keyword = '-ECSangle'
        if keyword not in line:
            return []
        param = NotebookPage.get_keyword_from_line(line, keyword)
        ecs_params.append(param)

        return ecs_params

    def show_cap_radii(self, cap_radii: list[str]) -> None:
        """Update the CAP radii label using the provided values."""
        self.cap_radii_label.config(text=f'Cap Radii [au]: {", ".join(cap_radii)}')

    def show_cap_strengths(self, cap_strengths: dict[str, list]) -> None:
        """Update the CAP strengths label with formatted values."""
        text = 'Cap Strengths [au]:\n'
        for state_sym, strengths_list in cap_strengths.items():
            text += f'\n{state_sym}:'
            for strengths in strengths_list:
                text += f'\t{", ".join(strengths)}\n'

        self.cap_strenghts_label.config(text=text)

    def erase_cc_data(self) -> None:
        """Clear CAP and target state tables."""
        for tv in [self.syms_tv, self.computed_syms_tv, self.target_states_tv]:
            for iid in tv.get_children():
                tv.delete(iid)

    def check_ket_sym(
        self,
        ket_syms: str,
        source: str = '',
        check_computed: bool = True,
        new_computed_syms: list[str] | None = None,
    ) -> bool:
        """Validate that requested ket symmetries exist in CC and computed sets.

        Returns
        -------
        bool
            True if all requested symmetries are valid.
        """
        ket_sym_list = self.unpack_all_symmetry(ket_syms.split(','))

        if not new_computed_syms:
            new_computed_syms = []

        for ket_sym in ket_sym_list:
            if ket_sym not in self.cc_syms:
                missing_symmetry_popup(ket_sym, source, root='cc')
                return False

            if check_computed and ket_sym not in self.computed_syms + new_computed_syms:
                missing_symmetry_popup(ket_sym, source, root='computed')
                return False

        return True

    def show_cc_data(self, target_states_data: np.ndarray, open_channels: list[bool]) -> None:
        """Populate the target states table and highlight closed channels."""
        self.show_computed_syms()
        self.target_states_tv.tag_configure(
            'disabled',
            background='light grey',
            foreground='grey',
        )
        for ind, (t_state, occ_chan) in enumerate(zip(target_states_data, open_channels), 1):
            tags = () if occ_chan else ('disabled',)
            self.target_states_tv.insert('', 'end', values=(ind, *t_state), tags=tags)

    def show_computed_syms(self) -> None:
        """Refresh the computed symmetry list from stored values."""
        self.computed_syms = self.get_computed_syms()
        for c_sym in self.pack_all_symmetry(self.computed_syms):
            self.computed_syms_tv.insert('', 'end', values=(c_sym,))

    def print_irrep(self, new_sym: bool = False) -> None:
        """Refresh displayed irreps when the molecular symmetry changes."""
        if new_sym:
            for iid in self.syms_tv.get_children():
                self.syms_tv.delete(iid)
            for irrep in self.sym.irrep[1:]:
                self.syms_tv.insert('', 'end', values=(irrep,))

    def save(self) -> None:
        """Persist the generated script for the current notebook page."""
        if not (commands := self.get_commands()):
            return

        self.save_script(self.SCRIPT_FILE, commands, f'{self.label} calculation', convert_cs_irreps=True)
        save_success_popup(f'{self.label} inputs saved successfully.')

    def run(self) -> None:
        """Execute the notebook script using the shared runner."""
        self.run_script(self.SCRIPT_FILE, self.label.capitalize(), self.SCRIPT_COMMANDS)

    def get_script_lines(self) -> list[str]:
        """Return the saved script lines if a script exists.

        Returns
        -------
        list[str]
            Lines from the stored script, empty list when missing.
        """
        if not self.path_exists(self.SCRIPT_FILE):
            return []

        return self.read_script(self.SCRIPT_FILE, convert_cs_irreps=True)

    def get_computed_syms(self) -> list[str]:
        """Discover symmetries that already have stored close-coupling data.

        Returns
        -------
        list[str]
            Sorted list of symmetry labels with available data.
        """
        assert self.controller.running_directory is not None

        base_path = Path('store/CloseCoupling')
        if not self.path_exists(base_path):
            return []

        computed_sym_folders = []
        if self.ssh_client:
            stdout, _, exit_code = self.ssh_client.run_remote_command(
                f"find '{self.controller.running_directory / base_path}' -mindepth 2 -maxdepth 2 -name aiM -print",
            )
            if exit_code:
                logger.error('Error finding computed symmetries: %d', exit_code)
                return []
            if stdout:
                computed_sym_folders = [Path(line.strip()) for line in stdout.splitlines() if line.strip()]
        else:
            computed_sym_folders = list(Path('store/CloseCoupling').glob('*/aiM'))

        computed_syms = []
        if computed_sym_folders:
            computed_syms = [str(c_sym.parts[-2]) for c_sym in computed_sym_folders]
            computed_syms = [c_sym.replace('p', "'") for c_sym in computed_syms]

            computed_syms = sorted(computed_syms, key=itemgetter(0))  # Sorts the list based on the multiplicity
            computed_syms = sorted(
                computed_syms,
                key=lambda x: self.sym.irrep.index(x[1:]),
            )  # Sorts the list based on the symmetry index

        return computed_syms

    @staticmethod
    def get_caps_from_entries(cap_entries: list[ttk.Entry]) -> list[str]:
        """Extract CAP strengths from entry widgets, defaulting to zero.

        Returns
        -------
        list[str]
            CAP strengths coerced to strings, defaulting to ``'0.0'``.
        """
        caps: list[str] = []
        for cap_entry in cap_entries:
            cap = cap_entry.get().strip()
            if cap:
                caps.append(cap)
            else:
                caps.append('0.0')

        if all(cap == '0.0' for cap in caps):
            required_field_popup('CAP strength(s) for complex calculation')

        return caps

    @staticmethod
    def get_ecs_params_from_entries(ecs_entries: list[ttk.Entry]) -> list[str]:
        """Collect ECS parameters from entry widgets, prompting if missing.

        Returns
        -------
        list[str]
            ECS parameters supplied by the user; empty when missing.
        """
        ecs_params: list[str] = []
        for ecs_entry in ecs_entries:
            ecs_param = ecs_entry.get().strip()
            if ecs_param:
                ecs_params.append(ecs_param)

        if len(ecs_params) == 0:
            required_field_popup('ECS parameters for complex calculation')

        return ecs_params

    @staticmethod
    def add_idle_thread_and_join_lines(lines: list[str]) -> str:
        """Add idle thread number, returning joined commands with a trailing wait.

        Returns
        -------
        str
            Command string with CPU affinity and ``wait`` instructions.
        """
        lines = [f'taskset -c ###(cpu) {line} &' for line in lines] + ['']

        return '\nwait $!\n\n'.join(lines)
