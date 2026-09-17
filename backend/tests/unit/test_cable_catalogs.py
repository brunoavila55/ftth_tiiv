from app.modules.inventory.catalogs import (
    get_color_standard,
    get_supported_color_standards,
    validate_color_standard,
)


def test_supported_color_standards() -> None:
    standards = get_supported_color_standards()
    assert "NBR" in standards
    assert "TIA-598" in standards
    assert "DIN-VDE-0888" in standards


def test_nbr_color_sequence() -> None:
    nbr_colors = get_color_standard("NBR")
    assert nbr_colors is not None
    assert len(nbr_colors) == 12
    # Ordem ABNT NBR 14106 / 14771: Verde, Amarelo, Branco, Azul, Vermelho, Violeta, Marrom, Rosa, Preto, Cinza, Laranja, Aqua
    assert nbr_colors[0] == "Verde"
    assert nbr_colors[1] == "Amarelo"
    assert nbr_colors[2] == "Branco"
    assert nbr_colors[3] == "Azul"
    assert nbr_colors[11] == "Aqua"


def test_tia_598_color_sequence() -> None:
    tia_colors = get_color_standard("TIA-598")
    assert tia_colors is not None
    assert len(tia_colors) == 12
    # Ordem TIA-598: Blue, Orange, Green, Brown, Slate, White, Red, Black, Yellow, Violet, Rose, Aqua
    assert tia_colors[0] == "Blue"
    assert tia_colors[1] == "Orange"
    assert tia_colors[2] == "Green"
    assert tia_colors[11] == "Aqua"


def test_validate_color_standard() -> None:
    assert validate_color_standard("nbr") is True
    assert validate_color_standard("TIA-598") is True
    assert validate_color_standard("padrao_inventado_invalido") is False
