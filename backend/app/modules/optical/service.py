import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import (
    ConflictError,
    NotFoundError,
    PreconditionFailedError,
    PreconditionRequiredError,
    UnprocessableEntityError,
)
from app.modules.optical.models import OpticalProfile
from app.schemas.optical import (
    BudgetAssessment,
    BudgetCalculationRequest,
    BudgetCalculationResponse,
    BudgetLossStep,
    OpticalProfileCreate,
    OpticalProfileRead,
    OpticalProfileUpdate,
    OpticalSimulationRequest,
    OpticalSimulationResponse,
    SimulationOverrideItem,
)


def _validate_if_match(if_match: str | None, current_version: int) -> None:
    if not if_match or not if_match.strip():
        raise PreconditionRequiredError()
    try:
        expected = int(if_match.strip('"'))
    except ValueError:
        raise PreconditionFailedError() from None
    if current_version != expected:
        raise PreconditionFailedError()


def optical_profile_to_read(profile: OpticalProfile) -> OpticalProfileRead:
    return OpticalProfileRead(
        id=str(profile.id),
        name=profile.name,
        technology=profile.technology,
        wavelength_nm=profile.wavelength_nm,
        tx_min_dbm=profile.tx_min_dbm,
        tx_max_dbm=profile.tx_max_dbm,
        rx_sensitivity_dbm=profile.rx_sensitivity_dbm,
        rx_overload_dbm=profile.rx_overload_dbm,
        default_attenuation_db_per_km=profile.default_attenuation_db_per_km,
        notes=profile.notes,
        version=profile.version,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def list_optical_profiles_paginated(
    session: Session,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[OpticalProfile], int]:
    query = select(OpticalProfile)
    count_query = select(func.count(OpticalProfile.id))

    total = session.scalar(count_query) or 0
    offset = (page - 1) * page_size
    items = list(
        session.scalars(
            query.order_by(OpticalProfile.created_at.desc(), OpticalProfile.id)
            .offset(offset)
            .limit(page_size)
        ).all()
    )
    return items, total


def get_optical_profile_by_id(session: Session, profile_id: str) -> OpticalProfile:
    try:
        profile_uuid = uuid.UUID(profile_id)
    except ValueError:
        raise NotFoundError("Perfil óptico não encontrado.", code="profile_not_found") from None

    profile = session.scalar(select(OpticalProfile).where(OpticalProfile.id == profile_uuid))
    if not profile:
        raise NotFoundError("Perfil óptico não encontrado.", code="profile_not_found")
    return profile


def create_optical_profile(session: Session, payload: OpticalProfileCreate) -> OpticalProfile:
    if payload.tx_min_dbm > payload.tx_max_dbm:
        raise UnprocessableEntityError(
            "Potência mínima de transmissão (tx_min_dbm) não pode ser maior que a máxima (tx_max_dbm).",
            field="tx_min_dbm",
        )
    if payload.rx_sensitivity_dbm > payload.rx_overload_dbm:
        raise UnprocessableEntityError(
            "Sensibilidade RX (rx_sensitivity_dbm) não pode ser maior que o limite de sobrecarga (rx_overload_dbm).",
            field="rx_sensitivity_dbm",
        )

    clean_name = payload.name.strip()
    existing = session.scalar(select(OpticalProfile).where(OpticalProfile.name == clean_name))
    if existing:
        raise ConflictError(
            f"Já existe um perfil óptico com o nome '{clean_name}'.",
            code="name_already_exists",
        )

    profile = OpticalProfile(
        name=clean_name,
        technology=payload.technology.strip(),
        wavelength_nm=payload.wavelength_nm,
        tx_min_dbm=payload.tx_min_dbm,
        tx_max_dbm=payload.tx_max_dbm,
        rx_sensitivity_dbm=payload.rx_sensitivity_dbm,
        rx_overload_dbm=payload.rx_overload_dbm,
        default_attenuation_db_per_km=payload.default_attenuation_db_per_km,
        notes=payload.notes,
        version=1,
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def update_optical_profile(
    session: Session,
    profile_id: str,
    payload: OpticalProfileUpdate,
    if_match: str | None,
) -> OpticalProfile:
    profile = get_optical_profile_by_id(session, profile_id)
    _validate_if_match(if_match, profile.version)

    new_tx_min = payload.tx_min_dbm if payload.tx_min_dbm is not None else profile.tx_min_dbm
    new_tx_max = payload.tx_max_dbm if payload.tx_max_dbm is not None else profile.tx_max_dbm
    new_rx_sens = (
        payload.rx_sensitivity_dbm
        if payload.rx_sensitivity_dbm is not None
        else profile.rx_sensitivity_dbm
    )
    new_rx_over = (
        payload.rx_overload_dbm if payload.rx_overload_dbm is not None else profile.rx_overload_dbm
    )

    if new_tx_min > new_tx_max:
        raise UnprocessableEntityError(
            "Potência mínima de transmissão (tx_min_dbm) não pode ser maior que a máxima (tx_max_dbm).",
            field="tx_min_dbm",
        )
    if new_rx_sens > new_rx_over:
        raise UnprocessableEntityError(
            "Sensibilidade RX (rx_sensitivity_dbm) não pode ser maior que o limite de sobrecarga (rx_overload_dbm).",
            field="rx_sensitivity_dbm",
        )

    if payload.name is not None:
        clean_name = payload.name.strip()
        if clean_name != profile.name:
            existing = session.scalar(
                select(OpticalProfile).where(
                    OpticalProfile.name == clean_name, OpticalProfile.id != profile.id
                )
            )
            if existing:
                raise ConflictError(
                    f"Já existe um perfil óptico com o nome '{clean_name}'.",
                    code="name_already_exists",
                )
            profile.name = clean_name

    if payload.tx_min_dbm is not None:
        profile.tx_min_dbm = payload.tx_min_dbm
    if payload.tx_max_dbm is not None:
        profile.tx_max_dbm = payload.tx_max_dbm
    if payload.rx_sensitivity_dbm is not None:
        profile.rx_sensitivity_dbm = payload.rx_sensitivity_dbm
    if payload.rx_overload_dbm is not None:
        profile.rx_overload_dbm = payload.rx_overload_dbm
    if payload.default_attenuation_db_per_km is not None:
        profile.default_attenuation_db_per_km = payload.default_attenuation_db_per_km
    if payload.notes is not None:
        profile.notes = payload.notes

    profile.version += 1
    profile.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(profile)
    return profile


def delete_optical_profile(session: Session, profile_id: str, if_match: str | None) -> None:
    profile = get_optical_profile_by_id(session, profile_id)
    _validate_if_match(if_match, profile.version)

    try:
        session.delete(profile)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ConflictError(
            "Não é possível excluir o perfil óptico pois ele está associado a circuitos ou cabos ativos.",
            code="referenced_entity_conflict",
        ) from None


def calculate_service_link_budget(
    session: Session,
    payload: BudgetCalculationRequest,
    overrides: list[SimulationOverrideItem] | None = None,
) -> BudgetCalculationResponse:
    """Calcula o balanço de potência óptica e margem de enlace (B10).

    Resolve o caminho óptico através da topologia (B09) e executa o cálculo determinístico
    através do módulo puro de cálculo óptico.
    """
    from app.modules.connectivity.models import Terminal
    from app.modules.customers.models import ServiceLink
    from app.modules.optical.calculator import (
        CalculationAssessment,
        OpticalProfileInput,
        OpticalStepInput,
        ParameterSource,
        StepElementType,
        calculate_optical_budget,
    )
    from app.modules.topology.service import get_current_topology_revision, trace_optical_path
    from app.schemas.topology import TraceDirection, TracePath, TraceRequest, TraceStatus, TraceStep

    topology_rev = get_current_topology_revision(session)

    # 1. Resolver Perfil Óptico
    profile_input: OpticalProfileInput
    if payload.profile_id:
        p_model = get_optical_profile_by_id(session, payload.profile_id)
        nominal_tx = (p_model.tx_min_dbm + p_model.tx_max_dbm) / 2.0
        profile_input = OpticalProfileInput(
            wavelength_nm=p_model.wavelength_nm,
            tx_nominal_dbm=nominal_tx,
            tx_min_dbm=p_model.tx_min_dbm,
            tx_max_dbm=p_model.tx_max_dbm,
            rx_sensitivity_dbm=p_model.rx_sensitivity_dbm,
            rx_overload_dbm=p_model.rx_overload_dbm,
            default_attenuation_db_per_km=p_model.default_attenuation_db_per_km,
            engineering_margin_db=payload.engineering_margin_db,
            technology=p_model.technology,
            profile_name=p_model.name,
        )
    else:
        # Busca perfil correspondente à direção ou adota defaults GPON
        target_wave = 1490 if payload.direction == TraceDirection.DOWNSTREAM else 1310
        existing_prof = session.scalar(
            select(OpticalProfile).where(OpticalProfile.wavelength_nm == target_wave).limit(1)
        )
        if existing_prof:
            nominal_tx = (existing_prof.tx_min_dbm + existing_prof.tx_max_dbm) / 2.0
            profile_input = OpticalProfileInput(
                wavelength_nm=existing_prof.wavelength_nm,
                tx_nominal_dbm=nominal_tx,
                tx_min_dbm=existing_prof.tx_min_dbm,
                tx_max_dbm=existing_prof.tx_max_dbm,
                rx_sensitivity_dbm=existing_prof.rx_sensitivity_dbm,
                rx_overload_dbm=existing_prof.rx_overload_dbm,
                default_attenuation_db_per_km=existing_prof.default_attenuation_db_per_km,
                engineering_margin_db=payload.engineering_margin_db,
                technology=existing_prof.technology,
                profile_name=existing_prof.name,
            )
        else:
            if payload.direction == TraceDirection.DOWNSTREAM:
                # GPON Classe B+ Downstream: 1490 nm, TX +3 dBm nominal (+1.5..+5.0), RX sens -27 dBm
                profile_input = OpticalProfileInput(
                    wavelength_nm=1490,
                    tx_nominal_dbm=3.0,
                    tx_min_dbm=1.5,
                    tx_max_dbm=5.0,
                    rx_sensitivity_dbm=-27.0,
                    rx_overload_dbm=-8.0,
                    default_attenuation_db_per_km=0.25,
                    engineering_margin_db=payload.engineering_margin_db,
                    technology="GPON",
                    profile_name="GPON B+ Padrão (Downstream)",
                )
            else:
                # GPON Classe B+ Upstream: 1310 nm, TX +2.5 dBm nominal (+0.5..+5.0), RX sens -28 dBm
                profile_input = OpticalProfileInput(
                    wavelength_nm=1310,
                    tx_nominal_dbm=2.5,
                    tx_min_dbm=0.5,
                    tx_max_dbm=5.0,
                    rx_sensitivity_dbm=-28.0,
                    rx_overload_dbm=-8.0,
                    default_attenuation_db_per_km=0.35,
                    engineering_margin_db=payload.engineering_margin_db,
                    technology="GPON",
                    profile_name="GPON B+ Padrão (Upstream)",
                )

    # 2. Localizar Terminal Inicial para Rastreamento
    chosen_path: TracePath | None = None
    trace_warnings: list[str] = []

    if payload.service_link_id:
        try:
            sl_uuid = uuid.UUID(payload.service_link_id)
        except ValueError:
            raise UnprocessableEntityError("service_link_id inválido.", field="service_link_id") from None

        link = session.get(ServiceLink, sl_uuid)
        if not link:
            raise NotFoundError("Atendimento óptico de cliente não encontrado.", code="service_link_not_found")

        cto_term = session.scalar(
            select(Terminal).where(Terminal.entity_type == "port", Terminal.entity_id == link.port_id)
        )
        if not cto_term:
            raise NotFoundError("Terminal óptico da porta CTO não localizado.", code="terminal_not_found")

        # No downstream, traçamos upstream da CTO para descobrir a OLT e os passos
        if payload.direction == TraceDirection.DOWNSTREAM:
            up_trace = trace_optical_path(
                session,
                TraceRequest(
                    start_terminal_id=str(cto_term.id),
                    direction=TraceDirection.UPSTREAM,
                ),
            )
            trace_warnings.extend(up_trace.warnings)
            if up_trace.paths and up_trace.status == TraceStatus.COMPLETE:
                # Invertemos a ordem dos passos upstream para representar downstream (OLT -> Cliente)
                raw_path = up_trace.paths[0]
                inverted_steps: list[TraceStep] = []
                for step_idx, stp in enumerate(reversed(raw_path.steps), start=1):
                    inverted_steps.append(
                        TraceStep(
                            step_number=step_idx,
                            element_type=stp.element_type,
                            element_id=stp.element_id,
                            element_code=stp.element_code,
                            input_terminal_id=stp.output_terminal_id,
                            output_terminal_id=stp.input_terminal_id,
                            length_m=stp.length_m,
                            loss_db=stp.loss_db,
                            accumulated_length_m=0.0,
                            accumulated_loss_db=0.0,
                            location_code=stp.location_code,
                        )
                    )
                acc_len = 0.0
                acc_loss = 0.0
                for s in inverted_steps:
                    acc_len += s.length_m
                    acc_loss += s.loss_db
                    s.accumulated_length_m = round(acc_len, 2)
                    s.accumulated_loss_db = round(acc_loss, 4)

                chosen_path = TracePath(
                    path_id=f"ds_{raw_path.path_id}",
                    origin_terminal_id=raw_path.destination_terminal_id or str(cto_term.id),
                    destination_terminal_id=str(cto_term.id),
                    total_length_m=raw_path.total_length_m,
                    total_loss_db=raw_path.total_loss_db,
                    steps=inverted_steps,
                )
        else:
            # Upstream direto (CTO/Cliente -> OLT)
            up_trace = trace_optical_path(
                session,
                TraceRequest(
                    start_terminal_id=str(cto_term.id),
                    direction=TraceDirection.UPSTREAM,
                ),
            )
            trace_warnings.extend(up_trace.warnings)
            if up_trace.paths and up_trace.status == TraceStatus.COMPLETE:
                chosen_path = up_trace.paths[0]

    elif payload.start_terminal_id:
        direct_trace = trace_optical_path(
            db=session,
            request=TraceRequest(
                start_terminal_id=payload.start_terminal_id,
                direction=payload.direction,
            ),
        )
        if direct_trace.paths and direct_trace.status == TraceStatus.COMPLETE:
            chosen_path = direct_trace.paths[0]
    else:
        raise UnprocessableEntityError(
            "Informe 'service_link_id' ou 'start_terminal_id' para efetuar o cálculo óptico.",
            field="service_link_id",
        )

    # 3. Se não há caminho contínuo, retorna resposta estruturada com dados insuficientes
    if not chosen_path:
        return BudgetCalculationResponse(
            status="insufficient_data",
            direction=payload.direction,
            wavelength_nm=profile_input.wavelength_nm,
            topology_revision=topology_rev,
            assumptions=["Circuito óptico sem continuidade ponta a ponta documentada."],
            missing_fields=["Caminho óptico completo entre transmissor e receptor"],
            steps=[],
            total_loss_db=None,
            tx_dbm=profile_input.tx_nominal_dbm,
            predicted_rx_dbm=None,
            rx_min_dbm=None,
            rx_max_dbm=None,
            engineering_margin_db=payload.engineering_margin_db,
            remaining_margin_db=None,
            overload_headroom_db=None,
            assessment=BudgetAssessment.UNKNOWN,
        )

    # Mapa de overrides por element_id
    override_map: dict[str, SimulationOverrideItem] = {}
    if overrides:
        for ov in overrides:
            override_map[str(ov.element_id)] = ov

    # 4. Converter passos para OpticalStepInput
    calc_steps: list[OpticalStepInput] = []
    ratio_loss_map = {2: 3.7, 4: 7.2, 8: 10.5, 16: 13.8, 32: 17.0, 64: 20.5}

    for step in chosen_path.steps:
        s_type = step.element_type.lower()
        elem_ov = override_map.get(str(step.element_id))

        if s_type in ("fiber", "fiber_segment"):
            f_len = step.length_m
            p_source = ParameterSource.DEFAULT_PROFILE
            lbl = step.element_code or f"Fibra ({f_len:.1f}m)"

            if elem_ov:
                if elem_ov.override_type == "length_m":
                    f_len = elem_ov.new_value
                    p_source = ParameterSource.CALCULATED
                    lbl = f"{lbl} [Simulado: {f_len:.1f}m]"
                elif elem_ov.override_type == "loss_db":
                    # Override direto de atenuação no segmento
                    calc_steps.append(
                        OpticalStepInput(
                            element_type=StepElementType.FIBER,
                            element_id=step.element_id,
                            element_name=f"{lbl} [Simulado perda: {elem_ov.new_value:.2f} dB]",
                            loss_db=elem_ov.new_value,
                            parameter_source=ParameterSource.MEASURED,
                        )
                    )
                    continue

            calc_steps.append(
                OpticalStepInput(
                    element_type=StepElementType.FIBER,
                    element_id=step.element_id,
                    element_name=lbl,
                    length_m=f_len,
                    attenuation_db_per_km=profile_input.default_attenuation_db_per_km,
                    parameter_source=p_source,
                )
            )
        elif s_type == "fusion":
            fus_loss = step.loss_db if step.loss_db > 0 else 0.10
            p_source = ParameterSource.MEASURED if step.loss_db > 0 else ParameterSource.STANDARD
            lbl = step.element_code or "Fusão Óptica"

            if elem_ov and elem_ov.override_type == "loss_db":
                fus_loss = elem_ov.new_value
                p_source = ParameterSource.MEASURED
                lbl = f"{lbl} [Simulado: {fus_loss:.2f} dB]"

            calc_steps.append(
                OpticalStepInput(
                    element_type=StepElementType.FUSION,
                    element_id=step.element_id,
                    element_name=lbl,
                    loss_db=fus_loss,
                    parameter_source=p_source,
                )
            )
        elif s_type == "splitter":
            spl_loss = step.loss_db
            p_source = ParameterSource.CATALOG
            lbl = step.element_code or "Splitter Óptico"

            if elem_ov:
                if elem_ov.override_type == "loss_db":
                    spl_loss = elem_ov.new_value
                    lbl = f"{lbl} [Simulado: {spl_loss:.2f} dB]"
                elif elem_ov.override_type == "splitter_ratio":
                    r_int = int(elem_ov.new_value)
                    spl_loss = ratio_loss_map.get(r_int, elem_ov.new_value)
                    lbl = f"{lbl} [Simulado 1:{r_int}: {spl_loss:.2f} dB]"

            calc_steps.append(
                OpticalStepInput(
                    element_type=StepElementType.SPLITTER,
                    element_id=step.element_id,
                    element_name=lbl,
                    loss_db=spl_loss,
                    parameter_source=p_source,
                )
            )
        elif s_type in ("patch_cord", "connector"):
            con_loss = step.loss_db if step.loss_db > 0 else 0.30
            p_source = ParameterSource.STANDARD
            lbl = step.element_code or "Par Acoplado / Patch Cord"

            if elem_ov and elem_ov.override_type == "loss_db":
                con_loss = elem_ov.new_value
                p_source = ParameterSource.MEASURED
                lbl = f"{lbl} [Simulado: {con_loss:.2f} dB]"

            calc_steps.append(
                OpticalStepInput(
                    element_type=StepElementType.MATED_PAIR,
                    element_id=step.element_id,
                    element_name=lbl,
                    loss_db=con_loss,
                    parameter_source=p_source,
                )
            )
        elif s_type == "port_pass_through":
            calc_steps.append(
                OpticalStepInput(
                    element_type=StepElementType.PASS_THROUGH,
                    element_id=step.element_id,
                    element_name=step.element_code or "Passagem de Porta",
                    loss_db=0.0,
                    parameter_source=ParameterSource.STANDARD,
                )
            )
        else:
            oth_loss = step.loss_db
            lbl = step.element_code or "Elemento Óptico"
            if elem_ov and elem_ov.override_type == "loss_db":
                oth_loss = elem_ov.new_value
                lbl = f"{lbl} [Simulado: {oth_loss:.2f} dB]"

            calc_steps.append(
                OpticalStepInput(
                    element_type=StepElementType.OTHER,
                    element_id=step.element_id,
                    element_name=lbl,
                    loss_db=oth_loss,
                    parameter_source=ParameterSource.STANDARD,
                )
            )

    # 5. Executar cálculo puro
    calc_res = calculate_optical_budget(calc_steps, profile_input)

    # 6. Converter passos para BudgetLossStep
    budget_steps: list[BudgetLossStep] = []
    for sb in calc_res.steps:
        budget_steps.append(
            BudgetLossStep(
                step_number=sb.step_number,
                element_type=sb.element_type,
                element_name=sb.element_name,
                parameter_source=str(sb.parameter_source),
                unit=sb.unit,
                individual_value=round(sb.individual_value, 4),
                loss_db=round(sb.loss_db, 4),
                accumulated_loss_db=round(sb.accumulated_loss_db, 4),
            )
        )

    # Mapear status e assessment
    assessment_map = {
        CalculationAssessment.PASS: BudgetAssessment.PASS,
        CalculationAssessment.LOW_MARGIN: BudgetAssessment.LOW_MARGIN,
        CalculationAssessment.BELOW_SENSITIVITY: BudgetAssessment.BELOW_SENSITIVITY,
        CalculationAssessment.OVERLOAD: BudgetAssessment.OVERLOAD,
        CalculationAssessment.UNKNOWN: BudgetAssessment.UNKNOWN,
    }

    assumptions = list(calc_res.assumptions)
    if overrides:
        assumptions.append(
            f"Simulação hipotética com {len(overrides)} substituição(ões) pontual(is) aplicadas em memória. "
            "A topologia operacional e dados cadastrais da rede não sofreram mutação."
        )

    return BudgetCalculationResponse(
        status=calc_res.status.value,
        direction=payload.direction,
        wavelength_nm=calc_res.wavelength_nm,
        topology_revision=topology_rev,
        assumptions=assumptions,
        missing_fields=calc_res.missing_fields,
        steps=budget_steps,
        total_loss_db=round(calc_res.total_loss_db, 4) if calc_res.total_loss_db is not None else None,
        tx_dbm=round(calc_res.tx_dbm, 4) if calc_res.tx_dbm is not None else None,
        predicted_rx_dbm=round(calc_res.predicted_rx_dbm, 4) if calc_res.predicted_rx_dbm is not None else None,
        rx_min_dbm=round(calc_res.rx_min_dbm, 4) if calc_res.rx_min_dbm is not None else None,
        rx_max_dbm=round(calc_res.rx_max_dbm, 4) if calc_res.rx_max_dbm is not None else None,
        engineering_margin_db=calc_res.engineering_margin_db,
        remaining_margin_db=round(calc_res.remaining_margin_db, 4) if calc_res.remaining_margin_db is not None else None,
        overload_headroom_db=round(calc_res.overload_headroom_db, 4) if calc_res.overload_headroom_db is not None else None,
        assessment=assessment_map.get(calc_res.assessment, BudgetAssessment.UNKNOWN),
    )


def simulate_optical_budget(
    session: Session,
    payload: OpticalSimulationRequest,
) -> OpticalSimulationResponse:
    """Executa simulação de engenharia com overrides pontuais sem alterar a rede física (B12)."""
    baseline_req = BudgetCalculationRequest(
        service_link_id=payload.service_link_id,
        direction=payload.direction,
        engineering_margin_db=payload.engineering_margin_db,
    )
    baseline = calculate_service_link_budget(session=session, payload=baseline_req)

    simulated = calculate_service_link_budget(
        session=session,
        payload=baseline_req,
        overrides=payload.overrides,
    )

    delta_loss_db = 0.0
    if baseline.total_loss_db is not None and simulated.total_loss_db is not None:
        delta_loss_db = round(simulated.total_loss_db - baseline.total_loss_db, 4)

    delta_rx_dbm = 0.0
    if baseline.predicted_rx_dbm is not None and simulated.predicted_rx_dbm is not None:
        delta_rx_dbm = round(simulated.predicted_rx_dbm - baseline.predicted_rx_dbm, 4)

    return OpticalSimulationResponse(
        baseline=baseline,
        simulated=simulated,
        delta_loss_db=delta_loss_db,
        delta_predicted_rx_dbm=delta_rx_dbm,
    )
