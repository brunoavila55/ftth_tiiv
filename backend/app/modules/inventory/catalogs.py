"""Catálogos de padrões de cores de cabos e especificações industriais de telecomunicações.

Normas suportadas:
- ABNT NBR 14106 / NBR 14771 (Padrão Nacional Brasileiro)
- TIA-598-C / TIA-598-D (Padrão Norte-Americano / Internacional)
- DIN VDE 0888 (Padrão Alemão / Europeu)
"""

COLOR_STANDARDS: dict[str, list[str]] = {
    "NBR": [
        "Verde",
        "Amarelo",
        "Branco",
        "Azul",
        "Vermelho",
        "Violeta",
        "Marrom",
        "Rosa",
        "Preto",
        "Cinza",
        "Laranja",
        "Aqua",
    ],
    "TIA-598": [
        "Blue",
        "Orange",
        "Green",
        "Brown",
        "Slate",
        "White",
        "Red",
        "Black",
        "Yellow",
        "Violet",
        "Rose",
        "Aqua",
    ],
    "DIN-VDE-0888": [
        "Rot",
        "Grün",
        "Blau",
        "Gelb",
        "Weiß",
        "Grau",
        "Braun",
        "Schwarz",
        "Violett",
        "Türkis",
        "Orange",
        "Rosa",
    ],
}


def get_supported_color_standards() -> list[str]:
    """Retorna lista de códigos de padrões de cores suportados."""
    return sorted(COLOR_STANDARDS.keys())


def get_color_standard(name: str) -> list[str] | None:
    """Retorna a sequência ordenada de cores de um determinado padrão."""
    clean_name = name.strip().upper()
    return COLOR_STANDARDS.get(clean_name)


def validate_color_standard(name: str) -> bool:
    """Verifica se o padrão de cores é suportado pelo sistema."""
    clean_name = name.strip().upper()
    return clean_name in COLOR_STANDARDS
