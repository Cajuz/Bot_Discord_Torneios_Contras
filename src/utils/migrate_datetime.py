"""
R3 — Script utilitário para encontrar todos os utcnow() no projeto.
Execute: python src/utils/migrate_datetime.py
Ele lista os arquivos que precisam ser atualizados.
"""
import os
import re
import sys

TARGET   = "utcnow()"
REPLACE  = "utcnow()"
IMPORT   = "from utils.datetime_utils import utcnow"
SRC_ROOT = os.path.join(os.path.dirname(__file__), "..")


def scan_and_fix(dry_run: bool = True):
    results = []
    for root, _, files in os.walk(SRC_ROOT):
        for fname in files:
            if not fname.endswith(".py"):
                continue
            path = os.path.join(root, fname)
            with open(path, encoding="utf-8") as f:
                content = f.read()

            if TARGET not in content:
                continue

            count  = content.count(TARGET)
            fixed  = content.replace(TARGET, REPLACE)

            # Adiciona import se não existir
            if IMPORT not in fixed:
                fixed = IMPORT + "\n" + fixed

            results.append((path, count))

            if not dry_run:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(fixed)
                print(f"  ✅ CORRIGIDO ({count}x): {os.path.relpath(path, SRC_ROOT)}")
            else:
                print(f"  ⚠️  PENDENTE ({count}x): {os.path.relpath(path, SRC_ROOT)}")

    if not results:
        print("✅ Nenhum utcnow() encontrado — projeto já migrado!")
    else:
        print(f"\nTotal: {len(results)} arquivo(s), {sum(c for _, c in results)} ocorrências")
        if dry_run:
            print("\nExecute com --fix para aplicar as correções:")
            print("  python src/utils/migrate_datetime.py --fix")


if __name__ == "__main__":
    dry_run = "--fix" not in sys.argv
    mode    = "DRY RUN" if dry_run else "APLICANDO CORREÇÕES"
    print(f"=== R3 — Migração utcnow() [{mode}] ===\n")
    scan_and_fix(dry_run)
