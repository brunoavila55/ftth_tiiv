"""Testes e validação de exemplos sintéticos de requisições e respostas do contrato OpenAPI v1."""

import uuid
from datetime import UTC, datetime

from app.core.errors import ProblemDetails, ValidationErrorItem
from app.schemas.auth import LoginRequest, LoginResponse, MeResponse
from app.schemas.cables import (
    CableCreate,
    CableSegmentCreate,
    CableSegmentRead,
    LengthSource,
)
from app.schemas.common import AdministrativeStatus, UserRole
from app.schemas.connectivity import (
    BatchOperationItem,
    BatchOperationType,
    ConnectionBatchRequest,
    ConnectionBatchResponse,
    ConnectionCreate,
    ConnectionType,
)
from app.schemas.geojson import LineStringGeometry
from app.schemas.optical import (
    BudgetAssessment,
    BudgetCalculationRequest,
    BudgetCalculationResponse,
    BudgetLossStep,
    OpticalSimulationRequest,
    SimulationOverrideItem,
)
from app.schemas.topology import (
    TraceDirection,
    TracePath,
    TraceRequest,
    TraceResponse,
    TraceStatus,
    TraceStep,
)


def test_auth_synthetic_examples() -> None:
    req = LoginRequest(
        email="engenharia@provedor.net.br",
        password="SenhaSegura123!",
    )
    assert req.email == "engenharia@provedor.net.br"

    resp = LoginResponse(
        user=MeResponse(
            id=str(uuid.uuid4()),
            name="Engenheiro Responsável",
            email="engenharia@provedor.net.br",
            role=UserRole.ENGINEER,
            permissions=["inventory:write", "topology:write", "optical:read"],
        ),
        message="Login realizado com sucesso",
    )
    assert resp.user.role == UserRole.ENGINEER


def test_cable_and_segment_synthetic_examples() -> None:
    cable = CableCreate(
        code="CAB-TRONCAL-01",
        model="CFOA-SM-AS80-S-24F",
        fiber_count=24,
        tube_count=2,
        color_standard="NBR",
        status=AdministrativeStatus.INSTALLED,
    )
    assert cable.fiber_count == 24

    segment = CableSegmentCreate(
        cable_id=str(uuid.uuid4()),
        origin_structure_id=str(uuid.uuid4()),
        destination_structure_id=str(uuid.uuid4()),
        geometry=LineStringGeometry(
            coordinates=[(-46.633308, -23.550520), (-46.634120, -23.551200)]
        ),
        measured_length_m=125.5,
        slack_length_m=15.0,
    )
    assert segment.measured_length_m == 125.5

    segment_read = CableSegmentRead(
        id=str(uuid.uuid4()),
        cable_id=segment.cable_id,
        origin_structure_id=segment.origin_structure_id,
        destination_structure_id=segment.destination_structure_id,
        geometry=segment.geometry,
        map_length_m=122.3,
        measured_length_m=125.5,
        slack_length_m=15.0,
        effective_length_m=125.5,
        length_source=LengthSource.MEASURED,
        version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert segment_read.length_source == LengthSource.MEASURED


def test_connection_and_batch_synthetic_examples() -> None:
    term_a = str(uuid.uuid4())
    term_b = str(uuid.uuid4())

    conn = ConnectionCreate(
        terminal_a_id=term_a,
        terminal_b_id=term_b,
        connection_type=ConnectionType.FUSION_SPLICE,
        loss_db=0.10,
    )
    assert conn.loss_db == 0.10

    batch = ConnectionBatchRequest(
        expected_topology_revision=14,
        structure_id=str(uuid.uuid4()),
        operations=[
            BatchOperationItem(
                action=BatchOperationType.CONNECT,
                terminal_a_id=term_a,
                terminal_b_id=term_b,
                connection_type=ConnectionType.FUSION_SPLICE,
                loss_db=0.08,
            ),
            BatchOperationItem(
                action=BatchOperationType.RESERVE,
                terminal_a_id=str(uuid.uuid4()),
                reservation_reason="Reserva técnica cliente corporativo",
            ),
        ],
    )
    assert len(batch.operations) == 2
    assert batch.expected_topology_revision == 14

    batch_resp = ConnectionBatchResponse(
        success=True,
        applied_operations_count=2,
        new_topology_revision=15,
    )
    assert batch_resp.new_topology_revision == 15


def test_topology_trace_synthetic_example() -> None:
    start_term = str(uuid.uuid4())
    req = TraceRequest(
        start_terminal_id=start_term,
        direction=TraceDirection.DOWNSTREAM,
        max_results=10,
    )
    assert req.direction == TraceDirection.DOWNSTREAM

    resp = TraceResponse(
        topology_revision=15,
        status=TraceStatus.COMPLETE,
        paths=[
            TracePath(
                path_id="rev15_olt01_pon1_onu04",
                origin_terminal_id=start_term,
                destination_terminal_id=str(uuid.uuid4()),
                total_length_m=3450.0,
                total_loss_db=18.65,
                steps=[
                    TraceStep(
                        step_number=1,
                        element_type="port_pass_through",
                        element_id=str(uuid.uuid4()),
                        element_code="DIO-01-PORTA-01",
                        length_m=0.0,
                        loss_db=0.30,
                        accumulated_length_m=0.0,
                        accumulated_loss_db=0.30,
                    ),
                    TraceStep(
                        step_number=2,
                        element_type="fiber_segment",
                        element_id=str(uuid.uuid4()),
                        element_code="CAB-01-F01",
                        length_m=3200.0,
                        loss_db=1.12,
                        accumulated_length_m=3200.0,
                        accumulated_loss_db=1.42,
                    ),
                    TraceStep(
                        step_number=3,
                        element_type="splitter",
                        element_id=str(uuid.uuid4()),
                        element_code="SPL-CTO-04-1x8",
                        length_m=0.0,
                        loss_db=10.50,
                        accumulated_length_m=3200.0,
                        accumulated_loss_db=11.92,
                    ),
                ],
            )
        ],
    )
    assert resp.status == TraceStatus.COMPLETE
    assert len(resp.paths[0].steps) == 3


def test_optical_budget_and_simulation_synthetic_example() -> None:
    req = BudgetCalculationRequest(
        service_link_id=str(uuid.uuid4()),
        direction=TraceDirection.DOWNSTREAM,
        engineering_margin_db=3.0,
    )
    assert req.engineering_margin_db == 3.0

    resp = BudgetCalculationResponse(
        status="complete",
        direction=TraceDirection.DOWNSTREAM,
        wavelength_nm=1490,
        topology_revision=15,
        assumptions=["Fibra G.652.D atenuação nominal 0.35 dB/km"],
        steps=[
            BudgetLossStep(
                step_number=1,
                element_type="fiber",
                element_name="Trecho Troncal",
                parameter_source="calculated",
                unit="m",
                individual_value=3200.0,
                loss_db=1.12,
                accumulated_loss_db=1.12,
            )
        ],
        total_loss_db=18.65,
        tx_dbm=3.0,
        predicted_rx_dbm=-15.65,
        rx_min_dbm=-17.15,
        rx_max_dbm=-14.15,
        engineering_margin_db=3.0,
        remaining_margin_db=9.35,  # -15.65 - (-28.0) - 3.0 = 9.35 dB
        overload_headroom_db=7.65,  # -8.0 - (-15.65) = 7.65 dB
        assessment=BudgetAssessment.PASS,
    )
    assert resp.assessment == BudgetAssessment.PASS
    assert resp.predicted_rx_dbm == -15.65

    # Simulação com override de splitter
    elem_id = str(uuid.uuid4())
    sim_req = OpticalSimulationRequest(
        service_link_id=req.service_link_id,
        overrides=[
            SimulationOverrideItem(
                element_id=elem_id,
                override_type="loss_db",
                new_value=13.80,  # troca por 1:16
            )
        ],
    )
    assert len(sim_req.overrides) == 1


def test_problem_details_concurrency_and_conflict_synthetic_examples() -> None:
    # 428 Precondition Required
    p428 = ProblemDetails(
        title="Precondição obrigatória",
        status=428,
        detail="O cabeçalho If-Match é obrigatório para mutações versionadas.",
        code="precondition_required",
        request_id="test-req-001",
    )
    assert p428.status == 428
    assert p428.code == "precondition_required"

    # 412 Precondition Failed
    p412 = ProblemDetails(
        title="Precondição falhou",
        status=412,
        detail="A versão fornecida '2' não corresponde à versão atual '3' do recurso.",
        code="precondition_failed",
        request_id="test-req-002",
    )
    assert p412.status == 412

    # 409 Conflict
    p409 = ProblemDetails(
        title="Conflito de negócio",
        status=409,
        detail="A porta selecionada já possui conexão externa ativa com o terminal de outra fibra.",
        code="conflict",
        request_id="test-req-003",
    )
    assert p409.status == 409

    # 422 Validation Error
    p422 = ProblemDetails(
        title="Erro de validação dos dados de entrada",
        status=422,
        detail="Um ou mais campos fornecidos na requisição são inválidos.",
        code="validation_error",
        request_id="test-req-004",
        errors=[
            ValidationErrorItem(
                field="body.wavelength_nm",
                code="greater_than_equal",
                message="Input should be greater than or equal to 800",
            )
        ],
    )
    assert p422.status == 422
    assert p422.errors is not None
    assert p422.errors[0].field == "body.wavelength_nm"
