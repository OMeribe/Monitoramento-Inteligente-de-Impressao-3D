"""
Distribuição de classes em dataset YOLO — sem dependências externas.
Coloque na mesma pasta do data.yaml e rode: python contar_classes_yolo.py
"""

import os
from collections import Counter

# Raiz = pasta onde ESTE arquivo está salvo (independente de onde você rodou o comando)
DATASET_ROOT = os.path.dirname(os.path.abspath(__file__))

SPLITS = {
    "Treinamento": "train/labels",
    "Validação":   "valid/labels",
    "Teste":       "test/labels",
}


def carregar_nomes_classes(root: str) -> dict:
    """Lê os nomes das classes do data.yaml sem biblioteca externa."""
    yaml_path = os.path.join(root, "data.yaml")
    if not os.path.exists(yaml_path):
        raise FileNotFoundError(f"data.yaml não encontrado em: {root}")

    names = {}
    inside_names = False
    idx = 0

    with open(yaml_path, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()

            # Detecta o bloco "names:"
            if stripped.startswith("names:"):
                inside_names = True
                # Formato inline: names: [a, b, c]
                if "[" in stripped:
                    content = stripped.split("[", 1)[1].rstrip("]").strip()
                    for item in content.split(","):
                        item = item.strip().strip("'\"")
                        if item:
                            names[idx] = item
                            idx += 1
                    inside_names = False
                continue

            if inside_names:
                # Formato de lista YAML: "  - classe"
                if stripped.startswith("-"):
                    name = stripped.lstrip("-").strip().strip("'\"")
                    names[idx] = name
                    idx += 1
                # Formato de dict YAML: "  0: classe"
                elif ":" in stripped and stripped[0].isdigit():
                    k, v = stripped.split(":", 1)
                    names[int(k.strip())] = v.strip().strip("'\"")
                elif stripped == "" or (not stripped.startswith(" ") and stripped):
                    inside_names = False

    if not names:
        raise ValueError("Nenhuma classe encontrada no data.yaml. Verifique o arquivo.")
    return names


def contar_anotacoes(labels_dir: str) -> Counter:
    counter: Counter = Counter()
    if not os.path.isdir(labels_dir):
        return counter
    for fname in os.listdir(labels_dir):
        if not fname.endswith(".txt"):
            continue
        with open(os.path.join(labels_dir, fname), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    counter[int(line.split()[0])] += 1
    return counter


def contar_imagens(labels_dir: str) -> int:
    if not os.path.isdir(labels_dir):
        return 0
    return len([f for f in os.listdir(labels_dir) if f.endswith(".txt")])


def main():
    print(f"\nRaiz do dataset: {DATASET_ROOT}\n")

    classes = carregar_nomes_classes(DATASET_ROOT)
    splits = list(SPLITS.keys())

    contagens = {}
    imagens   = {}
    for split_name, rel_path in SPLITS.items():
        full = os.path.join(DATASET_ROOT, rel_path)
        contagens[split_name] = contar_anotacoes(full)
        imagens[split_name]   = contar_imagens(full)

    total_anot = Counter()
    for c in contagens.values():
        total_anot += c

    # ── Tabela de anotações ────────────────────────────────────────────────
    col = 22
    header = f"{'Classe':<{col}}" + "".join(f"{s:>14}" for s in splits) + f"{'TOTAL':>14}"
    sep    = "-" * len(header)

    print("=" * len(header))
    print("  ANOTAÇÕES POR CLASSE E SPLIT")
    print("=" * len(header))
    print(header)
    print(sep)

    for cid in sorted(classes):
        nome = classes[cid]
        row  = f"{nome:<{col}}"
        for s in splits:
            row += f"{contagens[s].get(cid, 0):>14,}"
        row += f"{total_anot.get(cid, 0):>14,}"
        print(row)

    print(sep)

    row_anot = f"{'Total anotações':<{col}}"
    row_imgs = f"{'Total imagens':<{col}}"
    grand_anot = grand_imgs = 0
    for s in splits:
        ta = sum(contagens[s].values())
        ti = imagens[s]
        grand_anot += ta
        grand_imgs += ti
        row_anot += f"{ta:>14,}"
        row_imgs += f"{ti:>14,}"
    row_anot += f"{grand_anot:>14,}"
    row_imgs += f"{grand_imgs:>14,}"
    print(row_anot)
    print(row_imgs)
    print("=" * len(header))

    # ── Resumo para o artigo ───────────────────────────────────────────────
    print("\n── RESUMO PARA O ARTIGO ─────────────────────────────────────────────")
    for s in splits:
        n   = imagens[s]
        pct = 100 * n / grand_imgs if grand_imgs else 0
        print(f"  {s}: {n:,} imagens ({pct:.1f}%)")
    print(f"  Total geral: {grand_imgs:,} imagens | {len(classes)} classes")
    print("─" * 70)


if __name__ == "__main__":
    main()
