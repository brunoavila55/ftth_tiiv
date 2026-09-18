"""Módulo puro de cálculo óptico (Link Budget e Balanço de Potência).

Totalmente desacoplado de ORM, FastAPI ou infraestrutura de banco de dados.
Implementa as fórmulas canônicas e especificações de B10 / F13:
- Perda de fibra: (comprimento_m / 1000.0) * atenuação_db_por_km
- Perda total: soma das perdas reais modeladas no caminho óptico
- RX previsto: TX - Perda Total
- Margem restante: RX previsto - sensibilidade RX - margem de engenharia
- Folga de sobrecarga: limite máximo RX - RX previsto
- Intervalos: RX mínimo = TX mínimo - Perda máxima; RX máximo = TX máximo - Perda mínima
- Avaliação de sensibilidade no pior RX mínimo e sobrecarga no pior RX máximo
- Margem de engenharia não é perda física e não diminui a potência nominal prevista
"""

from dataclasses import dataclass, field
from enum import StrEnum


class StepElementType(StrEnum):
    FIBER = "fiber"
    FUSION = "fusion"
    CONNECTOR = "connector"
    MATED_PAIR = "mated_pair"
    SPLITTER = "splitter"
    PATCH_CORD = "patch_cord"
    PASS_THROUGH = "pass_through"
    ATTENUATOR = "attenuator"
    OTHER = "other"


class ParameterSource(StrEnum):
    CATALOG = "catalog"
    MEASURED = "measured"
    STANDARD = "standard"
    MANUAL = "manual"
    DEFAULT_PROFILE = "default_profile"
    CALCULATED = "calculated"


class CalculationStatus(StrEnum):
    COMPLETE = "complete"
    INSUFFICIENT_DATA = "insufficient_data"


class CalculationAssessment(StrEnum):
    PASS = "pass"
    LOW_MARGIN = "low_margin"
    BELOW_SENSITIVITY = "below_sensitivity"
    OVERLOAD = "overload"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class OpticalStepInput:
    """Entrada que descreve um elemento óptico atravessado pelo sinal."""

    element_type: StepElementType | str
    element_id: str
    element_name: str
    length_m: float = 0.0
    loss_db: float | None = None
    loss_min_db: float | None = None
    loss_max_db: float | None = None
    attenuation_db_per_km: float | None = None
    parameter_source: ParameterSource | str = ParameterSource.CATALOG
    is_typical: bool = True
    unit: str = "dB"
    metadata: dict[str, str | float | int | bool] = field(default_factory=dict)


@dataclass(frozen=True)
class OpticalProfileInput:
    """Parâmetros e limites de transmissão e recepção óptica para uma tecnologia/onda."""

    wavelength_nm: int
    tx_nominal_dbm: float
    tx_min_dbm: float | None = None
    tx_max_dbm: float | None = None
    rx_sensitivity_dbm: float = -27.0
    rx_overload_dbm: float = -8.0
    default_attenuation_db_per_km: float | None = None
    engineering_margin_db: float = 3.0
    technology: str = "GPON"
    profile_name: str = "Padrão"


@dataclass
class OpticalStepBreakdown:
    """Detalhamento passo a passo com perdas individuais e acumuladas."""

    step_number: int
    element_type: str
    element_id: str
    element_name: str
    parameter_source: str
    unit: str
    individual_value: float
    loss_db: float
    loss_min_db: float
    loss_max_db: float
    accumulated_loss_db: float
    is_typical: bool = True
    missing_data: bool = False
    warning: str | None = None


@dataclass
class OpticalCalculationResult:
    """Resultado determinístico do cálculo de balanço de potência óptica."""

    status: CalculationStatus
    assessment: CalculationAssessment
    wavelength_nm: int
    tx_dbm: float
    tx_min_dbm: float
    tx_max_dbm: float
    rx_sensitivity_dbm: float
    rx_overload_dbm: float
    engineering_margin_db: float
    total_loss_db: float | None = None
    total_loss_min_db: float | None = None
    total_loss_max_db: float | None = None
    predicted_rx_dbm: float | None = None
    rx_min_dbm: float | None = None
    rx_max_dbm: float | None = None
    remaining_margin_db: float | None = None
    overload_headroom_db: float | None = None
    steps: list[OpticalStepBreakdown] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def calculate_optical_budget(
    steps: list[OpticalStepInput],
    profile: OpticalProfileInput,
) -> OpticalCalculationResult:
    """Executa o cálculo de balanço de potência óptica de maneira pura e determinística.

    Preserva a precisão de ponto flutuante completa, sem arredondamentos prévios.
    Verifica ausência de parâmetros sem suposições silenciosas de zero.
    """
    assumptions: list[str] = []
    missing_fields: list[str] = []
    warnings: list[str] = []
    step_breakdowns: list[OpticalStepBreakdown] = []

    tx_nominal = profile.tx_nominal_dbm
    tx_min = profile.tx_min_dbm if profile.tx_min_dbm is not None else tx_nominal
    tx_max = profile.tx_max_dbm if profile.tx_max_dbm is not None else tx_nominal

    if profile.tx_min_dbm is None or profile.tx_max_dbm is None:
        assumptions.append(
            f"TX nominal de {tx_nominal:+.2f} dBm adotado como limite simétrico min/max de transmissão."
        )

    accumulated_loss = 0.0
    accumulated_loss_min = 0.0
    accumulated_loss_max = 0.0
    has_missing_data = False

    for idx, step in enumerate(steps, start=1):
        step_type = str(step.element_type).lower()
        step_loss: float | None = None
        step_loss_min: float | None = None
        step_loss_max: float | None = None
        param_source = str(step.parameter_source)
        step_warning: str | None = None
        indiv_value: float = 0.0
        step_unit = step.unit

        if step_type in ("fiber", "fiber_segment"):
            indiv_value = step.length_m
            step_unit = "m"
            attenuation = step.attenuation_db_per_km
            if attenuation is None:
                if profile.default_attenuation_db_per_km is not None:
                    attenuation = profile.default_attenuation_db_per_km
                    param_source = ParameterSource.DEFAULT_PROFILE
                    assumptions.append(
                        f"Fibra '{step.element_name}': adotada atenuação padrão do perfil "
                        f"({attenuation:.3f} dB/km em {profile.wavelength_nm} nm)."
                    )
                else:
                    has_missing_data = True
                    missing_fields.append(
                        f"Atenuação não informada para o trecho de fibra '{step.element_name}' "
                        f"(ID: {step.element_id}) em {profile.wavelength_nm} nm."
                    )
                    step_warning = "Atenuação de fibra não definida"

            if attenuation is not None:
                # Perda = (comprimento_m / 1000.0) * atenuacao_db_por_km
                step_loss = (step.length_m / 1000.0) * attenuation
                step_loss_min = (
                    (step.length_m / 1000.0) * step.loss_min_db
                    if step.loss_min_db is not None
                    else step_loss
                )
                step_loss_max = (
                    (step.length_m / 1000.0) * step.loss_max_db
                    if step.loss_max_db is not None
                    else step_loss
                )

        elif step_type == "pass_through":
            indiv_value = 0.0
            step_loss = 0.0
            step_loss_min = 0.0
            step_loss_max = 0.0
            param_source = ParameterSource.STANDARD

        else:
            # Fusão, conector, splitter, atenuador, patch cord, etc.
            indiv_value = step.loss_db if step.loss_db is not None else 0.0
            step_unit = "dB"

            if step.loss_db is None:
                has_missing_data = True
                missing_fields.append(
                    f"Perda de inserção não informada para o elemento '{step.element_name}' "
                    f"(tipo: {step_type}, ID: {step.element_id})."
                )
                step_warning = "Perda de inserção ausente"
            else:
                step_loss = step.loss_db
                step_loss_min = (
                    step.loss_min_db if step.loss_min_db is not None else step_loss
                )
                step_loss_max = (
                    step.loss_max_db if step.loss_max_db is not None else step_loss
                )

        if step_loss is not None:
            accumulated_loss += step_loss
            accumulated_loss_min += step_loss_min if step_loss_min is not None else step_loss
            accumulated_loss_max += step_loss_max if step_loss_max is not None else step_loss
            current_accum = accumulated_loss
            calc_loss = step_loss
            calc_loss_min = step_loss_min if step_loss_min is not None else step_loss
            calc_loss_max = step_loss_max if step_loss_max is not None else step_loss
            missing_item = False
        else:
            current_accum = accumulated_loss
            calc_loss = 0.0
            calc_loss_min = 0.0
            calc_loss_max = 0.0
            missing_item = True

        step_breakdowns.append(
            OpticalStepBreakdown(
                step_number=idx,
                element_type=step_type,
                element_id=step.element_id,
                element_name=step.element_name,
                parameter_source=param_source,
                unit=step_unit,
                individual_value=indiv_value,
                loss_db=calc_loss,
                loss_min_db=calc_loss_min,
                loss_max_db=calc_loss_max,
                accumulated_loss_db=current_accum,
                is_typical=step.is_typical,
                missing_data=missing_item,
                warning=step_warning,
            )
        )

    # Se faltam dados cruciais, status é insufficient_data e assessment é unknown
    if has_missing_data:
        return OpticalCalculationResult(
            status=CalculationStatus.INSUFFICIENT_DATA,
            assessment=CalculationAssessment.UNKNOWN,
            wavelength_nm=profile.wavelength_nm,
            tx_dbm=tx_nominal,
            tx_min_dbm=tx_min,
            tx_max_dbm=tx_max,
            rx_sensitivity_dbm=profile.rx_sensitivity_dbm,
            rx_overload_dbm=profile.rx_overload_dbm,
            engineering_margin_db=profile.engineering_margin_db,
            total_loss_db=None,
            total_loss_min_db=None,
            total_loss_max_db=None,
            predicted_rx_dbm=None,
            rx_min_dbm=None,
            rx_max_dbm=None,
            remaining_margin_db=None,
            overload_headroom_db=None,
            steps=step_breakdowns,
            assumptions=assumptions,
            missing_fields=missing_fields,
            warnings=["Cálculo incompleto devido a parâmetros ausentes no caminho óptico."],
        )

    # Fórmulas canônicas:
    # Perda total = soma das perdas reais
    total_loss = accumulated_loss
    total_loss_min = accumulated_loss_min
    total_loss_max = accumulated_loss_max

    # RX previsto = TX - perda total
    # (Margem de engenharia NÃO diminui a potência física prevista!)
    predicted_rx = tx_nominal - total_loss

    # Faixas: RX mínimo = TX mínimo - perda máxima; RX máximo = TX máximo - perda mínima
    rx_min = tx_min - total_loss_max
    rx_max = tx_max - total_loss_min

    # Margem restante = RX previsto - sensibilidade RX - margem de engenharia
    remaining_margin = predicted_rx - profile.rx_sensitivity_dbm - profile.engineering_margin_db

    # Folga de sobrecarga = limite máximo RX - RX previsto
    overload_headroom = profile.rx_overload_dbm - predicted_rx

    # Avaliação:
    # 1. Sobrecarga no pior RX máximo
    if rx_max > profile.rx_overload_dbm or predicted_rx > profile.rx_overload_dbm:
        assessment = CalculationAssessment.OVERLOAD
        warnings.append(
            f"Potência máxima prevista ({rx_max:+.2f} dBm) excede o limite de sobrecarga "
            f"do receptor ({profile.rx_overload_dbm:+.2f} dBm)."
        )
    # 2. Abaixo da sensibilidade no pior RX mínimo
    elif rx_min < profile.rx_sensitivity_dbm or predicted_rx < profile.rx_sensitivity_dbm:
        assessment = CalculationAssessment.BELOW_SENSITIVITY
        warnings.append(
            f"Potência mínima prevista ({rx_min:+.2f} dBm) está abaixo da sensibilidade "
            f"do receptor ({profile.rx_sensitivity_dbm:+.2f} dBm)."
        )
    # 3. Margem baixa: acima da sensibilidade, mas violou a margem de engenharia (remaining_margin < 0)
    elif remaining_margin < 0:
        assessment = CalculationAssessment.LOW_MARGIN
        warnings.append(
            f"Potência prevista atinge sensibilidade mas viola a margem de engenharia de "
            f"{profile.engineering_margin_db:.1f} dB (déficit de {abs(remaining_margin):.2f} dB)."
        )
    else:
        assessment = CalculationAssessment.PASS

    return OpticalCalculationResult(
        status=CalculationStatus.COMPLETE,
        assessment=assessment,
        wavelength_nm=profile.wavelength_nm,
        tx_dbm=tx_nominal,
        tx_min_dbm=tx_min,
        tx_max_dbm=tx_max,
        rx_sensitivity_dbm=profile.rx_sensitivity_dbm,
        rx_overload_dbm=profile.rx_overload_dbm,
        engineering_margin_db=profile.engineering_margin_db,
        total_loss_db=total_loss,
        total_loss_min_db=total_loss_min,
        total_loss_max_db=total_loss_max,
        predicted_rx_dbm=predicted_rx,
        rx_min_dbm=rx_min,
        rx_max_dbm=rx_max,
        remaining_margin_db=remaining_margin,
        overload_headroom_db=overload_headroom,
        steps=step_breakdowns,
        assumptions=assumptions,
        missing_fields=[],
        warnings=warnings,
    )
