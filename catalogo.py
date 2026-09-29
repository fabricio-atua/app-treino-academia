# Exercícios de musculação por região e músculo, para montar o treino no app.
# Os nomes do plano atual estão aqui escritos do mesmo jeito, porque o histórico
# de cargas é ligado ao nome do exercício. Exercícios que você criar no app ficam
# na aba treinos_academia_exercicios da planilha e aparecem junto destes.

CATALOGO = {
    "Braços": {
        "Bíceps": [
            "Rosca direta", "Rosca direta barra W", "Rosca alternada", "Rosca martelo",
            "Rosca Scott", "Rosca concentrada", "Rosca inclinada", "Rosca na polia",
            "Rosca martelo na corda", "Rosca 21", "Rosca spider",
        ],
        "Tríceps": [
            "Tríceps pulley", "Tríceps corda", "Tríceps testa", "Tríceps francês",
            "Tríceps coice", "Tríceps unilateral na polia", "Tríceps mergulho no banco",
            "Paralelas", "Supino fechado",
        ],
        "Antebraço": ["Rosca inversa", "Rosca de punho", "Rosca de punho inversa"],
    },
    "Tronco": {
        "Peito": [
            "Supino reto", "Supino reto com halteres", "Supino inclinado", "Supino inclinado com halteres",
            "Supino declinado", "Supino máquina", "Crucifixo com halteres", "Crucifixo inclinado",
            "Crossover", "Peck deck (voador)", "Flexão de braço",
        ],
        "Costas": [
            "Puxada frontal", "Puxada com triângulo", "Puxada supinada", "Barra fixa",
            "Remada baixa", "Remada curvada", "Remada unilateral", "Remada máquina",
            "Remada cavalinho", "Pulldown na polia", "Pullover", "Levantamento terra",
            "Hiperextensão lombar",
        ],
        "Ombros": [
            "Desenvolvimento", "Desenvolvimento com barra", "Desenvolvimento máquina",
            "Desenvolvimento Arnold", "Elevação lateral", "Elevação lateral na polia",
            "Elevação frontal", "Crucifixo inverso", "Face pull", "Remada alta",
        ],
        "Trapézio": ["Encolhimento com halteres", "Encolhimento com barra"],
    },
    "Pernas": {
        "Quadríceps": [
            "Agachamento livre", "Agachamento no Smith", "Leg press", "Hack", "Cadeira extensora",
            "Afundo", "Passada", "Agachamento búlgaro", "Agachamento goblet",
        ],
        "Posterior de coxa": ["Mesa flexora", "Cadeira flexora", "Flexora em pé", "Stiff", "Levantamento terra romeno"],
        "Glúteos": ["Elevação pélvica", "Glúteo na polia", "Glúteo máquina", "Agachamento sumô", "Cadeira abdutora"],
        "Adutores": ["Cadeira adutora"],
        "Panturrilha": ["Panturrilha", "Panturrilha em pé", "Panturrilha sentado", "Panturrilha no leg press"],
    },
    "Abdômen": {
        "Abdômen": [
            "Abdômen", "Abdominal supra", "Abdominal infra", "Abdominal na polia",
            "Abdominal oblíquo", "Prancha", "Elevação de pernas",
        ],
    },
}


def musculo_de(nome, catalogo=CATALOGO):
    """Devolve (região, músculo) do exercício, ou None se ele não estiver no catálogo."""
    alvo = nome.strip().lower()
    for regiao, musculos in catalogo.items():
        for musculo, exercicios in musculos.items():
            if any(e.lower() == alvo for e in exercicios):
                return regiao, musculo
    return None
