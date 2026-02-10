"""Unit tests for time-dependent pulse utilities."""

import math
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest
from numpy.testing import assert_allclose

try:
    from astra_gui.close_coupling.bsplines import Bsplines
    from astra_gui.close_coupling.clscplng import CheckList
    from astra_gui.time_dependent.pulse import (
        Pulse,
        Pulses,
        PumpProbePulses,
        compute_mask_free_time_interval,
        derive_max_photon_energy_ev,
    )
    from astra_gui.utils.constants import AU_TO_EV, EV_TO_AU
except ModuleNotFoundError:
    SRC_PATH = Path(__file__).resolve().parents[1] / 'src'
    if str(SRC_PATH) not in sys.path:
        sys.path.insert(0, str(SRC_PATH))
    from astra_gui.close_coupling.bsplines import Bsplines
    from astra_gui.close_coupling.clscplng import CheckList
    from astra_gui.time_dependent.pulse import (
        Pulse,
        Pulses,
        PumpProbePulses,
        compute_mask_free_time_interval,
        derive_max_photon_energy_ev,
    )
    from astra_gui.utils.constants import AU_TO_EV, EV_TO_AU


def make_gaussian_pulse(**overrides: Any) -> Pulse:
    """Return a Gaussian pulse with deterministic defaults.

    Returns
    -------
    Pulse
        Pulse instance initialised with the provided overrides.
    """
    params: dict[str, Any] = {
        'shape': 'Gaussian',
        'name': 'pump',
        'time': 0.0,
        'frequency': 0.75,
        'fwhm': 4.0,
        'cep': 0.0,
        'intensity': 1.2,
        'theta': 0.0,
        'phi': 0.0,
    }
    params.update(overrides)
    return Pulse(**params)


def make_cosine_pulse(**overrides: Any) -> Pulse:
    """Return a cosine-squared pulse with deterministic defaults.

    Returns
    -------
    Pulse
        Pulse instance initialised with the provided overrides.
    """
    params: dict[str, Any] = {
        'shape': 'Cosine Squared',
        'name': 'probe',
        'time': 0.0,
        'frequency': 0.65,
        'fwhm': 2.0,
        'cep': 0.0,
        'intensity': 0.8,
        'theta': 0.0,
        'phi': 0.0,
    }
    params.update(overrides)
    return Pulse(**params)


def test_pulse_initialisation_converts_parameters_to_float() -> None:
    """String parameters should be coerced to floats during validation."""
    pulse = make_gaussian_pulse(time='1', frequency='0.5', fwhm='3', intensity='2')

    assert pulse.good_parameters is True
    assert pulse.time == pytest.approx(1.0)
    assert pulse.freq == pytest.approx(0.5)
    assert pulse.fwhm == pytest.approx(3.0)
    assert pulse.intensity == pytest.approx(2.0)
    assert pulse.parameter_string().startswith('(G ')
    assert pulse.pulse_string().startswith('[pump]{(')


def test_gaussian_envelope_matches_expected_formula() -> None:
    """Gaussian envelopes should align with the analytical expression."""
    pulse = make_gaussian_pulse(time=2.0, frequency=1.0, fwhm=3.0)
    times = np.array([1.5, 2.0, 2.5])
    expected = np.exp(-np.log(2) * (pulse.freq * (times - pulse.time) / (np.pi * pulse.fwhm)) ** 2)

    values = pulse.eval_envelope(times)
    assert_allclose(values, expected)


def test_cosine_squared_envelope_is_zero_outside_support() -> None:
    """Cosine-squared pulses should drop to zero outside the envelope."""
    pulse = make_cosine_pulse(time=0.0, frequency=1.0, fwhm=1.0)
    times = np.array([-10.0, 0.0, 10.0])

    values = pulse.eval_envelope(times)
    assert values[0] == pytest.approx(0.0)
    assert values[2] == pytest.approx(0.0)
    assert values[1] == pytest.approx(1.0)


def test_pulse_eval_pulse_combines_envelope_and_carrier() -> None:
    """Full pulse evaluation multiplies the envelope and oscillation."""
    pulse = make_gaussian_pulse(time=0.5, frequency=1.4, fwhm=2.5, cep=0.2, intensity=1.1)
    sample_time = 0.75
    envelope = pulse.eval_envelope(sample_time)
    expected_carrier = math.cos(pulse.freq * (sample_time - pulse.time) + pulse.cep)
    c_to_au = 137.03599911
    a0 = c_to_au / 18.73 / pulse.freq * math.sqrt(10 * pulse.intensity)

    assert pulse.eval_pulse(sample_time) == pytest.approx(a0 * envelope * expected_carrier)


def test_pulse_time_bounds_and_tabulation() -> None:
    """Pulse helpers should provide consistent support bounds and tabulation."""
    pulse = make_gaussian_pulse(time=1.0, frequency=0.5, fwhm=4.0)

    start, stop = pulse.get_initial_and_final_times()
    assert stop - start == pytest.approx(2 * pulse.get_zero_envelope_time())

    table = pulse.tabulate(start, stop, dt=2.0)
    lines = table.splitlines()
    assert lines[0].count(' ') == 1
    assert float(lines[0].split()[0]) == pytest.approx(start)
    last_time = float(lines[-1].split()[0])
    assert last_time >= stop
    assert last_time - stop <= 2.0 + 1e-9


def test_pulses_collection_formats_and_bounds() -> None:
    """Pulse trains should report combined bounds and serialised names."""
    pump = make_gaussian_pulse(name='pump_a', time=0.0)
    probe = make_cosine_pulse(name='probe_b', time=5.0)
    collection = Pulses('sequence', [pump, probe])

    assert collection.pulses_string() == '[sequence]{pump_a;probe_b;}'

    start, stop = collection.get_initial_and_final_times()
    pump_bounds = pump.get_initial_and_final_times()
    probe_bounds = probe.get_initial_and_final_times()
    assert start == pytest.approx(min(pump_bounds[0], probe_bounds[0]))
    assert stop == pytest.approx(max(pump_bounds[1], probe_bounds[1]))


def test_pump_probe_sequences_shift_probe_and_emit_execute_block() -> None:
    """Pump-probe helpers should produce consistent per-delay blocks."""
    pump = Pulses('pump_train', [make_gaussian_pulse(name='pump')])
    probe = Pulses(
        'probe_train',
        [
            make_cosine_pulse(name='probe_0', time=-0.25),
            make_cosine_pulse(name='probe_1', time=0.5),
        ],
    )
    delays = np.array([-1.0, 1.0])

    pump_probe = PumpProbePulses(pump, probe, delays)
    sequence_lines = pump_probe.pump_probe_string().splitlines()
    assert sequence_lines[0].startswith('[pump_probe_-1.0]{pump_train;')
    assert '(C -1.25 ' in sequence_lines[0]
    assert '(C -0.5 ' in sequence_lines[0]
    assert '(C 0.75 ' in sequence_lines[1]
    assert '(C 1.5 ' in sequence_lines[1]
    assert pump_probe.execute_string() == 'EXECUTE{pump_train;pump_probe_-1.0;pump_probe_1.0;}'

    start, stop = pump_probe.get_initial_and_final_times()
    assert start < stop


def test_invalid_pulse_shape_triggers_popup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid shapes should alert the user instead of initialising."""
    calls: list[str] = []

    def fake_popup(message: str) -> None:
        calls.append(message)

    monkeypatch.setattr('astra_gui.time_dependent.pulse.invalid_input_popup', fake_popup)

    pulse = Pulse(
        shape='Triangle',
        name='bad',
        time=0.0,
        frequency=1.0,
        fwhm=1.0,
        cep=0.0,
        intensity=1.0,
        theta=0.0,
        phi=0.0,
    )

    assert calls, 'Expected invalid_input_popup to be called'
    assert getattr(pulse, 'good_parameters', False) is False


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('frequency', 0.0),
        ('fwhm', 0.0),
        ('intensity', 0.0),
    ],
)
def test_zero_frequency_fwhm_or_intensity_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: float,
) -> None:
    """Pulse validation should reject zero values for required nonzero fields."""
    calls: list[str] = []

    def fake_popup(message: str) -> None:
        calls.append(message)

    monkeypatch.setattr('astra_gui.time_dependent.pulse.warning_popup', fake_popup)

    pulse = make_gaussian_pulse(**{field: value})

    assert calls, 'Expected warning_popup to be called'
    assert pulse.good_parameters is False


def test_compute_mask_free_time_interval_formula() -> None:
    """Mask-free interval should follow issue #2 formula."""
    delta_t = compute_mask_free_time_interval(
        max_photon_energy_ev=20.0,
        cap_radii=[45.0, 60.0],
        mask_radius=40.0,
    )
    expected = (45.0 - 40.0) / math.sqrt(2 * (20.0 * EV_TO_AU))
    assert delta_t == pytest.approx(expected)


def test_derive_max_photon_energy_is_inverse_of_mask_free_time_formula() -> None:
    """Derived max photon energy should invert the interval formula."""
    expected_max_energy = 35.0
    mask_free_time = compute_mask_free_time_interval(expected_max_energy, [50.0, 75.0], 42.0)
    derived_energy = derive_max_photon_energy_ev(mask_free_time, [50.0, 75.0], 42.0)
    assert derived_energy == pytest.approx(expected_max_energy)


@pytest.mark.parametrize(
    ('max_photon_energy_ev', 'cap_radii', 'mask_radius'),
    [
        (0.0, [45.0], 40.0),
        (-1.0, [45.0], 40.0),
        (10.0, [], 40.0),
        (10.0, [39.0], 40.0),
    ],
)
def test_compute_mask_free_time_interval_rejects_invalid_inputs(
    max_photon_energy_ev: float,
    cap_radii: list[float],
    mask_radius: float,
) -> None:
    """Formula helper should reject invalid geometry/energy inputs."""
    with pytest.raises(ValueError, match=r'.+'):
        compute_mask_free_time_interval(max_photon_energy_ev, cap_radii, mask_radius)


def test_bsplines_data_helpers_update_and_initialize_notebook_state() -> None:
    """Bsplines helper methods should manage shared typed-dict notebook state."""
    bsplines = Bsplines.__new__(Bsplines)
    cast(Any, bsplines).notebook = SimpleNamespace(
        bsplines_data={},
        init_bsplines_data=lambda: setattr(
            bsplines.notebook,
            'bsplines_data',
            {
                'cap_radii': [],
                'mask_radius': 0.0,
                'mask_width': 0.0,
                'box_size': 0.0,
                'is_valid': False,
            },
        ),
    )

    bsplines.update_bsplines_data([55.0], 42.0, 3.0, 80.0)
    assert bsplines.notebook.bsplines_data['is_valid'] is True
    assert bsplines.notebook.bsplines_data['cap_radii'] == [55.0]
    assert bsplines.notebook.bsplines_data['mask_radius'] == pytest.approx(42.0)

    bsplines.notebook.init_bsplines_data()
    assert bsplines.notebook.bsplines_data['is_valid'] is False
    assert bsplines.notebook.bsplines_data['cap_radii'] == []


def test_shared_energy_constants_moved_out_of_checklist() -> None:
    """Energy constants should come from shared module instead of class attributes."""
    assert hasattr(CheckList, 'AU_TO_EV') is False
    assert pytest.approx(1.0) == AU_TO_EV * EV_TO_AU
