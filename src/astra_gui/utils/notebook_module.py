"""Shared notebook page infrastructure and supporting utilities."""

import getpass
import logging
import re
import shutil
import subprocess
import threading
import time
import tkinter as tk
from abc import ABC, abstractmethod
from collections import defaultdict
from pathlib import Path
from platform import system
from tkinter import ttk
from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast

import psutil

from .font_module import back_button_font, title_font
from .hover_widget_module import HoverWidgetClass
from .logger_module import log_operation
from .popup_module import (
    calculation_is_running_popup,
    completed_calculation_popup,
    idle_processor_popup,
    invalid_input_popup,
    missing_script_file_popup,
    required_field_popup,
)
from .symmetry_module import Symmetry

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from astra_gui.app import Astra

NbP = TypeVar('NbP', bound='NotebookPage')
Nb = TypeVar('Nb', bound='Notebook')


class NotebookPage(ttk.Frame, ABC, Generic[Nb]):
    """Base class for GUI notebook pages that share persistence helpers."""

    sym = Symmetry('C1')
    SAVE_BUTTON_PADY = (10, 0)

    def __init__(self, notebook: Nb, label: str = '', two_screens: bool = False) -> None:
        super().__init__(notebook, width=50)
        self.label = label
        self.grid_propagate(False)
        self.notebook = notebook
        self.controller = notebook.controller
        self.ssh_client = notebook.controller.ssh_client
        self.notification = notebook.controller.notification

        self.save_button = ttk.Button(self, text='Save', command=self.save)
        self.run_button = ttk.Button(self, text='Run', command=self.run)

        if two_screens:
            self.left_screen = ttk.Frame(self)
            self.left_screen.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=15)

            self.save_button = ttk.Button(self.left_screen, text='Save', command=self.save)
            self.run_button = ttk.Button(self.left_screen, text='Run', command=self.run)

            self.right_screen = ttk.Frame(self)
            self.right_screen.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=15)

            self.left_screen_def()
            self.right_screen_def()

    def left_screen_def(self) -> None:
        """Populate the widgets that appear on the left-hand side."""

    def right_screen_def(self) -> None:
        """Populate the widgets that appear on the right-hand side."""

    @abstractmethod
    def erase(self) -> None:
        """Clear and reset the page state."""
        ...

    @abstractmethod
    def save(self) -> None:
        """Persist the page state to disk."""
        ...

    @abstractmethod
    def load(self) -> None:
        """Load any persisted state into the UI."""
        ...

    @abstractmethod
    def run(self) -> None:
        """Execute the associated calculation or script."""
        ...

    @abstractmethod
    def print_irrep(self, _new_sym: bool = False) -> None:
        """Handle updates when the molecular symmetry changes."""
        ...

    @abstractmethod
    def get_outputs(self) -> None:
        """Refresh any outputs produced by the calculation."""
        ...

    @staticmethod
    def find_line_ind(lines: list[str], string: str) -> int | None:
        """Find the first index of the line with `string` inside.

        Returns
        -------
        int | None
            Index of the matching line, or ``None`` if not found.
        """
        for i, line in enumerate(lines):
            if string in line:
                return i
        return None

    @staticmethod
    def get_value_from_lines(lines: list[str], string: str, shift: int = 1) -> str:
        """Return the line that appears `shift` rows after the target string.

        Returns
        -------
        str
            Matching line or an empty string when the key is absent.
        """
        if (ind := NotebookPage.find_line_ind(lines, string)) is not None:
            return lines[ind + shift]
        return ''

    @staticmethod
    def get_keyword_from_line(line: str, keyword: str) -> str:
        """Get keyword value from script line.

        Returns
        -------
        str
            Token immediately following the keyword.
        """
        return line.split(keyword)[1].strip().split()[0].strip()

    @staticmethod
    def get_text_from_widget(entry: ttk.Entry | ttk.Combobox) -> str:
        """Return the text from an entry or combobox.

        Returns
        -------
        str
            Stripped widget text.
        """
        return entry.get().strip()

    @staticmethod
    def check_field_entries(
        required_fields: list[tuple[str, ttk.Entry | ttk.Combobox, type]],
    ) -> dict[str, str | int | float]:
        """Validate required widgets and return their parsed values when successful.

        Returns
        -------
        dict[str, str | int | float]
            Validated field values keyed by field name; empty dict if validation fails.
        """
        field_entries: dict[str, str | int | float] = {}
        for field, widget, type_ in required_fields:
            field_entries[field] = NotebookPage.get_text_from_widget(widget)

            if not field_entries[field]:
                required_field_popup(field)
                return {}

            try:
                temp_entry = type_(field_entries[field])

                # Check if the value is a valid integer
                if type_ is int and str(int(field_entries[field])) != field_entries[field]:
                    raise ValueError  # noqa: TRY301
            except ValueError:
                if type_ is float:
                    type_str = 'real'
                elif type_ is int:
                    type_str = 'integer'
                else:
                    type_str = 'string'

                invalid_input_popup(f'{field} must be a {type_str} value.')
                return {}
            else:
                field_entries[field] = temp_entry

        return field_entries

    def unpack_all_symmetry(self, sym_list: list[str]) -> list[str]:
        """Expand shorthand entries such as '2ALL' into explicit irreps.

        Returns
        -------
        list[str]
            Expanded list containing individual symmetry labels.
        """
        unpacked_list: list[str] = []
        for sym in sym_list:
            if 'all' in sym.lower():
                mult = sym.lower().replace('all', '')
                unpacked_list.extend([f'{mult}{irrep}' for irrep in self.sym.irrep[1:]])
            else:
                unpacked_list.append(sym)

        return unpacked_list

    def pack_all_symmetry(self, sym_list: list[str]) -> list[str]:
        """Collapse full irrep sets back into the shorthand `ALL` tokens.

        Returns
        -------
        list[str]
            Symmetry labels with sequences replaced by ``ALL``.
        """
        packed_list: list[str] = []

        # Dictionary where the key is the multiplicity and the value is the number of symmetries with that multiplicity
        mult_dict: dict[str, list[str]] = defaultdict(list)
        for sym in sym_list:
            mult_dict[sym[0]].append(sym[1:])

        for mult, syms in mult_dict.items():
            if len(syms) == len(self.sym.irrep) - 1:
                packed_list.append(f'{mult}ALL')
            else:
                packed_list.extend([f'{mult}{sym}' for sym in syms])

        return packed_list

    @staticmethod
    def convert_cs_irreps(string: str) -> str:
        """Convert A' (A'') to Ap (App) or vice-versa.

        Returns
        -------
        str
            Converted representation string.
        """
        if "A'" in string:
            return string.replace("A''", 'App').replace("A'", 'Ap')

        return string.replace('App', "A''").replace('Ap', "A'")

    @staticmethod
    def hover_widget(
        widget_class: type[ttk.Widget],
        frame: ttk.Frame,
        hover_text: str = '',
        **kwargs,
    ) -> ttk.Widget:
        """Return a widget with hover text.

        Returns
        -------
        ttk.Widget
            Instantiated widget with hover tooltip behaviour.
        """
        return HoverWidgetClass(widget_class, frame, hover_text, **kwargs).widget

    @staticmethod
    def get_widget_from_grid(
        frame: ttk.Frame,
        row: int,
        col: int,
    ) -> tk.Widget | None:
        """
        Get the widget at a specific grid position.

        Assumes only one widget per grid location.
        Could be changed to check if multiple widgets in the same location and return list[tk.Widget] | tk.Widget

        Returns
        -------
        tk.Widget | None
            Widget occupying the grid position, or ``None`` if empty.
        """
        if widgets := frame.grid_slaves(row=row, column=col):
            return widgets[0]
        return None

    def first_idle_cpu(self) -> tuple[str, int | None]:
        """Find the first 98% idle CPU, or the CPU with the highest idle percentage.

        Returns
        -------
        tuple[str, int | None]
            CPU identifier and optional idle percentage.
        """

        def get_cpu_stats_data() -> list[str]:
            """Return the file lines if the file exists.

            Returns
            -------
            list[str]
                Contents of ``/proc/stat`` split into lines.
            """
            proc_stat_file = '/proc/stat'
            lines = []
            if self.ssh_client:
                stdout, _, exit_status = self.ssh_client.run_remote_command(
                    f'cat {proc_stat_file}',
                )
                if exit_status != 0 or not stdout:
                    logger.error('Failed to get %s.', proc_stat_file)
                    return []
                lines = stdout.split('\n')
            else:
                try:
                    lines = Path(proc_stat_file).read_text().split('\n')
                except FileNotFoundError:
                    if system() == 'Darwin':
                        logger.warning(
                            '%s not found. Expected behaviour in MacOs',
                            proc_stat_file,
                        )
                        return []

                    logger.error('%s file not found!', proc_stat_file)

            if len(lines) == 0:
                logger.error('%s is empty!', proc_stat_file)

            return lines

        def get_cpu_stats() -> list[tuple[str, int, int]]:
            """Get CPU stats from /proc/stat.

            Returns
            -------
            list[tuple[str, int, int]]
                CPU name along with total and idle tick counts.
            """
            stats: list[tuple[str, int, int]] = []

            data = get_cpu_stats_data()

            for line in data:
                if line.startswith('cpu') and len(line.split()) > 2:  # noqa: PLR2004
                    parts = line.split()
                    cpu = parts[0].replace('cpu', '')
                    total = sum(int(x) for x in parts[1:9])
                    idle = int(parts[4])
                    stats.append((cpu, total, idle))

            return stats

        idle_threshold = 98
        min_cpu = 10  # Smallest thread number to be used (to avoid using threads used by background processes)
        # Get initial CPU stats
        stats1 = get_cpu_stats()
        if len(stats1) == 0:  # MacOs case
            return '0', None

        # Interval in seconds between the checking of thread utilization
        time.sleep(0.5)

        # Get CPU stats again after the interval
        stats2 = get_cpu_stats()

        highest_idle_cpu = '0'
        highest_idle_percentage = -1  # Starts with an impossible idle percentage

        # Compare stats over the interval
        for cpu1, total1, idle1 in stats1:
            # Find corresponding CPU stats in the second sample
            cpu2_data = next((total, idle) for cpu, total, idle in stats2 if cpu == cpu1)

            cpu1_ind = cpu1.replace('cpu', '')
            if not cpu1_ind:
                continue

            if int(cpu1_ind) < min_cpu:
                continue

            if cpu2_data:
                total2, idle2 = cpu2_data
                total_diff = total2 - total1
                idle_diff = idle2 - idle1
                idle_percent = int((idle_diff / total_diff) * 100)

                # Check if this CPU has a high idle percentage
                if idle_percent >= idle_threshold:
                    return cpu1_ind, None  # Return the CPU with high idle percentage

                # Track the CPU with the highest idle percentage
                if idle_percent > highest_idle_percentage:
                    highest_idle_percentage = idle_percent
                    highest_idle_cpu = cpu1_ind

        # Return the CPU with the highest idle percentage if no CPU reaches 98%
        return highest_idle_cpu, highest_idle_percentage

    def save_script(
        self,
        file_name: Path,
        commands: str | dict[str, Any],
        name: str,
        source_file: Path | None = None,
        update_statusbar: bool = True,
        convert_cs_irreps: bool = False,
    ) -> None:
        """Save the "file" script and updates the status bar for 2 seconds."""
        idle_cpu, cpu_idle_percentage = self.first_idle_cpu()
        flag = True
        if cpu_idle_percentage:
            # Asks the user if they want to run the code even if there is no idle processor
            flag = idle_processor_popup(idle_cpu, cpu_idle_percentage)

        # If the user chooses not to run the program, this function quits
        if not flag:
            return

        if not source_file:
            source_file = Path('run_script.sh')

        if isinstance(commands, str):
            commands = commands.replace('###(cpu)', idle_cpu)
            data = {'commands': commands}
        else:
            data = commands | {'cpu': idle_cpu}

        if self.notification.string:
            data['notification'] = self.notification.command(name)

        self.save_file(
            source_file,
            data,
            new_file_name=file_name,
            update_statusbar=update_statusbar,
            convert_cs_irreps=convert_cs_irreps,
        )
        if self.ssh_client:
            self.ssh_client.run_remote_command(
                f'cd {self.controller.running_directory} && chmod +x {file_name}',
            )
        else:
            subprocess.run(f'chmod +x {file_name}'.split(), check=False)

    @log_operation('saving file')
    def save_file(
        self,
        file_name: Path,
        data: dict,
        key_symbol: str = '#',
        new_file_name: Path | None = None,
        blank_lines: bool = True,
        update_statusbar: bool = True,
        convert_cs_irreps: bool = False,
    ) -> None:
        """Fill a template file with data and write it to disk or the remote host."""
        if self.controller.running_directory is None:
            raise RuntimeError('No directory was selected')

        template_file = self.controller.astra_gui_path / 'input_file_templates' / file_name

        with template_file.open('r') as f:
            content = f.read()

        filled_content = re.sub(
            rf'{re.escape(key_symbol) * 3}\((.*?)\)',
            lambda match: str(data.get(match.group(1), match.group(0))),
            content,
        )

        if not blank_lines:
            lines = filled_content.split('\n')
            lines = [line for line in lines if line.strip()]
            filled_content = '\n'.join(lines) + '\n'

        if convert_cs_irreps:
            filled_content = self.convert_cs_irreps(filled_content)

        if not new_file_name:
            new_file_name = file_name

        if self.ssh_client:
            self.ssh_client.write_to_file(
                self.controller.running_directory / new_file_name,
                filled_content,
            )
        else:
            with new_file_name.open('w') as f:
                f.write(filled_content)

        # Shows that the file was saved in the status bar
        if update_statusbar:
            self.controller.statusbar.show_message(f'{new_file_name} saved!', time=2)

    def save_file_from_blank(self, file_name: Path, lines: str, update_statusbar: bool = True) -> None:
        """Write plain text to a file using the blank template helper."""
        self.save_file(
            'blank_file',
            {'lines': lines},
            new_file_name=file_name,
            blank_lines=True,
            update_statusbar=update_statusbar,
        )

    def remove_path(self, path: Path) -> None:
        """Delete a file or directory locally or on the remote host."""
        if self.ssh_client:
            self.ssh_client.run_remote_command(
                f'rm -rf {self.controller.running_directory}/{path}',
            )
        elif not path.exists():
            return
        elif path.is_file():
            path.unlink(missing_ok=True)
        else:
            shutil.rmtree(path)

    def error_function(self) -> tuple[bool | None, str | None]:  # noqa: PLR6301
        """Check if calculation ran successfully, if not, handle it.

        Returns
        -------
        tuple[bool | None, str | None]
            Success flag and optional error message.
        """
        # To be overwritten by the necessary notebook pages
        return None, ''

    def show_completed_popup(self, script_name: str) -> None:
        """Show a completion popup once a background script finishes."""
        success, error = None, None

        success, error = self.error_function()

        if success:
            popup_message = f'{script_name} finished running successfully!'
        elif success is False:
            popup_message = f'{script_name} crashed \n Error:\n {error}'
        else:
            popup_message = f'{script_name} finished running.'

        completed_calculation_popup(popup_message)
        self.get_outputs()

    @log_operation('running script')
    def run_script(
        self,
        script_path: Path,
        script_name: str,
        script_commands: list[str],
    ) -> None:
        """Run the script and gives a pop up once the script is done."""

        def run_subprocess() -> None:
            def check_programs_helper(script_name: str) -> None:
                run.append(calculation_is_running_popup(script_name))

            run = []

            self.remove_path(Path('nohup.out'))
            self.remove_path(Path('.completed'))

            if not self.path_exists(script_path):
                self.controller.after(0, lambda: missing_script_file_popup(script_name))
                return

            logger.info('Background run requested: %s (%s)', script_name, script_path)

            if self.check_running_programs(script_commands):
                self.controller.after(0, lambda: check_programs_helper(script_name))
                if not run:
                    return
                if not run[0]:
                    return

            if self.ssh_client:
                remote_command = (
                    f'cd {self.controller.running_directory} && bash -l -c "nohup ./{script_path} > nohup.out 2>&1 &"'
                )
                logger.info('Background run (remote): %s', remote_command)
                stdout, stderr, exit_code = self.ssh_client.run_remote_command(remote_command)
                if stdout:
                    logger.debug('Background run remote stdout: %s', stdout)
                if exit_code != 0:
                    logger.error(
                        'Background run failed: %s (exit %s, stderr: %s)',
                        script_name,
                        exit_code,
                        stderr or stdout,
                    )
                    return
                logger.debug('Background run sentinel wait started: %s', script_name)
                while not self.path_exists(Path('.completed')):
                    time.sleep(1)
                logger.debug('Background run sentinel detected: %s', script_name)
            else:
                launch_command = f'nohup ./{script_path} &'
                logger.info('Background run (local): %s', launch_command)
                result = subprocess.run(
                    launch_command.split(),
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.stdout.strip():
                    logger.debug('Background run launcher stdout: %s', result.stdout.strip())
                if result.stderr.strip():
                    logger.debug('Background run launcher stderr: %s', result.stderr.strip())
                if result.returncode != 0:
                    logger.error(
                        'Background run failed: %s (exit %s)',
                        script_name,
                        result.returncode,
                    )
                    return

            self.controller.after(
                0,
                lambda: self.show_completed_popup(script_name),
            )  # Thread safe operation

        thread = threading.Thread(target=run_subprocess, daemon=True)
        thread.start()

    def check_running_programs(self, script_commands: list[str]) -> bool:
        """Return True if any of the provided commands are already running.

        Returns
        -------
        bool
            True if an existing process matches the script commands.
        """
        if self.ssh_client:
            for command in script_commands:
                escaped_pattern = command.replace("'", "'\\''")  # Escape single quotes

                user = self.ssh_client.username
                pgrep_cmd = f"pgrep -x -u '{user}' '{escaped_pattern}'"
                _, stderr, exit_status = self.ssh_client.run_remote_command(pgrep_cmd)

                # pgrep exits with 0 if a match is found, 1 if no match, >1 on error
                if exit_status == 0:
                    logger.info(
                        "Process check detected running command: '%s' (user '%s')",
                        command,
                        user,
                    )
                    return True  # Found a running instance
                if exit_status == 1:
                    logger.debug(
                        "Process check found no matches for '%s' (user '%s')",
                        command,
                        user,
                    )
                    # Continue checking next command in the list
                else:
                    # pgrep exited with an error (e.g., command not found, invalid user)
                    logger.error(
                        "Process check failed for pattern '%s': exit %s, stderr %s",
                        command,
                        exit_status,
                        stderr,
                    )
        else:
            current_user = getpass.getuser()
            for proc in psutil.process_iter(attrs=['name', 'username', 'status']):
                if (
                    proc.info['username'] == current_user
                    and proc.info['name'] in script_commands
                    and proc.info['status'] == psutil.STATUS_RUNNING
                ):
                    logger.info('Process check detected running command: %s', proc.info['name'])
                    return True

        return False

    def read_script(
        self,
        file_name: Path,
        convert_cs_irreps: bool = False,
    ) -> list[str]:
        """Return only the lines that have 'astra' from script file.

        Returns
        -------
        list[str]
            Filtered lines containing ``'astra'``.
        """
        lines = self.read_file(file_name, convert_cs_irreps=convert_cs_irreps)
        return [line for line in lines if 'astra' in line]

    def read_file(
        self,
        file_name: Path,
        comment: str = '#',
        empty_lines: bool = False,
        convert_cs_irreps: bool = False,
        remove_comments: bool = True,
    ) -> list[str]:
        """Return the lines of a file removing all comments.

        Returns
        -------
        list[str]
            File contents split into lines with optional comment removal.
        """
        if self.controller.running_directory is None:
            raise RuntimeError('No directory was selected')

        if self.ssh_client:
            lines = (
                cast(str, self.ssh_client.read_from_file(self.controller.running_directory / file_name))
                .strip()
                .split('\n')
            )
        else:
            with file_name.open('r') as f:
                lines = f.read().strip().split('\n')

        if not remove_comments:
            return lines

        comment_pattern = re.compile(rf'{re.escape(comment)}.*')

        clean_lines = []
        for line in lines:
            clean_line = re.sub(comment_pattern, '', line).strip()
            if not clean_line and not empty_lines:
                continue

            clean_lines.append(clean_line)

        if convert_cs_irreps:
            clean_lines = [self.convert_cs_irreps(line) for line in clean_lines]

        return clean_lines

    def read_file_content(
        self,
        file_name: Path,
        comment: str = '#',
        empty_lines: bool = False,
        convert_cs_irreps: bool = False,
        remove_comments: bool = True,
    ) -> str:
        """Return the content of a file removing all comments.

        Returns
        -------
        str
            File content joined into a single string.
        """
        return '\n'.join(
            self.read_file(
                file_name,
                comment,
                empty_lines,
                convert_cs_irreps,
                remove_comments,
            ),
        )

    def path_exists(self, path: Path) -> bool:
        """Check if a path exists either locally or on the remote host.

        Returns
        -------
        bool
            True if the path exists at the configured location.
        """
        if self.controller.running_directory is None:
            raise RuntimeError('No directory was selected')

        if self.ssh_client:
            return self.ssh_client.path_exists(self.controller.running_directory / path)

        return path.exists()

    def mkdir(self, path: Path) -> None:
        """Create a directory locally or via the remote connection."""
        if self.controller.running_directory is None:
            raise RuntimeError('No directory was selected')

        if self.ssh_client:
            self.ssh_client.run_remote_command(
                f'mkdir -p {self.controller.running_directory / path}',
            )
        else:
            path.mkdir(exist_ok=True)


class Notebook(ttk.Notebook, ABC, Generic[NbP]):
    """Container widget that hosts multiple `NotebookPage` instances."""

    def __init__(
        self,
        parent: ttk.Frame,
        controller: 'Astra',
        label: str,
        pack_notebook: bool = True,
    ) -> None:
        self.notebook_frame: ttk.Frame = ttk.Frame(parent)
        super().__init__(self.notebook_frame)
        self.controller = controller
        self.showing = False
        self.pages: list[NbP] = []

        if pack_notebook:
            top_row_frame = ttk.Frame(self.notebook_frame)
            top_row_frame.pack(side=tk.TOP, fill='x')

            back_button = ttk.Label(top_row_frame, text='<', font=back_button_font)
            back_button.pack(side=tk.LEFT, anchor=tk.W, padx=10)
            back_button.bind('<Button-1>', self.back_button_command)

            center_frame = ttk.Frame(top_row_frame)
            center_frame.pack(side=tk.LEFT, fill='x', expand=True, pady=(15, 10))

            ttk.Label(center_frame, text=label, font=title_font).pack()
        else:
            ttk.Label(self.notebook_frame, text=label, font=title_font).pack(side=tk.TOP, pady=40)

        self.enable_traversal()
        if pack_notebook:
            self.pack(fill=tk.BOTH, expand=True, padx=5)

    @abstractmethod
    def reset(self) -> None:
        """Reset notebook state before showing it."""
        ...

    def back_button_command(self, _event: tk.Event) -> None:
        """Command for '<' button."""
        self.controller.show_notebook(0)

    @log_operation('adding pages to notebook')
    def add_pages(self, pages: list[type[NbP]]) -> None:
        """Instantiate and add each page type to the underlying notebook."""
        for page in pages:
            cur_page = page(self)
            self.pages.append(cur_page)
            self.add(cur_page, text=cur_page.label)
            logger.info('Added %s page.', cur_page.__class__.__name__)

    def get_process_from_pages(self, action: str, *args, **kwargs) -> None:
        """Call the named action on every page in the notebook."""
        for page in self.pages:
            getattr(page, action)(*args, **kwargs)
            logger.info('Got %s from %s page.', action, page.__class__.__name__)

    @log_operation('erasing from all pages of notebook')
    def erase(self) -> None:
        """Invoke the `erase` workflow on all pages."""
        self.get_process_from_pages('erase')

    @log_operation('saving from all pages of notebook')
    def save(self) -> None:
        """Invoke the `save` workflow on all pages."""
        self.get_process_from_pages('save')

    @log_operation('loading from all pages of notebook')
    def load(self) -> None:
        """Invoke the `load` workflow on all pages."""
        self.get_process_from_pages('load')

    @log_operation('getting outputs from all pages of notebook')
    def get_outputs(self) -> None:
        """Ask each page to refresh its outputs."""
        self.get_process_from_pages('get_outputs')

    @log_operation('printing irrep all pages of notebook')
    def print_irrep(self, new_sym: bool = False) -> None:
        """Notify every page about a potential symmetry change."""
        self.get_process_from_pages('print_irrep', new_sym)
