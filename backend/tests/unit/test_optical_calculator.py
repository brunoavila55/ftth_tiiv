"""Testes unitários puros para o calculador de orçamento óptico (B10).

Verifica as fórmulas canônicas, o aceite sintético numérico exato,
detecção de sobrecarga, sensibilidade, margem baixa, ausência de dados,
splitters assimétricos e diferentes comprimentos de onda.
"""

import math

from app.modules.optical.calculator import (
    CalculationAssessment,
    CalculationStatus,
    OpticalProfileInput,
    OpticalStepInput,
    ParameterSource,
    StepElementType,
    calculate_optical_budget,
)


def test_b10_synthetic_acceptance_scenario():
    """Valida o caso de aceite numérico sintético de B10:

    - TX +3 dBm
    - 7 km × 0,25 dB/km = 1,75 dB
    - 4 fusões × 0,10 dB = 0,40 dB
    - 2 pares acoplados × 0,30 dB = 0,60 dB
    - 2 splitters × 10,5 dB = 21,0 dB
    - Perda total esperada = 23,75 dB
    - RX previsto = -20,75 dBm
    - Sensibilidade = -27 dBm
    - Margem de engenharia = 3 dB
    - Margem restante = 3,25 dB
    - Avaliação: PASS (Aprovado)
    """
    steps = [
        # 1. Par acoplado OLT/DIO
        OpticalStepInput(
            element_type=StepElementType.MATED_PAIR,
            element_id="conn-1",
            element_name="Acoplador OLT/DIO",
            loss_db=0.30,
            parameter_source=ParameterSource.STANDARD,
        ),
        # 2. Fibra 3,5 km
        OpticalStepInput(
            element_type=StepElementType.FIBER,
            element_id="fiber-1",
            element_name="Trecho Alimentador (3.5 km)",
            length_m=3500.0,
            attenuation_db_per_km=0.25,
            parameter_source=ParameterSource.CATALOG,
        ),
        # 3. Duas fusões no caminho
        OpticalStepInput(
            element_type=StepElementType.FUSION,
            element_id="fusion-1",
            element_name="Fusão CEO 1",
            loss_db=0.10,
            parameter_source=ParameterSource.MEASURED,
        ),
        OpticalStepInput(
            element_type=StepElementType.FUSION,
            element_id="fusion-2",
            element_name="Fusão CEO 2",
            loss_db=0.10,
            parameter_source=ParameterSource.MEASURED,
        ),
        # 4. Primeiro splitter (1:8)
        OpticalStepInput(
            element_type=StepElementType.SPLITTER,
            element_id="splitter-1",
            element_name="Splitter Primário 1:8",
            loss_db=10.50,
            parameter_source=ParameterSource.CATALOG,
        ),
        # 5. Fibra 3,5 km (totalizando 7,0 km)
        OpticalStepInput(
            element_type=StepElementType.FIBER,
            element_id="fiber-2",
            element_name="Trecho Distribuição (3.5 km)",
            length_m=3500.0,
            attenuation_db_per_km=0.25,
            parameter_source=ParameterSource.CATALOG,
        ),
        # 6. Mais duas fusões (totalizando 4 fusões)
        OpticalStepInput(
            element_type=StepElementType.FUSION,
            element_id="fusion-3",
            element_name="Fusão CEO 3",
            loss_db=0.10,
            parameter_source=ParameterSource.MEASURED,
        ),
        OpticalStepInput(
            element_type=StepElementType.FUSION,
            element_id="fusion-4",
            element_name="Fusão CTO 1",
            loss_db=0.10,
            parameter_source=ParameterSource.MEASURED,
        ),
        # 7. Segundo splitter (1:8)
        OpticalStepInput(
            element_type=StepElementType.SPLITTER,
            element_id="splitter-2",
            element_name="Splitter Secundário 1:8",
            loss_db=10.50,
            parameter_source=ParameterSource.CATALOG,
        ),
        # 8. Segundo par acoplado (totalizando 2 pares acoplados)
        OpticalStepInput(
            element_type=StepElementType.MATED_PAIR,
            element_id="conn-2",
            element_name="Acoplador Porta CTO / Drop",
            loss_db=0.30,
            parameter_source=ParameterSource.STANDARD,
        ),
    ]

    profile = OpticalProfileInput(
        wavelength_nm=1490,
        tx_nominal_dbm=3.0,
        tx_min_dbm=1.5,
        tx_max_dbm=5.0,
        rx_sensitivity_dbm=-27.0,
        rx_overload_dbm=-8.0,
        engineering_margin_db=3.0,
    )

    result = calculate_optical_budget(steps, profile)

    assert result.status == CalculationStatus.COMPLETE
    assert result.assessment == CalculationAssessment.PASS
    assert math.isclose(result.total_loss_db, 23.75, abs_tol=1e-6)
    assert math.isclose(result.predicted_rx_dbm, -20.75, abs_tol=1e-6)
    assert math.isclose(result.remaining_margin_db, 3.25, abs_tol=1e-6)
    # Folga de sobrecarga: -8.0 - (-20.75) = 12.75 dB
    assert math.isclose(result.overload_headroom_db, 12.75, abs_tol=1e-6)
    assert len(result.steps) == 10
    assert result.steps[-1].accumulated_loss_db == 23.75


def test_optical_overload_detection():
    """Detecta saturação quando potência no receptor excede rx_overload."""
    # Enlace muito curto sem splitters (ex: cabo de 50 metros e 1 conector)
    steps = [
        OpticalStepInput(
            element_type=StepElementType.MATED_PAIR,
            element_id="conn-1",
            element_name="Patch cord",
            loss_db=0.20,
        ),
        OpticalStepInput(
            element_type=StepElementType.FIBER,
            element_id="fiber-short",
            element_name="Drop 50m",
            length_m=50.0,
            attenuation_db_per_km=0.35,
        ),
    ]
    # TX de +5.0 dBm, sobrecarga de -8.0 dBm. RX previsto será ~ +4.78 dBm > -8.0 dBm
    profile = OpticalProfileInput(
        wavelength_nm=1490,
        tx_nominal_dbm=5.0,
        rx_sensitivity_dbm=-27.0,
        rx_overload_dbm=-8.0,
        engineering_margin_db=3.0,
    )

    result = calculate_optical_budget(steps, profile)
    assert result.status == CalculationStatus.COMPLETE
    assert result.assessment == CalculationAssessment.OVERLOAD
    assert result.predicted_rx_dbm > -8.0
    assert len(result.warnings) > 0


def test_optical_below_sensitivity_detection():
    """Detecta potência insuficiente abaixo da sensibilidade RX."""
    # Perda excessiva de 32 dB
    steps = [
        OpticalStepInput(
            element_type=StepElementType.SPLITTER,
            element_id="split-huge",
            element_name="Splitter cascata",
            loss_db=32.0,
        )
    ]
    # TX +3.0 dBm, perda 32.0 dB -> RX = -29.0 dBm < sensibilidade -27.0 dBm
    profile = OpticalProfileInput(
        wavelength_nm=1490,
        tx_nominal_dbm=3.0,
        rx_sensitivity_dbm=-27.0,
        rx_overload_dbm=-8.0,
        engineering_margin_db=3.0,
    )

    result = calculate_optical_budget(steps, profile)
    assert result.status == CalculationStatus.COMPLETE
    assert result.assessment == CalculationAssessment.BELOW_SENSITIVITY
    assert result.predicted_rx_dbm == -29.0
    assert len(result.warnings) > 0


def test_optical_low_margin_detection():
    """Detecta quando o sinal atinge a sensibilidade mas invade a margem de engenharia."""
    # RX previsto de -25.0 dBm: maior que -27.0 dBm (sensibilidade),
    # porém com margem de 3 dB, a margem mínima necessária é -24.0 dBm.
    # Margem restante = -25.0 - (-27.0) - 3.0 = 2.0 - 3.0 = -1.0 dB.
    steps = [
        OpticalStepInput(
            element_type=StepElementType.SPLITTER,
            element_id="split-1",
            element_name="Splitter",
            loss_db=28.0,
        )
    ]
    profile = OpticalProfileInput(
        wavelength_nm=1490,
        tx_nominal_dbm=3.0,
        rx_sensitivity_dbm=-27.0,
        rx_overload_dbm=-8.0,
        engineering_margin_db=3.0,
    )

    result = calculate_optical_budget(steps, profile)
    assert result.status == CalculationStatus.COMPLETE
    assert result.assessment == CalculationAssessment.LOW_MARGIN
    assert result.predicted_rx_dbm == -25.0
    assert math.isclose(result.remaining_margin_db, -1.0, abs_tol=1e-6)


def test_optical_missing_data_insufficient_data():
    """Não trata perda ausente como zero e retorna status insufficient_data."""
    steps = [
        # Fibra sem atenuação cadastrada e sem default de perfil
        OpticalStepInput(
            element_type=StepElementType.FIBER,
            element_id="fib-orphan",
            element_name="Fibra Sem Atenuação",
            length_m=1200.0,
            attenuation_db_per_km=None,
        ),
        # Splitter com perda nula
        OpticalStepInput(
            element_type=StepElementType.SPLITTER,
            element_id="split-unknown",
            element_name="Splitter Desconhecido",
            loss_db=None,
        ),
    ]
    profile = OpticalProfileInput(
        wavelength_nm=1490,
        tx_nominal_dbm=3.0,
        default_attenuation_db_per_km=None,  # Sem padrão para forçar missing_data
    )

    result = calculate_optical_budget(steps, profile)
    assert result.status == CalculationStatus.INSUFFICIENT_DATA
    assert result.assessment == CalculationAssessment.UNKNOWN
    assert result.total_loss_db is None
    assert result.predicted_rx_dbm is None
    assert len(result.missing_fields) == 2
    assert "fib-orphan" in result.missing_fields[0]
    assert "split-unknown" in result.missing_fields[1]


def test_optical_asymmetric_splitter_branch():
    """Testa splitter com saída assimétrica / desigual (ex: 10/90)."""
    # Ramo direto (10%): perda ~10.5 dB
    steps_drop = [
        OpticalStepInput(
            element_type=StepElementType.SPLITTER,
            element_id="split-asym",
            element_name="Splitter Assimétrico 10/90 (Tap)",
            loss_db=10.5,
        )
    ]
    # Ramo passante (90%): perda ~1.2 dB
    steps_through = [
        OpticalStepInput(
            element_type=StepElementType.SPLITTER,
            element_id="split-asym",
            element_name="Splitter Assimétrico 10/90 (Passante)",
            loss_db=1.2,
        )
    ]

    profile = OpticalProfileInput(wavelength_nm=1490, tx_nominal_dbm=3.0)

    res_drop = calculate_optical_budget(steps_drop, profile)
    res_through = calculate_optical_budget(steps_through, profile)

    assert math.isclose(res_drop.total_loss_db, 10.5)
    assert math.isclose(res_through.total_loss_db, 1.2)
    assert res_through.predicted_rx_dbm > res_drop.predicted_rx_dbm


def test_optical_different_wavelengths():
    """Testa atenuação em diferentes comprimentos de onda (1310 vs 1490 vs 1550)."""
    # Fibra de 20 km
    steps_1310 = [
        OpticalStepInput(
            element_type=StepElementType.FIBER,
            element_id="fib-long",
            element_name="Fibra 20km",
            length_m=20000.0,
            attenuation_db_per_km=0.35,  # 1310 nm
        )
    ]
    steps_1490 = [
        OpticalStepInput(
            element_type=StepElementType.FIBER,
            element_id="fib-long",
            element_name="Fibra 20km",
            length_m=20000.0,
            attenuation_db_per_km=0.25,  # 1490 nm
        )
    ]
    steps_1550 = [
        OpticalStepInput(
            element_type=StepElementType.FIBER,
            element_id="fib-long",
            element_name="Fibra 20km",
            length_m=20000.0,
            attenuation_db_per_km=0.20,  # 1550 nm
        )
    ]

    p1310 = OpticalProfileInput(wavelength_nm=1310, tx_nominal_dbm=2.0)
    p1490 = OpticalProfileInput(wavelength_nm=1490, tx_nominal_dbm=2.0)
    p1550 = OpticalProfileInput(wavelength_nm=1550, tx_nominal_dbm=2.0)

    r1310 = calculate_optical_budget(steps_1310, p1310)
    r1490 = calculate_optical_budget(steps_1490, p1490)
    r1550 = calculate_optical_budget(steps_1550, p1550)

    assert math.isclose(r1310.total_loss_db, 7.0)  # 20 * 0.35
    assert math.isclose(r1490.total_loss_db, 5.0)  # 20 * 0.25
    assert math.isclose(r1550.total_loss_db, 4.0)  # 20 * 0.20


def test_single_connector_vs_mated_pair():
    """Valida modelagem de conector isolado vs par acoplado."""
    steps_single = [
        OpticalStepInput(
            element_type=StepElementType.CONNECTOR,
            element_id="conn-single",
            element_name="Conector SC/APC Ponta",
            loss_db=0.15,
        )
    ]
    steps_pair = [
        OpticalStepInput(
            element_type=StepElementType.MATED_PAIR,
            element_id="conn-pair",
            element_name="Par Acoplado SC/APC",
            loss_db=0.30,
        )
    ]
    profile = OpticalProfileInput(wavelength_nm=1490, tx_nominal_dbm=0.0)

    res_single = calculate_optical_budget(steps_single, profile)
    res_pair = calculate_optical_budget(steps_pair, profile)

    assert math.isclose(res_single.total_loss_db, 0.15)
    assert math.isclose(res_pair.total_loss_db, 0.30)
